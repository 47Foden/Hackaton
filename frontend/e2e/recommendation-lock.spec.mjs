import {test, expect} from '@playwright/test';
import {createMockApi} from '../src/api/mock/createMockApi.ts';
test.use({launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']}});
for (const status of ['recommend','insufficient_data']) {
 test('recommendation control locks until restart: '+status,async({page})=>{
  const api=createMockApi({delayMs:0});
  let calls=0;
  await page.route('**/api/menus',async r=>r.fulfill({json:await api.getMenus()}));
  await page.route('**/api/voice/interpret',async r=>{
   calls++;
   await r.fulfill({json:{transcript:'딸기 추천',action:{type:'direct_recommendation',status,
    recommendations:status==='recommend'?[{menu_id:'strawberry_latte',temperature:'COLD'}]:[]}}});
  });
  await page.goto('/');
  await page.getByRole('button',{name:'음성으로 주문하기'}).click();
  const recommend=page.getByRole('button',{name:'메뉴 추천받기',exact:true});
  await expect(recommend).toBeEnabled();
  await recommend.click();
  await page.getByRole('button',{name:'녹음 종료',exact:true}).click();
  await expect(page.getByRole('region',{name:'추천 결과'})).toBeVisible();
  await expect(recommend).toBeDisabled();
  await expect(page.getByRole('button',{name:'주문하기',exact:true})).toBeEnabled();
  expect(calls).toBe(1);
  await page.getByRole('button',{name:'다시 추천받기',exact:true}).click();
  await expect(recommend).toBeEnabled();
  await expect(page.getByRole('region',{name:'추천 결과'})).toHaveCount(0);
 });
}
