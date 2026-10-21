import { spawn } from 'node:child_process';
import path from 'node:path';
import type { LocalRepairSuggestion } from '@/lib/types/local-files';
import { localFileIndex } from './local-files';
import { ensureLocalDataDir, foundationRoot, localDataDir } from './paths';

export type SuggestRequest = { action: 'suggest'; file_id: string; expected_sha256: string; finding_id: string | null };
type SuggestResponse = { status: number; data?: LocalRepairSuggestion; error?: string; code?: string };
// Keep across development module reloads as well as simultaneous route requests.
const globalAI = globalThis as typeof globalThis & { localFileAIRequests?: Map<string, Promise<SuggestResponse>> };
const requests = globalAI.localFileAIRequests ||= new Map<string, Promise<SuggestResponse>>();

export function runLocalFileSuggestion(input: SuggestRequest): Promise<SuggestResponse> {
  const key = JSON.stringify([input.file_id, input.expected_sha256, input.finding_id]);
  const existing = requests.get(key);
  if (existing) return existing;
  const pending = launch(input).finally(() => { if (requests.get(key) === pending) requests.delete(key); });
  requests.set(key, pending);
  return pending;
}

async function launch(input: SuggestRequest): Promise<SuggestResponse> {
  await localFileIndex();
  ensureLocalDataDir();
  const args = [path.join(foundationRoot(), 'tools', 'local_file_ai.py'), '--index', path.join(localDataDir(), 'local-files.json'), '--state', localDataDir()];
  return new Promise((resolve) => {
    const child = spawn('python3', args, { stdio: ['pipe', 'pipe', 'ignore'], detached: process.platform !== 'win32', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
    let output = '';
    let settled = false;
    const finish = (value: SuggestResponse) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    };
    const stop = () => {
      try { if (child.pid && process.platform !== 'win32') process.kill(-child.pid, 'SIGKILL'); else child.kill('SIGKILL'); } catch { /* Already exited. */ }
    };
    const failed = () => finish({ status: 503, code: 'ai_unavailable', error: 'AI analysis could not finish. No source changed; request a fresh analysis when available.' });
    const timer = setTimeout(() => { stop(); failed(); }, 135_000);
    child.stdout.on('data', (chunk: Buffer) => {
      output += chunk.toString();
      if (Buffer.byteLength(output) > 512 * 1024) { stop(); failed(); }
    });
    child.on('error', failed);
    child.stdin.on('error', () => { stop(); failed(); });
    child.on('close', (code) => {
      if (code !== 0) { failed(); return; }
      try {
        const result = JSON.parse(output) as SuggestResponse;
        if (![200, 400, 409, 422, 503].includes(result.status) || (!result.data && !result.error)) { failed(); return; }
        finish(result);
      } catch { failed(); }
    });
    child.stdin.end(JSON.stringify(input));
  });
}
