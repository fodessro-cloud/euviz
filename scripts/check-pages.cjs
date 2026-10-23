// Opens FINILA's pages the way a visitor does (headless Chromium) and reports what a visitor would
// notice: script errors, files that do not load, "NaN" or "undefined" in the text, empty tables.
// Usage: node scripts/check-pages.cjs [site]  (default https://www.finila.com). Exit 1 on a problem.
const { chromium } = require('playwright');

const SITE = (process.argv[2] || 'https://www.finila.com').replace(/\/$/, '');
const PAGES = [
  ['/', '#property, main'],
  ['/screener', 'tbody tr'],
  ['/map', '#hm-note'],
  ['/groups', '#groups-tbody tr'],
  ['/insiders', 'tbody tr'],
  ['/shorts', 'tbody tr'],
  ['/property', 'main'],
  ['/property/slovakia', 'main'],
  ['/rates', 'main'],
  ['/assets', '#chart svg'],
  ['/stock/shell', 'main'],
  ['/stock/siemens', 'main'],
];
const BAD_TEXT = /\b(NaN|undefined|Infinity)\b|null\s?%|€\s?NaN/;

(async () => {
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  const problems = [];
  for (const [path, mustHave] of PAGES) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.addInitScript(() => { try { localStorage.setItem('finila-consent', 'no'); } catch (e) { /* ignore */ } });
    const found = [];
    page.on('pageerror', e => found.push(`script error: ${e.message}`));
    page.on('response', r => {
      if (r.status() >= 400 && r.url().startsWith(SITE)) found.push(`HTTP ${r.status()} for ${r.url().slice(SITE.length)}`);
    });
    try {
      const url = SITE.includes('localhost') && path !== '/' ? SITE + path + '.html' : SITE + path;   // local test server has no clean URLs
      const res = await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
      if (!res || res.status() >= 400) found.push(`page answers HTTP ${res ? res.status() : 'nothing'}`);
      await page.waitForTimeout(1500);
      const ok = await page.$(mustHave);
      if (!ok) found.push(`nothing shown where "${mustHave}" should be`);
      const text = await page.evaluate(() => document.body.innerText);
      const bad = text.match(BAD_TEXT);
      if (bad) {
        const at = text.indexOf(bad[0]);
        found.push(`text shows "${bad[0]}": …${text.slice(Math.max(0, at - 60), at + 40).replace(/\s+/g, ' ')}…`);
      }
    } catch (e) {
      found.push(`did not load: ${e.message.split('\n')[0]}`);
    }
    for (const f of found) problems.push(`${path}: ${f}`);
    console.log(`${found.length ? 'PROBLEM' : 'ok     '} ${path}${found.length ? ` (${found.length})` : ''}`);
    await page.close();
  }
  await browser.close();
  for (const p of problems) console.log(`::error title=Page check::${p}`);
  console.log(`${PAGES.length} pages, ${problems.length} problems`);
  process.exit(problems.length ? 1 : 0);
})();
