import { test, expect } from '@playwright/test';
import { createMockApi } from '../src/api/mock/createMockApi.ts';

for (const width of [390, 1024]) {
  test(`two-level menu navigation and selection at ${width}px`, async ({ page }) => {
    const response = await createMockApi({ delayMs: 0 }).getMenus();
    await page.setViewportSize({ width, height: 900 });
    await page.route('**/api/menus', route => route.fulfill({ json: response }));
    await page.goto('/');
    await page.getByRole('button', { name: '주문하기', exact: true }).click();
    const parents = page.getByRole('group', { name: '음료 대분류', exact: true });
    const children = () => page.getByRole('group', { name: /세부 분류/ });
    const seen = new Set();
    for (const [parent, subs] of Object.entries({
      커피: ['에스프레소', '라떼', '콜드브루'],
      디카페인: ['에스프레소', '라떼', '콜드브루'],
      음료: ['에이드', '프라페', '스무디', '주스', '논커피라떼', '티'],
    })) {
      await parents.getByRole('button', { name: parent, exact: true }).click();
      await expect(parents.getByRole('button', { name: parent, exact: true })).toHaveAttribute('aria-pressed', 'true');
      for (const sub of subs) {
        await children().getByRole('button', { name: sub, exact: true }).click();
        const expected = response.menus.filter(m => m.categories[0] === parent &&
          (m.categories[1] === '스무디/주스' ? (m.name.includes('주스') ? '주스' : '스무디') : m.categories[1]) === sub);
        await expect(page.locator('.menu-card')).toHaveCount(expected.length);
        for (const m of expected) {
          seen.add(m.menu_id);
          await expect(page.locator('.menu-card__name').getByText(m.name, { exact: true })).toHaveCount(1);
        }
      }
    }
    expect(seen.size).toBe(response.menus.length);
    await parents.getByRole('button', { name: '음료', exact: true }).click();
    await children().getByRole('button', { name: '주스', exact: true }).click();
    await page.getByRole('button', { name: '크게 보기', exact: true }).click();
    await expect(children().getByRole('button', { name: '주스', exact: true })).toHaveAttribute('aria-pressed', 'true');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/menu-categories-${width}.png`, fullPage: true });
    await page.locator('.menu-card').first().click();
    await expect(page.getByRole('region', { name: '추가 옵션 선택' })).toBeVisible();
  });
}
