export async function selectCategory(page, parent, child) {
  await page.getByRole('group', { name: '음료 대분류', exact: true }).getByRole('button', { name: parent, exact: true }).click();
  await page.getByRole('group', { name: /세부 분류/ }).getByRole('button', { name: child, exact: true }).click();
}
