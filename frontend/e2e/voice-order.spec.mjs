import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';
test.use({ launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } });

test('independent voice session mixes speech and touch and submits only after confirmation', async ({ page }) => {
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  let orders = 0;
  await page.route('**/api/orders', async route => {
    orders++;
    const input = route.request().postDataJSON();
    await route.fulfill({ status: 201, json: { ...input, order_id: '42', order_number: '42', menu_name: '카페라떼', quantity: 1, total_price_krw: 4000, created_at: new Date().toISOString() } });
  });
  const actions = [{ type: 'select_menu', menu_id: 'cafe_latte' }, { type: 'confirm' },
    { type: 'set_service_type', service_type: 'TAKEOUT' }, { type: 'confirm' }];
  const stages = [];
  await page.route('**/api/voice/interpret', async route => {
    stages.push(route.request().postData());
    await route.fulfill({ json: { transcript: 'test', action: actions.shift() } });
  });
  await page.addInitScript(() => {
    window.prompts = [];
    window.speechSynthesis.speak = u => window.prompts.push(u.text);
    window.speechSynthesis.cancel = () => window.prompts.push('cancel');
  });
  await page.goto('/');
  await page.getByRole('button', { name: '음성으로 주문하기' }).click();
  await expect.poll(() => page.evaluate(() => window.prompts.join(' '))).toContain('아래 마이크 버튼');
  async function say() {
    await page.getByRole('button', { name: '음성 녹음', exact: true }).click();
    await expect(page.getByRole('button', { name: '녹음 종료' })).toBeVisible();
    await page.getByRole('button', { name: '녹음 종료' }).click();
  }
  await say();
  await expect(page.getByRole('button', { name: '네, 이 메뉴로 주문' })).toBeVisible();
  expect(orders).toBe(0);
  await say();
  await page.getByRole('button', { name: /따뜻하게/ }).click();
  await say();
  await expect(page.getByRole('button', { name: '주문 확정', exact: true })).toBeVisible();
  expect(orders).toBe(0);
  await say();
  await expect(page.getByText('42', { exact: true })).toBeVisible();
  expect(orders).toBe(1);
  expect(actions).toHaveLength(0);
  expect(stages[0]).toContain('menu');
  expect(stages[1]).toContain('menu_confirmation');
  expect(stages[2]).toContain('service_type');
  expect(stages[3]).toContain('review');
});

test('voice menu uses kiosk cards, enlargement and matching centered confirmation buttons', async ({ page }) => {
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  await page.goto('/');
  await expect(page.getByText('터치뿐 아니라 음성으로도 주문할 수 있어요.')).toBeVisible();
  const entry = page.getByRole('button', { name: '음성으로 주문하기' });
  await expect(entry.locator('svg')).toBeVisible();
  await entry.click();
  await expect(page.getByRole('heading', { name: '간편 메뉴판' })).toBeVisible();
  await page.getByRole('button', { name: '전체 메뉴판 보기' }).click();
  await page.getByRole('button', { name: '크게 보기' }).click();
  await expect(page.locator('.menu-board--enlarged')).toBeVisible();
  await page.getByRole('button', { name: /카페라떼/ }).click();
  const confirmation = page.getByRole('region', { name: '선택 메뉴 확인' });
  await expect(confirmation).toBeVisible();
  const card = await page.locator('.voice-menu-confirmation__card').boundingBox();
  const content = await page.locator('.kiosk-layout__content').evaluate(el => ({ x: el.getBoundingClientRect().x, width: el.clientWidth }));
  expect(Math.abs(card.x + card.width / 2 - content.x - content.width / 2)).toBeLessThan(3);
  await expect(confirmation.getByRole('button', { name: '네, 이 메뉴로 주문' })).toHaveClass('primary-button');
  await expect(confirmation.getByRole('button', { name: '다른 메뉴 선택' })).toHaveClass('primary-button');
  await expect(confirmation.getByRole('button', { name: '다른 메뉴 선택' })).toBeInViewport();
  await page.screenshot({ path: '/tmp/voice-confirmation.png' });
  await confirmation.getByRole('button', { name: '다른 메뉴 선택' }).click();
  await expect(page.getByRole('heading', { name: '전체 메뉴판' })).toBeVisible();
});
