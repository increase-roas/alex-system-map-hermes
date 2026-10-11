#!/usr/bin/env node
/**
 * APP-REVIEW-02 real-path browser: isolated LOCAL_DATA_DIR, process restart proof, network diagnostics.
 */
import { spawn, spawnSync } from 'node:child_process';
import net from 'node:net';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  BENIGN,
  CANARY,
  containsExposedLocalMutationToken,
  screenNetworkLogEntry,
} from './diagnostic_emission_screening.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const APP = path.join(ROOT, 'app');
const DELIVERY =
  process.env.BROWSER_CAPTURE_DELIVERY || 'emitted-boundaries-served-restart-20261010-0754';
const RUN_CAPTURE_SUFFIX = process.env.BROWSER_RUN_CAPTURE_SUFFIX || '';
const OUT = path.join(
  ROOT,
  'reports',
  'browser-proof',
  DELIVERY,
  RUN_CAPTURE_SUFFIX ? `capture-${RUN_CAPTURE_SUFFIX}` : 'capture',
);
const NETWORK_LOG_PATH = path.join(
  OUT,
  RUN_CAPTURE_SUFFIX ? `network-log-${RUN_CAPTURE_SUFFIX}.json` : 'network-log.json',
);
const PORT = process.env.BROWSER_TEST_PORT || '3202';
const BASE = `http://127.0.0.1:${PORT}`;
const STALE_A = 'UI stale baseline instruction 0754-A';
const CORRECTION_A = 'Revise upstream instruction after output';
const CORRECTION_T2 = 'Revise downstream instruction 0754-t2';
const OUTPUT_T1 = 'browser-artifact-out-t1-0754:Fixture T1 retained output';
const ISOLATED_DIR = path.join(APP, '.data', DELIVERY);
const DB_PATH = path.join(ISOLATED_DIR, 'local.sqlite');
const RUNNER_SHA = crypto.createHash('sha256').update(fs.readFileSync(fileURLToPath(import.meta.url))).digest('hex');

const networkLog = [];

async function fetchLogged(label, url, init) {
  const res = await fetch(url, init);
  const contentType = res.headers.get('content-type') || '';
  const text = await res.text();
  let parsed = null;
  let parseError = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch (err) {
    parseError = String(err);
  }
  let bodyPreview = text.slice(0, 500);
  if (label.startsWith('health-') && parsed && typeof parsed === 'object') {
    bodyPreview = JSON.stringify({ ...parsed, canary_probe: CANARY }).slice(0, 500);
  }
  const rawEntry = {
    label,
    url,
    status: res.status,
    contentType,
    parseError,
    bodyLength: text.length,
    bodyPreview,
    parsedKeys: parsed && typeof parsed === 'object' ? Object.keys(parsed) : [],
  };
  const entry = screenNetworkLogEntry(rawEntry);
  networkLog.push(entry);
  return { res, text, parsed, entry };
}

function sha256File(p) {
  return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
}

function isPidAlive(pid) {
  if (!pid || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function probeLoopbackPortRefused(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port: Number(port) });
    const finish = (result) => {
      socket.removeAllListeners();
      try {
        socket.destroy();
      } catch {
        /* ignore */
      }
      resolve(result);
    };
    socket.once('connect', () => finish({ econnrefused: false, connected: true }));
    socket.once('error', (err) => finish({ econnrefused: err.code === 'ECONNREFUSED', code: err.code }));
    socket.setTimeout(1500, () => finish({ econnrefused: false, timeout: true }));
  });
}

async function waitForServer() {
  const start = Date.now();
  while (Date.now() - start < 180000) {
    try {
      const res = await fetch(`${BASE}/api/health`);
      if (res.ok) return;
    } catch {
      await new Promise((r) => setTimeout(r, 400));
    }
  }
  throw new Error('server not ready on loopback');
}

async function stopServedInstance({ launcher, servedPidBefore }) {
  if (launcher) launcher.kill('SIGTERM');
  if (servedPidBefore) {
    try {
      process.kill(servedPidBefore, 'SIGTERM');
    } catch {
      /* ignore */
    }
  }
  const start = Date.now();
  let portRefusedObserved = false;
  while (Date.now() - start < 60000) {
    const oldAlive = isPidAlive(servedPidBefore);
    const portProbe = await probeLoopbackPortRefused(PORT);
    if (portProbe.econnrefused) portRefusedObserved = true;
    if (!oldAlive && portRefusedObserved) {
      return {
        oldPidExited: true,
        listenerReleased: true,
        portRefusedObserved: true,
        port_probe_code: portProbe.code || 'ECONNREFUSED',
      };
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  return {
    oldPidExited: !isPidAlive(servedPidBefore),
    listenerReleased: portRefusedObserved && !isPidAlive(servedPidBefore),
    portRefusedObserved,
    port_probe_code: portRefusedObserved ? 'ECONNREFUSED' : null,
  };
}

function startServer() {
  fs.mkdirSync(ISOLATED_DIR, { recursive: true });
  const env = {
    ...process.env,
    PORT,
    LOCAL_DATA_DIR: ISOLATED_DIR,
    WORKFLOW_SQLITE_PATH: DB_PATH,
    FOUNDATION_ROOT: ROOT,
  };
  const child = spawn('npx', ['next', 'start', '-H', '127.0.0.1', '-p', PORT], {
    cwd: APP,
    stdio: ['ignore', 'pipe', 'pipe'],
    env,
  });
  return child;
}

async function initIsolatedDb() {
  fs.mkdirSync(ISOLATED_DIR, { recursive: true });
  if (fs.existsSync(DB_PATH)) fs.unlinkSync(DB_PATH);
  const proc = spawnSync('python3', [path.join(ROOT, 'tools/local_service.py'), '--db', DB_PATH, 'init'], {
    cwd: ROOT,
    encoding: 'utf8',
  });
  if (proc.status !== 0) throw new Error(`db init failed: ${proc.stderr}`);
  return sha256File(DB_PATH);
}

async function mutate(token, body) {
  const { parsed, entry } = await fetchLogged(`workflow-${body.operation_id}`, `${BASE}/api/workflow`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Local-Token': token },
    body: JSON.stringify({ actor_owner: 'owner-a', ...body }),
  });
  if (!parsed || parsed.error) {
    const safeDetail = parsed?.error || entry.parseError || entry.label;
    throw new Error(`mutation failed at ${entry.label}: ${safeDetail}`);
  }
  return parsed;
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const checks = { delivery: DELIVERY, runner_sha256: RUNNER_SHA, networkLog: [] };
  let server = null;
  try {
    const dbShaBefore = await initIsolatedDb();
    server = startServer();
    await waitForServer();

    const health1 = await fetchLogged('health-before', `${BASE}/api/health`);
    const h1 = health1.parsed;
    checks.served_pid_before = h1?.process?.pid;
    checks.launcher_pid_before = server.pid;
    checks.build_id = h1?.build_id;
    checks.db_path_served = h1?.runtime?.workflow_sqlite_path;
    checks.db_sha256_before = h1?.runtime?.workflow_db_sha256;
    const defaultUserDb = path.join(APP, '.data', 'local.sqlite');
    checks.db_isolated =
      checks.db_path_served === DB_PATH &&
      checks.db_path_served !== defaultUserDb &&
      checks.db_path_served.includes(DELIVERY) &&
      h1?.ok === true;
    checks.db_sha256_matches_fresh_init = checks.db_sha256_before === dbShaBefore;
    if (!checks.build_id) throw new Error('missing build_id from health');
    const token = String(h1?.token || '');

    const jobA = `rec-ui-a-${Date.now()}`;
    const jobB = `rec-ui-b-${Date.now()}`;
    const opA = `${jobA}-handoff`;
    const opB = `${jobB}-handoff`;

    await mutate(token, {
      job_id: jobA,
      expected_revision: 0,
      operation_id: `${jobA}-create`,
      action: 'create',
      payload: {
        goal: 'Recovery job A chain',
        scope: ['browser'],
        constraints: [],
        owner: 'owner-a',
        acceptance: ['check'],
      },
    });
    await mutate(token, {
      job_id: jobA,
      expected_revision: 1,
      operation_id: `${jobA}-add-t1`,
      action: 'add_task',
      handoff_operation_id: opA,
      payload: {
        id: 't1',
        goal: 'upstream',
        owner: 'owner-a',
        acceptance: ['check'],
        deps: [],
        next_action: STALE_A,
      },
    });
    await mutate(token, {
      job_id: jobA,
      expected_revision: 2,
      operation_id: `${jobA}-add-t2`,
      action: 'add_task',
      handoff_operation_id: opA,
      payload: {
        id: 't2',
        goal: 'downstream',
        owner: 'owner-a',
        acceptance: ['check'],
        deps: ['t1'],
        next_action: 'wait for t1',
      },
    });
    await mutate(token, {
      job_id: jobA,
      expected_revision: 3,
      operation_id: `${jobA}-produce-t1`,
      action: 'update',
      handoff_operation_id: opA,
      payload: {
        task_id: 't1',
        status: 'in_progress',
        attempt: 'produce-t1',
        next_action: STALE_A,
        outputs: [OUTPUT_T1],
      },
    });
    await mutate(token, {
      job_id: jobA,
      expected_revision: 4,
      operation_id: `${jobA}-correct-t2`,
      action: 'correct',
      handoff_operation_id: opA,
      payload: { id: 'corr-t2', task_id: 't2', reason: CORRECTION_T2 },
    });
    await mutate(token, {
      job_id: jobA,
      expected_revision: 5,
      operation_id: `${jobA}-correct-t1`,
      action: 'correct',
      handoff_operation_id: opA,
      payload: { id: 'corr-t1', task_id: 't1', reason: CORRECTION_A },
    });

    await mutate(token, {
      job_id: jobB,
      expected_revision: 0,
      operation_id: `${jobB}-create`,
      action: 'create',
      payload: {
        goal: 'Recovery job B control',
        scope: ['browser'],
        constraints: [],
        owner: 'owner-a',
        acceptance: ['check'],
      },
    });
    await mutate(token, {
      job_id: jobB,
      expected_revision: 1,
      operation_id: `${jobB}-add`,
      action: 'add_task',
      handoff_operation_id: opB,
      payload: {
        id: 'b1',
        goal: 'independent',
        owner: 'owner-a',
        acceptance: ['check'],
        deps: [],
        next_action: 'Independent B step',
      },
    });

    const recBefore = await fetchLogged('recover-a-before-restart', `${BASE}/api/workflow/recover/${jobA}`);
    checks.recover_a_before = {
      governing: recBefore.parsed?.reliability_recovery?.governing_applied,
      stale: recBefore.parsed?.superseded_next_permitted_action?.action,
    };

    const restartStop = await stopServedInstance({
      launcher: server,
      servedPidBefore: checks.served_pid_before,
    });
    checks.restart_stop = restartStop;
    server = startServer();
    await waitForServer();
    const health2 = await fetchLogged('health-after', `${BASE}/api/health`);
    checks.served_pid_after = health2.parsed?.process?.pid;
    checks.launcher_pid_after = server.pid;
    checks.served_process_restarted =
      checks.served_pid_after &&
      checks.served_pid_before &&
      checks.served_pid_after !== checks.served_pid_before &&
      restartStop.oldPidExited &&
      restartStop.listenerReleased;
    checks.db_path_served_after = health2.parsed?.runtime?.workflow_sqlite_path;
    checks.db_path_stable_after_restart = checks.db_path_served_after === checks.db_path_served;
    checks.build_id_after = health2.parsed?.build_id;
    checks.build_id_stable = checks.build_id_after === checks.build_id;

    const recA = await fetchLogged('recover-a', `${BASE}/api/workflow/recover/${jobA}`);
    const recB = await fetchLogged('recover-b', `${BASE}/api/workflow/recover/${jobB}`);
    const pktA = recA.parsed;
    const pktB = recB.parsed;
    checks.api_a = {
      governing: pktA?.reliability_recovery?.governing_applied === true,
      stale_history: pktA?.superseded_next_permitted_action?.action === STALE_A,
      actionable: pktA?.next_permitted_action?.action,
      actionable_not_stale: pktA?.next_permitted_action?.action !== STALE_A,
      affected_count: pktA?.affected_outputs_needing_recheck?.length ?? 0,
      affected_has_t1_output: (pktA?.affected_outputs_needing_recheck ?? []).some(
        (row) => row?.task_id === 't1' && String(row?.output || '').includes('browser-artifact-out-t1-0754'),
      ),
      t2_pending_t1: (pktA?.pending_dependencies?.t2 ?? []).includes('t1'),
      t2_ineligible_next: pktA?.next_permitted_action?.task_id === 't1',
      t2_status: pktA?.tasks?.t2?.status,
      next_task_id: pktA?.next_permitted_action?.task_id,
      next_not_blocked_t2: pktA?.next_permitted_action?.task_id !== 't2',
      t2_correction_applied: (pktA?.active_corrections ?? []).some(
        (c) => c?.task_id === 't2' && String(c?.reason || '').includes('0754-t2'),
      ),
      governed_t2_not_actionable:
        pktA?.correction_governed_task?.task_id !== 't2' ||
        pktA?.correction_governed_task?.actionable === false,
    };
    checks.api_b = {
      no_governing: pktB?.reliability_recovery?.governing_applied !== true,
      no_leak_correction_a: !JSON.stringify(pktB).includes(CORRECTION_A),
      next: pktB?.next_permitted_action?.action,
    };

    const playwrightPath = path.join(APP, 'node_modules', 'playwright', 'index.mjs');
    const { chromium } = await import(playwrightPath);
    const browser = await chromium.launch({
      headless: true,
      channel: fs.existsSync('/Applications/Google Chrome.app') ? 'chrome' : undefined,
    });
    const page = await browser.newPage();
    await page.goto(`${BASE}/explorer`, { waitUntil: 'domcontentloaded', timeout: 120000 });
    await page.locator('header').getByRole('button', { name: 'workflows', exact: true }).click();
    await page.getByRole('button', { name: new RegExp(`^${jobA} \\(r`) }).click();
    await page.getByRole('button', { name: 'Tasks & actions', exact: true }).click();
    await page.getByTestId('workflow-actionable-next').waitFor({ timeout: 60000 });
    checks.ui_a_actionable = await page.getByTestId('workflow-actionable-next').innerText();
    checks.ui_a_stale = await page.getByTestId('workflow-stale-next').innerText();
    checks.ui_a_actionable_ok = !checks.ui_a_actionable.includes(STALE_A) && checks.ui_a_actionable.includes('t1');
    checks.ui_a_stale_ok = checks.ui_a_stale.includes(STALE_A);
    checks.ui_a_actionable_matches_api =
      checks.ui_a_actionable.includes(pktA?.next_permitted_action?.task_id || 't1');
    checks.ui_a_affected = await page.getByTestId('workflow-affected-recheck').innerText();
    checks.ui_a_affected_ok = /Affected outputs needing recheck:\s*[1-9]/.test(checks.ui_a_affected);
    checks.ui_a_affected_output_record = await page.getByTestId('workflow-affected-output-record').innerText();
    checks.ui_a_affected_output_ok =
      checks.ui_a_affected_output_record.includes('t1') &&
      checks.ui_a_affected_output_record.includes('browser-artifact-out-t1-0754');
    try {
      checks.ui_a_history = await page.getByTestId('workflow-correction-history').innerText();
      checks.ui_a_history_ok =
        checks.ui_a_history.includes(STALE_A) || checks.ui_a_history.includes('corr-t1');
    } catch {
      checks.ui_a_history = '';
      checks.ui_a_history_ok = false;
    }
    const blockedLoc = page.getByTestId('workflow-correction-blocked');
    await blockedLoc.waitFor({ timeout: 60000 });
    checks.ui_t2_downstream_blocked = await blockedLoc.innerText();
    checks.ui_t2_downstream_blocked_ok =
      checks.ui_t2_downstream_blocked.includes('t2') &&
      checks.ui_t2_downstream_blocked.includes('t1') &&
      (checks.ui_t2_downstream_blocked.includes('corr-t2') ||
        checks.ui_t2_downstream_blocked.includes('0754-t2'));

    await page.getByRole('button', { name: new RegExp(`^${jobB} \\(r`) }).click();
    await page.getByRole('button', { name: 'Tasks & actions', exact: true }).click();
    await page.getByTestId('workflow-actionable-next').filter({ hasText: 'b1' }).waitFor({ timeout: 60000 });
    checks.ui_b_actionable = await page.getByTestId('workflow-actionable-next').innerText();
    checks.ui_b_actionable_ok =
      checks.ui_b_actionable.includes('Independent B step') && checks.ui_b_actionable.includes('b1');
    checks.ui_b_no_correction_a = !checks.ui_b_actionable.includes(CORRECTION_A);
    const histCountB = await page.getByTestId('workflow-correction-history').count();
    if (histCountB > 0) {
      const histText = await page.getByTestId('workflow-correction-history').innerText();
      checks.ui_b_no_history = !histText.includes(CORRECTION_A);
    } else {
      checks.ui_b_no_history = true;
    }

    const shot = path.join(OUT, `recovery-${RUN_CAPTURE_SUFFIX || 'capture'}.png`);
    await page.screenshot({ path: shot, fullPage: true });
    checks.screenshot = { path: path.relative(ROOT, shot), sha256: sha256File(shot), bytes: fs.statSync(shot).size };
    checks.network_log_immutable_path = path.relative(ROOT, NETWORK_LOG_PATH);
    await browser.close();

    checks.diagnostic_capture = {
      benign_marker_present: networkLog.every(
        (e) => e.diagnostic_marker === BENIGN || !e.label?.startsWith('health-'),
      ),
      local_token_redacted: !containsExposedLocalMutationToken(JSON.stringify(networkLog)),
      canary_redacted_in_health_preview: networkLog
        .filter((e) => e.label?.startsWith('health-'))
        .every((e) => !String(e.bodyPreview).includes(CANARY)),
    };
    checks.overall =
      checks.db_isolated &&
      checks.served_process_restarted &&
      checks.build_id_stable &&
      checks.db_path_stable_after_restart &&
      checks.api_a.governing &&
      checks.api_a.stale_history &&
      checks.api_a.actionable_not_stale &&
      checks.api_a.affected_count >= 1 &&
      checks.api_a.affected_has_t1_output &&
      checks.api_a.next_not_blocked_t2 &&
      checks.api_a.t2_pending_t1 &&
      checks.api_a.t2_ineligible_next &&
      checks.api_b.no_governing &&
      checks.api_b.no_leak_correction_a &&
      checks.ui_a_actionable_ok &&
      checks.ui_a_stale_ok &&
      checks.ui_a_actionable_matches_api &&
      checks.ui_a_affected_ok &&
      checks.ui_a_affected_output_ok &&
      checks.ui_b_actionable_ok &&
      checks.ui_b_no_correction_a &&
      checks.ui_b_no_history &&
      checks.ui_a_history_ok &&
      checks.ui_t2_downstream_blocked_ok &&
      checks.api_a.t2_correction_applied &&
      checks.api_a.governed_t2_not_actionable &&
      checks.restart_stop?.listenerReleased &&
      checks.restart_stop?.portRefusedObserved &&
      checks.diagnostic_capture.local_token_redacted &&
      checks.diagnostic_capture.canary_redacted_in_health_preview &&
      checks.diagnostic_capture.benign_marker_present
        ? 'passed'
        : 'failed';
  } catch (err) {
    checks.overall = 'failed';
    checks.error = String(err);
  } finally {
    checks.networkLog = networkLog;
    if (server) server.kill('SIGTERM');
    fs.writeFileSync(NETWORK_LOG_PATH, JSON.stringify(networkLog, null, 2) + '\n');
    checks.network_log_sha256 = sha256File(NETWORK_LOG_PATH);
    const checksOut = screenNetworkLogEntry({ ...checks, networkLog });
    console.log(JSON.stringify(checksOut, null, 2));
    process.exit(checks.overall === 'passed' ? 0 : 1);
  }
}

main().catch((err) => {
  console.log(JSON.stringify({ overall: 'failed', error: String(err), delivery: DELIVERY }, null, 2));
  process.exit(1);
});
