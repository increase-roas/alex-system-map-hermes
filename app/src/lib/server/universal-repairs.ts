import { spawn } from 'node:child_process';
import path from 'node:path';
import { ensureLocalDataDir, foundationRoot, localDataDir } from './paths';

export type RepairBridgeResult = { status: number; data?: unknown; code?: string; error?: string };
export function runUniversalRepair(input: Record<string, unknown>): Promise<RepairBridgeResult> {
  ensureLocalDataDir();
  return new Promise((resolve) => {
    const child = spawn('python3', ['-B', path.join(foundationRoot(), 'tools', 'universal_repairs.py'), '--state', path.join(localDataDir(), 'universal-repairs')], { stdio: ['pipe', 'pipe', 'ignore'], env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
    let output = '';
    let settled = false;
    const finish = (result: RepairBridgeResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };
    const failure = () => finish({ status: 503, code: 'repair_unavailable', error: 'Repair status unavailable. Reopen the recorded job before another action.' });
    // Effects run in a detached Python worker and survive bridge/HTTP loss.
    const timer = setTimeout(() => { child.kill(); failure(); }, input.action === 'propose' ? 510_000 : 60_000);
    child.stdout.on('data', (chunk: Buffer) => {
      output += chunk.toString();
      if (Buffer.byteLength(output) > 2 * 1024 * 1024) { child.kill(); failure(); }
    });
    child.on('error', failure);
    child.stdin.on('error', failure);
    child.on('close', (code) => {
      if (code !== 0) return failure();
      try {
        const result = JSON.parse(output) as RepairBridgeResult;
        if (![200, 400, 404, 409, 422, 503].includes(result.status)) return failure();
        finish(result);
      } catch { failure(); }
    });
    child.stdin.end(JSON.stringify(input));
  });
}

export async function repairResponse(input: Record<string, unknown>): Promise<Response> {
  const result = await runUniversalRepair(input);
  return Response.json(result.data ?? { error: result.error, code: result.code }, { status: result.status, headers: { 'Cache-Control': 'no-store' } });
}

export async function repairBody(request: Request): Promise<Record<string, unknown> | null> {
  if (!request.body) return null;
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const value = await reader.read();
      if (value.done) break;
      size += value.value.byteLength;
      if (size > 32 * 1024) { await reader.cancel(); return null; }
      chunks.push(value.value);
    }
    const parsed: unknown = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null;
  } catch { return null; }
}
export function invalidRepairRequest() {
  return Response.json({ code: 'invalid_request', error: 'Use the exact recorded repair identifiers and supported action.' }, { status: 400, headers: { 'Cache-Control': 'no-store' } });
}
