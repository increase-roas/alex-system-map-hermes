#!/usr/bin/env node
/**
 * Browser/sync/restart proof for delivery browser-sync-recovery-20261010-1249.
 */
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { runWithDeadline, spawnGroup, terminateGroup } from './node_process_bounded.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const APP = path.join(ROOT, 'app');
const DELIVERY = process.env.BROWSER_CAPTURE_DELIVERY || 'browser-sync-recovery-20261010-1249';
const PORT = process.env.BROWSER_TEST_PORT || '3229';
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
  return spawnGroup(
    'npx',
    ['next', 'start', '-H', '127.0.0.1', '-p', PORT],
    {
      cwd: APP,
      env: {
        ...process.env,
        PORT,
        LOCAL_DATA_DIR: ISOLATED,
        WORKFLOW_SQLITE_PATH: DB,
        FOUNDATION_ROOT: ROOT,
        CATALOG_FIXTURE_ROOT: CLONE,
      },
    },
  );
}

async function stopServer(server) {
  return terminateGroup(server);
}

async function fetchJsonDeadline(url, init = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_DEADLINE_MS);
  try {
    const res = await fetch(url, { ...init, signal: ctrl.signal });
    const text = await res.text();
    return { ok: res.ok, json: JSON.parse(text), status: res.status };
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
  const checks = {
    delivery: DELIVERY,
    overall: 'failed',
    exit: 1,
    catalog_fixture_root: CLONE,
    late_response_mode_switch_passed: false,
    draft_blocks_stale_preview_apply: false,
    disk_auto_sync_passed: false,
    malformed_json_shows_lkg: false,
    component_edit_disk_derived_match: false,
    metadata_edit_disk_match: false,
    frozen_preview_matches_apply: false,
    metadata_ui_passed: false,
    port_refused_after_stop: false,
    restart_pid_changed: false,
    persisted_after_restart_fresh_fetch: false,
    runtime_fixture_matches: false,
  };
  let server = null;
  let browser = null;
  const compPath = path.join(CLONE, 'data/components.json');
  const metaPath = path.join(CLONE, 'data/catalog-metadata.json');
  let compBackup = null;
  let metaBackup = null;
  try {
    compBackup = fs.readFileSync(compPath);
    metaBackup = fs.readFileSync(metaPath);
    if (process.env.SKIP_BROWSER_BUILD !== '1') {
      await runWithDeadline('npm', ['run', 'build'], { cwd: APP, env: { ...process.env, NEXT_TELEMETRY_DISABLED: '1' } }, 600000);
    }
    server = startServer();
    const health = await waitForHealth();
    checks.served_pid_before = health.process?.pid;
    checks.build_id_before = health.build_id;
    checks.db_path = health.runtime?.sqlite_path ?? null;
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

    let delayState = 0;
    await page.route('**/api/catalog/edit/state**', async (route) => {
      if (delayState > 0) {
        await new Promise((r) => setTimeout(r, delayState));
      }
      await route.continue();
    });
    await page.getByTestId('maintained-edit-mode-catalog').click();
    await page.getByTestId('maintained-edit-path').filter({ hasText: TABLE }).waitFor({ timeout: 60000 });
    delayState = 2500;
    const reloadPromise = page.getByTestId('maintained-edit-reload').click();
    await page.getByTestId('maintained-edit-mode-doc').click();
    await reloadPromise;
    await page.waitForTimeout(3000);
    const pathAfter = await page.getByTestId('maintained-edit-path').innerText();
    checks.late_response_mode_switch_passed = pathAfter.includes('catalog-metadata');
    delayState = 0;
    await page.unroute('**/api/catalog/edit/state**');

    let delayPreview = 0;
    await page.route('**/api/catalog/edit**', async (route, request) => {
      if (request.method() === 'POST' && delayPreview > 0) {
        await new Promise((r) => setTimeout(r, delayPreview));
      }
      await route.continue();
    });
    await page.getByTestId('maintained-edit-mode-catalog').click();
    await page.getByTestId('maintained-edit-record-id').fill(RECORD_ID);
    await page.getByTestId('maintained-edit-reload').click();
    await page.getByTestId('maintained-edit-revision').waitFor({ timeout: 60000 });
    const stalePurpose = 'Stale preview race 1249';
    await page.getByTestId('maintained-edit-purpose').fill(stalePurpose);
    delayPreview = 2000;
    void page.getByTestId('maintained-edit-preview').click();
    await page.waitForTimeout(300);
    await page.getByTestId('maintained-edit-purpose').fill(`${stalePurpose} CHANGED`);
    await page.waitForTimeout(2500);
    await page.getByTestId('maintained-edit-apply').click();
    const draftErr = await page.getByTestId('maintained-edit-error').innerText().catch(() => '');
    checks.draft_blocks_stale_preview_apply = /draft changed|preview again/i.test(draftErr);
    delayPreview = 0;
    await page.unroute('**/api/catalog/edit**');

    const diskPurpose = 'Disk auto-sync observer 1249';
    const comp = JSON.parse(fs.readFileSync(compPath, 'utf8'));
    const rec = (comp.records || []).find((r) => r.id === RECORD_ID);
    const prevPurpose = rec?.purpose;
    rec.purpose = diskPurpose;
    fs.writeFileSync(compPath, `${JSON.stringify(comp, null, 2)}\n`);
    await page.getByTestId('maintained-edit-mode-catalog').click();
    await page.getByTestId('maintained-edit-reload').click();
    await page.waitForTimeout(5000);
    const purposeField = await page.getByTestId('maintained-edit-purpose').inputValue();
    checks.disk_auto_sync_passed = purposeField === diskPurpose;
    rec.purpose = prevPurpose;
    fs.writeFileSync(compPath, `${JSON.stringify(comp, null, 2)}\n`);

    fs.writeFileSync(compPath, '{ "records": ');
    await page.waitForTimeout(4000);
    const syncErr = await page.getByTestId('maintained-edit-sync-error').innerText().catch(() => '');
    const lkgLine = await page.getByTestId('maintained-edit-sync-line').innerText().catch(() => '');
    checks.malformed_json_shows_lkg = Boolean(syncErr || lkgLine.includes('last success'));
    fs.writeFileSync(compPath, compBackup);

    const purpose = 'Browser sync recovery 1249 component purpose';
    await page.getByTestId('maintained-edit-reload').click();
    await page.getByTestId('maintained-edit-revision').waitFor({ timeout: 60000 });
    const revBefore = await page.getByTestId('maintained-edit-revision').innerText();
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
    const diskDoc = JSON.parse(fs.readFileSync(compPath, 'utf8'));
    const diskRec = (diskDoc.records || []).find((r) => r.id === RECORD_ID);
    checks.component_edit_disk_derived_match =
      diskRec?.purpose === purpose &&
      stateRes.json.document?.purpose === purpose &&
      frozenPurpose === purpose;
    checks.frozen_preview_matches_apply = checks.component_edit_disk_derived_match;
    checks.final_component_purpose = diskRec?.purpose;

    await page.getByTestId('maintained-edit-mode-doc').click();
    await page.getByTestId('maintained-edit-path').filter({ hasText: METADATA }).waitFor({ timeout: 60000 });
    const metaRevBefore = await page.getByTestId('maintained-edit-revision').innerText();
    const policy = 'Browser sync recovery 1249 metadata policy';
    await page.getByTestId('maintained-edit-update-policy').fill(policy);
    await page.getByTestId('maintained-edit-preview').click();
    await page.getByTestId('maintained-edit-frozen-preview').waitFor({ timeout: 15000 });
    await page.getByTestId('maintained-edit-apply').click();
    await page.getByTestId('maintained-edit-revision').filter({ hasText: String(Number(metaRevBefore) + 1) }).waitFor({
      timeout: 60000,
    });
    const metaDisk = JSON.parse(fs.readFileSync(metaPath, 'utf8'));
    checks.metadata_ui_passed = String(metaDisk.update_policy || '').includes('1249 metadata policy');
    checks.metadata_edit_disk_match = checks.metadata_ui_passed;
    checks.final_metadata_policy = metaDisk.update_policy;

    const stop1 = await stopServer(server);
    checks.port_refused_after_stop = await probePortRefused(PORT);
    server = startServer();
    const health2 = await waitForHealth();
    checks.restart_pid_changed = health2.process?.pid !== checks.served_pid_before;
    checks.build_id_after = health2.build_id;
    await page.reload({ waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'maintained', exact: true }).click();
    await page.getByTestId('maintained-edit-mode-catalog').click();
    await page.getByTestId('maintained-edit-record-id').fill(RECORD_ID);
    await page.getByTestId('maintained-edit-reload').click();
    const revAfter = await page.getByTestId('maintained-edit-revision').innerText();
    const fresh = await fetchJsonDeadline(
      `${BASE}/api/catalog/edit/state?path=${encodeURIComponent(TABLE)}&record_id=${encodeURIComponent(RECORD_ID)}`,
    );
    checks.persisted_after_restart_fresh_fetch =
      revAfter === expectedRev && fresh.json.document?.purpose === purpose;
    checks.server_stop_reaped = stop1.reaped === true;

    checks.overall =
      checks.late_response_mode_switch_passed &&
      checks.draft_blocks_stale_preview_apply &&
      checks.disk_auto_sync_passed &&
      checks.malformed_json_shows_lkg &&
      checks.frozen_preview_matches_apply &&
      checks.metadata_ui_passed &&
      checks.port_refused_after_stop &&
      checks.restart_pid_changed &&
      checks.persisted_after_restart_fresh_fetch &&
      checks.runtime_fixture_matches
        ? 'passed'
        : 'failed';
    checks.exit = checks.overall === 'passed' ? 0 : 1;
  } catch (err) {
    checks.error = String(err);
    checks.overall = 'failed';
    checks.exit = 1;
  } finally {
    if (compBackup) fs.writeFileSync(compPath, compBackup);
    if (metaBackup) fs.writeFileSync(metaPath, metaBackup);
    if (browser) await browser.close();
    await stopServer(server);
    console.log(JSON.stringify(checks, null, 2));
    process.exit(checks.exit);
  }
}

main();
