#!/usr/bin/env node
'use strict';
/**
 * SessionStart: print the rules from AGENTS.md that must never be forgotten.
 * Stdout of a SessionStart hook is added to the session context. Always exits 0.
 * Source of truth is AGENTS.md; if a rule changes there, change it here too.
 */
const fs = require('node:fs');

const RULES = [
  'CRITICAL RULES (from AGENTS.md; read it for the full text):',
  '1. The Mac is read-only outside this project. Builders read Alex\'s files and write only inside app/.data/. Never edit ~/.agents, ~/Alex-Director or app settings from here.',
  '2. Back up before editing a file you did not create this session.',
  '3. No branch switch, stash, reset or clean in a shared folder. Use a worktree: git worktree add ../alex-system-map-<topic> -b <topic>.',
  '4. No keys, tokens or secrets in chat, files or logs.',
  '5. Done needs an alex-reviewer packet (node or task ID, acceptance text, evidence paths, your model), reviewed by the other model family. Only the Director marks work verified.',
  '6. Ask Alex before spending money, contacting anyone, changing production or DNS, or deleting data.',
  '7. Say whether each thing is written, configured or seen working. The map never invents state: every claim needs a source file or link; unknown stays unknown.',
  '8. Run the acceptance check that matches the change (tools/*_acceptance.py) and look at UI changes in the browser. No em or en dashes in anything Alex reads.',
  'Guards in this harness block git push, repo-state git commands, secret commits and edits to ~/.agents, ~/Alex-Director, ~/.claude and .env files. Overrides are env vars that only Alex sets before launching Claude Code.',
].join('\n');

function drainStdin(done) {
  let finished = false;
  const finish = () => { if (!finished) { finished = true; done(); } };
  try {
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', () => {});
    process.stdin.on('end', finish);
    process.stdin.on('error', finish);
    setTimeout(finish, 2000).unref();
  } catch (_) {
    finish();
  }
}

drainStdin(() => {
  try {
    fs.writeSync(1, RULES + '\n');
  } catch (err) {
    try { fs.writeSync(2, 'critical-rules: could not print rules: ' + (err && err.message) + '\n'); } catch (_) { /* ignore */ }
  }
  process.exit(0);
});
