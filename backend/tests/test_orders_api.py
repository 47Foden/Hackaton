"""Verify the order API and transaction against an isolated PostgreSQL schema."""
import asyncio
import json
import os
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.db.connection import connect
from app.db.migrate import migrate
from app.db.seed import seed
from app.main import app

SELECTION = {"menu_id": "espresso", "temperature": "HOT", "service_type": "TAKEOUT"}
ORDER = {**SELECTION, "request_id": "550e8400-e29b-41d4-a716-446655440000"}


async def asgi_post_order(payload):
    messages = []

    async def receive():
        return {"type": "http.request", "body": json.dumps(payload).encode(), "more_body": False}

    async def send(message):
        messages.append(message)

    await app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": "/api/orders", "raw_path": b"/api/orders",
        "query_string": b"", "root_path": "", "headers": [(b"content-type", b"application/json")],
        "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
    }, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], json.loads(body)


class OrdersApiTests(unittest.TestCase):
    def setUp(self):
        self.admin_url = os.environ["DATABASE_URL"]
        self.schema = "test_orders_api_" + uuid.uuid4().hex
        with connect(self.admin_url) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.addCleanup(self.drop_schema)
        self.url = make_conninfo(self.admin_url, options=f"-c search_path={self.schema} -c timezone=Asia/Seoul")
        migrate(self.url)
        seed(self.url)

    def drop_schema(self):
        with connect(self.admin_url) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))

    def post(self, payload):
        with patch.dict(os.environ, {"DATABASE_URL": self.url}):
            return asyncio.run(asgi_post_order(payload))

    def assert_no_orders(self):
        with connect(self.url) as connection:
            self.assertEqual(connection.execute("SELECT count(*) AS count FROM orders").fetchone()["count"], 0)

    def test_uses_current_db_price_and_persists_order_snapshot(self):
        with connect(self.url) as connection:
            connection.execute("UPDATE menus SET price_krw = 1700 WHERE menu_id = 'espresso'")
        status, body = self.post(ORDER)
        self.assertEqual(status, 201)
        created_at = datetime.fromisoformat(body.pop("created_at"))
        self.assertEqual(created_at.utcoffset(), timedelta(0))

        with connect(self.url) as connection:
            connection.execute("UPDATE menus SET name = '변경한 이름', price_krw = 1800 WHERE menu_id = 'espresso'")
            stored = connection.execute("SELECT * FROM orders").fetchone()
        self.assertEqual(stored["unit_price_krw"], 1700)
        self.assertEqual(stored["total_price_krw"], 1700)
        self.assertEqual(stored["menu_name_snapshot"], "에스프레소")
        self.assertEqual(stored["created_at"], created_at)
        self.assertEqual(body, {
            **SELECTION, "order_id": str(stored["id"]), "order_number": str(stored["id"]),
            "menu_name": "에스프레소", "quantity": 1, "total_price_krw": 1700,
        })

    def test_rejects_invalid_requests_without_inserting(self):
        for payload in (
            {**ORDER, "price_krw": 1}, {**ORDER, "quantity": 1}, {**ORDER, "menu_id": 1},
            {**ORDER, "menu_id": ""}, {**ORDER, "menu_id": "espresso\x00"},
            {**ORDER, "temperature": "ICE"}, {**ORDER, "service_type": "DELIVERY"},
            {**ORDER, "request_id": "invalid"}, {**ORDER, "request_id": 1}, SELECTION,
            {"request_id": ORDER["request_id"], "menu_id": "espresso", "temperature": "HOT"},
        ):
            with self.subTest(payload=payload):
                status, body = self.post(payload)
                self.assertEqual(status, 422)
                self.assertIsInstance(body["detail"], list)
        self.assert_no_orders()

    def test_replay_keeps_snapshot_and_rejects_changed_payload(self):
        status, created = self.post(ORDER)
        self.assertEqual(status, 201)
        with connect(self.url) as connection:
            connection.execute("UPDATE menus SET price_krw = 1900, is_available = false WHERE menu_id = 'espresso'")
        self.assertEqual(self.post({**ORDER, "request_id": ORDER["request_id"].upper()}), (200, created))
        for changed in ({"menu_id": "unknown"}, {"temperature": "COLD"}, {"service_type": "DINE_IN"}):
            status, body = self.post({**ORDER, **changed})
            self.assertEqual(status, 409)
            self.assertEqual(body["detail"]["code"], "IDEMPOTENCY_CONFLICT")
        with connect(self.url) as connection:
            self.assertEqual(connection.execute("SELECT count(*) AS count FROM orders").fetchone()["count"], 1)

    def test_concurrent_retries_create_one_order(self):
        async def post_concurrently():
            return await asyncio.gather(*(asgi_post_order(ORDER) for _ in range(5)))

        with patch.dict(os.environ, {"DATABASE_URL": self.url}):
            responses = asyncio.run(post_concurrently())
        self.assertEqual(sorted(status for status, _ in responses), [200, 200, 200, 200, 201])
        self.assertTrue(all(body == responses[0][1] for _, body in responses))
        with connect(self.url) as connection:
            self.assertEqual(connection.execute("SELECT count(*) AS count FROM orders").fetchone()["count"], 1)

    def test_rejects_unregistered_unsold_and_unsupported_options(self):
        with connect(self.url) as connection:
            connection.execute("UPDATE menus SET is_available = false WHERE menu_id = 'iced_americano'")
        for payload, expected_status, code in (
            ({**ORDER, "menu_id": "unknown"}, 404, "MENU_NOT_FOUND"),
            ({**ORDER, "menu_id": "iced_americano", "temperature": "COLD"}, 409, "MENU_UNAVAILABLE"),
            ({**ORDER, "temperature": "COLD"}, 422, "INVALID_OPTION"),
        ):
            with self.subTest(code=code):
                status, body = self.post(payload)
                self.assertEqual(status, expected_status)
                self.assertEqual(body["detail"]["code"], code)
        self.assert_no_orders()

    def test_order_waits_for_concurrent_price_update(self):
        order_url = make_conninfo(self.url, options=f"-c search_path={self.schema} -c lock_timeout=500ms")
        order_connection = connect(order_url)
        self.addCleanup(order_connection.close)
        with connect(self.url) as writer:
            writer.execute("UPDATE menus SET price_krw = 1900 WHERE menu_id = 'espresso'")
            with patch("app.services.orders.connect", return_value=order_connection):
                with self.assertLogs("app.routers.orders", level="WARNING") as logs:
                    status, body = self.post(ORDER)
            self.assertEqual(status, 503)
            self.assertEqual(body["detail"]["code"], "ORDER_STORAGE_UNAVAILABLE")
            self.assertIn("LockNotAvailable", logs.output[0])
            self.assert_no_orders()

        status, body = self.post(ORDER)
        self.assertEqual(status, 201)
        self.assertEqual(body["total_price_krw"], 1900)

    def test_commit_failure_rolls_back_and_returns_503(self):
        with connect(self.url) as connection:
            connection.execute("""
                CREATE FUNCTION reject_order_on_commit() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'private commit failure';
                END;
                $$
            """)
            connection.execute("""
                CREATE CONSTRAINT TRIGGER reject_order_on_commit AFTER INSERT ON orders
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_order_on_commit()
            """)
        order_connection = connect(self.url)
        self.addCleanup(order_connection.close)
        with patch("app.services.orders.connect", return_value=order_connection):
            with self.assertLogs("app.routers.orders", level="WARNING"):
                status, body = self.post(ORDER)
        self.assertTrue(order_connection.closed)
        self.assertEqual(status, 503)
        self.assertEqual(body["detail"]["code"], "ORDER_STORAGE_UNAVAILABLE")
        self.assertNotIn("private commit failure", json.dumps(body))
        self.assert_no_orders()
