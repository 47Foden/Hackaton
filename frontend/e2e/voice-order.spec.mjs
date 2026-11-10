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
  await expect(page.getByRole('button', { name: '음성 녹음', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '옵션 없이 계속' }).click();
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
  await expect(page.getByText(/음성으로 주문 안내나 메뉴 추천을 받고 싶거나/)).toBeVisible();
  const entry = page.getByRole('button', { name: '음성으로 주문하기' });
  await expect(entry.locator('svg')).toBeVisible();
  await entry.click();
  await expect(page.getByRole('heading', { name: '전체 메뉴판' })).toBeVisible();
  await expect(page.getByRole('button', { name: /간편 메뉴판 보기|전체 메뉴판 보기/ })).toHaveCount(0);
  await page.getByRole('button', { name: '크게 보기' }).click();
  await expect(page.locator('.menu-board--enlarged')).toBeVisible();
  await page.getByRole('group', { name: '커피 세부 분류' }).getByRole('button', { name: '라떼', exact: true }).click();
  await page.getByText('카페라떼', { exact: true }).click();
  const confirmation = page.getByRole('region', { name: '선택 메뉴 확인' });
  await expect(confirmation).toBeVisible();
  const card = await page.locator('.voice-menu-confirmation__card').boundingBox();
  const content = await page.locator('.kiosk-layout__content').evaluate(el => ({ x: el.getBoundingClientRect().x, width: el.clientWidth }));
  expect(Math.abs(card.x + card.width / 2 - content.x - content.width / 2)).toBeLessThan(3);
  await expect(confirmation.getByRole('button', { name: '네, 이 메뉴로 주문' })).toHaveClass('primary-button');
  await expect(confirmation.getByRole('button', { name: '다른 메뉴 선택' })).toHaveClass('primary-button');
  await expect(confirmation.getByRole('button', { name: '다른 메뉴 선택' })).toBeInViewport();
  await page.screenshot({ path: test.info().outputPath('voice-confirmation.png') });
  await confirmation.getByRole('button', { name: '다른 메뉴 선택' }).click();
  await expect(page.getByRole('heading', { name: '전체 메뉴판' })).toBeVisible();
});

test('voice recommendation, spoken restart, candidate selection and order completion', async ({ page }) => {
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  let orders = 0;
  await page.route('**/api/orders', route => {
    orders++;
    return route.fulfill({ status: 201, json: { ...route.request().postDataJSON(), order_id:'52', order_number:'52', menu_name:'카페라떼', quantity:1, total_price_krw:2900, created_at:new Date().toISOString() } });
  });
  const actions = [
    { type:'direct_recommendation', engine:'llm-direct', status:'recommend', recommendations:[{menu_id:'cafe_latte', temperature:'HOT', reason:'검증용 후보'}], questions:[], missing_information:[] },
    { type:'restart_recommendation' },
    { type:'direct_recommendation', engine:'llm-direct', status:'recommend', recommendations:[{menu_id:'cafe_latte', temperature:'HOT', reason:'검증용 후보'}], questions:[], missing_information:[] },
    { type:'select_menu', menu_id:'cafe_latte' },
    { type:'confirm' }, { type:'set_temperature', temperature:'HOT' },
    { type:'set_service_type', service_type:'TAKEOUT' }, { type:'confirm' },
  ];
  await page.route('**/api/voice/interpret', route => route.fulfill({ json: { transcript:'test', action:actions.shift() } }));
  await page.addInitScript(() => { window.speechSynthesis.speak=()=>{}; window.speechSynthesis.cancel=()=>{}; });
  await page.goto('/');
  await page.getByRole('button',{name:'음성으로 주문하기'}).click();
  async function say() {
    await page.getByRole('button',{name:'음성 녹음',exact:true}).click();
    await page.getByRole('button',{name:'녹음 종료'}).click();
  }
  await say();
  await expect(page.getByRole('heading',{name:'추천 메뉴',exact:true})).toBeVisible();
  await expect(page.getByRole('region',{name:'추천 결과'}).locator('.menu-card')).toHaveCount(1);
  await say();
  await expect(page.getByRole('heading',{name:'음성 주문',exact:true})).toBeVisible();
  await say();
  await expect(page.getByRole('heading',{name:'추천 메뉴',exact:true})).toBeVisible();
  await say();
  await expect(page.getByRole('button',{name:'네, 이 메뉴로 주문'})).toBeVisible();
  await say();
  await expect(page.getByRole('heading',{name:'따뜻하게, 차갑게?'})).toBeVisible();
  await say();
  await page.getByRole('button', { name: '옵션 없이 계속' }).click();
  await expect(page.getByRole('heading',{name:'어디에서 드시겠어요?'})).toBeVisible();
  await say();
  await expect(page.getByRole('button',{name:'주문 확정',exact:true})).toBeVisible();
  expect(orders).toBe(0);
  await say();
  await expect(page.getByText('52',{exact:true})).toBeVisible();
  expect(orders).toBe(1);
});
