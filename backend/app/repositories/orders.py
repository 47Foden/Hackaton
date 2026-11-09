from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

ORDER_RESULT_COLUMNS = """
    id, menu_id, menu_name_snapshot, temperature, service_type,
    quantity, total_price_krw, selected_options, created_at
"""


def find_order_for_request(connection: psycopg.Connection, request_id: UUID) -> dict | None:
    # The next statement must get a fresh snapshot after waiting on the request lock.
    connection.execute("SELECT pg_advisory_xact_lock(47071003, hashtext(%s::uuid::text))", (request_id,))
    return connection.execute(f"""
        SELECT {ORDER_RESULT_COLUMNS} FROM orders WHERE request_id = %s
    """, (request_id,)).fetchone()


def lock_menu(connection: psycopg.Connection, menu_id: str) -> dict | None:
    return connection.execute("""
        SELECT name, price_krw, is_available
        FROM menus
        WHERE menu_id = %s
        FOR SHARE
    """, (menu_id,)).fetchone()


def get_variant_options(connection: psycopg.Connection, menu_id: str, temperature: str) -> list[dict] | None:
    variant = connection.execute("""
        SELECT option_groups FROM menu_variants WHERE menu_id = %s AND temperature = %s
    """, (menu_id, temperature)).fetchone()
    return None if variant is None else variant["option_groups"]


def insert_order(
    connection: psycopg.Connection,
    *,
    request_id: UUID,
    menu_id: str,
    menu_name: str,
    price_krw: int,
    temperature: str,
    service_type: str,
    selected_options: list[dict],
) -> dict:
    return connection.execute(f"""
        INSERT INTO orders (
            request_id, menu_id, menu_name_snapshot, unit_price_krw, temperature, service_type,
            total_price_krw, selected_options
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING {ORDER_RESULT_COLUMNS}
    """, (request_id, menu_id, menu_name, price_krw, temperature, service_type,
          price_krw, Jsonb(selected_options))).fetchone()
