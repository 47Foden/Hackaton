import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

test.use({ launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } });

async function showMenu(page, path = '/', updateCatalogue) {
  const catalogue = await createMockApi({ delayMs: 0 }).getMenus();
  updateCatalogue?.(catalogue);
  await page.route('**/api/menus', route => route.fulfill({ json: catalogue }));
  await page.goto(path);
  await page.getByRole('button', { name: '주문하기', exact: true }).click();
  await expect(page.getByRole('heading', { name: '간편 메뉴판' })).toBeVisible();
}

test('cancels the guide, records WebM/Opus and uploads only when stopped explicitly', async ({ page }) => {
  const uploads = [];
  await page.route('**/api/voice/audio', route => {
    const request = route.request();
    uploads.push(request.postDataBuffer());
    return route.fulfill({ json: { duration_seconds: 1 } });
  });
  await page.addInitScript(() => {
    window.microphoneEvents = [];
    window.recordedBytes = 0;
    window.speechSynthesis.speak = () => window.microphoneEvents.push('speak');
    window.speechSynthesis.cancel = () => window.microphoneEvents.push('cancel');
    const getUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async constraints => {
      window.microphoneEvents.push(constraints);
      await new Promise(resolve => { window.allowMicrophone = resolve; });
      window.microphoneStream = await getUserMedia(constraints);
      return window.microphoneStream;
    };
    window.MediaRecorder = class extends window.MediaRecorder {
      start(timeslice) {
        this.addEventListener('dataavailable', event => { window.recordedBytes += event.data.size; });
        super.start(timeslice);
        window.microphoneEvents.push('recording');
      }
    };
  });
  await showMenu(page);
  await expect.poll(() => page.evaluate(() => window.microphoneEvents)).toEqual(['speak']);

  await page.getByRole('button', { name: '음성 녹음' }).click();
  await expect(page.getByRole('button', { name: '권한 확인 중…' })).toBeDisabled();
  expect(await page.evaluate(() => window.microphoneEvents)).toEqual(['speak', 'cancel', { audio: true }]);
  await page.evaluate(() => window.allowMicrophone());
  await expect(page.getByText('녹음 중이에요.')).toBeVisible();
  expect(await page.evaluate(() => window.microphoneEvents)).toEqual(['speak', 'cancel', { audio: true }, 'recording']);
  await expect.poll(() => page.evaluate(() => window.recordedBytes)).toBeGreaterThan(0);

  await page.getByRole('button', { name: '녹음 종료' }).click();
  await expect(page.getByText('녹음 파일을 확인했어요.')).toBeVisible();
  expect(uploads).toHaveLength(1);
  expect(uploads[0].includes('filename="recording.webm"')).toBe(true);
  expect(uploads[0].includes('Content-Type: audio/webm;codecs=opus')).toBe(true);
  expect(uploads[0].includes(Buffer.from([0x1a, 0x45, 0xdf, 0xa3]))).toBe(true);
  await expect(page.getByRole('button', { name: '음성 녹음' })).toBeEnabled();
  await expect.poll(() => page.evaluate(() => window.microphoneStream.getAudioTracks().map(track => track.readyState)))
    .toEqual(['ended']);

  await page.getByRole('button', { name: '음성 녹음' }).click();
  await expect(page.getByRole('button', { name: '권한 확인 중…' })).toBeDisabled();
  await page.evaluate(() => window.allowMicrophone());
  await expect(page.getByRole('button', { name: '녹음 종료' })).toBeEnabled();
  await page.getByRole('button', { name: /아이스아메리카노/ }).click();
  await expect(page.getByRole('heading', { name: '어디에서 드시겠어요?' })).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.microphoneStream.getAudioTracks().map(track => track.readyState)))
    .toEqual(['ended']);
  expect(uploads).toHaveLength(1);
});

async function useMockRecording(page) {
  await page.getByRole('button', { name: '음성 녹음' }).click();
  await page.getByRole('button', { name: '녹음 종료' }).click();
}

test('mock voice selections reach review without submitting an order', async ({ page }) => {
  let submissions = 0;
  await page.route('**/api/orders', route => {
    submissions += 1;
    return route.abort();
  });
  await showMenu(page, '/?voice=mock');
  await expect(page.getByText(/개발용 음성 모드예요/)).toBeVisible();

  await useMockRecording(page);
  await expect(page.getByRole('region', { name: '온도 선택' }).getByRole('heading', { name: '카페라떼' })).toBeVisible();
  await useMockRecording(page);
  await expect(page.getByRole('region', { name: '매장 또는 포장 선택' })).toBeVisible();
  await useMockRecording(page);

  const review = page.getByRole('region', { name: '최종 주문 확인' });
  await expect(review.getByRole('heading', { name: '카페라떼' })).toBeVisible();
  await expect(review.getByText('따뜻하게 · 포장해서')).toBeVisible();
  await expect(review.getByRole('button', { name: '주문 확정', exact: true })).toBeEnabled();
  expect(submissions).toBe(0);
});

test('mock selection respects menu availability and touch choices still work', async ({ page }) => {
  await showMenu(page, '/?voice=mock', catalogue => {
    catalogue.menus.find(menu => menu.menu_id === 'cafe_latte').is_available = false;
  });
  await useMockRecording(page);
  await expect(page.getByRole('heading', { name: '간편 메뉴판' })).toBeVisible();
  await expect(page.getByRole('button', { name: /카페라떼/ })).toBeDisabled();
  await page.getByRole('button', { name: /아이스아메리카노/ }).click();
  await page.getByRole('button', { name: /매장에서/ }).click();
  const review = page.getByRole('region', { name: '최종 주문 확인' });
  await expect(review.getByRole('heading', { name: '아이스아메리카노' })).toBeVisible();
  await expect(review.getByText('차갑게 · 매장에서')).toBeVisible();
});

test('releases a permission result that arrives after leaving the order screen', async ({ page }) => {
  await page.addInitScript(() => {
    window.trackStops = 0;
    window.recorderStarts = 0;
    navigator.mediaDevices.getUserMedia = () => new Promise(resolve => {
      window.allowMicrophone = () => resolve({ getTracks: () => [{ stop: () => { window.trackStops += 1; } }] });
    });
    window.MediaRecorder = class {
      start() { window.recorderStarts += 1; }
    };
  });
  await showMenu(page);
  await page.getByRole('button', { name: '음성 녹음' }).click();
  await expect(page.getByRole('button', { name: '권한 확인 중…' })).toBeDisabled();
  await page.getByRole('button', { name: '처음으로', exact: true }).click();
  await expect(page.getByRole('button', { name: '주문하기', exact: true })).toBeVisible();
  await page.evaluate(() => window.allowMicrophone());
  await expect.poll(() => page.evaluate(() => window.trackStops)).toBe(1);
  expect(await page.evaluate(() => window.recorderStarts)).toBe(0);
});

test('a denied microphone permission preserves touch ordering', async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      throw new DOMException('Permission denied', 'NotAllowedError');
    };
  });
  await showMenu(page);
  await page.getByRole('button', { name: '음성 녹음' }).click();
  await expect(page.getByText('마이크 사용 권한을 허용해 주세요.')).toBeVisible();
  await page.getByRole('button', { name: /아이스아메리카노/ }).click();
  await page.getByRole('button', { name: /포장해서/ }).click();
  await expect(page.getByRole('button', { name: '주문 확정', exact: true })).toBeEnabled();
});

test('the recording deadline releases the mic and asks for a shorter recording', async ({ page }) => {
  const uploads = [];
  await page.route('**/api/voice/audio', route => {
    uploads.push(route.request());
    return route.abort();
  });
  await page.addInitScript(() => {
    const setTimeout = window.setTimeout.bind(window);
    window.setTimeout = (callback, delay, ...args) => setTimeout(callback, delay === 30_000 ? 150 : delay, ...args);
    const getUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async constraints => {
      window.microphoneStream = await getUserMedia(constraints);
      return window.microphoneStream;
    };
  });
  await showMenu(page);
  await page.getByRole('button', { name: '음성 녹음' }).click();
  await expect(page.getByText('녹음이 30초를 넘었어요. 30초 이내로 다시 녹음해 주세요.')).toBeVisible();
  await expect(page.getByRole('button', { name: '다시 녹음' })).toBeEnabled();
  await expect.poll(() => page.evaluate(() => window.microphoneStream.getAudioTracks().map(track => track.readyState)))
    .toEqual(['ended']);
  expect(uploads).toHaveLength(0);
});
