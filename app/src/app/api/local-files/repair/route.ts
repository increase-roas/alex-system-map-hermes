import { runLocalFileRepair, type RepairRequest } from '@/lib/server/local-file-repairs';
import { runLocalFileSuggestion, type SuggestRequest } from '@/lib/server/local-file-ai';
import { mutationAuthError } from '@/lib/server/local-auth';
import { isLocalRequest } from '@/lib/server/request-origin';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
const headers = { 'Cache-Control': 'no-store' };
const MAX_BODY = 192 * 1024;
const invalid = () => Response.json({ error: 'Use a supported repair action with its exact named text fields', code: 'invalid_request' }, { status: 400, headers });

export async function GET(request: Request) {
  if (!isLocalRequest(request)) return Response.json({ error: 'Local source repair is available on loopback only', code: 'nonlocal' }, { status: 403, headers });
  const url = new URL(request.url);
  if ([...url.searchParams.keys()].some((key) => key !== 'id') || url.searchParams.getAll('id').length !== 1) return invalid();
  const id = url.searchParams.get('id') || '';
  if (!/^[a-f0-9]{24}$/.test(id)) return invalid();
  try {
    const result = await runLocalFileRepair({ action: 'source', file_id: id });
    return Response.json(result.data || { error: result.error, code: result.code }, { status: result.status, headers });
  } catch {
    return Response.json({ error: 'Refresh the local inventory before reviewing this source', code: 'index_unavailable' }, { status: 409, headers });
  }
}

export async function POST(request: Request) {
  const denied = await mutationAuthError(request);
  if (denied) return denied;
  let value: unknown;
  try {
    if (Number(request.headers.get('content-length') || 0) > MAX_BODY) return invalid();
    if (!request.body) return invalid();
    const reader = request.body.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const item = await reader.read();
      if (item.done) break;
      size += item.value.byteLength;
      if (size > MAX_BODY) { await reader.cancel(); return invalid(); }
      chunks.push(item.value);
    }
    value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch { return invalid(); }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid();
  const fields = value as Record<string, unknown>;
  const keys: Record<string, string[]> = {
    suggest: ['action', 'file_id', 'expected_sha256', 'finding_id'],
    preview: ['action', 'file_id', 'expected_sha256', 'new_content'],
    apply: ['action', 'repair_id', 'proposal_sha256'],
    undo: ['action', 'repair_id'],
  };
  if (typeof fields.action !== 'string' || !Object.hasOwn(keys, fields.action)) return invalid();
  const expected = keys[fields.action];
  if (Object.keys(fields).length !== expected.length || expected.some((key) => key === 'finding_id' ? fields[key] !== null && typeof fields[key] !== 'string' : typeof fields[key] !== 'string')) return invalid();
  if (fields.action === 'preview' && (!/^[a-f0-9]{24}$/.test(String(fields.file_id)) || !/^[a-f0-9]{64}$/.test(String(fields.expected_sha256)) || Buffer.byteLength(String(fields.new_content)) > 65536)) return invalid();
  if (fields.action === 'suggest' && (!/^[a-f0-9]{24}$/.test(String(fields.file_id)) || !/^[a-f0-9]{64}$/.test(String(fields.expected_sha256)) || (fields.finding_id !== null && !/^[a-f0-9]{24}$/.test(String(fields.finding_id))))) return invalid();
  if (!['preview', 'suggest'].includes(String(fields.action)) && !/^[a-f0-9]{32}$/.test(String(fields.repair_id))) return invalid();
  if (fields.action === 'apply' && !/^[a-f0-9]{64}$/.test(String(fields.proposal_sha256))) return invalid();
  try {
    const result = fields.action === 'suggest' ? await runLocalFileSuggestion(value as SuggestRequest) : await runLocalFileRepair(value as RepairRequest);
    return Response.json(result.data || { error: result.error, code: result.code }, { status: result.status, headers });
  } catch {
    if (fields.action === 'suggest') return Response.json({ error: 'AI analysis is unavailable. No source changed; refresh the inventory and request a fresh analysis.', code: 'ai_unavailable' }, { status: 503, headers });
    return Response.json({ error: 'Local source repair is unavailable; inspect the inventory and private recovery state', code: 'repair_unavailable' }, { status: 409, headers });
  }
}
