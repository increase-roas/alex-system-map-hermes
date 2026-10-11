#!/usr/bin/env node
/**
 * Browser proof for canonical-review-fixes: frozen preview apply, metadata doc, restart bounds.
 */
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const APP = path.join(ROOT, 'app');
const DELIVERY = process.env.BROWSER_CAPTURE_DELIVERY || 'canonical-review-fixes-20261010-1044';
const PORT = process.env.BROWSER_TEST_PORT || '3224';
const BASE = `http://127.0.0.1:${PORT}`;
const CLONE = path.resolve(
  process.env.CATALOG_FIXTURE_ROOT || path.join(APP, '.data', DELIVERY, 'catalog-clone'),
);
const ISOLATED = path.join(APP, '.data', DELIVERY);
const DB = path.join(ISOLATED, 'local.sqlite');
const TABLE = 'data/components.json';
const METADATA = 'data/catalog-metadata.json';
const RECORD_ID = 'component_6f112167c8a413f0f3ab';
const REQUEST_DEADLINE_MS = 120000;
const LOOP_DEADLINE_MS = 600000;
const PROBE_MS = 5000;

function probePortRefused(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port: Number(port) });
    const timer = setTimeout(() => {
      socket.destroy();
      resolve(false);
    }, PROBE_MS);
    const finish = (v) => {
      clearTimeout(timer);
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
    detached: true,
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

async function stopServer(server) {
  if (!server?.pid) return;
  try {
    process.kill(-server.pid, 'SIGTERM');
  } catch {
    server.kill('SIGTERM');
  }
  await new Promise((r) => setTimeout(r, 1500));
}

async function fetchJsonDeadline(url, init = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_DEADLINE_MS);
  try {
    const res = await fetch(url, { ...init, signal: ctrl.signal });
    const bodyTimer = setTimeout(() => ctrl.abort(), REQUEST_DEADLINE_MS);
    const text = await res.text();
    clearTimeout(bodyTimer);
    return { ok: res.ok, json: JSON.parse(text) };
  } finally {
    clearTimeout(timer);
  }
}

async function waitForHealth() {
  const start = Date.now();
  while (Date.now() - start < LOOP_DEADLINE_MS) {
    try {
      const res = await fetchJsonDeadline(`${BASE}/api/health`);
      if (res.ok) return res.json;
    } catch {
      await new Promise((r) => setTimeout(r, 400));
    }
  }
  throw new Error('health timeout');
}

async function main() {
  const loopStart = Date.now();
  const checks = {
    delivery: DELIVERY,
    overall: 'failed',
    catalog_fixture_root: CLONE,
    frozen_preview_matches_apply: false,
    metadata_ui_passed: false,
  };
  let server = null;
  let browser = null;
  try {
    if (process.env.SKIP_BROWSER_BUILD !== '1') {
      const build = spawn('npm', ['run', 'build'], {
        cwd: APP,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env, NEXT_TELEMETRY_DISABLED: '1' },
      });
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('build deadline')), 600000);
        build.on('close', (code) => {
          clearTimeout(timer);
          code === 0 ? resolve() : reject(new Error(`next build exit ${code}`));
        });
      });
    }
    server = startServer();
    const health = await waitForHealth();
    checks.served_pid_before = health.process?.pid;
    checks.build_id = health.build_id;
    checks.runtime_catalog_fixture_root = health.runtime?.catalog_fixture_root ?? null;
    checks.runtime_fixture_matches = checks.runtime_catalog_fixture_root === CLONE;
    const playwrightPath = path.join(APP, 'node_modules', 'playwright', 'index.mjs');
    const { chromium } = await import(playwrightPath);
    browser = await chromium.launch({
      headless: true,
      channel: fs.existsSync('/Applications/Google Chrome.app') ? 'chrome' : undefined,
    });
    const page = await browser.newPage();
    await page.goto(`${BASE}/explorer`, { waitUntil: 'networkidle', timeout: 120000 });
    await page.getByRole('button', { name: 'maintained', exact: true }).click();
    await page.getByTestId('maintained-edit-mode-doc').click();
    await page.getByTestId('maintained-edit-path').filter({ hasText: METADATA }).waitFor({ timeout: 60000 });
    const metaRevBefore = await page.getByTestId('maintained-edit-revision').innerText();
    const policy = 'Maintained doc UI edit 1044 (local-only)';
    await page.getByTestId('maintained-edit-update-policy').fill(policy);
    await page.getByTestId('maintained-edit-preview').click();
    try {
      await page.getByTestId('maintained-edit-frozen-preview').waitFor({ timeout: 15000 });
    } catch {
      checks.metadata_preview_error = await page.getByTestId('maintained-edit-error').innerText();
      throw new Error(checks.metadata_preview_error || 'metadata preview did not freeze');
    }
    await page.getByTestId('maintained-edit-apply').click();
    const metaExpectedRev = String(Number(metaRevBefore) + 1);
    await page.getByTestId('maintained-edit-revision').filter({ hasText: metaExpectedRev }).waitFor({ timeout: 60000 });
    const metaDiskEarly = JSON.parse(fs.readFileSync(path.join(CLONE, 'data/catalog-metadata.json'), 'utf8'));
    checks.metadata_ui_passed = String(metaDiskEarly.update_policy || '').includes('Maintained doc UI edit 1044');
    checks.metadata_ui_revision = await page.getByTestId('maintained-edit-revision').innerText();

    await page.getByTestId('maintained-edit-mode-catalog').click();
    await page.getByTestId('maintained-edit-path').filter({ hasText: TABLE }).waitFor({ timeout: 60000 });
    await page.getByTestId('maintained-edit-record-id').fill(RECORD_ID);
    await page.getByTestId('maintained-edit-reload').click();
    await page.getByTestId('maintained-edit-revision').waitFor({ timeout: 60000 });
    const revBefore = await page.getByTestId('maintained-edit-revision').innerText();
    const purpose = 'Browser canonical review fixes 1044 purpose';
    await page.getByTestId('maintained-edit-purpose').fill(purpose);
    await page.getByTestId('maintained-edit-preview').click();
    await page.getByTestId('maintained-edit-frozen-preview').waitFor({ timeout: 60000 });
    const frozenPurpose = await page.getByTestId('maintained-edit-frozen-purpose').innerText();
    await page.getByTestId('maintained-edit-apply').click();
    const expectedRev = String(Number(revBefore) + 1);
    await page.getByTestId('maintained-edit-revision').filter({ hasText: expectedRev }).waitFor({ timeout: 60000 });
    const stateRes = await fetchJsonDeadline(
      `${BASE}/api/catalog/edit/state?path=${encodeURIComponent(TABLE)}&record_id=${encodeURIComponent(RECORD_ID)}`,
    );
    const diskDoc = JSON.parse(fs.readFileSync(path.join(CLONE, 'data/components.json'), 'utf8'));
    const diskRec = (diskDoc.records || []).find((r) => r.id === RECORD_ID);
    checks.disk_purpose = diskRec?.purpose;
    checks.disk_matches_ui = diskRec?.purpose === purpose && frozenPurpose === purpose;
    checks.frozen_preview_matches_apply =
      frozenPurpose === purpose && diskRec?.purpose === purpose && stateRes.json.document?.purpose === purpose;
    await stopServer(server);
    checks.port_refused_after_stop = await probePortRefused(PORT);
    server = startServer();
    const health2 = await waitForHealth();
    checks.restart_pid_changed = health2.process?.pid !== checks.served_pid_before;
    await page.getByTestId('maintained-edit-revision').filter({ hasText: expectedRev }).waitFor({ timeout: 60000 });
    checks.persisted_after_restart = (await page.getByTestId('maintained-edit-revision').innerText()) === expectedRev;

    checks.loop_elapsed_ms = Date.now() - loopStart;
    checks.overall =
      checks.runtime_fixture_matches &&
      checks.frozen_preview_matches_apply &&
      checks.disk_matches_ui &&
      checks.persisted_after_restart &&
      checks.restart_pid_changed &&
      checks.metadata_ui_passed
        ? 'passed'
        : 'failed';
  } catch (err) {
    checks.error = String(err);
    checks.overall = 'failed';
  } finally {
    if (browser) await browser.close();
    await stopServer(server);
    console.log(JSON.stringify(checks, null, 2));
    process.exit(checks.overall === 'passed' ? 0 : 1);
  }
}

main();
