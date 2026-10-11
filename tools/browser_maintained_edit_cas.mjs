#!/usr/bin/env node
/**
 * Browser proof: maintained edit panel preview + apply on isolated fixture DB.
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const APP = path.join(ROOT, 'app');
const DELIVERY = process.env.BROWSER_CAPTURE_DELIVERY || 'maintained-edit-cas-20261010-0844';
const SUFFIX = process.env.BROWSER_RUN_CAPTURE_SUFFIX || 'cas-ui';
const PORT = process.env.BROWSER_TEST_PORT || '3220';
const BASE = `http://127.0.0.1:${PORT}`;
const STAGING = 'work/maintained/staging-catalog-record.json';
const ISOLATED = path.join(APP, '.data', DELIVERY);
const DB = path.join(ISOLATED, 'local.sqlite');

function sha256File(p) {
  return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
}

function startServer() {
  fs.mkdirSync(ISOLATED, { recursive: true });
  return spawn('npx', ['next', 'start', '-H', '127.0.0.1', '-p', PORT], {
    cwd: APP,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      PORT,
      LOCAL_DATA_DIR: ISOLATED,
      WORKFLOW_SQLITE_PATH: DB,
      FOUNDATION_ROOT: ROOT,
    },
  });
}

async function waitForHealth(timeoutMs = 120000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${BASE}/api/health`);
      if (res.ok) return res.json();
    } catch {
      await new Promise((r) => setTimeout(r, 400));
    }
  }
  throw new Error('health timeout');
}

async function waitForPortDown(timeoutMs = 60000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${BASE}/api/health`);
      if (!res.ok) return;
    } catch {
      return;
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error('port still up after stop');
}

async function main() {
  const checks = { delivery: DELIVERY, overall: 'failed' };
  let server = null;
  const stagingPath = path.join(ROOT, STAGING);
  const backup = fs.readFileSync(stagingPath);
  try {
    server = startServer();
    const health = await waitForHealth();
    checks.served_pid_before = health.process?.pid;
    checks.build_id = health.build_id;
    const token = health.token;

    const playwrightPath = path.join(APP, 'node_modules', 'playwright', 'index.mjs');
    const { chromium } = await import(playwrightPath);
    const browser = await chromium.launch({
      headless: true,
      channel: fs.existsSync('/Applications/Google Chrome.app') ? 'chrome' : undefined,
    });
    const page = await browser.newPage();
    await page.goto(`${BASE}/explorer`, { waitUntil: 'domcontentloaded', timeout: 120000 });
    await page.getByRole('button', { name: 'maintained', exact: true }).click();
    await page.getByTestId('maintained-edit-path').fill(STAGING);
    await page.getByRole('button', { name: 'Reload state' }).click();
    await page.getByTestId('maintained-edit-revision').waitFor({ timeout: 60000 });
    const revBefore = await page.getByTestId('maintained-edit-revision').innerText();
    checks.ui_revision_before = revBefore;
    await page.getByTestId('maintained-edit-label').fill('UI CAS staging label 0844');
    await page.getByTestId('maintained-edit-note').fill('Browser maintained edit CAS proof');
    await page.getByTestId('maintained-edit-preview').click();
    await page.getByTestId('maintained-edit-diff').waitFor({ timeout: 60000 });
    checks.ui_diff_ok = (await page.getByTestId('maintained-edit-diff').innerText()).includes('label');
    await page.getByTestId('maintained-edit-apply').click();
    await page.getByTestId('maintained-edit-outcome').waitFor({ timeout: 60000 });
    checks.ui_outcome = await page.getByTestId('maintained-edit-outcome').innerText();
    checks.ui_outcome_ok = checks.ui_outcome.includes('Applied revision');
    const expectedRev = String(Number(revBefore) + 1);
    await page.getByTestId('maintained-edit-revision').filter({ hasText: expectedRev }).waitFor({
      timeout: 60000,
    });
    checks.ui_revision_after = await page.getByTestId('maintained-edit-revision').innerText();
    checks.ui_revision_incremented = checks.ui_revision_after === expectedRev;
    const derivedMeta = path.join(ROOT, 'work/maintained/derived/staging-catalog-record.meta.json');
    checks.derived_meta_ok = fs.existsSync(derivedMeta);
    if (checks.derived_meta_ok) {
      const meta = JSON.parse(fs.readFileSync(derivedMeta, 'utf8'));
      checks.derived_revision = meta.revision;
      checks.derived_lineage_ok = meta.revision === Number(checks.ui_revision_after);
    }
    await browser.close();
    checks.overall =
      checks.ui_diff_ok &&
      checks.ui_outcome_ok &&
      checks.ui_revision_incremented &&
      checks.derived_meta_ok &&
      checks.derived_lineage_ok
        ? 'passed'
        : 'failed';
  } catch (err) {
    checks.error = String(err);
    checks.overall = 'failed';
  } finally {
    fs.writeFileSync(stagingPath, backup);
    const derivedMd = path.join(ROOT, 'work/maintained/derived/staging-catalog-record.md');
    const derivedMetaPath = path.join(ROOT, 'work/maintained/derived/staging-catalog-record.meta.json');
    for (const p of [derivedMd, derivedMetaPath]) {
      if (fs.existsSync(p)) fs.unlinkSync(p);
    }
    if (server) server.kill('SIGTERM');
    console.log(JSON.stringify(checks, null, 2));
    process.exit(checks.overall === 'passed' ? 0 : 1);
  }
}

main();
