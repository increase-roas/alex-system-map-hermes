#!/usr/bin/env node
'use strict';
/**
 * PreToolUse (Bash) guard. Reads the hook JSON on stdin. Exit 0 allows, exit 2 blocks
 * (reason on stderr). Any internal error fails OPEN (note on stderr, exit 0).
 *
 * Blocks, each with one override env var (set by Alex in the environment that launches
 * Claude Code; an inline "VAR=1 git ..." prefix inside the command does NOT count):
 *   git push                                              ALLOW_PUSH=1
 *   git commit when the staged diff has credential text   ALLOW_SECRET_COMMIT=1
 *   git stash | reset --hard | clean | switch | checkout | restore
 *                                                         ALLOW_REPO_STATE_CHANGE=1
 * Allowed on purpose: git worktree add, git stash list/show, git clean --dry-run.
 * Not a git repo: allow everything.
 *
 * The command is tokenised (quotes, heredoc bodies and comments are not scanned as
 * commands), so echo "..." or a heredoc that merely mentions a git command is allowed.
 */
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const HOOK = 'guard-bash';

function note(msg) {
  try { fs.writeSync(2, HOOK + ': ' + msg + '\n'); } catch (_) { /* ignore */ }
}

const envOn = (name) => process.env[name] === '1';

function onPath(cmd) {
  const dirs = (process.env.PATH || '').split(path.delimiter).filter(Boolean);
  const exts = process.platform === 'win32' ? (process.env.PATHEXT || '.EXE;.CMD;.BAT').split(';') : [''];
  for (const d of dirs) {
    for (const e of exts) {
      const f = path.join(d, cmd + e);
      try {
        if (fs.statSync(f).isFile()) { fs.accessSync(f, fs.constants.X_OK); return true; }
      } catch (_) { /* keep looking */ }
    }
  }
  return false;
}

// ---------- command parsing ----------

function stripHeredocs(src) {
  const out = [];
  const pending = [];
  for (const line of src.split('\n')) {
    if (pending.length) {
      const cur = pending[0];
      const probe = cur.strip ? line.replace(/^\t+/, '') : line;
      if (probe === cur.tag) pending.shift();
      continue; // body or terminator line
    }
    out.push(line);
    const re = /<<(-?)\s*(?:'([^']+)'|"([^"]+)"|([A-Za-z_][A-Za-z0-9_]*))/g;
    let m;
    while ((m = re.exec(line)) !== null) {
      if (m.index > 0 && line[m.index - 1] === '<') continue; // here-string <<<
      pending.push({ tag: m[2] || m[3] || m[4], strip: m[1] === '-' });
    }
  }
  return out.join('\n');
}

function substitutions(src) {
  const bodies = [];
  const dollar = /\$\(([^()]*)\)/g;
  const tick = /`([^`]*)`/g;
  let m;
  while ((m = dollar.exec(src)) !== null) bodies.push(m[1]);
  while ((m = tick.exec(src)) !== null) bodies.push(m[1]);
  return bodies;
}

function tokenize(src) {
  const segs = [];
  let toks = [];
  let cur = '';
  let has = false;
  let q = null;
  const endTok = () => { if (has) { toks.push(cur); cur = ''; has = false; } };
  const endSeg = () => { endTok(); if (toks.length) segs.push(toks); toks = []; };
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (q === "'") { if (c === "'") q = null; else cur += c; continue; }
    if (q === '"') {
      if (c === '"') q = null;
      else if (c === '\\' && i + 1 < src.length) cur += src[++i];
      else cur += c;
      continue;
    }
    if (c === "'" || c === '"') { q = c; has = true; continue; }
    if (c === '\\') {
      if (src[i + 1] === '\n') { i++; continue; }
      if (i + 1 < src.length) { cur += src[++i]; has = true; }
      continue;
    }
    if (c === '#' && !has) { while (i + 1 < src.length && src[i + 1] !== '\n') i++; continue; }
    if (c === '\n' || c === ';' || c === '|' || c === '&' || c === '(' || c === ')' || c === '`') { endSeg(); continue; }
    if (c === ' ' || c === '\t' || c === '\r') { endTok(); continue; }
    cur += c;
    has = true;
  }
  endSeg();
  return segs;
}

const WRAPPERS = new Set(['sudo', 'doas', 'env', 'command', 'time', 'nohup', 'exec', 'nice', 'builtin', 'xargs', 'timeout', 'caffeinate']);
const SHELLS = new Set(['bash', 'sh', 'zsh', 'dash', 'ksh']);
const GIT_OPTS_WITH_VALUE = new Set(['-c', '--git-dir', '--work-tree', '--namespace', '--super-prefix', '--config-env']);

/** Returns [{ sub, args, dir }] for every git invocation found in the command text. */
function gitCalls(command, depth = 0) {
  const calls = [];
  if (depth > 3 || typeof command !== 'string') return calls;
  const text = stripHeredocs(command);
  for (const body of substitutions(text)) calls.push(...gitCalls(body, depth + 1));
  for (const toks of tokenize(text)) {
    let i = 0;
    while (i < toks.length) {
      const t = toks[i];
      if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(t)) { i++; continue; }
      if (WRAPPERS.has(path.basename(t))) {
        i++;
        while (i < toks.length && (toks[i].startsWith('-') || /^\d+[smhd]?$/.test(toks[i]))) i++;
        continue;
      }
      break;
    }
    if (i >= toks.length) continue;
    const head = path.basename(toks[i]);
    if (SHELLS.has(head)) {
      const k = toks.findIndex((x, idx) => idx > i && /^-[A-Za-z]*c[A-Za-z]*$/.test(x));
      if (k !== -1 && toks[k + 1] != null) calls.push(...gitCalls(toks[k + 1], depth + 1));
      continue;
    }
    if (head === 'eval') { calls.push(...gitCalls(toks.slice(i + 1).join(' '), depth + 1)); continue; }
    if (head !== 'git') continue;
    let j = i + 1;
    let dir = null;
    while (j < toks.length) {
      const a = toks[j];
      if (a === '-C') { dir = toks[j + 1] || null; j += 2; }
      else if (GIT_OPTS_WITH_VALUE.has(a)) j += 2;
      else if (a.startsWith('-')) j += 1;
      else break;
    }
    if (j < toks.length) calls.push({ sub: toks[j], args: toks.slice(j + 1), dir });
  }
  return calls;
}

// ---------- git helpers (execFileSync, stdio piped, tool probed first) ----------

function gitOut(args, cwd) {
  return execFileSync('git', args, {
    cwd,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    maxBuffer: 64 * 1024 * 1024,
    timeout: 20000,
  });
}

function inRepo(cwd) {
  try { return gitOut(['rev-parse', '--is-inside-work-tree'], cwd).trim() === 'true'; } catch (_) { return false; }
}

const SECRET_PATTERNS = [
  ['OpenAI-style secret key (sk-...)', /sk-[A-Za-z0-9]{20,}/],
  ['AWS access key id (AKIA...)', /AKIA[0-9A-Z]{16}/],
  ['private key block', /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
  ['JWT (eyJ...eyJ...)', /eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\./],
  ['api key assignment', /api[_-]?key\s*[:=]\s*["'][^"']{16,}/i],
];

/** Scans only added lines. Returns [{ file, label, count }]; never returns the matched text. */
function scanDiff(diff) {
  const hits = new Map();
  let file = '(unknown file)';
  for (const line of diff.split('\n')) {
    if (line.startsWith('+++ ')) { file = line.slice(4).replace(/^b\//, ''); continue; }
    if (!line.startsWith('+')) continue;
    for (const [label, re] of SECRET_PATTERNS) {
      if (re.test(line)) {
        const key = file + '\u0000' + label;
        hits.set(key, (hits.get(key) || 0) + 1);
      }
    }
  }
  return [...hits.entries()].map(([k, count]) => {
    const [file, label] = k.split('\u0000');
    return { file, label, count };
  });
}

const hasShortFlag = (args, ch) => args.some((a) => /^-[A-Za-z]+$/.test(a) && a.includes(ch));

// ---------- decision ----------

function block(message) { return { block: true, message }; }

function decide(payload) {
  const command = payload && payload.tool_input && payload.tool_input.command;
  if (typeof command !== 'string' || !command.trim()) return null;
  const calls = gitCalls(command);
  if (!calls.length) return null;
  if (!onPath('git')) { note('git is not installed, allowing'); return null; }
  const base = payload.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();

  for (const call of calls) {
    const cwd = call.dir ? path.resolve(base, call.dir) : base;
    const { sub, args } = call;
    const needsRepo = ['push', 'commit', 'stash', 'reset', 'clean', 'switch', 'checkout', 'restore'].includes(sub);
    if (!needsRepo) continue;
    if (!inRepo(cwd)) continue; // not a git repo: allow

    if (sub === 'push' && !envOn('ALLOW_PUSH')) {
      return block('BLOCKED (guard-bash): git push. The parent session commits and Alex pushes. Override: Alex sets ALLOW_PUSH=1 in the environment that launches Claude Code.');
    }

    if (sub === 'commit' && !envOn('ALLOW_SECRET_COMMIT')) {
      const diffArgs = ['diff', '--cached', '--no-color', '--no-ext-diff', '--unified=0'];
      let diff = '';
      try {
        diff = gitOut(diffArgs, cwd);
        if (args.includes('--all') || hasShortFlag(args.filter((a) => !a.startsWith('--')), 'a')) {
          diff += '\n' + gitOut(['diff', '--no-color', '--no-ext-diff', '--unified=0'], cwd);
        }
      } catch (err) {
        note('could not read the staged diff, allowing: ' + (err && err.code ? err.code : err && err.message));
        continue;
      }
      const hits = scanDiff(diff);
      if (hits.length) {
        const list = hits.slice(0, 8).map((h) => '  ' + h.file + ': ' + h.label + ' (' + h.count + ' line' + (h.count === 1 ? '' : 's') + ')').join('\n');
        return block('BLOCKED (guard-bash): the staged diff contains credential-shaped text. Values are not shown here on purpose.\n' + list + '\nRemove the secret from the files (AGENTS.md: no keys in files or logs), re-stage, then commit. Override for a known-safe test fixture: Alex sets ALLOW_SECRET_COMMIT=1.');
      }
    }

    if (!envOn('ALLOW_REPO_STATE_CHANGE')) {
      let why = null;
      if (sub === 'stash' && !['list', 'show'].includes(args[0])) why = 'git stash';
      else if (sub === 'reset' && args.includes('--hard')) why = 'git reset --hard';
      else if (sub === 'clean' && !args.some((a) => a === '--dry-run' || (/^-[A-Za-z]+$/.test(a) && a.includes('n')))) why = 'git clean';
      else if (sub === 'switch' || sub === 'checkout' || sub === 'restore') why = 'git ' + sub;
      if (why) {
        return block('BLOCKED (guard-bash): ' + why + ' changes repo state in a shared folder (AGENTS.md: no branch switch, stash, reset or clean here). Use a worktree: git worktree add ../alex-system-map-<topic> -b <topic>. Override: Alex sets ALLOW_REPO_STATE_CHANGE=1 in the environment that launches Claude Code.');
      }
    }
  }
  return null;
}

// ---------- entry ----------

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
