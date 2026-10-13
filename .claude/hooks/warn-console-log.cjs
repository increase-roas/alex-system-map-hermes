#!/usr/bin/env node
'use strict';
/**
 * PostToolUse (Edit|Write|MultiEdit): warn when new content written to app/src/**\/*.ts or
 * *.tsx contains console.log(. Non-blocking: always exits 0. The warning goes to stderr
 * (visible in the transcript) and, as additionalContext on stdout, to the model.
 * Fails open on any internal error. Not applied to *.mts check scripts or tools/.
 */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const HOOK = 'warn-console-log';
const ROOT = path.resolve(__dirname, '..', '..');

function note(msg) {
  try { fs.writeSync(2, HOOK + ': ' + msg + '\n'); } catch (_) { /* ignore */ }
}

function newText(ti) {
  if (typeof ti.content === 'string') return ti.content; // Write
  if (typeof ti.new_string === 'string') return ti.new_string; // Edit
  if (Array.isArray(ti.edits)) return ti.edits.map((e) => (e && typeof e.new_string === 'string' ? e.new_string : '')).join('\n'); // MultiEdit
  return '';
}

function inspect(payload) {
  const ti = (payload && payload.tool_input) || {};
  const raw = ti.file_path;
  if (typeof raw !== 'string' || !raw) return null;
  const base = payload.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const home = process.env.HOME || os.homedir();
  const abs = path.resolve(base, raw.startsWith('~/') ? path.join(home, raw.slice(2)) : raw);
  const rel = path.relative(ROOT, abs).split(path.sep).join('/');
  if (!/^app\/src\/.+\.(ts|tsx)$/.test(rel)) return null;
  const text = newText(ti);
  const idx = text.indexOf('console.log(');
  if (idx === -1) return null;
  const line = text.slice(0, idx).split('\n').length;
  return { rel, line };
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
  try {
    const hit = inspect(JSON.parse(raw || '{}'));
    if (hit) {
      const msg = 'warn-console-log: console.log( added in ' + hit.rel + ' (about line ' + hit.line + ' of the new text). Remove it before calling the work done unless it is intentional server logging; never log tokens or credentials.';
      fs.writeSync(2, msg + '\n');
      fs.writeSync(1, JSON.stringify({ hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: msg } }) + '\n');
    }
  } catch (err) {
    note('internal error, ignoring: ' + (err && err.message));
  }
  process.exit(0);
});
