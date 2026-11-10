import { selectCategory } from './category-navigation.mjs';
import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

const draft = { menu_id: 'iced_americano', temperature: 'COLD', service_type: 'TAKEOUT' };
const orderNumber = '9007199254740993';
const result = {
  ...draft,
  order_id: orderNumber,
  order_number: orderNumber,
  menu_name: '아메리카노',
  quantity: 1,
  total_price_krw: 2300,
  created_at: '2026-11-07T00:00:00Z',
};

async function startOrder(page) {
  const catalogue = await createMockApi({ delayMs: 0 }).getMenus();
  await page.route('**/api/menus', route => route.fulfill({ json: catalogue }));
  await page.goto('/');
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
}

async function openReview(page) {
  await startOrder(page);
  await chooseIcedAmericano(page);
  await page.getByRole('button', { name: /포장해서/ }).click();
  const confirm = page.getByRole('button', { name: '주문 확정', exact: true });
  await expect(confirm).toBeEnabled();
  return confirm;
}

async function chooseIcedAmericano(page) {
  await page.getByText('아메리카노', { exact: true }).click();
  await page.getByRole('button', { name: /차갑게/ }).click();
  await page.getByRole('button', { name: '옵션 없이 계속' }).click();
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
  expect(requests).toEqual([{ method: 'POST', body: { ...draft, items: [{...draft, quantity: 1, option_ids: []}], request_id: expect.stringMatching(/^[0-9a-f-]{36}$/) } }]);
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
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
  await expect(page.getByRole('heading', { name: '전체 메뉴판' })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await chooseIcedAmericano(page);
  await page.getByRole('button', { name: /포장해서/ }).click();
  await page.getByRole('button', { name: '주문 확정', exact: true }).click();
  await expect(page.getByRole('definition')).toHaveText(orderNumber);
  expect(requests).toHaveLength(2);
  expect(requests[0].request_id).not.toBe(requests[1].request_id);
});

test('returning home from touch completion starts a fresh order', async ({ page }) => {
  await page.route('**/api/orders', route => route.fulfill({ status: 201, json: result }));
  await startOrder(page);
  await page.evaluate(() => {
    window.speechCancelCount = 0;
    window.speechSynthesis.cancel = () => { window.speechCancelCount += 1; };
  });

  await expect(page.getByRole('button', { name: /간편 메뉴판 보기|전체 메뉴판 보기/ })).toHaveCount(0);
  await page.getByRole('button', { name: '크게 보기' }).click();
  await expect(page.getByRole('button', { name: '기본 크기로 보기' })).toHaveAttribute('aria-pressed', 'true');
  await chooseIcedAmericano(page);
  await page.getByRole('button', { name: /포장해서/ }).click();
  await page.getByRole('button', { name: '주문 확정', exact: true }).click();
  await expect(page.getByRole('definition')).toHaveText(orderNumber);
  const cancellationsBeforeHome = await page.evaluate(() => window.speechCancelCount);

  await page.getByRole('button', { name: '처음으로 돌아가기' }).click();
  await expect.poll(() => page.evaluate(() => window.speechCancelCount)).toBe(cancellationsBeforeHome);
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
  await expect(page.getByRole('heading', { name: '전체 메뉴판' })).toBeVisible();
  await expect(page.getByRole('button', { name: '크게 보기' })).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByRole('region', { name: '주문 완료' })).toHaveCount(0);
  await expect(page.getByText(orderNumber, { exact: true })).toHaveCount(0);

  await selectCategory(page, '커피', '라떼');
  await page.getByRole('button', { name: /카페라떼/ }).click();
  await page.getByRole('button', { name: /따뜻하게/ }).click();
  await page.getByRole('button', { name: '옵션 없이 계속' }).click();
  await page.getByRole('button', { name: /매장에서/ }).click();
  const review = page.getByRole('region', { name: '최종 주문 확인' });
  await expect(review.getByRole('heading', { name: '카페라떼' })).toBeVisible();
  await expect(review.getByText('따뜻하게 · 매장에서')).toBeVisible();
});

test('customization adds the correct price and appears in confirmation and receipt', async ({ page }) => {
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/orders', async route => {
    const payload = route.request().postDataJSON();
    expect(payload.option_ids).toEqual(['size:up', 'milk:oat', 'sweetness:vanilla']);
    const order = await api.createOrder(payload);
    await route.fulfill({ status: 201, json: { ...order, order_id: '42', order_number: '42' } });
  });
  await startOrder(page);
  await selectCategory(page, '커피', '라떼');
  await page.getByText('카페라떼', { exact: true }).click();
  await page.getByRole('button', { name: /따뜻하게/ }).click();
  const options = page.getByRole('region', { name: '추가 옵션 선택' });
  await options.getByRole('button', { name: /사이즈업/ }).click();
  await options.getByRole('button', { name: /아몬드밀크/ }).click();
  await options.getByRole('button', { name: /오트밀크/ }).click();
  await expect(options.getByRole('button', { name: /아몬드밀크/ })).toHaveAttribute('aria-pressed', 'false');
  await options.getByRole('button', { name: /^바닐라 시럽/ }).click();
  await expect(options.getByText('4,800원', { exact: true })).toBeVisible();
  await options.getByRole('button', { name: '선택한 옵션으로 계속' }).click();
  await page.getByRole('button', { name: /매장에서/ }).click();
  const review = page.getByRole('region', { name: '최종 주문 확인' });
  await expect(review).toContainText('오트밀크 변경');
  await expect(review).toContainText('4,800원');
  await review.getByRole('button', { name: '주문 확정', exact: true }).click();
  const receipt = page.getByRole('region', { name: '주문 완료' });
  await expect(receipt).toContainText('바닐라 시럽 추가');
  await expect(receipt).toContainText('4,800원');
});

test('continue ordering preserves both lines and quantity including options', async ({page}) => {
  let sent;
  await page.route('**/api/orders', async route => {
    sent = route.request().postDataJSON();
    await route.fulfill({status:201,json:result});
  });
  await openReview(page);
  await page.getByRole('button', {name:'아메리카노 수량 늘리기',exact:true}).click();
  await expect(page.getByText('2잔', {exact:true})).toBeVisible();
  await page.getByRole('button', {name:'계속 주문하기'}).click();
  await chooseIcedAmericano(page);
  await page.getByRole('button', {name:/포장해서/}).click();
  await expect(page.getByRole('heading', {name:'아메리카노',exact:true})).toHaveCount(2);
  await page.getByRole('button', {name:'주문 확정',exact:true}).click();
  await expect(page.getByRole('region', {name:'주문 완료'})).toBeVisible();
  expect(sent.items.map(i => i.quantity)).toEqual([2,1]);
});
