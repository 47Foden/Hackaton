import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

test.use({ launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } });

async function setup(page) {
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  // Never let a browser regression test reach STT, LLM or the real order DB.
  await page.route('**/api/voice/**', route => route.abort());
  await page.route('**/api/orders', route => route.abort());
  await page.goto('/');
  return api;
}

async function touchOrder(page) {
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
  await page.getByText('아메리카노', { exact: true }).click();
  await page.getByRole('button', { name: /차갑게/ }).click();
  await expect(page.getByRole('region', { name: '추가 옵션 선택' })).toBeVisible();
}

test('browser back and forward between start and ordering stay in the kiosk', async ({ page }) => {
  await setup(page);
  await page.getByRole('button', { name: '포장', exact: true }).click();
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
  await expect(page.getByText('아메리카노', { exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('main', { name: '주문 시작' })).toBeVisible();
  await expect(page.getByRole('button', { name: '포장', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.goForward();
  await expect(page.getByText('아메리카노', { exact: true })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe('/');
});

test('back restores selected options and forward restores review without sending an order', async ({ page }) => {
  await setup(page);
  await touchOrder(page);
  const choice = page.locator('.customization-choice').first();
  await choice.click();
  await expect(choice).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '선택한 옵션으로 계속' }).click();
  await expect(page.getByRole('region', { name: '최종 주문 확인' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('region', { name: '추가 옵션 선택' })).toBeVisible();
  await expect(page.locator('.customization-choice').first()).toHaveAttribute('aria-pressed', 'true');
  await page.goBack();
  await expect(page.getByRole('region', { name: '온도 선택' })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('region', { name: '추가 옵션 선택' })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('region', { name: '최종 주문 확인' })).toBeVisible();
});

test('continuing an order then going back preserves cart quantity', async ({ page }) => {
  await setup(page);
  await touchOrder(page);
  await page.getByRole('button', { name: '옵션 없이 계속' }).click();
  await page.getByRole('button', { name: '아메리카노 수량 늘리기' }).click();
  await page.getByRole('button', { name: '계속 주문하기' }).click();
  await expect(page.getByText('아메리카노', { exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('region', { name: '최종 주문 확인' })).toContainText('2잔');
  await page.goForward();
  await expect(page.getByText('아메리카노', { exact: true })).toBeVisible();
});

test('voice menu confirmation returns to menu, then to start without STT', async ({ page }) => {
  await setup(page);
  await page.getByRole('button', { name: '음성으로 주문하기' }).click();
  await page.getByText('아메리카노', { exact: true }).click();
  await expect(page.getByRole('region', { name: '선택 메뉴 확인' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('region', { name: '선택 메뉴 확인' })).toHaveCount(0);
  await expect(page.getByText('아메리카노', { exact: true })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('region', { name: '선택 메뉴 확인' })).toBeVisible();
  await page.goBack();
  await page.goBack();
  await expect(page.getByRole('main', { name: '주문 시작' })).toBeVisible();
});

test('returning home closes the old session even when browser back is used', async ({ page }) => {
  await setup(page);
  await touchOrder(page);
  await page.getByRole('button', { name: '처음으로', exact: true }).click();
  await expect(page.getByRole('main', { name: '주문 시작' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('main', { name: '주문 시작' })).toBeVisible();
});

test('back during submission preserves pending request; completed orders cannot be reopened', async ({ page }) => {
  const api = await setup(page);
  const requests = [];
  const gate = Promise.withResolvers();
  await page.route('**/api/orders', async route => {
    const body = route.request().postDataJSON(); requests.push(body);
    await gate.promise;
    await route.fulfill({ status: 201, json: { ...await api.createOrder(body), order_id: '101', order_number: '101' } });
  });
  await touchOrder(page);
  await page.getByRole('button', { name: '옵션 없이 계속' }).click();
  await page.getByRole('button', { name: '주문 확정', exact: true }).click();
  try {
    await expect(page.getByRole('button', { name: '주문 처리 중…' })).toBeDisabled();
    await page.goBack();
    await expect(page.getByText('주문 접수 결과를 확인한 뒤 이동해 주세요.')).toBeVisible();
    await expect(page.getByRole('button', { name: '주문 처리 중…' })).toBeDisabled();
  } finally { gate.resolve(); }
  await expect(page.getByRole('region', { name: '주문 완료' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('main', { name: '주문 시작' })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('main', { name: '주문 시작' })).toBeVisible();
  expect(requests).toHaveLength(1);
});

test('reload starts a fresh kiosk screen instead of restoring a stale draft', async ({ page }) => {
  await setup(page);
  await touchOrder(page);
  await page.reload();
  await expect(page.getByRole('main', { name: '주문 시작' })).toBeVisible();
});
