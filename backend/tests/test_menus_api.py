"""Exercise the ASGI HTTP application against isolated real PostgreSQL schemas."""
import asyncio
import json
import os
import unittest
import uuid
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.db.catalog import load_catalog
from app.db.connection import connect
from app.db.migrate import migrate
from app.db.seed import seed
from app.main import app


async def asgi_get(path):
    messages = []

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message):
        messages.append(message)

    await app({
        'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
        'method': 'GET', 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
        'query_string': b'', 'root_path': '', 'headers': [],
        'server': ('testserver', 80), 'client': ('127.0.0.1', 12345),
    }, receive, send)
    start = next(message for message in messages if message['type'] == 'http.response.start')
    body = b''.join(message.get('body', b'') for message in messages if message['type'] == 'http.response.body')
    return start['status'], json.loads(body)


class MenusApiTests(unittest.TestCase):
    def setUp(self):
        self.admin_url = os.environ['DATABASE_URL']
        self.schema = 'test_menus_api_' + uuid.uuid4().hex
        with connect(self.admin_url) as connection:
            connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.url = make_conninfo(self.admin_url, options=f'-c search_path={self.schema}')

    def tearDown(self):
        with connect(self.admin_url) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def get(self):
        with patch.dict(os.environ, {'DATABASE_URL': self.url}):
            return asyncio.run(asgi_get('/api/menus'))

    def prepare(self):
        migrate(self.url)
        seed(self.url)

    def assert_unavailable(self):
        with self.assertLogs('app.routers.menus', level='WARNING'):
            status, body = self.get()
        self.assertEqual(status, 503)
        self.assertEqual(body['detail']['code'], 'CATALOG_UNAVAILABLE')
        self.assertNotIn('menus', body)
        return body

    def test_seeded_catalogue_matches_common_and_public_contract(self):
        self.prepare()
        status, body = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {'menus'})
        menus = body['menus']
        self.assertEqual(len(menus), 45)
        self.assertEqual(sum(len(menu['variants']) for menu in menus), 71)
        self.assertEqual(sum(menu['is_featured'] for menu in menus), 4)
        self.assertEqual([menu['name'] for menu in menus], [menu.name for menu in load_catalog()])
        for menu, expected in zip(menus, load_catalog()):
            self.assertEqual(menu['price_krw'], expected.price_krw)
            self.assertEqual(menu['categories'], list(expected.categories))
            self.assertEqual(menu['available_temperatures'], [t for t, _ in expected.variants])
            self.assertEqual(menu['variants'], [
                {'temperature': t, 'image_url': image, 'option_groups': expected.option_groups}
                for t, image in expected.variants
            ])
            variants = dict(expected.variants)
            self.assertEqual(menu['image_url'], variants.get('COLD', variants.get('HOT')))
            self.assertIs(type(menu['is_available']), bool)
        self.assertEqual(set(menus[0]), {'menu_id','name','categories','price_krw','available_temperatures',
            'variants','image_url','is_available','display_order','is_featured'})

    def test_sale_and_feature_flags_do_not_filter_or_override_sort(self):
        self.prepare()
        with connect(self.url) as connection:
            connection.execute('UPDATE menus SET display_order=20')
            connection.execute("UPDATE menus SET display_order=1, is_available=false, is_featured=false WHERE menu_id='espresso'")
            connection.execute("UPDATE menus SET display_order=1, is_featured=true WHERE menu_id='cafe_latte'")
        status, body = self.get()
        self.assertEqual(status, 200)
        menus = body['menus']
        self.assertEqual(len(menus), 45)
        self.assertEqual([m['menu_id'] for m in menus[:2]], ['cafe_latte', 'espresso'])
        self.assertFalse(menus[1]['is_available'])
        self.assertFalse(menus[1]['is_featured'])
        self.assertEqual([(m['display_order'],m['menu_id']) for m in menus],
                         sorted((m['display_order'],m['menu_id']) for m in menus))

    def test_empty_catalogue_is_success_not_storage_failure(self):
        migrate(self.url)
        self.assertEqual(self.get(), (200, {'menus': []}))

    def test_missing_tables_and_missing_options_use_503(self):
        self.assert_unavailable()
        self.prepare()
        with connect(self.url) as connection:
            connection.execute("DELETE FROM menu_variants WHERE menu_id='espresso'")
        self.assert_unavailable()

    def test_invalid_response_data_and_connection_failure_do_not_leak_details(self):
        self.prepare()
        with connect(self.url) as connection:
            connection.execute("UPDATE menu_variants SET image_url='/images/menus/' WHERE menu_id='espresso'")
        self.assert_unavailable()
        with patch('app.routers.menus.list_menus', side_effect=psycopg.OperationalError('private database details')):
            body = self.assert_unavailable()
        self.assertNotIn('private database details', json.dumps(body))


if __name__ == '__main__':
    unittest.main()
