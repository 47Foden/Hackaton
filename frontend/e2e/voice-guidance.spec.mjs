import { selectCategory } from './category-navigation.mjs';
import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

test('start announces voice ordering, touch session remains silent without microphone UI', async ({ page }) => {
  await page.addInitScript(() => {
    window.prompts = [];
    window.speechSynthesis.speak = u => window.prompts.push(u.text);
    window.speechSynthesis.cancel = () => {};
  });
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  await page.goto('/');
  await expect.poll(() => page.evaluate(() => window.prompts.length)).toBe(1);
  await expect(page.getByRole('button', { name: '안내 다시 듣기' })).toBeVisible();
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
  await expect(page.getByRole('heading', { name: '전체 메뉴판' })).toBeVisible();
  await expect(page.locator('.order-footer').getByRole('status')).toHaveText('메뉴와 주문 내용을 확인해 주세요.');
  await expect(page.locator('.microphone-control')).toHaveCount(0);
  await selectCategory(page, '커피', '라떼');
  await page.getByRole('button', { name: /카페라떼/ }).click();
  await page.getByRole('button', { name: /따뜻하게/ }).click();
  await page.getByRole('button', { name: '옵션 없이 계속' }).click();
  await page.getByRole('button', { name: /매장에서/ }).click();
  await expect(page.getByRole('button', { name: '주문 확정', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.prompts.length)).toBe(1);
  await expect(page.locator('.microphone-control')).toHaveCount(0);
});

test('voice ordering remains accessible when speech synthesis is unavailable', async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(window, 'speechSynthesis', { value: undefined }));
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  await page.goto('/');
  await page.getByRole('button', { name: '음성으로 주문하기' }).click();
  await expect(page.getByRole('heading', { name: '전체 메뉴판' })).toBeVisible();
  await selectCategory(page, '커피', '라떼');
  await page.getByRole('button', { name: /카페라떼/ }).click();
  await expect(page.getByRole('button', { name: '네, 이 메뉴로 주문' })).toBeVisible();
});
