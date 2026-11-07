import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.db.catalog import CatalogError, load_catalog
from app.db.connection import connect
from app.db.migrate import MIGRATIONS_DIR, MigrationError, migrate
from app.db.seed import seed
from app.repositories.menus import list_menus


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.admin_url = os.environ['DATABASE_URL']
        self.schema = 'test_menu_' + uuid.uuid4().hex
        with connect(self.admin_url) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.url = make_conninfo(self.admin_url, options=f'-c search_path={self.schema}')
        self.common = Path(os.environ['COMMON_DIR'])
        self.public = Path(os.environ['FRONTEND_PUBLIC_DIR'])

    def tearDown(self):
        # Only the unique schema created by this test is removed.
        with connect(self.admin_url) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def prepare(self):
        migrate(self.url)
        seed(self.url)

    def test_new_database_and_repeated_seed_preserve_settings_and_orders(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            shutil.copyfile(MIGRATIONS_DIR / '0001_menu_orders.sql', directory / '0001_menu_orders.sql')
            self.assertEqual(migrate(self.url, directory), ['0001_menu_orders'])
        self.assertEqual(seed(self.url), 11)
        with connect(self.url) as conn:
            conn.execute("UPDATE menus SET is_available=false, is_featured=false WHERE menu_id='iced_americano'")
            legacy_order = conn.execute("""INSERT INTO orders(menu_id, menu_name_snapshot, unit_price_krw,
                temperature, service_type, total_price_krw)
                VALUES ('iced_americano', '기존 주문명', 2000, 'COLD', 'TAKEOUT', 2000)
                RETURNING *""").fetchone()
        self.assertEqual(migrate(self.url), ['0002_order_request_id'])
        self.assertEqual(migrate(self.url), [])
        seed(self.url)
        menus = list_menus(self.url)
        self.assertEqual(len(menus), 11)
        self.assertEqual(sum(len(menu['variants']) for menu in menus), 16)
        actual = {menu['name']: menu for menu in menus}
        for expected in load_catalog():
            self.assertEqual(actual[expected.name]['price_krw'], expected.price_krw)
            self.assertEqual(actual[expected.name]['categories'], list(expected.categories))
        self.assertFalse(actual['아이스아메리카노']['is_available'])
        self.assertFalse(actual['아이스아메리카노']['is_featured'])
        self.assertEqual(actual['레몬티']['image_url'], actual['레몬차']['image_url'])
        self.assertNotEqual(actual['레몬티']['menu_id'], actual['레몬차']['menu_id'])
        with connect(self.url) as conn:
            order = conn.execute('SELECT * FROM orders').fetchone()
            self.assertIsInstance(order.pop('request_id'), uuid.UUID)
            self.assertEqual(order, legacy_order)
            self.assertEqual(conn.execute('SELECT count(*) AS count FROM menu_categories').fetchone()['count'], 14)

    def test_validation_failure_writes_nothing(self):
        self.prepare()
        with tempfile.TemporaryDirectory() as temp:
            common = Path(temp) / 'common'
            shutil.copytree(self.common, common)
            prices = json.loads((common / 'menu_prices.json').read_text(encoding='utf-8-sig'))
            prices['에스프레소'] = True
            (common / 'menu_prices.json').write_text(json.dumps(prices), encoding='utf-8')
            with self.assertRaises(CatalogError):
                seed(self.url, common_dir=common)
        self.assertEqual(len(list_menus(self.url)), 11)

    def test_missing_image_and_unknown_existing_menu_reject_seed(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(CatalogError):
                load_catalog(public_dir=Path(temp))
        self.prepare()
        with connect(self.url) as conn:
            conn.execute("INSERT INTO menus(menu_id,name,price_krw,display_order) VALUES ('extra','추가',1000,12)")
        with self.assertRaises(CatalogError):
            seed(self.url)
        with connect(self.url) as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS count FROM menus').fetchone()['count'], 12)

    def test_migration_checksum_and_failure_rollback(self):
        migrate(self.url)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            shutil.copytree(MIGRATIONS_DIR, directory, dirs_exist_ok=True)
            first = directory / '0001_menu_orders.sql'
            first.write_text(first.read_text() + '\n-- changed\n')
            with self.assertRaises(MigrationError):
                migrate(self.url, directory)
            shutil.copyfile(MIGRATIONS_DIR / first.name, first)
            (directory / '0003_invalid.sql').write_text('CREATE TABLE rollback_probe(id INTEGER); SELECT missing_column;')
            with self.assertRaises(psycopg.Error):
                migrate(self.url, directory)
        with connect(self.url) as conn:
            self.assertIsNone(conn.execute("SELECT to_regclass('rollback_probe') AS name").fetchone()['name'])
            self.assertEqual(conn.execute('SELECT count(*) AS count FROM schema_migrations').fetchone()['count'], 2)

    def test_database_constraints_and_connection_rollback(self):
        self.prepare()
        for statement in [
            "UPDATE menus SET price_krw=-1 WHERE menu_id='espresso'",
            "INSERT INTO menu_variants VALUES ('espresso','WARM','/images/menus/test.jpg')",
            "INSERT INTO menu_categories VALUES ('missing','커피')",
        ]:
            with self.assertRaises(psycopg.Error):
                with connect(self.url) as conn:
                    conn.execute(statement)
        self.assertEqual(len(list_menus(self.url)), 11)
        with self.assertRaises(RuntimeError):
            with connect(self.url) as conn:
                conn.execute("UPDATE menus SET price_krw=0 WHERE menu_id='espresso'")
                raise RuntimeError('rollback')
        espresso = next(menu for menu in list_menus(self.url) if menu['menu_id'] == 'espresso')
        self.assertEqual(espresso['price_krw'], 1500)


if __name__ == '__main__':
    unittest.main()
