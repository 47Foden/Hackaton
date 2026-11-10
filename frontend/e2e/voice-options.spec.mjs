import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

test.use({ launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } });

const customization = { status: 'pending', option_ids: [],
  intents: [{ expression: '샷추가', candidate_option_ids: ['shot:extra'] }], unresolved: [] };
const recommendation = { type: 'direct_recommendation', status: 'recommend', recommendations: [
  { menu_id: 'cafe_latte', temperature: 'COLD' }] };
async function say(page) {
  await page.getByRole('button', { name: '음성 녹음', exact: true }).click();
  await page.getByRole('button', { name: '녹음 종료' }).click();
}
async function setup(page, responses) {
  const api = createMockApi({ delayMs: 0 });
  await page.route('**/api/menus', async route => route.fulfill({ json: await api.getMenus() }));
  const contexts = [];
  await page.route('**/api/voice/interpret', async route => {
    contexts.push(route.request().postData());
    await route.fulfill({ json: { transcript: '음성 테스트', ...responses.shift() } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: '음성으로 주문하기' }).click();
  return contexts;
}

test('recommendation intent survives touch selection and confirmation into final order', async ({ page }) => {
  const contexts = await setup(page, [
    { action: recommendation, recognized_options: { service_type: 'TAKEOUT', customization } },
    { action: { type: 'confirm' } },
  ]);
  let submitted;
  await page.route('**/api/orders', async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ status: 201, json: { ...submitted, order_id: '42', order_number: '42', menu_name: '카페라떼',
      quantity: 1, total_price_krw: 4600, selected_options: [], created_at: new Date().toISOString() } });
  });
  await say(page);
  await page.getByRole('region', { name: '추천 결과' }).getByRole('button', { name: /카페라떼/ }).click();
  await say(page);
  await page.getByRole('button', { name: /따뜻하게/ }).click();
  await expect(page.getByRole('region', { name: '최종 주문 확인' })).toBeVisible();
  await expect(page.getByRole('region', { name: '추가 옵션 선택' })).toHaveCount(0);
  expect(submitted).toBeUndefined();
  expect(contexts[1]).toContain('selected_menu_id');
  await page.getByRole('button', { name: '주문 확정', exact: true }).click();
  await expect.poll(() => submitted?.option_ids).toEqual(['shot:extra']);
  expect(submitted.temperature).toBe('HOT');
  expect(submitted.service_type).toBe('TAKEOUT');
});

test('restart clears prior temperature and customization', async ({ page }) => {
  await setup(page, [{ action: recommendation, recognized_options: { temperature: 'COLD', service_type: 'TAKEOUT', customization } }]);
  await say(page);
  await page.getByRole('button', { name: '다시 추천받기' }).click();
  await page.getByRole('button', { name: '라떼', exact: true }).click();
  await page.getByRole('button', { name: /카페라떼/ }).first().click();
  await page.getByRole('button', { name: '네, 이 메뉴로 주문' }).click();
  await page.getByRole('button', { name: /따뜻하게/ }).click();
  await expect(page.getByRole('region', { name: '추가 옵션 선택' })).toBeVisible();
  await expect(page.getByRole('button', { name: /^샷 추가/ })).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('button', { name: '옵션 없이 계속' }).click();
  await expect(page.getByRole('region', { name: '매장 또는 포장 선택' })).toBeVisible();
});

test('customization voice keeps valid choices while ambiguous request waits for confirmation', async ({ page }) => {
  const contexts = await setup(page, [
    { action: { type: 'select_menu', menu_id: 'cafe_latte' }, recognized_options: { temperature: 'COLD' } },
    { action: { type: 'set_options', option_ids: ['shot:extra'] }, recognized_options: { service_type: 'TAKEOUT',
      customization: { ...customization, status: 'needs_clarification', option_ids: ['shot:extra'], unresolved: ['시럽'] } } },
  ]);
  await say(page);
  await page.getByRole('button', { name: '네, 이 메뉴로 주문' }).click();
  await expect(page.getByRole('region', { name: '추가 옵션 선택' })).toBeVisible();
  await say(page);
  await expect(page.getByRole('button', { name: /^샷 추가/ })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('말씀하신 옵션 중 확인이 필요한 항목이 있어요.', { exact: false })).toBeVisible();
  expect(contexts[1]).toContain('customization');
  expect(contexts[1]).toContain('selected_temperature');
  await page.getByRole('button', { name: '선택한 옵션으로 계속' }).click();
  await expect(page.getByRole('region', { name: '최종 주문 확인' })).toBeVisible();
});

test('late voice response cannot overwrite a touch selection', async ({ page }) => {
  await setup(page, []);
  await page.getByRole('button', { name: '라떼', exact: true }).click();
  let release;
  let started = false;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/voice/interpret', async route => {
    started = true;
    await gate;
    await route.fulfill({ json: { transcript: '이전 응답', action: recommendation,
      recognized_options: { temperature: 'COLD', service_type: 'TAKEOUT', customization } } }).catch(() => {});
  });
  await say(page);
  await expect.poll(() => started).toBe(true);
  await page.getByRole('button', { name: /카페라떼/ }).first().click();
  release();
  await page.getByRole('button', { name: '네, 이 메뉴로 주문' }).click();
  await page.getByRole('button', { name: /따뜻하게/ }).click();
  await expect(page.getByRole('button', { name: /^샷 추가/ })).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('button', { name: '옵션 없이 계속' }).click();
  await expect(page.getByRole('region', { name: '매장 또는 포장 선택' })).toBeVisible();
});

for (const ids of [[], ['shot:extra']]) {
  test(`complete voice options skip all selection screens and their guidance (${ids.length} extras)`, async ({ page }) => {
    await page.addInitScript(() => {
      window.stepHistory = [];
      window.voicePrompts = [];
      window.speechSynthesis.speak = utterance => window.voicePrompts.push(utterance.text);
      window.speechSynthesis.cancel = () => {};
      new MutationObserver(records => {
        for (const record of records) for (const node of record.addedNodes) {
          if (!(node instanceof Element)) continue;
          for (const section of [node, ...node.querySelectorAll('section[aria-label]')]) {
            if (section.matches('section[aria-label]')) window.stepHistory.push(section.getAttribute('aria-label'));
          }
        }
      }).observe(document, { childList: true, subtree: true });
    });
    await setup(page, [{ action: { type: 'select_menu', menu_id: 'cafe_latte' },
      recognized_options: { temperature: 'COLD', service_type: 'TAKEOUT', customization: {
        status: 'resolved', option_ids: ids,
        intents: ids.map(id => ({ expression: id, candidate_option_ids: [id] })), unresolved: [] } } }]);
    let submissions = 0;
    await page.route('**/api/orders', async route => { submissions++; await route.abort(); });
    await say(page);
    await page.getByRole('button', { name: '네, 이 메뉴로 주문' }).click();
    await expect(page.getByRole('region', { name: '최종 주문 확인' })).toBeVisible();
    const history = await page.evaluate(() => ({ steps: window.stepHistory, prompts: window.voicePrompts.join(' ') }));
    for (const label of ['온도 선택', '추가 옵션 선택', '매장 또는 포장 선택']) expect(history.steps).not.toContain(label);
    for (const prompt of ['따뜻하게, 차갑게?', '추가 옵션을 고르시겠어요?', '어디에서 드시겠어요?']) expect(history.prompts).not.toContain(prompt);
    expect(submissions).toBe(0);
    if (ids.length) await expect(page.getByRole('region', { name: '최종 주문 확인' })).toContainText('샷 추가');
  });
}

for (const ids of [['shot:extra'], ['shot:extra', 'sweetness:vanilla']]) {
  test(`voice extras match review, request and receipt prices (${ids.length} groups)`, async ({ page }) => {
    const api = createMockApi({ delayMs: 0 });
    const menu = (await api.getMenus()).menus.find(m => m.menu_id === 'cafe_latte');
    const choices = menu.variants.find(v => v.temperature === 'COLD').option_groups.flatMap(g => g.choices)
      .filter(choice => ids.includes(choice.id));
    const expectedTotal = menu.price_krw + choices.reduce((sum, c) => sum + c.price_delta_krw, 0);
    await setup(page, [{ action: { type: 'select_menu', menu_id: menu.menu_id }, recognized_options: {
      temperature: 'COLD', service_type: 'TAKEOUT', customization: { status: 'resolved', option_ids: ids,
        intents: ids.map(id => ({ expression: id, candidate_option_ids: [id] })), unresolved: [] } } }]);
    let submitted;
    let result;
    await page.route('**/api/orders', async route => {
      submitted = route.request().postDataJSON();
      result = await api.createOrder(submitted);
      // The HTTP adapter requires numeric database identifiers.
      await route.fulfill({ status: 201, json: { ...result, order_id: '123', order_number: '123' } });
    });
    await say(page);
    await page.getByRole('button', { name: '네, 이 메뉴로 주문' }).click();
    const review = page.getByRole('region', { name: '최종 주문 확인' });
    await expect(review).toContainText(`${expectedTotal.toLocaleString('ko-KR')}원`);
    for (const choice of choices) await expect(review).toContainText(choice.label);
    expect(submitted).toBeUndefined();
    await page.getByRole('button', { name: '주문 확정', exact: true }).click();
    const receipt = page.getByRole('region', { name: '주문 완료', exact: true });
    await expect(receipt).toBeVisible();
    expect(submitted.option_ids).toEqual(ids);
    expect(result.total_price_krw).toBe(expectedTotal);
    expect(result.selected_options.map(c => c.id)).toEqual(ids);
    await expect(receipt).toContainText(`${expectedTotal.toLocaleString('ko-KR')}원`);
    for (const choice of choices) await expect(receipt).toContainText(choice.label);
    await page.getByRole('button', { name: '처음으로 돌아가기', exact: true }).click();
    await page.getByRole('button', { name: '음성으로 주문하기' }).click();
    await page.getByRole('button', { name: '라떼', exact: true }).click();
    await page.getByRole('button', { name: /^카페라떼/ }).click();
    await page.getByRole('button', { name: '네, 이 메뉴로 주문' }).click();
    await expect(page.getByRole('region', { name: '온도 선택' })).toBeVisible();
  });
}
