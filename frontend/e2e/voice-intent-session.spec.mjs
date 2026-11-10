import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

test.use({ launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } });
const recommendation = { type: 'direct_recommendation', status: 'recommend', recommendations: [{ menu_id: 'cafe_latte', temperature: 'COLD' }] };
const originalOptions = { temperature: 'COLD', service_type: 'TAKEOUT', customization: {
  status: 'pending', option_ids: [], intents: [{ expression: '샷추가', candidate_option_ids: ['shot:extra'] }], unresolved: [] } };
const initial = { action: recommendation, recognized_options: originalOptions };

async function open(page, replies) {
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  const requests = [];
  await page.route('**/api/voice/interpret', async route => {
    requests.push(route.request().postData());
    const reply = replies.shift();
    await route.fulfill({ status: reply.status ?? 200, json: { transcript: '검증 발화', ...(reply.body ?? reply) } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: '음성으로 주문하기' }).click();
  return requests;
}
async function say(page, label = '메뉴 추천받기') {
  await page.getByRole('button', { name: label, exact: true }).click();
  await page.getByRole('button', { name: '녹음 종료', exact: true }).click();
}
async function choose(page) {
  await page.getByRole('region', { name: '추천 결과' }).getByRole('button', { name: /카페라떼/ }).click();
  await page.getByRole('button', { name: '네, 이 메뉴로 주문' }).click();
}
async function expectOriginalOrder(page) {
  await choose(page);
  const review = page.getByRole('region', { name: '최종 주문 확인' });
  await expect(review).toBeVisible();
  await expect(review).toContainText('차갑게');
  await expect(review).toContainText('포장해서');
  await expect(review).toContainText('샷 추가');
}

for (const [label, action] of [['주문하기', recommendation], ['메뉴 추천받기', { type: 'select_menu', menu_id: 'cafe_latte' }]]) {
  test(`unexpected action for ${label} cannot change the screen or session`, async ({ page }) => {
    await open(page, [initial, { action, recognized_options: { temperature: 'HOT', service_type: 'DINE_IN' } }]);
    await say(page);
    await expect(page.getByRole('region', { name: '추천 결과' })).toBeVisible();
    await say(page, label);
    await expect(page.getByRole('alert')).toContainText('입력 목적에 맞는 응답');
    await expect(page.getByRole('region', { name: '선택 메뉴 확인' })).toHaveCount(0);
    await expectOriginalOrder(page);
  });
}

test('unknown order offers recommendation without automatically requesting it', async ({ page }) => {
  const requests = await open(page, [{ action: { type: 'retry', reason: 'UNRECOGNIZED' } }]);
  await say(page, '주문하기');
  await expect(page.getByRole('alert')).toContainText('메뉴 이름을 확인하지 못했어요. 다시 말씀하시거나 메뉴 추천받기를 눌러 주세요.');
  expect(requests).toHaveLength(1);
  expect(requests[0]).toContain('name="intent"\r\n\r\norder');
  await expect(page.getByRole('region', { name: '추천 결과' })).toHaveCount(0);
});

test('successful fresh recommendation replaces previous options instead of merging', async ({ page }) => {
  await open(page, [initial, { action: recommendation }]);
  await say(page);
  await expect(page.getByRole('region', { name: '추천 결과' })).toBeVisible();
  await say(page);
  await expect(page.getByRole('button', { name: '메뉴 추천받기', exact: true })).toBeEnabled();
  await choose(page);
  await expect(page.getByRole('region', { name: '온도 선택' })).toBeVisible();
  await page.getByRole('button', { name: /차갑게/ }).click();
  await expect(page.getByRole('button', { name: /^샷 추가/ })).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('button', { name: '옵션 없이 계속' }).click();
  await expect(page.getByRole('region', { name: '매장 또는 포장 선택' })).toBeVisible();
});

for (const [name, reply] of [
  ['HTTP failure', { status: 502, body: { detail: { message: '추천 실패', code: 'LLM_RECOMMENDATION_FAILED' } } }],
  ['retry with conflicting options', { action: { type: 'retry', reason: 'UNRECOGNIZED' }, recognized_options: { unresolved_fields: ['temperature', 'service_type'] } }],
  ['invalid candidate', { action: { ...recommendation, recommendations: [{ menu_id: 'unknown', temperature: 'COLD' }] } }],
  ['inconsistent empty result', { action: { ...recommendation, status: 'insufficient_data' } }],
]) {
  test(`new recommendation ${name} preserves the original candidates and options`, async ({ page }) => {
    await open(page, [initial, reply]);
    await say(page);
    await expect(page.getByRole('region', { name: '추천 결과' })).toBeVisible();
    await say(page);
    await expect(page.getByRole('alert')).toBeVisible();
    await expectOriginalOrder(page);
  });
}

test('spoken candidate selection and confirmation preserve the recommendation session', async ({ page }) => {
  const requests = await open(page, [initial, { action: { type: 'select_menu', menu_id: 'cafe_latte' } }, { action: { type: 'confirm' } }]);
  await say(page);
  await expect(page.getByRole('region', { name: '추천 결과' })).toBeVisible();
  await say(page, '주문하기');
  await expect(page.getByRole('region', { name: '선택 메뉴 확인' })).toBeVisible();
  await say(page, '음성 녹음');
  await expect(page.getByRole('region', { name: '최종 주문 확인' })).toContainText('샷 추가');
  expect(requests[1]).toContain('name="stage"\r\n\r\nrecommendations');
  expect(requests[1]).toContain('name="candidate_menu_ids"\r\n\r\ncafe_latte');
  expect(requests[2]).not.toContain('name="intent"');
});

test('canceled fresh recommendation cannot replace a touch-selected original order', async ({ page }) => {
  await open(page, [initial]);
  await say(page);
  await expect(page.getByRole('region', { name: '추천 결과' })).toBeVisible();
  let release;
  let requested = false;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/voice/interpret', async route => {
    requested = true;
    await gate;
    await route.fulfill({ json: { transcript: '새 조건', action: recommendation } }).catch(() => {});
  });
  await say(page);
  await expect.poll(() => requested).toBe(true);
  await page.getByRole('region', { name: '추천 결과' }).getByRole('button', { name: /카페라떼/ }).click();
  release();
  await page.getByRole('button', { name: '네, 이 메뉴로 주문' }).click();
  await expect(page.getByRole('region', { name: '최종 주문 확인' })).toContainText('샷 추가');
  await expect(page.getByRole('region', { name: '추천 결과' })).toHaveCount(0);
});
