import {test,expect} from '@playwright/test';
import {createMockApi} from '../src/api/mock/createMockApi.ts';
test.use({launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']}});
async function open(page,voice=false){
 const api=createMockApi({delayMs:0});
 await page.route('**/api/menus',async r=>r.fulfill({json:await api.getMenus()}));
 await page.goto('/');
 await page.getByRole('button',{name:voice?'음성으로 주문하기':'주문하기',exact:true}).click();
}
test('touch back restores options and quantities, including continued orders',async({page})=>{
 await open(page);
 const back=page.getByRole('button',{name:'이전',exact:true});
 await expect(back).toBeDisabled();
 await page.getByText('아메리카노',{exact:true}).click();
 await back.click();
 await expect(page.getByRole('heading',{name:'전체 메뉴판'})).toBeVisible();
 await page.getByText('아메리카노',{exact:true}).click();
 await page.getByRole('button',{name:/차갑게/}).click();
 await page.getByRole('button',{name:/^샷 추가/}).click();
 await page.getByRole('button',{name:'선택한 옵션으로 계속'}).click();
 await page.getByRole('button',{name:'아메리카노 수량 늘리기',exact:true}).click();
 await back.click();
 await expect(page.getByRole('button',{name:/^샷 추가/})).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('.order-summary')).toContainText('2잔');
 await page.getByRole('button',{name:'선택한 옵션으로 계속'}).click();
 await page.getByRole('button',{name:'계속 주문하기'}).click();
 await back.click();
 await expect(page.getByRole('region',{name:'최종 주문 확인'})).toBeVisible();
 await expect(page.locator('.order-summary')).toHaveCount(1);
 await expect(page.locator('.order-summary')).toContainText('2잔');
});
test('voice batch back restores prior item without dropping next item or duplicating cart',async({page})=>{
 await page.route('**/api/voice/interpret',r=>r.fulfill({json:{transcript:'아메리카노 두잔 카페라떼 한잔',action:{type:'select_items',items:[
 {menu_id:'iced_americano',temperature:'COLD',quantity:2,option_ids:[]},
 {menu_id:'cafe_latte',temperature:'COLD',quantity:1,option_ids:[]}
 ]}}}));
 await open(page,true);
 await page.getByRole('button',{name:'주문하기',exact:true}).click();
 await page.getByRole('button',{name:'녹음 종료'}).click();
 await page.getByRole('button',{name:'옵션 없이 계속'}).click();
 await expect(page.getByRole('heading',{name:'카페라떼',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'이전',exact:true}).click();
 await expect(page.getByRole('heading',{name:'아메리카노',exact:true})).toBeVisible();
 await expect(page.locator('.order-summary')).toContainText('2잔');
 await page.getByRole('button',{name:'옵션 없이 계속'}).click();
 await expect(page.getByRole('heading',{name:'카페라떼',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'옵션 없이 계속'}).click();
 await expect(page.getByRole('region',{name:'최종 주문 확인'})).toBeVisible();
 await expect(page.locator('.order-summary')).toHaveCount(2);
});
test('back is locked after an uncertain order submission',async({page})=>{
 await page.route('**/api/orders',r=>r.fulfill({status:503,json:{detail:{code:'ORDER_STORAGE_UNAVAILABLE',message:'접수 여부를 확인해 주세요.'}}}));
 await open(page);
 await page.getByText('아메리카노',{exact:true}).click();
 await page.getByRole('button',{name:/차갑게/}).click();
 await page.getByRole('button',{name:'옵션 없이 계속'}).click();
 await page.getByRole('button',{name:'주문 확정',exact:true}).click();
 await expect(page.getByRole('alert')).toBeVisible();
 await expect(page.getByRole('button',{name:'이전',exact:true})).toBeDisabled();
 await expect(page.getByRole('button',{name:'같은 주문 다시 시도'})).toBeEnabled();
});
