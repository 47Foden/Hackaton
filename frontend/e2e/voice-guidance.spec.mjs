import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

async function showMenu(page) {
  const catalogue = await createMockApi({ delayMs: 0 }).getMenus();
  await page.route('**/api/menus', route => route.fulfill({ json: catalogue }));
  await page.goto('/');
  await page.getByRole('button', { name: '주문하기' }).click();
  await expect(page.getByRole('heading', { name: '간편 메뉴판' })).toBeVisible();
}

test('reads each stage in Korean and cancels the previous prompt when the stage changes', async ({ page }) => {
  await page.addInitScript(() => {
    window.voiceEvents = [];
    Object.defineProperty(window, 'speechSynthesis', {
      value: {
        speak: utterance => window.voiceEvents.push({ text: utterance.text, lang: utterance.lang }),
        cancel: () => window.voiceEvents.push('cancel'),
      },
    });
  });
  await showMenu(page);
  await page.getByRole('button', { name: '전체 메뉴판 보기' }).click();
  await page.getByRole('button', { name: '크게 보기' }).click();
  const events = [{ text: '어떤 음료를 드시겠어요? 메뉴를 눌러 선택해 주세요.', lang: 'ko-KR' }];
  await expect.poll(() => page.evaluate(() => window.voiceEvents)).toEqual(events);

  await page.getByRole('button', { name: /카페라떼/ }).click();
  events.push('cancel', { text: '따뜻하게, 차갑게? 원하는 음료 온도를 선택해 주세요.', lang: 'ko-KR' });
  await expect.poll(() => page.evaluate(() => window.voiceEvents)).toEqual(events);

  await page.getByRole('button', { name: /따뜻하게/ }).click();
  events.push('cancel', { text: '어디에서 드시겠어요? 매장 또는 포장을 선택해 주세요.', lang: 'ko-KR' });
  await expect.poll(() => page.evaluate(() => window.voiceEvents)).toEqual(events);

  await page.getByRole('button', { name: /매장에서/ }).click();
  events.push('cancel', { text: '주문 내용을 확인해 주세요. 메뉴와 옵션을 확인한 후 주문 확정을 눌러 주세요.', lang: 'ko-KR' });
  await expect.poll(() => page.evaluate(() => window.voiceEvents)).toEqual(events);

  await page.getByRole('button', { name: '처음으로', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.voiceEvents)).toEqual([...events, 'cancel']);
});

test('text guidance and touch ordering remain available without browser speech synthesis', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'speechSynthesis', { value: undefined });
  });
  await showMenu(page);
  await page.getByRole('button', { name: /아이스아메리카노/ }).click();
  await expect(page.getByRole('heading', { name: '어디에서 드시겠어요?' })).toBeVisible();
  await page.getByRole('button', { name: /포장해서/ }).click();
  await expect(page.getByRole('button', { name: '주문 확정', exact: true })).toBeEnabled();
});
