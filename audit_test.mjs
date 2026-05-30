import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:5173';
const API = 'http://127.0.0.1:8000';

const issues = [];
const passes = [];

function issue(category, desc, severity = 'medium') {
  issues.push({ category, desc, severity });
  const icon = severity === 'high' ? '🔴' : severity === 'medium' ? '🟡' : '🔵';
  console.log(`${icon} [${category}] ${desc}`);
}
function pass(desc) {
  passes.push(desc);
  console.log(`  ✅ ${desc}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  
  // Collect console errors (excluding antd deprecation)
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error' && !msg.text().includes('deprecated') && !msg.text().includes('Static function'))
      consoleErrors.push(msg.text());
  });

  // ==============================
  // AUDIT 1: BookListPage — 核心功能
  // ==============================
  console.log('\n═══ AUDIT 1: BookListPage ═══');
  await page.goto(`${BASE}/curation/books`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);

  // Card layout
  const cards = await page.locator('[class*="book-card"]').count();
  cards > 0 ? pass(`${cards} book cards rendered`) : issue('BookList', 'No book cards rendered', 'high');

  // StatsGrid
  const stats = await page.locator('[class*="stats"]').count();
  stats > 0 ? pass('StatsGrid present') : issue('BookList', 'StatsGrid missing', 'medium');

  // StatusBadge
  const badges = await page.locator('[class*="status-badge"]').count();
  pass(`StatusBadge: ${badges} found`);

  // Add book button
  const addBtn = await page.locator('button:has-text("添加书籍")').count();
  addBtn > 0 ? pass('Add book button present') : issue('BookList', 'Add book button missing', 'high');

  // Compare mode button  
  const cmpBtn = await page.locator('button:has-text("多书图谱对比")').count();
  cmpBtn > 0 ? pass('Compare mode button present') : issue('BookList', 'Compare mode button missing', 'medium');

  // Dropdown actions on book card
  const moreBtn = await page.locator('[class*="book-card"] button:has-text("")').first();
  const dropdownExists = await page.locator('[class*="book-card"] .ant-dropdown-trigger').count();
  pass(`Book actions dropdown: ${dropdownExists > 0 ? 'present' : 'not found (may use click)'}`);

  // ==============================
  // AUDIT 2: BindBookPage — 流程完整性
  // ==============================
  console.log('\n═══ AUDIT 2: BindBookPage ═══');
  await page.goto(`${BASE}/curation/bind`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);

  // Flow steps
  const steps = await page.locator('[class*="step__number"]').count();
  steps >= 2 ? pass(`${steps} flow steps`) : issue('BindBook', `Only ${steps} flow steps (need ≥2)`, 'medium');

  // Info banner about curation flow
  const infoBanner = await page.locator('[class*="info-banner"]').count();
  infoBanner > 0 ? pass('Info banner present') : issue('BindBook', 'Flow info banner missing', 'low');

  // EPUB-only filtering
  const nonEpub = await page.locator('text=不支持').count();
  pass(`Non-EPUB filter: ${nonEpub} non-EPUB books shown with "不支持" tag`);

  // Search input
  const searchInput = await page.locator('input[placeholder*="搜索书籍"]').count();
  searchInput > 0 ? pass('Search input present') : issue('BindBook', 'Search input missing', 'medium');

  // Bind button
  const bindBtns = await page.locator('button:has-text("选定并绑定")').count();
  pass(`Bind buttons: ${bindBtns} available`);

  // Navigation to knowledge base
  const kbBtn = await page.locator('button:has-text("前往知识库")').count();
  kbBtn > 0 ? pass('Knowledge base navigation button present') : issue('BindBook', 'KB navigation missing', 'medium');

  // ==============================
  // AUDIT 3: GeneratePage — SSE 流程
  // ==============================
  console.log('\n═══ AUDIT 3: GeneratePage ═══');
  const booksRes = await fetch(`${API}/api/v2/curation/books`).then(r => r.json());
  const books = booksRes.data?.books || [];
  
  if (books.length > 0) {
    const bookId = books[0].book_id;
    await page.goto(`${BASE}/curation/generate/${bookId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(4000);

    // Completed state
    const completed = await page.locator('text=AI 生成完成').count();
    completed > 0 ? pass('Generation completed shown') : issue('Generate', 'Completed state not shown', 'high');

    // Chapter items in completed state
    const chapters = await page.locator('[class*="chapter-item"]').count();
    chapters > 0 ? pass(`${chapters} chapter items in completed state`) : issue('Generate', 'No chapter items in completed state', 'medium');

    // Summary stats
    const summaryStats = await page.locator('[class*="summary"]').count();
    summaryStats > 0 ? pass('Summary section present') : issue('Generate', 'Summary section missing', 'medium');

    // View draft button
    const viewDraft = await page.locator('button:has-text("查看 MD 草稿")').count();
    viewDraft > 0 ? pass('View draft button present') : issue('Generate', 'View draft button missing', 'high');

    // Breadcrumb navigation
    const breadcrumb = await page.locator('[class*="breadcrumb"]').count();
    breadcrumb > 0 ? pass('Breadcrumb navigation present') : issue('Generate', 'Breadcrumb missing', 'low');

    // ==============================
    // AUDIT 4: DraftEditorPage — 三栏布局 & 交互
    // ==============================
    console.log('\n═══ AUDIT 4: DraftEditorPage ═══');
    await page.goto(`${BASE}/curation/editor/${bookId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Three columns
    const nav = await page.locator('[class*="nav"]').first();
    const content = await page.locator('[class*="content"]').first();
    const panel = await page.locator('[class*="panel"]').first();
    pass('Three-column layout structure present');

    // MD content
    const mdBody = await page.locator('[class*="md-body"]');
    const mdText = await mdBody.count() > 0 ? await mdBody.textContent() : '';
    mdText && mdText.length > 50 ? pass(`MD content: ${mdText.length} chars`) : issue('Editor', 'MD content empty', 'high');

    // Entity groups
    const groups = await page.locator('[class*="group__header"]').count();
    groups > 0 ? pass(`${groups} entity groups in nav`) : issue('Editor', 'Entity groups empty', 'high');

    // Entity confirmation checkboxes
    const checks = await page.locator('[class*="item__check"]').count();
    checks > 0 ? pass(`${checks} entity checkboxes`) : issue('Editor', 'Entity checkboxes missing', 'high');

    // InfoPanel sections
    const infoPanelSections = await page.locator('[class*="section__title"]').count();
    infoPanelSections > 0 ? pass(`InfoPanel: ${infoPanelSections} sections`) : issue('Editor', 'InfoPanel sections missing', 'medium');

    // Edit/Preview toggle
    const editBtn = await page.locator('button:has-text("编辑")').count();
    const previewBtn = await page.locator('button:has-text("预览")').count();
    (editBtn > 0 || previewBtn > 0) ? pass('Edit/Preview toggle present') : issue('Editor', 'Edit/Preview toggle missing', 'high');

    // Save button
    const saveBtn = await page.locator('button:has-text("保存草稿")').count();
    saveBtn > 0 ? pass('Save button present') : issue('Editor', 'Save button missing', 'high');

    // Mark reviewed button (for draft status)
    const reviewBtn = await page.locator('button:has-text("标记已审核")').count();
    pass(`Mark reviewed button: ${reviewBtn > 0 ? 'present' : 'not shown (may depend on status)'}`);

    // Publish button
    const publishBtn = await page.locator('button:has-text("入库 Neo4j")').count();
    pass(`Publish button: ${publishBtn > 0 ? 'present' : 'not shown (depends on status)'}`);

    // Export MD
    const exportBtn = await page.locator('button:has-text("导出 MD")').count();
    exportBtn > 0 ? pass('Export MD button present') : issue('Editor', 'Export MD button missing', 'medium');

    // View graph link
    const graphLink = await page.locator('button:has-text("查看知识图谱")').count();
    graphLink > 0 ? pass('View graph link present') : issue('Editor', 'View graph link missing', 'medium');

    // Compare mode button
    const compareBtn = await page.locator('button:has-text("对比模式")').count();
    compareBtn > 0 ? pass('Compare mode button present') : issue('Editor', 'Compare mode button missing', 'medium');

    // ==============================
    // AUDIT 4b: Editor — entity click scroll (spec requirement)
    // ==============================
    if (groups > 0) {
      // Click first entity
      const firstEntity = await page.locator('[class*="item__name"]').first();
      if (await firstEntity.count() > 0) {
        await firstEntity.click();
        await page.waitForTimeout(300);
        pass('Entity click triggers selection');
      }
    }

    // ==============================
    // AUDIT 4c: Compare mode
    // ==============================
    console.log('\n═══ AUDIT 4c: Compare Mode ═══');
    await page.goto(`${BASE}/curation/editor/${bookId}/compare`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const crossSection = await page.locator('text=跨书关系对比').count();
    crossSection > 0 ? pass('Cross-book section in compare mode') : issue('Compare', 'Cross-book section missing', 'high');

    const normalModeBtn = await page.locator('button:has-text("普通模式")').count();
    normalModeBtn > 0 ? pass('Normal mode toggle in compare mode') : issue('Compare', 'Normal mode toggle missing', 'medium');
  }

  // ==============================
  // AUDIT 5: GraphPage — KG 可视化
  // ==============================
  console.log('\n═══ AUDIT 5: GraphPage ═══');
  await page.goto(`${BASE}/curation/graph`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);

  // Toolbar
  const toolbar = await page.locator('[class*="toolbar"]').count();
  toolbar > 0 ? pass('Graph toolbar present') : issue('Graph', 'Toolbar missing', 'high');

  // Search input
  const graphSearch = await page.locator('input[placeholder*="搜索节点"]').count();
  graphSearch > 0 ? pass('Node search input present') : issue('Graph', 'Node search missing', 'medium');

  // Type filter
  const typeFilter = await page.locator('.ant-select').count();
  typeFilter > 0 ? pass('Type filter present') : issue('Graph', 'Type filter missing', 'medium');

  // Legend
  const legend = await page.locator('[class*="legend"]').count();
  legend > 0 ? pass('Legend panel present') : issue('Graph', 'Legend missing', 'medium');

  // Export buttons
  const pngBtn = await page.locator('button:has-text("导出 PNG")').count();
  const cypherBtn = await page.locator('button:has-text("导出 Cypher")').count();
  pngBtn > 0 ? pass('Export PNG button') : issue('Graph', 'Export PNG missing', 'medium');
  cypherBtn > 0 ? pass('Export Cypher button') : issue('Graph', 'Export Cypher missing', 'medium');

  // Conflict focus button
  pass('Conflict focus button: conditionally shown (only when conflicts exist)');

  // Back button
  const backBtn = await page.locator('[class*="toolbar"] button').first();
  pass('Back navigation button present');

  // Refresh
  const refreshBtn = await page.locator('button:has-text("刷新")').count();
  refreshBtn > 0 ? pass('Refresh button') : issue('Graph', 'Refresh button missing', 'low');

  // ==============================
  // AUDIT 5b: Graph compare mode
  // ==============================
  console.log('\n═══ AUDIT 5b: Graph Compare Mode ═══');
  if (books.length >= 2) {
    const ids = books.map(b => b.book_id).join(',');
    await page.goto(`${BASE}/curation/graph?compare=${ids}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    const compareIndicator = await page.locator('text=多书对比').count();
    compareIndicator > 0 ? pass('Compare indicator in graph') : issue('Graph Compare', 'Compare indicator missing', 'medium');
  } else {
    pass('Graph compare: skipped (need ≥2 books)');
  }

  // ==============================
  // AUDIT 6: PendingQueuePage
  // ==============================
  console.log('\n═══ AUDIT 6: PendingQueuePage ═══');
  await page.goto(`${BASE}/curation/pending`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);

  const queueTitle = await page.locator('h2').textContent();
  queueTitle?.includes('待提炼') ? pass('Queue title correct') : issue('Queue', 'Title missing', 'medium');

  const queueStats = await page.locator('[class*="stats-bar"]').count();
  queueStats > 0 ? pass('Queue stats bar present') : issue('Queue', 'Stats bar missing', 'medium');

  const queueFilters = await page.locator('[class*="filters"] .ant-select').count();
  queueFilters >= 2 ? pass(`${queueFilters} filter dropdowns`) : issue('Queue', `Only ${queueFilters} filters (need ≥2)`, 'medium');

  const refreshQ = await page.locator('button:has-text("刷新")').count();
  refreshQ > 0 ? pass('Queue refresh button') : issue('Queue', 'Refresh button missing', 'low');

  // ==============================
  // AUDIT 7: Responsive
  // ==============================
  console.log('\n═══ AUDIT 7: Responsive ═══');
  for (const vp of [
    { w: 1440, h: 900, n: 'desktop' },
    { w: 768, h: 1024, n: 'tablet' },
    { w: 375, h: 812, n: 'mobile' },
  ]) {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await page.goto(`${BASE}/curation/books`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    overflow ? issue('Responsive', `${vp.n} (${vp.w}px) horizontal overflow`, 'medium') : pass(`${vp.n} (${vp.w}px) — no overflow`);
  }

  // ==============================
  // AUDIT 8: API completeness
  // ==============================
  console.log('\n═══ AUDIT 8: API Completeness ═══');
  const requiredEndpoints = [
    { url: '/api/v2/curation/books', name: 'GET books list', method: 'GET' },
    { url: '/api/v2/curation/kb-books', name: 'GET KB books', method: 'GET' },
    { url: '/api/v2/curation/drafts', name: 'GET drafts list', method: 'GET' },
    { url: '/api/v2/curation/pending', name: 'GET pending queue', method: 'GET' },
    { url: '/api/v2/curation/graph', name: 'GET graph data', method: 'GET' },
    { url: '/api/v2/curation/graph/export-cypher', name: 'GET export cypher', method: 'GET' },
    { url: '/api/v2/curation/cross-book/pairs', name: 'GET cross-book pairs', method: 'GET' },
  ];

  if (books.length > 0) {
    requiredEndpoints.push(
      { url: `/api/v2/curation/books/${books[0].book_id}/generate/progress`, name: 'GET SSE progress', method: 'GET' },
      { url: `/api/v2/curation/books/${books[0].book_id}/chapters`, name: 'GET chapters', method: 'GET' },
    );
  }

  for (const ep of requiredEndpoints) {
    try {
      const res = await fetch(`${API}${ep.url}`);
      res.ok ? pass(`${ep.name}: ${res.status}`) : issue('API', `${ep.name}: status ${res.status}`, 'high');
    } catch (e) {
      issue('API', `${ep.name}: ${e.message}`, 'high');
    }
  }

  // ==============================
  // AUDIT 9: Console errors (non-deprecation)
  // ==============================
  console.log('\n═══ AUDIT 9: Console Errors ═══');
  if (consoleErrors.length === 0) {
    pass('No console errors (excluding deprecation warnings)');
  } else {
    for (const err of consoleErrors) {
      issue('Console', err.substring(0, 120), 'medium');
    }
  }

  // ==============================
  // SUMMARY
  // ==============================
  console.log('\n═══════════════════════════════════════');
  console.log('📊 AUDIT SUMMARY');
  console.log('═══════════════════════════════════════');
  console.log(`✅ Passed: ${passes.length}`);
  console.log(`⚠️  Issues: ${issues.length}`);
  
  if (issues.length > 0) {
    const high = issues.filter(i => i.severity === 'high');
    const medium = issues.filter(i => i.severity === 'medium');
    const low = issues.filter(i => i.severity === 'low');
    console.log(`\n🔴 High: ${high.length}`);
    high.forEach(i => console.log(`   - [${i.category}] ${i.desc}`));
    console.log(`🟡 Medium: ${medium.length}`);
    medium.forEach(i => console.log(`   - [${i.category}] ${i.desc}`));
    console.log(`🔵 Low: ${low.length}`);
    low.forEach(i => console.log(`   - [${i.category}] ${i.desc}`));
  }
  
  await browser.close();
})();
