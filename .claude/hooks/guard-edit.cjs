#!/usr/bin/env node
'use strict';
/**
 * PreToolUse (Edit|Write|MultiEdit) guard. Reads the hook JSON on stdin. Exit 0 allows,
 * exit 2 blocks (reason on stderr). Any internal error fails OPEN (note, exit 0).
 *
 * Blocks, each with one override env var (Alex sets it in the environment that launches
 * Claude Code):
 *   writes under $HOME/.agents, $HOME/Alex-Director, $HOME/.claude   ALLOW_HOME_EDIT=1
 *     (narrow carve-out: $HOME/.claude/projects/<x>/memory/ is Claude Code's own auto
 *      memory and stays writable)
 *   .env and .env.* files, except .env.example                      ALLOW_ENV_EDIT=1
 *   creating a new FINDINGS.md or REPORT.md in the repo root         ALLOW_ROOT_DOCS=1
 */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const HOOK = 'guard-edit';
const ROOT = path.resolve(__dirname, '..', '..'); // <repo>/.claude/hooks/ -> <repo>

function note(msg) {
  try { fs.writeSync(2, HOOK + ': ' + msg + '\n'); } catch (_) { /* ignore */ }
}

const envOn = (name) => process.env[name] === '1';
const fold = (p) => (process.platform === 'linux' ? p : p.toLowerCase()); // macOS and Windows are case-insensitive by default
const within = (p, dir) => fold(p) === fold(dir) || fold(p).startsWith(fold(dir) + path.sep);

/** Resolve symlinks on the deepest existing ancestor, then re-append the missing tail. */
function realish(p) {
  let cur = p;
  const tail = [];
  for (;;) {
    try {
      return path.join(fs.realpathSync(cur), ...tail.reverse());
    } catch (_) {
      const parent = path.dirname(cur);
      if (parent === cur) return p;
      tail.push(path.basename(cur));
      cur = parent;
    }
  }
}

function expandHome(p, home) {
  if (p === '~') return home;
  if (p.startsWith('~/')) return path.join(home, p.slice(2));
  return p;
}

function block(message) { return { block: true, message }; }

function decide(payload) {
  const ti = (payload && payload.tool_input) || {};
  const raw = ti.file_path || ti.notebook_path || ti.path;
  if (typeof raw !== 'string' || !raw) return null;

  const home = process.env.HOME || os.homedir();
  const base = payload.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const abs = path.resolve(base, expandHome(raw, home));
  const real = realish(abs);
  const candidates = [abs, real];

  // 1. Alex's home config (not this project's .claude/).
  if (!envOn('ALLOW_HOME_EDIT')) {
    const protectedDirs = ['.agents', 'Alex-Director', '.claude'].map((d) => path.join(home, d));
    const roots = [...new Set([...protectedDirs, ...protectedDirs.map(realish)])];
    const memoryDirs = [...new Set([path.join(home, '.claude', 'projects'), realish(path.join(home, '.claude', 'projects'))])];
    const isMemory = (c) => memoryDirs.some((m) => within(c, m) && /^[^/\\]+[/\\]memory[/\\]/.test(c.slice(m.length + 1)));
    for (const c of candidates) {
      if (roots.some((r) => within(c, r)) && !isMemory(c)) {
        return block('BLOCKED (guard-edit): ' + abs + ' is under ~/.agents, ~/Alex-Director or ~/.claude. AGENTS.md: never edit these from this project. Write a proposed diff inside the project instead. Override: Alex sets ALLOW_HOME_EDIT=1 in the environment that launches Claude Code.');
      }
    }
  }

  // 2. Env files.
  const name = path.basename(abs);
  if (!envOn('ALLOW_ENV_EDIT') && /^\.env(\..+)?$/.test(name) && name !== '.env.example') {
    return block('BLOCKED (guard-edit): ' + name + ' may hold secrets (AGENTS.md: no keys in files). Only .env.example is editable. Override: Alex sets ALLOW_ENV_EDIT=1.');
  }

  // 3. New ad-hoc report files in the repo root.
  if (!envOn('ALLOW_ROOT_DOCS') && /^(FINDINGS|REPORT)\.md$/i.test(name)) {
    const roots = [ROOT, realish(ROOT)];
    if (candidates.some((c) => roots.some((r) => fold(path.dirname(c)) === fold(r))) && !fs.existsSync(abs)) {
      return block('BLOCKED (guard-edit): a new ' + name + ' in the repo root. Return findings in your reply, or put a dated receipt under reviews/receipts/. Override: Alex sets ALLOW_ROOT_DOCS=1.');
    }
  }
  return null;
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
  let verdict = null;
  try {
    verdict = decide(JSON.parse(raw || '{}'));
  } catch (err) {
    note('internal error, allowing: ' + (err && err.message));
  }
  if (verdict && verdict.block) {
    try { fs.writeSync(2, verdict.message + '\n'); } catch (_) { /* ignore */ }
    process.exit(2);
  }
  process.exit(0);
});
