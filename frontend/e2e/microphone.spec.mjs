import { selectCategory } from './category-navigation.mjs';
import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';
test.use({ launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } });
async function openVoice(page) {
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  await page.goto('/');
  await page.getByRole('button', { name: '음성으로 주문하기' }).click();
}

test('records only in voice mode, stops guidance and submits only after explicit stop', async ({ page }) => {
  let requests = 0;
  await page.route('**/api/voice/interpret', async route => {
    requests++;
    expect(route.request().postDataBuffer().includes('recording.webm')).toBe(true);
    await route.fulfill({ json: { transcript: '알 수 없는 메뉴', action: { type: 'retry' } } });
  });
  await page.addInitScript(() => {
    window.cancels = 0;
    window.speechSynthesis.cancel = () => { window.cancels++; };
    window.speechSynthesis.speak = () => {};
  });
  await openVoice(page);
  const before = await page.evaluate(() => window.cancels);
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
  await expect(page.getByRole('button', { name: '녹음 종료' })).toBeVisible();
  expect(requests).toBe(0);
  expect(await page.evaluate(() => window.cancels)).toBeGreaterThan(before);
  await page.getByRole('button', { name: '녹음 종료' }).click();
  await expect(page.getByText('인식한 말: 알 수 없는 메뉴')).toBeVisible();
  await expect(page.getByRole('button', { name: '주문하기', exact: true })).toBeEnabled();
  expect(requests).toBe(1);
});

test('transcription connectivity error preserves touch ordering', async ({ page }) => {
  await page.route('**/api/voice/interpret', route => route.fulfill({ status: 503,
    json: { detail: { code: 'TRANSCRIPTION_UNAVAILABLE', message: '음성 전사 서버에 연결하지 못했어요.' } } }));
  await openVoice(page);
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
  await page.getByRole('button', { name: '녹음 종료' }).click();
  await expect(page.getByRole('alert')).toContainText('TRANSCRIPTION_UNAVAILABLE');
  await selectCategory(page, '커피', '라떼');
  await page.getByRole('button', { name: /카페라떼/ }).click();
  await expect(page.getByRole('button', { name: '네, 이 메뉴로 주문' })).toBeVisible();
});

test('permission denied leaves touch menu usable', async ({ page }) => {
  await page.addInitScript(() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('denied', 'NotAllowedError'); }; });
  await openVoice(page);
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
  await expect(page.getByRole('button', { name: '주문하기', exact: true })).toBeEnabled();
  await selectCategory(page, '커피', '라떼');
  await page.getByRole('button', { name: /카페라떼/ }).click();
  await expect(page.getByRole('button', { name: '네, 이 메뉴로 주문' })).toBeVisible();
});
