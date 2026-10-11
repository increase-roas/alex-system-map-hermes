#!/usr/bin/env node
/**
 * Browser proof — delivery browser-original-milestone-20261010-0525
 * Requires production build (next start). System Chrome via Playwright channel when bundled incomplete.
 */
import { spawn } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const APP = path.join(ROOT, 'app');
const OUT = path.join(ROOT, 'reports', 'browser-proof');
const DELIVERY_ID = process.env.BROWSER_MILESTONE_DELIVERY || 'browser-original-milestone-20261010-0525';
const PORT = process.env.BROWSER_TEST_PORT || '3200';
const BASE = `http://127.0.0.1:${PORT}`;
const SERVER_CMD = ['npx', 'next', 'start', '-H', '127.0.0.1', '-p', PORT];
const DELIVERY_CONSOLIDATED = 'consolidated-local-corrections-20261010-0550';

async function waitForServer() {
  const start = Date.now();
  while (Date.now() - start < 180000) {
    try {
      const res = await fetch(`${BASE}/api/health`);
      if (res.ok) return;
    } catch {
      await new Promise((r) => setTimeout(r, 500));
    }
  }
  throw new Error('server not ready');
}

function sha256File(filePath) {
  const data = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(data).digest('hex');
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const checks = {};
  const errors = [];
  let server = null;

  if (process.env.SKIP_SERVER_START !== '1') {
    server = spawn(SERVER_CMD[0], SERVER_CMD.slice(1), { cwd: APP, stdio: 'ignore' });
    await waitForServer();
  } else {
    await waitForServer();
  }

  const health = await fetch(`${BASE}/api/health`).then((r) => r.json());
  checks.health_ok = health.ok === true;
  checks.catalog_complete = health.completeness?.complete === true;

  const catalog = await fetch(`${BASE}/api/catalog`).then((r) => r.json());
  checks.relationship_count = catalog.data?.relationships?.length ?? 0;
  checks.component_count = catalog.data?.components?.length ?? 0;
  checks.relationships_at_least_59 = checks.relationship_count >= 59;
  checks.components_nonempty = checks.component_count > 0;

  const browsersPath =
    process.env.PLAYWRIGHT_BROWSERS_PATH || path.join(APP, '.playwright-browsers');
  process.env.PLAYWRIGHT_BROWSERS_PATH = browsersPath;
  const playwrightPath = path.join(APP, 'node_modules', 'playwright', 'index.mjs');
  const { chromium } = await import(playwrightPath);

  function bundledChromeReady() {
    if (!fs.existsSync(browsersPath) || fs.existsSync(path.join(browsersPath, '__dirlock'))) {
      return undefined;
    }
    for (const entry of fs.readdirSync(browsersPath)) {
      if (!entry.startsWith('chromium-')) continue;
      const macApp = path.join(
        browsersPath,
        entry,
        'chrome-mac-arm64',
        'Google Chrome for Testing.app',
        'Contents',
        'MacOS',
        'Google Chrome for Testing',
      );
      if (fs.existsSync(macApp)) return macApp;
    }
    return undefined;
  }

  const systemChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const bundled = bundledChromeReady();
  let browserRoute = 'none';
  let launchOptions = { headless: true };
  if (bundled) {
    browserRoute = 'project_chrome_for_testing';
    launchOptions.executablePath = bundled;
  } else if (fs.existsSync(systemChrome)) {
    browserRoute = 'system_google_chrome_playwright_channel';
    launchOptions = { headless: true, channel: 'chrome' };
  } else {
    throw new Error('No supported browser executable');
  }

  const userDataDir = path.join(OUT, 'isolated-profile');
  fs.mkdirSync(userDataDir, { recursive: true });

  let context;
  try {
    context = await chromium.launchPersistentContext(userDataDir, {
      ...launchOptions,
      viewport: { width: 1400, height: 900 },
    });
  } catch (launchErr) {
    errors.push(String(launchErr));
    if (browserRoute.startsWith('system') && bundled) {
      browserRoute = 'project_chrome_for_testing_fallback';
      context = await chromium.launchPersistentContext(userDataDir, {
        headless: true,
        executablePath: bundled,
        viewport: { width: 1400, height: 900 },
      });
    } else {
      throw launchErr;
    }
  }
  checks.persistent_profile_dir = fs.existsSync(userDataDir);

  const page = context.pages()[0] ?? (await context.newPage());
  page.on('pageerror', (err) => errors.push(`pageerror:${err.message}`));
  const shots = [];

  async function snap(name) {
    const file = path.join(OUT, `${name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    const stat = fs.statSync(file);
    shots.push({
      name,
      path: path.relative(ROOT, file),
      bytes: stat.size,
      sha256: sha256File(file),
    });
  }

  await page.goto(`${BASE}/explorer`, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await page.getByRole('heading', { name: 'Alex system map' }).waitFor({ timeout: 120000 });
  checks.heading_visible = true;

  const stats = page.getByTestId('catalog-stats');
  await stats.waitFor({ timeout: 30000 });
  const statsText = await stats.innerText();
  checks.stats_show_relationships = statsText.includes(String(checks.relationship_count));
  checks.stats_show_complete = statsText.includes('catalog complete');
  await snap('01-explorer-overview-light');

  const layerOrders = [];
  for (let order = 1; order <= 8; order += 1) {
    const node = page.getByTestId(`layer-order-${order}`);
    if (await node.count()) {
      const box = await node.boundingBox();
      if (box) layerOrders.push({ order, y: box.y });
    }
  }
  checks.overview_layer_nodes = layerOrders.length;
  checks.overview_layer_top_down =
    layerOrders.length >= 6 &&
    layerOrders.every((row, idx, arr) => idx === 0 || row.y >= arr[idx - 1].y - 8);
  const docWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  const viewWidth = await page.evaluate(() => document.documentElement.clientWidth);
  checks.no_horizontal_overflow = docWidth <= viewWidth + 4;

  const themeButton = page.getByRole('button', { name: 'Toggle theme' });
  if (await themeButton.count()) {
    await themeButton.click();
    await page.waitForTimeout(500);
    await snap('02-explorer-overview-dark');
    checks.dark_theme_toggled = true;
  }

  const nav = page.locator('header');
  const views = ['subsystem', 'files', 'problems', 'workflows', 'tracing', 'reliability'];
  for (const view of views) {
    await nav.getByRole('button', { name: view, exact: true }).click();
    await page.waitForTimeout(600);
    await snap(`view-${view}`);
  }
  checks.all_view_screenshots = shots.filter((s) => s.name.startsWith('view-')).length === views.length;

  await nav.getByRole('button', { name: 'workflows', exact: true }).click();
  await page.getByRole('button', { name: 'Start guided job' }).waitFor({ timeout: 30000 });
  checks.workflows_panel_has_content = true;
  checks.workflows_recovery_ux = (await page.getByText('Recover packet').count()) > 0;

  await nav.getByRole('button', { name: 'reliability', exact: true }).click();
  await page.getByRole('heading', { name: /Reliability/i }).waitFor({ timeout: 30000 });
  const relEvidence = page.getByTestId('REL-02-evidence').first();
  checks.reliability_shows_evidence = (await relEvidence.count()) > 0;
  if (checks.reliability_shows_evidence) {
    const text = await relEvidence.innerText();
    checks.reliability_evidence_nonempty = text.trim().length > 40 && text.includes('{');
    const fontSize = await relEvidence.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
    checks.reliability_evidence_readable = fontSize >= 13;
  } else {
    checks.reliability_evidence_nonempty = false;
    checks.reliability_evidence_readable = false;
  }
  checks.reliability_recovery_note = (await page.getByText('Last verified').count()) > 0;

  await nav.getByRole('button', { name: 'tracing', exact: true }).click();
  await page.getByRole('heading', { name: /Agent tracing/i }).waitFor({ timeout: 30000 });
  await page.waitForTimeout(800);
  const tracePick = page.getByRole('button', { name: /Local catalog read/i });
  if ((await tracePick.count()) > 0) {
    await tracePick.first().click();
  }
  await page.getByText(/explorer\.load_catalog|span-root/i).first().waitFor({ timeout: 30000 });
  checks.tracing_span_visible = true;
  await snap('view-tracing-detail');

  await nav.getByRole('button', { name: 'subsystem', exact: true }).click();
  await page.waitForTimeout(500);
  checks.subsystem_view_loaded = (await page.locator('.react-flow').count()) > 0;
  await snap('view-subsystem-impact');

  await nav.getByRole('button', { name: 'overview', exact: true }).click();
  await page.waitForTimeout(400);
  const search = page.getByPlaceholder('Search IDs, names, files, issues');
  await search.fill('Composio');
  await page.waitForTimeout(400);
  const match = page.locator('aside').getByRole('button').filter({ hasText: /Composio/i }).first();
  if (await match.count()) {
    await match.click();
    checks.search_navigation = true;
    await snap('component-detail-from-search');
  }

  await context.close();
  if (server) server.kill('SIGTERM');

  checks.no_page_errors = errors.filter((e) => e.startsWith('pageerror:')).length === 0;

  const required = [
    'health_ok',
    'relationships_at_least_59',
    'components_nonempty',
    'heading_visible',
    'stats_show_relationships',
    'all_view_screenshots',
    'workflows_panel_has_content',
    'workflows_recovery_ux',
    'reliability_evidence_nonempty',
    'reliability_evidence_readable',
    'reliability_recovery_note',
    'overview_layer_top_down',
    'no_horizontal_overflow',
    'persistent_profile_dir',
    'tracing_span_visible',
    'subsystem_view_loaded',
    'no_page_errors',
  ];
  const failed = required.filter((k) => !checks[k]);
  const status = failed.length === 0 ? 'PASS' : 'FAIL';

  const report = {
    delivery_id: DELIVERY_ID,
    consolidated_delivery_id: DELIVERY_CONSOLIDATED,
    status,
    failed_checks: failed,
    checks,
    browser_route: browserRoute,
    server_command: SERVER_CMD.join(' '),
    loopback: BASE,
    build_identity: {
      package_json_sha256: sha256File(path.join(APP, 'package.json')),
    },
    api_catalog_counts: {
      relationships: checks.relationship_count,
      components: checks.component_count,
    },
    screenshots: shots,
    errors,
    source_sha256: {
      'tools/browser_acceptance.mjs': sha256File(fileURLToPath(import.meta.url)),
    },
    at: new Date().toISOString(),
    owner_evidence_not_independent_acceptance: true,
  };
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ status, failed_checks: failed, browser_route: browserRoute }, null, 2));
  if (status !== 'PASS') process.exit(1);
}

main().catch((error) => {
  const fail = {
    delivery_id: DELIVERY_ID,
    status: 'FAIL',
    error: String(error),
    at: new Date().toISOString(),
  };
  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(fail, null, 2) + '\n');
  console.error(error);
  process.exit(1);
});
