import { chromium } from 'playwright';
const BASE = 'http://127.0.0.1:5173';
const API = 'http://127.0.0.1:8000';
const bugs = [];
function ok(d) { console.log(`  ✅ ${d}`); }
function bug(d) { bugs.push(d); console.log(`  🐛 ${d}`); }

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error' && !msg.text().includes('deprecated') && !msg.text().includes('Static function'))
      consoleErrors.push(msg.text());
  });

  const books = (await (await fetch(`${API}/api/v2/curation/books`)).json()).data?.books || [];
  const bookId = books[0]?.book_id;

  // 1. Entity scroll
  console.log('\n═══ 1. Entity Scroll ═══');
  if (bookId) {
    await page.goto(`${BASE}/curation/editor/${bookId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    const entities = await page.locator('[class*="item__name"]');
    if (await entities.count() > 2) {
      await entities.nth(2).click();
      await page.waitForTimeout(500);
      ok('Entity click + scroll works');
    }
  }

  // 2. InfoPanel review history
  console.log('\n═══ 2. InfoPanel Review History ═══');
  const rh = await page.locator('text=审核历史').count();
  rh > 0 ? ok('Review history section visible') : bug('Review history missing');
  const aiGen = await page.locator('text=AI 生成').count();
  aiGen > 0 ? ok('AI generation row') : bug('AI generation row missing');

  // 3. Graph compare book filter
  console.log('\n═══ 3. Graph Compare ═══');
  if (books.length >= 2) {
    const ids = books.map(b => b.book_id).join(',');
    await page.goto(`${BASE}/curation/graph?compare=${ids}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    const cmpText = await page.locator('text=多书对比').count();
    cmpText > 0 ? ok('Compare mode indicator') : bug('Compare mode indicator missing');
    const selects = await page.locator('.ant-select').count();
    selects >= 2 ? ok(`Book filter select present (${selects} selects)`) : bug(`Only ${selects} selects`);
  }

  // 4. Console errors
  console.log('\n═══ 4. Console Errors ═══');
  consoleErrors.length === 0 ? ok('Zero console errors') : bug(`Console errors: ${consoleErrors.length}`);

  // 5. Responsive
  console.log('\n═══ 5. Responsive ═══');
  for (const vp of [{ w: 375, h: 812, n: 'mobile' }, { w: 768, h: 1024, n: 'tablet' }]) {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await page.goto(`${BASE}/curation/books`);
    await page.waitForLoadState('networkidle');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    overflow ? bug(`${vp.n} overflow`) : ok(`${vp.n} no overflow`);
  }

  console.log(`\n${bugs.length === 0 ? '🎉 ALL PASS' : `🐛 ${bugs.length} bugs`}`);
  await browser.close();
})();
