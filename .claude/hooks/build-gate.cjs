#!/usr/bin/env node
'use strict';
/**
 * Stop: type-check gate. Runs `node app/node_modules/typescript/bin/tsc --noEmit -p app/tsconfig.json`
 * from the repo root. Exit 2 (first 40 lines of tsc output on stderr) only when tsc ran and
 * reported TypeScript errors. Exit 0 in every other case:
 *   - stop_hook_active is true (a previous block already continued this turn: never loop)
 *   - typescript is not installed yet (probed at run time, so a later npm install enables it)
 *   - tsc timed out, could not start, or failed without a TypeScript error (fail open)
 * Override: ALLOW_BUILD_GATE_SKIP=1 skips the check.
 */
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const HOOK = 'build-gate';
const ROOT = path.resolve(__dirname, '..', '..');
const TSC = path.join('app', 'node_modules', 'typescript', 'bin', 'tsc');
const TSCONFIG = path.join('app', 'tsconfig.json');
const TSC_TIMEOUT_MS = 100000; // below the 120000 hook timeout so we exit 0 before being killed

function note(msg) {
  try { fs.writeSync(2, HOOK + ': ' + msg + '\n'); } catch (_) { /* ignore */ }
}

function run(raw) {
  const payload = (() => { try { return JSON.parse(raw || '{}'); } catch (_) { return {}; } })();
  if (payload.stop_hook_active === true) return { code: 0 };
  if (process.env.ALLOW_BUILD_GATE_SKIP === '1') return { code: 0 };

  if (!fs.existsSync(path.join(ROOT, TSC))) {
    note('warning: ' + TSC + ' not found (run npm install in app/). Type check skipped.');
    return { code: 0 };
  }
  if (!fs.existsSync(path.join(ROOT, TSCONFIG))) {
    note('warning: ' + TSCONFIG + ' not found. Type check skipped.');
    return { code: 0 };
  }

  try {
    execFileSync(process.execPath, [TSC, '--noEmit', '-p', TSCONFIG], {
      cwd: ROOT,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
      maxBuffer: 32 * 1024 * 1024,
      timeout: TSC_TIMEOUT_MS,
    });
    return { code: 0 };
  } catch (err) {
    const out = String((err && err.stdout) || '') + String((err && err.stderr) || '');
    if (err && (err.killed || err.signal)) {
      note('warning: tsc did not finish (' + (err.signal || 'killed') + '). Type check skipped.');
      return { code: 0 };
    }
    if (typeof (err && err.status) === 'number' && /error TS\d+/.test(out)) {
      const lines = out.split('\n').filter((l) => l.trim() !== '').slice(0, 40);
      return {
        code: 2,
        message: 'BLOCKED (build-gate): tsc --noEmit found type errors. Fix them before finishing (first ' + lines.length + ' lines):\n' + lines.join('\n') + '\nSkip once: Alex sets ALLOW_BUILD_GATE_SKIP=1.',
      };
    }
    note('warning: tsc failed without a TypeScript error (' + ((err && (err.code || err.message)) || 'unknown') + '). Type check skipped.');
    return { code: 0 };
  }
}

function readStdin(cb) {
  let buf = '';
  let done = false;
  const finish = () => { if (!done) { done = true; cb(buf); } };
  try {
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (d) => { buf += d; });
    process.stdin.on('end', finish);
    process.stdin.on('error', finish);
    setTimeout(finish, 5000).unref();
  } catch (_) {
    finish();
  }
}

readStdin((raw) => {
  let result = { code: 0 };
  try {
    result = run(raw);
  } catch (err) {
    note('internal error, allowing: ' + (err && err.message));
  }
  if (result.code === 2) {
    try { fs.writeSync(2, result.message + '\n'); } catch (_) { /* ignore */ }
    process.exit(2);
  }
  process.exit(0);
});
