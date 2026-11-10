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
    await route.fulfill({ status, json: status === 200 ? { transcript: '과일 음료 추천해줘', action }
      : { detail: { code: 'LLM_RECOMMENDATION_FAILED', message: 'LLM 추천을 확인하지 못했어요.' } } });
  });
  await page.addInitScript(() => {
    window.spokenPrompts = [];
    window.speechSynthesis.speak = utterance => window.spokenPrompts.push(utterance.text);
    window.speechSynthesis.cancel = () => {};
  });
  await page.goto('/');
  await page.getByRole('button', { name: '음성으로 주문하기' }).click();
  await page.getByRole('button', { name: '음성 녹음', exact: true }).click();
  await expect(page.getByRole('button', { name: '녹음 종료' })).toBeVisible();
  await page.getByRole('button', { name: '녹음 종료' }).click();
  return () => calls;
}

for (const size of [5, 45]) {
  test(`all ${size} matching menus appear without questions or conversation notices`, async ({ page }) => {
    const response = await createMockApi({ delayMs: 0 }).getMenus();
    const selected = response.menus.slice(0, size);
    const calls = await setup(page, { type: 'direct_recommendation', engine: 'llm-direct', status: 'recommend',
      recommendations: selected.map(m => ({ menu_id: m.menu_id,
        temperature: m.available_temperatures[0], reason: '검증용 모델 후보' })), questions: [], missing_information: [] });
    const results = page.getByRole('region', { name: '추천 결과' });
    await expect(results.locator('.menu-card')).toHaveCount(size);
    for (const menu of selected) await expect(results.locator('.menu-card__name', { hasText: menu.name })).not.toHaveCount(0);
    await expect(page.getByText(/대화 기록은 아직|원래 조건과 답을|과일차도 괜찮/)).toHaveCount(0);
    await expect(page.getByRole('region', { name: '추천 추가 안내' })).toHaveCount(0);
    expect((await page.evaluate(() => window.spokenPrompts)).join(' ')).not.toMatch(/대화 기록|원래 조건과 답|과일차도 괜찮/);
    expect(calls()).toBe(1);
    // A candidate beyond the former 4-menu limit is still selectable.
    await results.locator('.menu-card').last().click();
    await expect(page.getByRole('region', { name: '선택 메뉴 확인' })).toContainText(selected.at(-1).name);
  });
}

test('no supported match shows an empty result and restart without dialogue instructions', async ({ page }) => {
  const calls = await setup(page, { type: 'direct_recommendation', engine: 'llm-direct', status: 'insufficient_data',
    recommendations: [], questions: [], missing_information: ['확인된 성분 자료가 없어요.'] });
  await expect(page.getByRole('heading', { name: '조건에 맞는 메뉴가 없어요.' })).toBeVisible();
  await expect(page.locator('.menu-card')).toHaveCount(0);
  await expect(page.getByText(/대화 기록은 아직|원래 조건과 답을/)).toHaveCount(0);
  expect(calls()).toBe(1);
  await page.getByRole('button', { name: '다시 추천받기' }).click();
  await expect(page.getByRole('heading', { name: '음성 주문', exact: true })).toBeVisible();
});

test('failed direct recommendation reports error once without retry or fallback', async ({ page }) => {
  const calls = await setup(page, null, 502);
  await expect(page.getByRole('alert').filter({ hasText: 'LLM_RECOMMENDATION_FAILED' })).toBeVisible();
  await page.waitForTimeout(300);
  expect(calls()).toBe(1);
  await expect(page.getByRole('region', { name: '추천 결과' })).toHaveCount(0);
});
