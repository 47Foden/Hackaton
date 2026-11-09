import argparse

from psycopg.types.json import Jsonb

from app.db.catalog import CatalogError, load_catalog
from app.db.connection import connect

SEED_LOCK = 47071002


def seed(database_url: str | None = None, *, common_dir=None, public_dir=None) -> int:
    menus = load_catalog(common_dir, public_dir)
    with connect(database_url) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (SEED_LOCK,))
        existing = list(connection.execute("SELECT menu_id FROM menus ORDER BY menu_id FOR UPDATE"))
        if {row["menu_id"] for row in existing} - {menu.menu_id for menu in menus}:
            raise CatalogError("Existing menus are absent from common; explicit migration required")
        for menu in sorted(menus, key=lambda item: item.menu_id):
            connection.execute("""
                INSERT INTO menus(menu_id, name, price_krw, display_order, is_featured)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (menu_id) DO UPDATE SET
                    name = EXCLUDED.name, price_krw = EXCLUDED.price_krw,
                    display_order = EXCLUDED.display_order
            """, (menu.menu_id, menu.name, menu.price_krw, menu.display_order, menu.is_featured))
            connection.execute("DELETE FROM menu_categories WHERE menu_id = %s", (menu.menu_id,))
            connection.execute("DELETE FROM menu_variants WHERE menu_id = %s", (menu.menu_id,))
            with connection.cursor() as cursor:
                cursor.executemany("INSERT INTO menu_categories(menu_id, category) VALUES (%s, %s)",
                                   [(menu.menu_id, category) for category in menu.categories])
                cursor.executemany(
                    "INSERT INTO menu_variants(menu_id, temperature, image_url, option_groups) VALUES (%s, %s, %s, %s)",
                    [(menu.menu_id, temperature, image, Jsonb(menu.option_groups)) for temperature, image in menu.variants],
                )
    return len(menus)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and explicitly seed the common catalogue")
    parser.add_argument("--check", action="store_true", help="Validate files without opening a database connection")
    args = parser.parse_args()
    count = len(load_catalog()) if args.check else seed()
    print(f"{'Validated' if args.check else 'Seeded'} {count} menus")


if __name__ == "__main__":
    main()
