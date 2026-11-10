"""Run against a migrated, seeded test PostgreSQL database."""
import unittest
import os
from uuid import uuid4
from app.schemas.orders import CreateOrderRequest
from app.services.orders import create_order, OrderRejected
from app.db.connection import connect

@unittest.skipUnless(os.environ.get("DATABASE_URL"), "requires seeded test database")
class CartStorageTests(unittest.TestCase):
    def test_atomic_replay_and_changed_quantity(self):
        line=dict(menu_id="iced_americano",temperature="COLD",service_type="TAKEOUT",quantity=2,option_ids=[])
        req=CreateOrderRequest(request_id=str(uuid4()),menu_id=line["menu_id"],temperature="COLD",service_type="TAKEOUT",items=[line,dict(line,quantity=3)])
        first,created=create_order(req)
        self.assertTrue(created)
        self.assertEqual([i["quantity"] for i in first.items],[2,3])
        self.assertEqual(first.total_price_krw,first.items[0]["unit_price_krw"]*5)
        second,created=create_order(req)
        self.assertFalse(created)
        self.assertEqual(first.order_id,second.order_id)
        req.items[0].quantity=4
        with self.assertRaises(OrderRejected): create_order(req)
    def test_invalid_second_line_saves_nothing(self):
        request_id=str(uuid4())
        req=CreateOrderRequest(request_id=request_id,menu_id="iced_americano",temperature="COLD",service_type="TAKEOUT",items=[dict(menu_id=k,temperature="COLD",service_type="TAKEOUT") for k in ["iced_americano","missing"]])
        with self.assertRaises(OrderRejected): create_order(req)
        with connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM orders WHERE request_id=%s",(request_id,)).fetchone()["n"],0)
