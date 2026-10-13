import { fail } from '@/lib/langflow/api';
import { redactForExport } from '@/lib/langflow/model';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { isValidFlowId, readFlow } from '@/lib/langflow/store';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: Request, { params }: { params: Promise<{ flowId: string }> }) {
  const { flowId } = await params;
  if (!isValidFlowId(flowId)) return fail(404, 'No such flow.');
  const read = authorize(resolveCaller(request.headers, loadAccess()), 'read', flowId);
  if (!read.ok) return fail(read.status, read.reason);
  const stored = readFlow(flowId);
  if (!stored) return fail(404, 'No such flow.');
  const { flow, redacted } = redactForExport(stored.flow);
  const slug = (typeof flow.name === 'string' ? flow.name : 'flow').replace(/[^a-z0-9]+/gi, '-').toLowerCase() || 'flow';
  return new Response(JSON.stringify(flow, null, 2) + '\n', {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Disposition': `attachment; filename="${slug}.flow.json"`,
      'Cache-Control': 'no-store',
      'X-Flow-Hash': stored.hash,
      'X-Secrets-Redacted': String(redacted),
    },
  });
}
