import { fail, ok, readJson, screenDeep } from '@/lib/langflow/api';
import { executionPlan, problemsHaveErrors, validateFlow } from '@/lib/langflow/model';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { engineLabel } from '@/lib/langflow/catalog';
import { runnerConfig } from '@/lib/langflow/runner';
import { beginRun, listRuns } from '@/lib/langflow/runs';
import { isValidFlowId, readFlow } from '@/lib/langflow/store';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type Params = { params: Promise<{ flowId: string }> };
const SESSION = /^[A-Za-z0-9-]{8,80}$/;
const KEY = /^[A-Za-z0-9_-]{8,80}$/;

export async function GET(request: Request, { params }: Params) {
  const { flowId } = await params;
  if (!isValidFlowId(flowId)) return fail(404, 'No such flow.');
  const c = resolveCaller(request.headers, loadAccess());
  const read = authorize(c, 'read', flowId);
  if (!read.ok) return fail(read.status, read.reason);
  const session = request.headers.get('x-browser-session');
  if (session && !SESSION.test(session)) return fail(422, 'The browser session id is malformed.');
  const runs = listRuns({ ownerId: c!.id, sessionNonce: session, flowId });
  return ok(screenDeep({ runs }));
}

export async function POST(request: Request, { params }: Params) {
  const { flowId } = await params;
  if (!isValidFlowId(flowId)) return fail(404, 'No such flow.');
  const c = resolveCaller(request.headers, loadAccess());
  const run = authorize(c, 'run', flowId);
  if (!run.ok) return fail(run.status, run.reason);

  const session = request.headers.get('x-browser-session');
  if (!session || !SESSION.test(session)) return fail(422, 'Start the run from the panel so the browser session id is sent.');
  const idempotencyKey = request.headers.get('idempotency-key');
  if (idempotencyKey !== null && !KEY.test(idempotencyKey)) return fail(422, 'The Idempotency-Key header is malformed.');

  const body = await readJson(request);
  if (!body.ok) return fail(body.status, body.message);
  const input = (body.value as { input?: unknown }).input;
  if (typeof input !== 'string' || input.trim().length === 0 || input.length > 2000) {
    return fail(422, 'Type a message of 1 to 2000 characters to run the flow.');
  }

  const stored = readFlow(flowId);
  if (!stored) return fail(404, 'No such flow.');
  const problems = validateFlow(stored.flow);
  if (problemsHaveErrors(problems)) {
    return fail(422, 'Fix the errors in this flow before running it.', { problems: screenDeep(problems) });
  }
  const plan = executionPlan(stored.flow);
  if (plan.blockers.length > 0) {
    return fail(422, 'This flow needs something this app does not run yet, so it was not started.', {
      blockers: screenDeep(plan.blockers.map((b) => ({ nodeId: b.nodeId, componentType: b.componentType, reason: b.reason }))),
    });
  }
  if (!plan.hasChatInput || !plan.hasChatOutput) {
    return fail(422, 'The flow needs a Chat Input and a Chat Output to run here.');
  }
  const cfg = runnerConfig();
  if (!cfg.lfxBin) {
    return fail(503, 'The Langflow engine is not configured on this Mac, so the flow was not started.');
  }

  let result;
  try {
    result = beginRun({
      ownerId: c!.id,
      sessionNonce: session,
      flowId,
      flowName: typeof stored.flow.name === 'string' ? stored.flow.name : 'Untitled flow',
      flowHash: stored.hash,
      flowUpdatedAt: stored.updatedAt,
      flowSnapshot: JSON.stringify(stored.flow),
      input,
      idempotencyKey,
      config: cfg,
      engineVersion: engineLabel(cfg),
    });
  } catch {
    return fail(500, 'The run could not be recorded, so it was not started.');
  }
  if (result.kind === 'busy') {
    return fail(409, 'This flow is already running. Wait for it to finish, or stop it.', { run: screenDeep(result.record) });
  }
  if (result.kind === 'duplicate') {
    return ok({ run: screenDeep(result.record), duplicate: true });
  }
  return ok({ run: screenDeep(result.record), duplicate: false }, 202);
}
