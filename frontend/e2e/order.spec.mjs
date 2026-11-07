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

async function startOrder(page) {
  const catalogue = await createMockApi({ delayMs: 0 }).getMenus();
  await page.route('**/api/menus', route => route.fulfill({ json: catalogue }));
  await page.goto('/');
  await page.getByRole('button', { name: '주문하기' }).click();
}

async function openReview(page) {
  await startOrder(page);
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
  expect(requests).toEqual([{ method: 'POST', body: { ...draft, request_id: expect.stringMatching(/^[0-9a-f-]{36}$/) } }]);
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

test('a lost response can be recovered by retrying the same order request', async ({ page }) => {
  const requests = [];
  await page.route('**/api/orders', route => {
    requests.push(route.request().postDataJSON());
    return requests.length === 1
      ? route.abort('failed')
      : route.fulfill({ status: 200, json: result });
  });

  await (await openReview(page)).click();
  await expect(page.getByRole('heading', { name: '주문 접수 여부를 확인해 주세요.' })).toBeVisible();
  await expect(page.getByRole('region', { name: '주문 완료' })).toHaveCount(0);
  expect(requests).toHaveLength(1);

  await page.getByRole('button', { name: '같은 주문 다시 시도', exact: true }).click();
  await expect(page.getByRole('definition')).toHaveText(orderNumber);
  expect(requests).toEqual([requests[0], requests[0]]);
});

test('an ID conflict locks retry until the customer starts a fresh order', async ({ page }) => {
  const requests = [];
  await page.route('**/api/orders', route => {
    requests.push(route.request().postDataJSON());
    return requests.length === 1
      ? route.fulfill({ status: 409, json: { detail: { code: 'IDEMPOTENCY_CONFLICT', message: '같은 요청 ID로 접수된 주문의 내용이 다릅니다.' } } })
      : route.fulfill({ status: 201, json: result });
  });
  await (await openReview(page)).click();
  await expect(page.getByRole('heading', { name: '주문 요청을 확인해 주세요.' })).toBeVisible();
  await expect(page.getByRole('button', { name: '요청 정보 확인 필요' })).toBeDisabled();
  await page.getByRole('button', { name: '처음으로', exact: true }).click();
  await page.getByRole('button', { name: '주문하기' }).click();
  await expect(page.getByRole('heading', { name: '간편 메뉴판' })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await page.getByRole('button', { name: /아이스아메리카노/ }).click();
  await page.getByRole('button', { name: /포장해서/ }).click();
  await page.getByRole('button', { name: '주문 확정', exact: true }).click();
  await expect(page.getByRole('definition')).toHaveText(orderNumber);
  expect(requests).toHaveLength(2);
  expect(requests[0].request_id).not.toBe(requests[1].request_id);
});

test('returning home from completion releases speech and starts a fresh order', async ({ page }) => {
  await page.route('**/api/orders', route => route.fulfill({ status: 201, json: result }));
  await startOrder(page);
  await page.evaluate(() => {
    window.speechCancelCount = 0;
    window.speechSynthesis.cancel = () => { window.speechCancelCount += 1; };
  });

  await page.getByRole('button', { name: '전체 메뉴판 보기' }).click();
  await page.getByRole('button', { name: '크게 보기' }).click();
  await expect(page.getByRole('button', { name: '기본 크기로 보기' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: /아이스아메리카노/ }).click();
  await page.getByRole('button', { name: /포장해서/ }).click();
  await page.getByRole('button', { name: '주문 확정', exact: true }).click();
  await expect(page.getByRole('definition')).toHaveText(orderNumber);
  const cancellationsBeforeHome = await page.evaluate(() => window.speechCancelCount);

  await page.getByRole('button', { name: '처음으로 돌아가기' }).click();
  await expect.poll(() => page.evaluate(() => window.speechCancelCount)).toBe(cancellationsBeforeHome + 1);
  await page.getByRole('button', { name: '주문하기' }).click();
  await expect(page.getByRole('heading', { name: '간편 메뉴판' })).toBeVisible();
  await expect(page.getByRole('button', { name: '크게 보기' })).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByRole('region', { name: '주문 완료' })).toHaveCount(0);
  await expect(page.getByText(orderNumber, { exact: true })).toHaveCount(0);

  await page.getByRole('button', { name: /카페라떼/ }).click();
  await page.getByRole('button', { name: /따뜻하게/ }).click();
  await page.getByRole('button', { name: /매장에서/ }).click();
  const review = page.getByRole('region', { name: '최종 주문 확인' });
  await expect(review.getByRole('heading', { name: '카페라떼' })).toBeVisible();
  await expect(review.getByText('따뜻하게 · 매장에서')).toBeVisible();
});
