// Screenshot the Pro Map tab. Usage: node work/shot-pro-map.mjs <url> <out.png>
import { createRequire } from 'module';
const require = createRequire('/Users/alexlobaito/Projects/alex-system-map/app/package.json');
const { chromium } = require('playwright');
const [url, out] = process.argv.slice(2);
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1800, height: 1500 } });
await page.goto(url, { waitUntil: 'networkidle' });
await page.getByRole('button', { name: 'Pro Map' }).click();
await page.waitForSelector('[data-testid="pro-map"] .react-flow__node', { timeout: 20000 });
await page.waitForTimeout(1500);
const counts = await page.evaluate(() => ({
  nodes: document.querySelectorAll('[data-testid="pro-map"] .react-flow__node').length,
  edges: document.querySelectorAll('[data-testid="pro-map"] .react-flow__edge').length,
}));
await page.screenshot({ path: out });
await page.locator('.react-flow__node', { hasText: 'Read when no CLAUDE.md' }).first().click();
await page.waitForSelector('[data-testid="pro-map-detail"]');
const detail = await page.locator('[data-testid="pro-map-detail"]').innerText();
await page.screenshot({ path: out.replace('.png', '-detail.png') });
console.log(JSON.stringify({ ...counts, detail: detail.slice(0, 200) }));
await browser.close();
