import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createMockApi } from '../src/api/mock/createMockApi.ts';
import { createHttpApi } from '../src/api/http.ts';

const selection = { menu_id: 'iced_americano', temperature: 'COLD', service_type: 'TAKEOUT' };
const request = { ...selection, request_id: '550e8400-e29b-41d4-a716-446655440000' };
const storedOrder = {
  ...selection,
  order_id: '9007199254740993',
  order_number: '9007199254740993',
  menu_name: '아이스아메리카노',
  quantity: 1,
  total_price_krw: 2000,
  created_at: '2026-11-07T00:00:00Z',
};

test('mock uses the API catalogue and computes server-side order fields', async () => {
  const api = createMockApi({ delayMs: 0 });
  const { menus } = await api.getMenus();
  assert.equal(menus.length, 11);
  assert.equal(menus.filter(menu => menu.is_featured).length, 4);
  assert.equal(menus.reduce((sum, menu) => sum + menu.variants.length, 0), 16);
  const result = await api.createOrder(request);
  assert.equal(result.total_price_krw, menus.find(menu => menu.menu_id === request.menu_id).price_krw);
  assert.match(result.order_number, /^DEV-/);
  assert.deepEqual(Object.keys(result).sort(), ['menu_id','temperature','service_type','order_id','order_number','menu_name','quantity','total_price_krw','created_at'].sort());
  menus[0].price_krw = -1;
  assert.notEqual((await api.getMenus()).menus[0].price_krw, -1);
});

test('mock rejects unknown menus, unsupported options, and client prices', async () => {
  const api = createMockApi({ delayMs: 0 });
  for (const [payload, status] of [
    [selection, 422],
    [{ ...request, request_id: 'invalid' }, 422],
    [{ ...request, menu_id: 'missing' }, 404],
    [{ ...request, temperature: 'HOT' }, 422],
    [{ ...request, price_krw: 1 }, 422],
  ]) await assert.rejects(api.createOrder(payload), error => error.status === status && !error.uncertain);
});

test('mock recovers a saved response after an uncertain failure and rejects a changed payload', async () => {
  const api = createMockApi({ orderError: 'uncertain', delayMs: 0 });
  await assert.rejects(api.createOrder(request), error => error.uncertain);
  const saved = await api.createOrder(request);
  assert.equal(saved.order_number, 'DEV-0001');
  assert.deepEqual(await api.createOrder(request), saved);
  await assert.rejects(api.createOrder({ ...request, service_type: 'DINE_IN' }), error => error.code === 'IDEMPOTENCY_CONFLICT');
});

test('mock supports empty menus, failure, and cancellation without returning success', async () => {
  assert.deepEqual(await createMockApi({ menus: [], delayMs: 0 }).getMenus(), { menus: [] });
  await assert.rejects(createMockApi({ menuError: true, delayMs: 0 }).getMenus(), error => error.code === 'CATALOG_UNAVAILABLE');
  await assert.rejects(createMockApi({ orderError: 'uncertain', delayMs: 0 }).createOrder(request), error => error.uncertain);
  const controller = new AbortController();
  const pending = createMockApi({ delayMs: 1000 }).getMenus(controller.signal);
  controller.abort();
  await assert.rejects(pending, error => error.name === 'AbortError');
});

test('HTTP adapter preserves the exact DB order number string', async () => {
  const api = createHttpApi(async (url, init) => {
    assert.equal(url, '/api/orders');
    assert.equal(init.method, 'POST');
    assert.deepEqual(JSON.parse(init.body), request);
    return Response.json(storedOrder, { status: 201 });
  });
  assert.deepEqual(await api.createOrder(request), storedOrder);
});

test('HTTP orders require matching DB order ID and number strings', async () => {
  for (const identifiers of [
    { order_id: '', order_number: '' },
    { order_id: 42, order_number: 42 },
    { order_id: '42', order_number: '43' },
    { order_id: 'DEV-0001', order_number: 'DEV-0001' },
  ]) {
    const api = createHttpApi(async () => Response.json({ ...storedOrder, ...identifiers }, { status: 201 }));
    await assert.rejects(api.createOrder(request), error => error.code === 'INVALID_RESPONSE' && error.uncertain);
  }
});

test('HTTP errors distinguish safe rejection from uncertain storage and transport outcomes', async () => {
  for (const [status, uncertain] of [[404, false], [409, false], [422, false], [503, true], [500, true]]) {
    const api = createHttpApi(async () => Response.json({ detail: { code: 'TEST', message: '실패' } }, { status }));
    await assert.rejects(api.createOrder(request), error => error.status === status && error.uncertain === uncertain);
  }
  for (const [status, uncertain] of [[409, false], [503, true]]) {
    const api = createHttpApi(async () => new Response('Service error', { status }));
    await assert.rejects(api.createOrder(request), error => error.status === status && error.uncertain === uncertain);
  }
  await assert.rejects(createHttpApi(async () => { throw new TypeError('offline'); }).createOrder(request), error => error.uncertain);
  await assert.rejects(createHttpApi(async () => Response.json({}, { status: 201 })).createOrder(request), error => error.code === 'INVALID_RESPONSE' && error.uncertain);
});

test('order creation and replay accept 201 and 200 but not 202', async () => {
  for (const status of [200, 201]) {
    const api = createHttpApi(async () => Response.json(storedOrder, { status }));
    assert.deepEqual(await api.createOrder(request), storedOrder);
  }
  const api = createHttpApi(async () => Response.json(storedOrder, { status: 202 }));
  await assert.rejects(api.createOrder(request), error => error.code === 'INVALID_RESPONSE' && error.uncertain);
});
