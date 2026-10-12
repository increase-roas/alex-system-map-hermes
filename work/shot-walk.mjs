// Plays the Pro Map walkthrough and screenshots chosen steps. Usage: node work/shot-walk.mjs <url> <out-prefix> <job-name> <steps comma list>
import { createRequire } from 'module';
const require = createRequire('/Users/alexlobaito/Projects/alex-system-map/app/package.json');
const { chromium } = require('playwright');
const [url, out, jobName, stepsArg] = process.argv.slice(2);
const steps = stepsArg.split(',').map(Number);
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1800, height: 1300 } });
await page.goto(url, { waitUntil: 'networkidle' });
await page.getByRole('button', { name: 'Pro Map' }).click();
await page.waitForSelector('[data-testid="walkthrough"]', { timeout: 20000 });
await page.getByTestId('wt-toggle').click();
await page.locator('[data-testid="walkthrough"] select').selectOption({ label: jobName });
let at = 1;
for (const s of steps) {
  while (at < s) { await page.getByTestId('wt-next').click(); at++; }
  await page.waitForTimeout(1100);
  await page.screenshot({ path: `${out}-${s}.png` });
}
console.log(await page.getByTestId('walkthrough').innerText());
await browser.close();
