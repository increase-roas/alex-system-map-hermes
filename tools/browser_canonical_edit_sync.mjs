#!/usr/bin/env node
/**
 * Browser proof: canonical catalog record edit on isolated CATALOG_FIXTURE_ROOT clone.
 * Reuses served-process restart pattern from browser_recovery_screening.mjs.
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const APP = path.join(ROOT, 'app');
const DELIVERY = process.env.BROWSER_CAPTURE_DELIVERY || 'canonical-edit-sync-20261010-0913';
const SUFFIX = process.env.BROWSER_RUN_CAPTURE_SUFFIX || 'canonical-ui';
const PORT = process.env.BROWSER_TEST_PORT || '3223';
const BASE = `http://127.0.0.1:${PORT}`;
const CLONE = path.resolve(
  process.env.CATALOG_FIXTURE_ROOT || path.join(APP, '.data', DELIVERY, 'catalog-clone'),
);
const ISOLATED = path.join(APP, '.data', DELIVERY);
const DB = path.join(ISOLATED, 'local.sqlite');
const TABLE = 'data/components.json';
const RECORD_ID = 'component_6f112167c8a413f0f3ab';
const REQUEST_DEADLINE_MS = 120000;
const LOOP_DEADLINE_MS = 600000;

function probePortRefused(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port: Number(port) });
    const finish = (v) => {
      socket.destroy();
      resolve(v);
    };
    socket.on('connect', () => finish(false));
    socket.on('error', (err) => finish(err.code === 'ECONNREFUSED'));
  });
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
      CATALOG_FIXTURE_ROOT: CLONE,
    },
  });
}

async function fetchDeadline(url, init = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_DEADLINE_MS);
  try {
    return await fetch(url, { ...init, signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function waitForHealth() {
  const start = Date.now();
  while (Date.now() - start < LOOP_DEADLINE_MS) {
    try {
      const res = await fetchDeadline(`${BASE}/api/health`);
      if (res.ok) return res.json();
    } catch {
      await new Promise((r) => setTimeout(r, 400));
    }
  }
  throw new Error('health timeout');
}

async function main() {
  const loopStart = Date.now();
  const checks = { delivery: DELIVERY, overall: 'failed', catalog_fixture_root: CLONE };
  let server = null;
  let browser = null;
  try {
    const build = spawn('npm', ['run', 'build'], {
      cwd: APP,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, NEXT_TELEMETRY_DISABLED: '1' },
    });
    await new Promise((resolve, reject) => {
      build.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`next build exit ${code}`))));
    });
    server = startServer();
    const health = await waitForHealth();
    checks.served_pid_before = health.process?.pid;
    checks.build_id = health.build_id;
    checks.runtime_catalog_fixture_root = health.runtime?.catalog_fixture_root ?? null;
    checks.runtime_fixture_matches = checks.runtime_catalog_fixture_root === CLONE;
    const token = health.token;
    const playwrightPath = path.join(APP, 'node_modules', 'playwright', 'index.mjs');
    const { chromium } = await import(playwrightPath);
    browser = await chromium.launch({
      headless: true,
      channel: fs.existsSync('/Applications/Google Chrome.app') ? 'chrome' : undefined,
    });
    const page = await browser.newPage();
    await page.goto(`${BASE}/explorer`, { waitUntil: 'networkidle', timeout: 120000 });
    await page.getByRole('button', { name: 'maintained', exact: true }).click();
    await page.getByTestId('maintained-edit-mode-catalog').click();
    await page.getByTestId('maintained-edit-record-id').fill(RECORD_ID);
    await page.getByTestId('maintained-edit-reload').click();
    await page.getByTestId('maintained-edit-revision').waitFor({ timeout: 60000 });
    const revBefore = await page.getByTestId('maintained-edit-revision').innerText();
    checks.ui_revision_before = revBefore;
    const purpose = 'Browser canonical edit sync 0913 purpose';
    const purposeField = page.getByTestId('maintained-edit-purpose');
    await purposeField.fill(purpose);
    await page.waitForTimeout(250);
    await page.getByTestId('maintained-edit-preview').click();
    await page.getByTestId('maintained-edit-diff').waitFor({ timeout: 60000 });
    const diffText = await page.getByTestId('maintained-edit-diff').innerText();
    checks.ui_diff_has_purpose = diffText.includes('purpose') && diffText.includes(purpose);
    await page.getByTestId('maintained-edit-apply').click();
    await page.getByTestId('maintained-edit-outcome').waitFor({ timeout: 60000 });
    checks.ui_outcome = await page.getByTestId('maintained-edit-outcome').innerText();
    checks.ui_outcome_has_record = checks.ui_outcome.includes(RECORD_ID);
    const expectedRev = String(Number(revBefore) + 1);
    await page.getByTestId('maintained-edit-revision').filter({ hasText: expectedRev }).waitFor({ timeout: 60000 });
    checks.ui_revision_after = await page.getByTestId('maintained-edit-revision').innerText();
    const stateRes = await fetchDeadline(
      `${BASE}/api/catalog/edit/state?path=${encodeURIComponent(TABLE)}&record_id=${encodeURIComponent(RECORD_ID)}`,
    );
    const stateBody = await stateRes.json();
    const cloneComponents = path.join(CLONE, 'data/components.json');
    const diskDoc = JSON.parse(fs.readFileSync(cloneComponents, 'utf8'));
    const diskRec = (diskDoc.records || []).find((r) => r.id === RECORD_ID);
    checks.disk_purpose = diskRec?.purpose;
    checks.disk_matches_ui = diskRec?.purpose === purpose;
    checks.api_readback_purpose = stateBody.document?.purpose;
    checks.api_readback_matches_ui = stateBody.document?.purpose === purpose;
    const exportRes = await fetchDeadline(`${BASE}/api/catalog`);
    const bundle = await exportRes.json();
    const comps = bundle.data?.components || bundle.components || [];
    const comp = comps.find((c) => c.id === RECORD_ID);
    checks.api_list_purpose = comp?.purpose;
    checks.api_list_matches_ui = comp?.purpose === purpose;
    checks.catalog_list_matches_readback = comp?.purpose === stateBody.document?.purpose;
    server.kill('SIGTERM');
    await new Promise((r) => setTimeout(r, 2000));
    checks.port_refused_after_stop = await probePortRefused(PORT);
    server = startServer();
    const health2 = await waitForHealth();
    checks.served_pid_after_restart = health2.process?.pid;
    checks.restart_pid_changed = health2.process?.pid !== checks.served_pid_before;
    await page.getByTestId('maintained-edit-reload').click();
    await page.getByTestId('maintained-edit-revision').filter({ hasText: expectedRev }).waitFor({ timeout: 60000 });
    checks.persisted_after_restart = (await page.getByTestId('maintained-edit-revision').innerText()) === expectedRev;
    checks.loop_elapsed_ms = Date.now() - loopStart;
    checks.overall =
      checks.runtime_fixture_matches &&
      checks.ui_diff_has_purpose &&
      checks.ui_outcome_has_record &&
      checks.disk_matches_ui &&
      checks.api_readback_matches_ui &&
      checks.catalog_list_matches_readback &&
      checks.persisted_after_restart &&
      checks.restart_pid_changed &&
      checks.port_refused_after_stop
        ? 'passed'
        : 'failed';
  } catch (err) {
    checks.error = String(err);
    checks.overall = 'failed';
  } finally {
    if (browser) await browser.close();
    if (server) server.kill('SIGTERM');
    console.log(JSON.stringify(checks, null, 2));
    process.exit(checks.overall === 'passed' ? 0 : 1);
  }
}

main();
