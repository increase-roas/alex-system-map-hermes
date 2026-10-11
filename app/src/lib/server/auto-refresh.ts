import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { readFile, stat, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';

import { ensureLocalDataDir, foundationRoot, localDataDir } from './paths';

const run = promisify(execFile);

// One in-flight job per kind, so many open tabs never start parallel scans.
const inflight = new Map<string, Promise<void>>();
function once(key: string, job: () => Promise<void>): Promise<void> {
  const current = inflight.get(key);
  if (current) return current;
  const next = job().finally(() => inflight.delete(key));
  inflight.set(key, next);
  return next;
}

/** The Director's live trace file (kept by its trace writer); falls back to the old copy in this project. */
export function directorReceipts(): string {
  const live = path.join(os.homedir(), 'Alex-Director', 'inputs', 'real-traces', 'director-controller', 'receipts.jsonl');
  return existsSync(live) ? live : path.join(foundationRoot(), 'inputs', 'real-traces', 'director-controller', 'receipts.jsonl');
}

export const orgMapFile = () => path.join(localDataDir(), 'org-map.json');

export const liveScanFile = () => path.join(localDataDir(), 'live-setup.json');

async function ageMs(file: string): Promise<number> {
  try {
    return Date.now() - (await stat(file)).mtimeMs;
  } catch {
    return Number.POSITIVE_INFINITY;
  }
}

/** Re-run the read-only Mac scan (about 3s) when the saved one is older than maxAgeMs. */
export function runLiveScan(): Promise<void> {
  return once('live-scan', async () => {
    await run('python3', [path.join(foundationRoot(), 'tools', 'live_scan.py')], { timeout: 120_000 });
    // The org-chart map is built on top of the fresh scan (about 3s, read-only on the Mac).
    await run('python3', [path.join(foundationRoot(), 'tools', 'build_org_map.py')], { timeout: 120_000 });
  });
}

export async function refreshLiveScanIfStale(maxAgeMs: number): Promise<void> {
  if ((await ageMs(liveScanFile())) > maxAgeMs) await runLiveScan();
}

let lastWriterRun = 0;

/** Ask the Director's trace writer (read-only on its runtime, about 0.1s) to pick up newly finished writes. */
async function runDirectorTraceWriter(): Promise<void> {
  const writer = path.join(os.homedir(), 'Alex-Director', 'scripts', 'export-trace-receipts.py');
  if (Date.now() - lastWriterRun < 55_000 || !existsSync(writer)) return;
  lastWriterRun = Date.now();
  await once('director-trace-writer', async () => {
    await run('python3', [writer], { timeout: 30_000 });
  });
}

/** Re-import Director traces only when the export file changed (size or modified time). */
export async function refreshDirectorTracesIfChanged(): Promise<void> {
  await runDirectorTraceWriter().catch(() => undefined); // a writer failure never blocks the map
  const receipts = directorReceipts();
  const stampFile = path.join(localDataDir(), 'director-traces.stamp');
  let fingerprint: string;
  try {
    const s = await stat(receipts);
    fingerprint = `${s.size}:${Math.floor(s.mtimeMs)}`;
  } catch {
    return; // no export yet: nothing to load
  }
  const previous = await readFile(stampFile, 'utf8').catch(() => '');
  if (previous.trim() === fingerprint) return;
  await once('director-traces', async () => {
    await run('python3', [path.join(foundationRoot(), 'tools', 'load_director_traces.py')], { timeout: 120_000 });
    ensureLocalDataDir();
    await writeFile(stampFile, fingerprint);
  });
}
