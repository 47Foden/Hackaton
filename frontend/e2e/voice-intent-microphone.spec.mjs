import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

test.use({ launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } });

async function open(page) {
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  await page.goto('/');
  await page.getByRole('button', { name: '음성으로 주문하기' }).click();
}

for (const viewport of [{ width: 320, height: 600 }, { width: 390, height: 844 }, { width: 1440, height: 900 }]) {
  test(`voice footer keeps equal controls in two columns at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await open(page);
    const footer = page.locator('.order-footer');
    const left = footer.getByRole('button', { name: '주문하기', exact: true });
    const right = footer.getByRole('button', { name: '메뉴 추천받기', exact: true });
    await expect(footer.getByRole('status')).toHaveCount(0);
    await expect(page.getByText('음성 또는 터치로 주문해 주세요.', { exact: true })).toHaveCount(0);
    await expect(footer.locator('button svg[aria-hidden="true"]')).toHaveCount(2);
    await right.scrollIntoViewIfNeeded();
    const a = await left.boundingBox();
    const b = await right.boundingBox();
    expect(a.x + a.width).toBeLessThan(b.x);
    expect(a.y).toBeCloseTo(b.y);
    expect(a.width).toBeCloseTo(b.width);
    expect(a.height).toBeCloseTo(b.height);
    expect(a.height).toBeGreaterThanOrEqual(68);
    expect(b.x + b.width).toBeLessThanOrEqual(viewport.width);
    expect(await footer.evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true);
    const content = await page.locator('.kiosk-layout__content').boundingBox();
    const footerBox = await footer.boundingBox();
    expect(content.y + content.height).toBeLessThanOrEqual(footerBox.y + 1);
    await left.focus();
    await page.keyboard.press('Tab');
    await expect(right).toBeFocused();
    await expect(right).toHaveCSS('outline-style', 'solid');
  });
}

test('two buttons share one locked recording and preserve the first clicked intent', async ({ page }) => {
  await page.addInitScript(() => {
    window.micCalls = 0;
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async constraints => {
      window.micCalls++;
      await new Promise(resolve => { window.allowMic = resolve; });
      const stream = await original(constraints);
      window.micTracks = stream.getTracks();
      return stream;
    };
  });
  const bodies = [];
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/voice/interpret', async route => {
    bodies.push(route.request().postData());
    await gate;
    await route.fulfill({ json: { transcript: '미인식', action: { type: 'retry', reason: 'UNRECOGNIZED' } } });
  });
  await open(page);
  const buttons = page.getByRole('group', { name: '음성 입력 목적' }).getByRole('button');
  await expect(buttons).toHaveText(['주문하기', '메뉴 추천받기']);
  await expect(buttons.locator('svg')).toHaveCount(2);
  // All clicks happen before React has rendered the disabled state.
  await buttons.evaluateAll(([order, recommend]) => { order.click(); recommend.click(); order.click(); });
  await expect.poll(() => page.evaluate(() => window.micCalls)).toBe(1);
  await expect(buttons.nth(0)).toBeDisabled();
  await expect(buttons.nth(1)).toBeDisabled();
  await expect(page.getByText('브라우저에서 마이크 사용을 허용해 주세요.', { exact: true })).toHaveCount(1);
  await page.evaluate(() => window.allowMic());
  const stop = page.getByRole('button', { name: '녹음 종료', exact: true });
  await expect(stop).toBeEnabled();
  await expect(page.getByRole('button', { name: '메뉴 추천받기', exact: true })).toBeDisabled();
  expect(bodies).toHaveLength(0);
  await stop.evaluate(button => { button.click(); button.click(); });
  await expect.poll(() => bodies.length).toBe(1);
  expect(bodies[0]).toContain('name="intent"\r\n\r\norder');
  await expect(page.getByRole('button', { name: '음성 처리 중…' })).toBeDisabled();
  await expect(buttons.nth(1)).toBeDisabled();
  release();
  await expect(page.getByRole('button', { name: '주문하기', exact: true })).toBeEnabled();
  await expect(page.getByRole('button', { name: '메뉴 추천받기', exact: true })).toBeEnabled();
  expect(await page.evaluate(() => window.micTracks.every(track => track.readyState === 'ended'))).toBe(true);
});

test('permission failure can retry with the other intent, then later stages use one button', async ({ page }) => {
  await page.addInitScript(() => {
    window.micCalls = 0;
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = constraints => {
      if (++window.micCalls === 1) return Promise.reject(new DOMException('denied', 'NotAllowedError'));
      return original(constraints);
    };
  });
  let body;
  await page.route('**/api/voice/interpret', async route => {
    body = route.request().postData();
    await route.fulfill({ json: { transcript: '추천', action: { type: 'direct_recommendation', status: 'recommend',
      recommendations: [{ menu_id: 'cafe_latte', temperature: 'COLD' }] } } });
  });
  await open(page);
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
  await expect(page.getByText('마이크 사용 권한을 허용해 주세요.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '메뉴 추천받기', exact: true }).click();
  await page.getByRole('button', { name: '녹음 종료' }).click();
  await expect(page.getByRole('region', { name: '추천 결과' })).toBeVisible();
  expect(body).toContain('name="intent"\r\n\r\nrecommend');
  expect(await page.evaluate(() => window.micCalls)).toBe(2);
  await page.getByRole('region', { name: '추천 결과' }).getByRole('button', { name: /카페라떼/ }).click();
  await expect(page.getByRole('group', { name: '음성 입력 목적' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '음성 녹음', exact: true })).toBeVisible();
});

test('leaving while permission is pending releases the eventual stream without uploading', async ({ page }) => {
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async constraints => {
      await new Promise(resolve => { window.allowMic = resolve; });
      const stream = await original(constraints);
      window.micTracks = stream.getTracks();
      return stream;
    };
  });
  let requests = 0;
  await page.route('**/api/voice/interpret', async route => { requests++; await route.abort(); });
  await open(page);
  await page.getByRole('button', { name: '메뉴 추천받기', exact: true }).click();
  await expect(page.getByRole('button', { name: '권한 확인 중…' })).toBeDisabled();
  await page.getByRole('button', { name: '처음으로', exact: true }).click();
  await page.evaluate(() => window.allowMic());
  await expect.poll(() => page.evaluate(() => window.micTracks?.every(track => track.readyState === 'ended'))).toBe(true);
  expect(requests).toBe(0);
});
