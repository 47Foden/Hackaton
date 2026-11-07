import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createKioskApi } from '../src/api/createKioskApi.ts';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

const request = { menu_id: 'iced_americano', temperature: 'COLD', service_type: 'TAKEOUT' };

test('default configuration uses HTTP for menus and orders', async () => {
  const mock = createMockApi({ delayMs: 0 });
  const catalogue = await mock.getMenus();
  const order = { ...await mock.createOrder(request), order_id: '42', order_number: '42' };
  const calls = [];
  const api = createKioskApi({ transport: async (url, init) => {
    calls.push(url);
    if (url === '/api/menus') return Response.json(catalogue);
    assert.equal(url, '/api/orders');
    assert.equal(init.method, 'POST');
    assert.deepEqual(JSON.parse(init.body), request);
    return Response.json(order, { status: 201 });
  }});
  assert.deepEqual(await api.getMenus(), catalogue);
  assert.deepEqual(await api.createOrder(request), order);
  assert.deepEqual(calls, ['/api/menus', '/api/orders']);
});

test('explicit mock orders use prices from HTTP menus', async () => {
  const catalogue = await createMockApi({ delayMs: 0 }).getMenus();
  catalogue.menus.find(menu => menu.menu_id === request.menu_id).price_krw = 2300;
  const calls = [];
  const api = createKioskApi({ orderMode: 'mock', mock: { delayMs: 0 }, transport: async (url, init) => {
    calls.push({ url, init });
    assert.equal(url, '/api/menus');
    return Response.json(catalogue);
  }});
  await assert.rejects(api.createOrder(request), error => error.code === 'CATALOG_NOT_LOADED');
  assert.deepEqual(await api.getMenus(), catalogue);
  const order = await api.createOrder(request);
  assert.equal(order.total_price_krw, 2300);
  assert.match(order.order_number, /^DEV-/);
  assert.equal(calls.length, 1);
});

test('HTTP menu failures never fall back to fixture menus', async () => {
  const api = createKioskApi({ orderMode: 'mock', transport: async () => Response.json({ detail: {
    code: 'CATALOG_UNAVAILABLE', message: '메뉴 조회 실패',
  }}, { status: 503 }) });
  await assert.rejects(api.getMenus(), error => error.code === 'CATALOG_UNAVAILABLE');
  await assert.rejects(api.createOrder(request), error => error.code === 'CATALOG_NOT_LOADED');
});

test('mixed mode preserves availability and temperatures from real menu responses', async () => {
  const catalogue = await createMockApi({ delayMs: 0 }).getMenus();
  catalogue.menus.find(menu => menu.menu_id === request.menu_id).is_available = false;
  const api = createKioskApi({ orderMode: 'mock', mock: { delayMs: 0 }, transport: async () => Response.json(catalogue) });
  await api.getMenus();
  await assert.rejects(api.createOrder(request), error => error.code === 'MENU_UNAVAILABLE');
  await assert.rejects(api.createOrder({ ...request, menu_id: 'espresso', temperature: 'COLD' }),
    error => error.code === 'INVALID_OPTION');
});

test('offline mock menu mode remains explicitly selectable', async () => {
  const api = createKioskApi({ menuMode: 'mock', orderMode: 'mock', mock: { delayMs: 0 }, transport: async () => {
    assert.fail('explicit mock mode must not request HTTP');
  }});
  assert.equal((await api.getMenus()).menus.length, 11);
});
