import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

test.use({ launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } });

async function setup(page, action, status = 200) {
  const api = createMockApi({ delayMs: 0 });
  let calls = 0;
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  await page.route('**/api/voice/interpret', async route => {
    calls++;
    await route.fulfill({ status, json: status === 200 ? { transcript: '차가운 음료 추천', action }
      : { detail: { code: 'LLM_RECOMMENDATION_FAILED', message: 'LLM 추천을 확인하지 못했어요.' } } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: '음성으로 주문하기' }).click();
  await page.getByRole('button', { name: '음성 녹음', exact: true }).click();
  await expect(page.getByRole('button', { name: '녹음 종료' })).toBeVisible();
  await page.getByRole('button', { name: '녹음 종료' }).click();
  return () => calls;
}

test('direct candidate shows a current menu name and grounded reason without a text test panel', async ({ page }) => {
  const calls = await setup(page, { type: 'direct_recommendation', engine: 'llm-direct', status: 'recommend',
    recommendations: [{ menu_id: 'iced_americano', temperature: 'COLD', reason: '확인 가격과 온도로 선택한 mock 후보입니다.' }], questions: [], missing_information: [] });
  await expect(page.getByText(/LLM 추천 · COLD: 확인 가격과 온도/)).toBeVisible();
  await expect(page.locator('.menu-card__name', { hasText: '아메리카노' })).toBeVisible();
  await expect(page.getByText('텍스트로 추천 시험 (개발용)', { exact: true })).toHaveCount(0);
  expect(calls()).toBe(1);
});

for (const status of ['clarify', 'insufficient_data']) {
  test(`direct ${status} is shown without silently choosing a menu`, async ({ page }) => {
    const message = status === 'clarify' ? '원하는 온도를 알려주세요.' : '확인된 우유 성분 자료가 필요해요.';
    const calls = await setup(page, { type: 'direct_recommendation', engine: 'llm-direct', status,
      recommendations: [], questions: status === 'clarify' ? [message] : [], missing_information: status === 'insufficient_data' ? [message] : [] });
    await expect(page.getByRole('region', { name: '추천 추가 안내' })).toContainText(message);
    await expect(page.getByRole('region', { name: '선택 메뉴 확인' })).toHaveCount(0);
    expect(calls()).toBe(1);
  });
}

test('failed direct recommendation reports error once without retry or fallback', async ({ page }) => {
  const calls = await setup(page, null, 502);
  await expect(page.getByRole('alert').filter({ hasText: 'LLM_RECOMMENDATION_FAILED' })).toBeVisible();
  await page.waitForTimeout(300);
  expect(calls()).toBe(1);
  await expect(page.getByRole('region', { name: '추천 결과' })).toHaveCount(0);
});
