import psycopg
from psycopg.rows import dict_row

from app.db.catalog import CATEGORY_ORDER
from app.db.connection import connect


class CatalogReadError(ValueError):
    pass


def list_menus(database_url: str | None = None) -> list[dict]:
    """Read a consistent catalogue snapshot; callers handle HTTP errors."""
    with connect(database_url) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        return read_menus(connection)


def read_menus(connection: psycopg.Connection) -> list[dict]:
    with connection.cursor(row_factory=dict_row) as cursor:
        menus = cursor.execute('SELECT * FROM menus ORDER BY display_order, menu_id COLLATE "C"').fetchall()
        categories = cursor.execute("SELECT menu_id, category FROM menu_categories").fetchall()
        variants = cursor.execute("SELECT menu_id, temperature, image_url FROM menu_variants").fetchall()
    by_id = {menu["menu_id"]: {**menu, "categories": [], "variants": []} for menu in menus}
    for row in categories:
        by_id[row["menu_id"]]["categories"].append(row["category"])
    for row in variants:
        by_id[row["menu_id"]]["variants"].append({"temperature": row["temperature"], "image_url": row["image_url"]})
    for menu in by_id.values():
        if not menu["categories"] or any(category not in CATEGORY_ORDER for category in menu["categories"]):
            raise CatalogReadError(f"Menu has invalid categories: {menu['menu_id']}")
        menu["categories"].sort(key=CATEGORY_ORDER.index)
        menu["variants"].sort(key=lambda variant: ("HOT", "COLD").index(variant["temperature"]))
        menu["available_temperatures"] = [variant["temperature"] for variant in menu["variants"]]
        if not menu["variants"]:
            raise CatalogReadError(f"Menu has no temperature variants: {menu['menu_id']}")
        menu["image_url"] = next((v["image_url"] for v in menu["variants"] if v["temperature"] == "COLD"),
                                 menu["variants"][0]["image_url"])
    return list(by_id.values())
