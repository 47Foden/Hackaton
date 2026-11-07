import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

test('final confirmation sends the selected options to POST /api/orders', async ({ page }) => {
  const catalogue = await createMockApi({ delayMs: 0 }).getMenus();
  const draft = { menu_id: 'iced_americano', temperature: 'COLD', service_type: 'TAKEOUT' };
  const requests = [];
  await page.route('**/api/menus', route => route.fulfill({ json: catalogue }));
  await page.route('**/api/orders', route => {
    const request = route.request();
    requests.push({ method: request.method(), body: request.postDataJSON() });
    return route.fulfill({ status: 201, json: {
      ...draft,
      order_id: '42',
      order_number: '42',
      menu_name: '아이스아메리카노',
      quantity: 1,
      total_price_krw: 2300,
      created_at: '2026-11-07T00:00:00Z',
    } });
  });

  await page.goto('/');
  await page.getByRole('button', { name: '주문하기' }).click();
  await page.getByRole('button', { name: /아이스아메리카노/ }).click();
  await page.getByRole('button', { name: /포장해서/ }).click();
  const confirm = page.getByRole('button', { name: '주문 확정', exact: true });
  await expect(confirm).toBeEnabled();
  expect(requests).toHaveLength(0);

  await confirm.click();
  const completion = page.getByRole('region', { name: '주문 완료' });
  await expect(completion).toBeVisible();
  await expect(completion.getByText('42', { exact: true })).toBeVisible();
  await expect(completion).toContainText('2,300원');
  expect(requests).toEqual([{ method: 'POST', body: draft }]);
});
