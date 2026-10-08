import {test,expect} from '@playwright/test';

test('portal reverses, travels, grows and tightens; controls remain accessible',async({page})=>{
 await page.goto('/');await page.locator('.portal.motion').waitFor();
 const read=()=>page.locator('.panel.left').evaluate(el=>({x:el.getBoundingClientRect().x,transform:getComputedStyle(document.querySelector('.wordmark')!).transform,tracking:parseFloat(getComputedStyle(document.querySelector('.wordmark')!).letterSpacing)}));
 const before=await read();await page.evaluate(()=>scrollTo(0,700));await expect.poll(async()=>(await read()).x).toBeLessThan(before.x-100);
 const after=await read();expect(after.tracking).toBeLessThan(before.tracking);expect(after.transform).not.toBe(before.transform);
 await page.evaluate(()=>scrollTo(0,0));await expect.poll(async()=>(await read()).x).toBeCloseTo(before.x,0);
 await page.locator('.topnav').getByRole('link',{name:'Open workspace'}).click();await expect(page.locator('.work-main')).toBeVisible();
});
test('deck keyboard, pointer throw and cancel do not navigate or delete',async({page})=>{
 await page.route('**/api/summary',r=>r.fulfill({json:{investigations:[]}}));
 await page.goto('/');const deck=page.locator('.deck');await deck.scrollIntoViewIfNeeded();await deck.focus();
 const indicator=page.locator('.deck-controls span');const initial=await indicator.textContent();await page.keyboard.press('ArrowRight');await expect(indicator).not.toHaveText(initial!);
 const b=await deck.boundingBox();if(!b)throw Error('Deck missing');
 const second=await indicator.textContent();await page.mouse.move(b.x+b.width*.4,b.y+b.height*.6);await page.mouse.down();await page.mouse.move(b.x+b.width*.75,b.y+b.height*.6,{steps:8});await page.mouse.up();await expect(indicator).not.toHaveText(second!);
 await page.locator('.sleeve.front').qualityEvent('pointercancel');await expect(page).toHaveURL(/\/$/);
});
test('reduced motion open readable hero',async({page})=>{
 await page.route('**/api/summary',r=>r.fulfill({json:{investigations:[]}}));
 await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');await expect(page.locator('.panel.left')).toBeHidden();await expect(page.locator('.wordmark')).toBeVisible();
 await page.locator('.deck').scrollIntoViewIfNeeded();await page.getByRole('button',{name:'Next →'}).click();await expect(page.locator('.deck-controls span')).toHaveText(/2 \/ /);
});
test('mobile no page overflow and vertical scrolling',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.locator('.deck').scrollIntoViewIfNeeded();expect(await page.locator('.deck').evaluate(e=>getComputedStyle(e).touchAction)).toBe('pan-y');
 await page.mouse.wheel(0,400);await expect(page.locator('.topnav .button')).toBeVisible();
});
test('no JavaScript has readable content and truthful workspace explanation',async({browser})=>{
 const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();await page.goto('http://localhost:8080');await expect(page.getByRole('heading',{name:'ROOTLENS',exact:true})).toBeVisible();await expect(page.getByText('The operational workspace requires JavaScript.',{exact:false})).toBeVisible();await context.close();
});
test('API failure visible, import failure visible',async({page})=>{
 await page.route('**/api/summary',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Test database unavailable'})}));
 await page.goto('/#workspace');await expect(page.getByRole('alert')).toContainText('Test database unavailable');
 await page.goto('/#workspace/setup');await page.locator('input[type=file]').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from('{broken')});await expect(page.getByRole('status')).toContainText('Import failed');
});
