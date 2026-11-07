import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

async function catalogue() {
  return createMockApi({ delayMs: 0 }).getMenus();
}

async function start(page) {
  await page.goto('/');
  await page.getByRole('button', { name: '주문하기' }).click();
}

test('loading remains visible until HTTP menus arrive', async ({ page }) => {
  const response = await catalogue();
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/menus', async route => {
    await gate;
    await route.fulfill({ json: response });
  });
  await start(page);
  await expect(page.getByRole('heading', { name: '메뉴를 불러오는 중이에요…' })).toBeVisible();
  await expect(page.locator('.menu-card')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '처음으로', exact: true })).toBeEnabled();
  release();
  await expect(page.locator('.menu-card')).toHaveCount(4);
  await expect(page.getByRole('heading', { name: '메뉴를 불러오는 중이에요…' })).toHaveCount(0);
});

test('503 displays a retry action and a successful retry restores the menu', async ({ page }) => {
  const response = await catalogue();
  let calls = 0;
  await page.route('**/api/menus', route => ++calls === 1
    ? route.fulfill({ status: 503, json: { detail: { code: 'CATALOG_UNAVAILABLE', message: '잠시 후 다시 시도해 주세요.' } } })
    : route.fulfill({ json: response }));
  await page.setViewportSize({ width: 390, height: 844 });
  await start(page);
  await expect(page.getByRole('alert')).toContainText('메뉴를 불러오지 못했어요.');
  await expect(page.locator('.menu-card')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '다시 불러오기' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: '다시 불러오기' }).click();
  await expect(page.locator('.menu-card')).toHaveCount(4);
  expect(calls).toBe(2);
});

test('empty success is separate from failure and can reload', async ({ page }) => {
  const response = await catalogue();
  let calls = 0;
  await page.route('**/api/menus', route => route.fulfill({ json: ++calls === 1 ? { menus: [] } : response }));
  await start(page);
  await expect(page.getByRole('heading', { name: '표시할 메뉴가 없어요.' })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.locator('.menu-card')).toHaveCount(0);
  await page.getByRole('button', { name: '다시 불러오기' }).click();
  await expect(page.locator('.menu-card')).toHaveCount(4);
});

test('404 images preserve card selection, prices, options and the order summary', async ({ page }) => {
  const response = await catalogue();
  const menu = response.menus.find(item => item.menu_id === 'iced_americano');
  menu.image_url = '/images/menus/not-found.jpg';
  menu.variants[0].image_url = menu.image_url;
  await page.route('**/api/menus', route => route.fulfill({ json: response }));
  await page.route('**/images/menus/not-found.jpg', route => route.fulfill({ status: 404, body: '' }));
  await start(page);
  const card = page.getByRole('button', { name: /아이스아메리카노/ });
  await expect(card).toContainText('사진 준비 중');
  await expect(card).toContainText('2,000원');
  await expect(card).toBeEnabled();
  await card.click();
  await expect(page.getByRole('heading', { name: '어디에서 드시겠어요?' })).toBeVisible();
  await expect(page.locator('.order-summary')).toContainText('사진 준비 중');
  await expect(page.locator('.order-summary')).toContainText('아이스아메리카노');
  await page.getByRole('button', { name: /매장에서/ }).click();
  await expect(page.getByRole('button', { name: '주문 확정 (개발용)' })).toBeEnabled();
});

test('an empty image path has a placeholder and can still be ordered', async ({ page }) => {
  const response = await catalogue();
  const menu = response.menus.find(item => item.menu_id === 'iced_americano');
  menu.image_url = '';
  menu.variants[0].image_url = '';
  await page.route('**/api/menus', route => route.fulfill({ json: response }));
  await start(page);
  const card = page.getByRole('button', { name: /아이스아메리카노/ });
  await expect(card).toContainText('사진 준비 중');
  await expect(card.locator('img')).toHaveCount(0);
  await card.click();
  await expect(page.getByRole('heading', { name: '어디에서 드시겠어요?' })).toBeVisible();
});
