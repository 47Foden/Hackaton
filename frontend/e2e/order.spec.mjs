import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

const draft = { menu_id: 'iced_americano', temperature: 'COLD', service_type: 'TAKEOUT' };
const orderNumber = '9007199254740993';
const result = {
  ...draft,
  order_id: orderNumber,
  order_number: orderNumber,
  menu_name: '아이스아메리카노',
  quantity: 1,
  total_price_krw: 2300,
  created_at: '2026-11-07T00:00:00Z',
};

async function openReview(page) {
  const catalogue = await createMockApi({ delayMs: 0 }).getMenus();
  await page.route('**/api/menus', route => route.fulfill({ json: catalogue }));
  await page.goto('/');
  await page.getByRole('button', { name: '주문하기' }).click();
  await page.getByRole('button', { name: /아이스아메리카노/ }).click();
  await page.getByRole('button', { name: /포장해서/ }).click();
  const confirm = page.getByRole('button', { name: '주문 확정', exact: true });
  await expect(confirm).toBeEnabled();
  return confirm;
}

test('final confirmation submits once and locks the buttons while waiting', async ({ page }) => {
  const requests = [];
  const { promise: responseGate, resolve: releaseResponse } = Promise.withResolvers();
  await page.route('**/api/orders', async route => {
    const request = route.request();
    requests.push({ method: request.method(), body: request.postDataJSON() });
    await responseGate;
    await route.fulfill({ status: 201, json: result });
  });

  const confirm = await openReview(page);
  expect(requests).toHaveLength(0);

  try {
    await confirm.evaluate(button => {
      button.click();
      button.click();
    });
    await expect(page.getByRole('button', { name: '주문 처리 중…' })).toBeDisabled();
    await expect(page.getByRole('button', { name: '처음으로', exact: true })).toBeDisabled();
    await expect(page.getByRole('region', { name: '주문 완료' })).toHaveCount(0);
  } finally {
    releaseResponse();
  }
  const completion = page.getByRole('region', { name: '주문 완료' });
  await expect(completion).toBeVisible();
  await expect(completion.getByRole('term')).toHaveText('주문번호');
  const displayedNumber = completion.getByRole('definition');
  await expect(displayedNumber).toBeVisible();
  await expect(displayedNumber).toHaveText(orderNumber);
  await expect(completion).toContainText('2,300원');
  expect(requests).toEqual([{ method: 'POST', body: draft }]);
});

test('a definite rejection displays the reason and permits a manual retry', async ({ page }) => {
  let calls = 0;
  await page.route('**/api/orders', route => ++calls === 1
    ? route.fulfill({ status: 409, json: { detail: { code: 'MENU_UNAVAILABLE', message: '현재 판매하지 않는 메뉴입니다.' } } })
    : route.fulfill({ status: 201, json: result }));

  await (await openReview(page)).click();
  await expect(page.getByRole('heading', { name: '주문이 접수되지 않았어요.' })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveText('현재 판매하지 않는 메뉴입니다.');
  await expect(page.getByRole('region', { name: '주문 완료' })).toHaveCount(0);
  expect(calls).toBe(1);

  await page.getByRole('button', { name: '다시 시도', exact: true }).click();
  await expect(page.getByRole('region', { name: '주문 완료' })).toBeVisible();
  expect(calls).toBe(2);
});

test('an uncertain storage response keeps resubmission locked', async ({ page }) => {
  let calls = 0;
  await page.route('**/api/orders', route => {
    calls += 1;
    return route.fulfill({ status: 503, json: { detail: { code: 'ORDER_STORAGE_UNAVAILABLE', message: '주문 응답을 확인할 수 없어요.' } } });
  });

  await (await openReview(page)).click();
  await expect(page.getByRole('heading', { name: '주문 접수 여부를 확인해 주세요.' })).toBeVisible();
  await expect(page.getByText('이미 접수됐을 수 있어요. 새 주문을 넣기 전에 직원에게 확인해 주세요.')).toBeVisible();
  await expect(page.getByRole('button', { name: '접수 여부 확인 필요' })).toBeDisabled();
  await expect(page.getByRole('button', { name: '다시 시도', exact: true })).toHaveCount(0);
  await expect(page.getByRole('region', { name: '주문 완료' })).toHaveCount(0);
  expect(calls).toBe(1);
});
