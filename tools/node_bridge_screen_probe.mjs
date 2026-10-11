#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const proc = spawnSync('npx', ['tsx', path.join(ROOT, 'tools/node_bridge_screen_probe.ts')], {
  cwd: ROOT,
  encoding: 'utf8',
});
process.stdout.write(proc.stdout || '');
process.stderr.write(proc.stderr || '');
process.exit(proc.status ?? 1);
