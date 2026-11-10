import {test, expect} from '@playwright/test';
import {createMockApi} from '../src/api/mock/createMockApi.ts';
test.use({launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']}});
async function setup(page) {
 const api=createMockApi({delayMs:0});
 await page.route('**/api/menus',async r=>r.fulfill({json:await api.getMenus()}));
 let sent;
 await page.route('**/api/orders',async r=>{
   sent=r.request().postDataJSON();
   await r.fulfill({status:201,json:{...await api.createOrder(sent),order_id:'101',order_number:'101'}});
 });
 await page.goto('/');
 return ()=>sent;
}
test('start layout groups service above order controls at mobile and desktop widths', async({page})=>{
 await setup(page);
 for (const width of [390,1280]) {
   await page.setViewportSize({width,height:1000});
   const service=page.getByRole('group',{name:'매장 또는 포장'});
   const actions=page.locator('.start-screen__actions');
   const guide=page.locator('.start-screen__voice-guide');
   expect((await service.boundingBox()).y).toBeLessThan((await actions.boundingBox()).y);
   expect((await actions.boundingBox()).y).toBeLessThan((await guide.boundingBox()).y);
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 }
});
test('touch orders retain initial takeout across continue ordering and submit every line alike',async({page})=>{
 const sent=await setup(page);
 await page.getByRole('button',{name:'포장',exact:true}).click();
 await page.getByRole('button',{name:'주문하기',exact:true}).click();
 await expect(page.getByText('메뉴와 주문 내용을 확인해 주세요.',{exact:true})).toHaveCount(0);
 async function add() {
   await page.getByText('아메리카노',{exact:true}).click();
   await page.getByRole('button',{name:/차갑게/}).click();
   await expect(page.getByText('화면에서 옵션을 선택하거나 옵션 없이 계속할 수 있어요.',{exact:true})).toHaveCount(0);
   await page.getByRole('button',{name:'옵션 없이 계속'}).click();
   await expect(page.getByRole('button',{name:'주문 확정',exact:true})).toBeVisible();
   await expect(page.getByRole('region',{name:'매장 또는 포장 선택'})).toHaveCount(0);
 }
 await add();
 await page.getByRole('button',{name:'계속 주문하기'}).click();
 await add();
 await page.getByRole('button',{name:'주문 확정',exact:true}).click();
 await expect(page.getByRole('region',{name:'주문 완료'})).toBeVisible();
 expect(sent().items.map(i=>i.service_type)).toEqual(['TAKEOUT','TAKEOUT']);
});
test('multiple voice items ignore conflicting spoken service and use start selection',async({page})=>{
 const sent=await setup(page);
 await page.route('**/api/voice/interpret',r=>r.fulfill({json:{transcript:'아메리카노 두잔 카페라떼 한잔 매장',action:{type:'select_items',items:[
 {menu_id:'iced_americano',quantity:2,temperature:'COLD',option_ids:[],recognized_options:{temperature:'COLD',service_type:'DINE_IN'}},
 {menu_id:'cafe_latte',quantity:1,temperature:'HOT',option_ids:[],recognized_options:{temperature:'HOT',service_type:'DINE_IN'}}
 ]},recognized_options:{service_type:'DINE_IN'}}}));
 await page.getByRole('button',{name:'포장',exact:true}).click();
 await page.getByRole('button',{name:'음성으로 주문하기'}).click();
 await page.getByRole('button',{name:'주문하기',exact:true}).click();
 await page.getByRole('button',{name:'녹음 종료'}).click();
 await page.getByRole('button',{name:'옵션 없이 계속'}).click();
 await page.getByRole('button',{name:'옵션 없이 계속'}).click();
 await page.getByRole('button',{name:'주문 확정',exact:true}).click();
 await expect(page.getByRole('region',{name:'주문 완료'})).toBeVisible();
 expect(sent().items.map(i=>[i.quantity,i.service_type])).toEqual([[2,'TAKEOUT'],[1,'TAKEOUT']]);
});
