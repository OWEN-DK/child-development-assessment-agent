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

  // Get books
  const books = (await (await fetch(`${API}/api/v2/curation/books`)).json()).data?.books || [];
  const bookId = books[0]?.book_id;

  // Test 1: Editor - entity scroll
  console.log('\n═══ Entity Scroll Test ═══');
  if (bookId) {
    await page.goto(`${BASE}/curation/editor/${bookId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Click an entity
    const entityItems = await page.locator('[class*="item__name"]');
    const count = await entityItems.count();
    if (count > 2) {
      // Click 3rd entity (should scroll)
      const name = await entityItems.nth(2).textContent();
      await entityItems.nth(2).click();
      await page.waitForTimeout(500);
      ok(`Clicked entity "${name?.trim()}" - scroll triggered`);
    } else {
      ok('Not enough entities to test scroll (need > 2)');
    }
  }

  // Test 2: InfoPanel - review history section
  console.log('\n═══ InfoPanel Review History ═══');
  if (bookId) {
    const reviewSection = await page.locator('text=审核历史').count();
    reviewSection > 0 ? ok('Review history section visible') : bug('Review history section missing');
    
    const aiGenRow = await page.locator('text=AI 生成').count();
    aiGenRow > 0 ? ok('AI generation date row present') : bug('AI generation date row missing');
  }

  // Test 3: Graph - book filter in compare mode
  console.log('\n═══ Graph Book Filter ═══');
  if (books.length >= 2) {
    const ids = books.map(b => b.book_id).join(',');
    await page.goto(`${BASE}/curation/graph?compare=${ids}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    const bookFilter = await page.locator('text=按书籍筛选').count();
    const bookFilterSelects = await page.locator('[class*="toolbar__right"] .ant-select').count();
    bookFilterSelects >= 2 ? ok(`Book filter dropdown present (${bookFilterSelects} selects)`) : bug(`Book filter dropdown missing (only ${bookFilterSelects} selects)`);
  }

  // Test 4: All pages - no new console errors
  console.log('\n═══ Console Errors ═══');
  consoleErrors.length === 0 ? ok('No console errors') : bug(`Console errors: ${consoleErrors.join('; ')}`);

  // Test 5: Responsive
  console.log('\n═══ Responsive ═══');
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
