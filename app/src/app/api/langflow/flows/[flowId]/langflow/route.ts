import { fail, ok } from '@/lib/langflow/api';
import { sendToLangflow } from '@/lib/langflow/langflow-server';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { isValidFlowId, readFlow } from '@/lib/langflow/store';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type Params = { params: Promise<{ flowId: string }> };

/** Owner only: sends a copy of the saved flow to Langflow on this Mac and returns its editor address. */
export async function POST(request: Request, { params }: Params) {
  const { flowId } = await params;
  if (!isValidFlowId(flowId)) return fail(404, 'No such flow.');
  const c = resolveCaller(request.headers, loadAccess());
  const save = authorize(c, 'save', flowId);
  if (!save.ok) return fail(save.status, save.reason);
  const stored = readFlow(flowId);
  if (!stored) return fail(404, 'No such flow.');
  const name = `${typeof stored.flow.name === 'string' ? stored.flow.name : 'Untitled flow'} (from dashboard)`;
  const sent = await sendToLangflow(stored.flow, name);
  if (!sent.ok) return fail(sent.status, sent.reason);
  return ok({ langflowId: sent.id, url: sent.url }, 201);
}
