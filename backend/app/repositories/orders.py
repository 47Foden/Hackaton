import psycopg


def lock_menu(connection: psycopg.Connection, menu_id: str) -> dict | None:
    return connection.execute("""
        SELECT name, price_krw, is_available
        FROM menus
        WHERE menu_id = %s
        FOR SHARE
    """, (menu_id,)).fetchone()


def has_temperature(connection: psycopg.Connection, menu_id: str, temperature: str) -> bool:
    return connection.execute("""
        SELECT 1 FROM menu_variants WHERE menu_id = %s AND temperature = %s
    """, (menu_id, temperature)).fetchone() is not None


def insert_order(
    connection: psycopg.Connection,
    *,
    menu_id: str,
    menu_name: str,
    price_krw: int,
    temperature: str,
    service_type: str,
) -> dict:
    return connection.execute("""
        INSERT INTO orders (
            menu_id, menu_name_snapshot, unit_price_krw, temperature, service_type, total_price_krw
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, menu_id, menu_name_snapshot, temperature, service_type,
                  quantity, total_price_krw, created_at
    """, (menu_id, menu_name, price_krw, temperature, service_type, price_krw)).fetchone()
