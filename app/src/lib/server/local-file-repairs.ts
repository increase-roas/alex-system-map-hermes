import { spawn } from 'node:child_process';
import path from 'node:path';
import type { LocalRepairPreview, LocalRepairResult, LocalRepairSource } from '@/lib/types/local-files';
import { localFileIndex } from './local-files';
import { ensureLocalDataDir, foundationRoot, localDataDir } from './paths';

export type RepairRequest =
  | { action: 'preview'; file_id: string; expected_sha256: string; new_content: string }
  | { action: 'apply'; repair_id: string; proposal_sha256: string }
  | { action: 'undo'; repair_id: string };
type SourceRequest = { action: 'source'; file_id: string };
type RepairResponse = { status: number; data?: LocalRepairSource | LocalRepairPreview | LocalRepairResult; error?: string; code?: string };

export async function runLocalFileRepair(input: RepairRequest | SourceRequest): Promise<RepairResponse> {
  // Browser requests select only indexed IDs; root and state paths stay server-owned.
  await localFileIndex();
  ensureLocalDataDir();
  const args = [path.join(foundationRoot(), 'tools', 'local_file_repairs.py'), '--index', path.join(localDataDir(), 'local-files.json'), '--state', localDataDir()];
  return new Promise((resolve) => {
    const child = spawn('python3', args, { stdio: ['pipe', 'pipe', 'ignore'], env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
    let output = '';
    let settled = false;
    const finish = (value: RepairResponse) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    };
    const failed = () => finish({ status: 409, code: 'repair_unavailable', error: 'Repair operation interrupted; inspect source and private recovery state before continuing' });
    // Apply/Undo include bounded local generation, copy readback and Git publication.
    const timer = setTimeout(() => { child.kill('SIGKILL'); failed(); }, input.action === 'apply' || input.action === 'undo' ? 300_000 : 120_000);
    child.stdout.on('data', (chunk: Buffer) => {
      output += chunk.toString();
      if (Buffer.byteLength(output) > 2 * 1024 * 1024) { child.kill('SIGKILL'); failed(); }
    });
    child.on('error', failed);
    child.stdin.on('error', failed);
    child.on('close', (code) => {
      if (code !== 0) { failed(); return; }
      try {
        const result = JSON.parse(output) as RepairResponse;
        if (![200, 400, 409, 422].includes(result.status) || (!result.data && !result.error)) { failed(); return; }
        finish(result);
      } catch { failed(); }
    });
    child.stdin.end(JSON.stringify(input));
  });
}
