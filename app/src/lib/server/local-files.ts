import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import type { LocalFileContent, LocalFileIndex } from '@/lib/types/local-files';
import { ensureLocalDataDir, foundationRoot, localDataDir } from './paths';

let inFlight: Promise<LocalFileIndex> | null = null;
const TTL_MS = 60_000;
const indexPath = () => path.join(localDataDir(), 'local-files.json');

function run(command: 'scan' | 'content', id?: string): Promise<unknown> {
  ensureLocalDataDir();
  const args = [path.join(foundationRoot(), 'tools', 'local_files.py'), command, '--index', indexPath()];
  if (id) args.push('--id', id);
  return new Promise((resolve, reject) => {
    const child = spawn('python3', args, { stdio: ['ignore', 'pipe', 'ignore'] });
    let output = '';
    let settled = false;
    const finish = (error?: Error, value?: unknown) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(value);
    };
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      finish(new Error('Local file scan exceeded its time limit'));
    }, 60_000);
    child.stdout.on('data', (chunk: Buffer) => {
      output += chunk.toString();
      if (output.length > 24 * 1024 * 1024) {
        child.kill('SIGKILL');
        finish(new Error('Local file response exceeded its size limit'));
      }
    });
    child.on('error', () => finish(new Error('Unable to start local file reader')));
    child.on('close', (code) => {
      if (code !== 0) { finish(new Error('Local file reader failed')); return; }
      try { finish(undefined, JSON.parse(output)); }
      catch { finish(new Error('Invalid local file reader response')); }
    });
  });
}

export async function localFileIndex(refresh = false): Promise<LocalFileIndex> {
  if (inFlight) return inFlight;
  if (!refresh) {
    try {
      const value = JSON.parse(fs.readFileSync(indexPath(), 'utf8')) as LocalFileIndex;
      const age = Date.now() - Date.parse(value.scanned_at);
      const scannerMtime = fs.statSync(path.join(foundationRoot(), 'tools', 'local_files.py')).mtimeMs;
      if (value.schema_version === 1 && age >= 0 && age < TTL_MS && fs.statSync(indexPath()).mtimeMs >= scannerMtime) return value;
    } catch { /* Missing or invalid snapshot gets rebuilt from selected roots. */ }
  }
  inFlight = run('scan').then((value) => value as LocalFileIndex).finally(() => { inFlight = null; });
  return inFlight;
}

export async function localFileContent(id: string): Promise<LocalFileContent | null> {
  if (!/^[a-f0-9]{24}$/.test(id)) return null;
  const index = await localFileIndex();
  if (!index.files.some((file) => file.id === id)) return null;
  return await run('content', id) as LocalFileContent;
}
