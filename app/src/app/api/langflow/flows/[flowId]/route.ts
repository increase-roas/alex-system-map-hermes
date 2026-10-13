import { fail, ok, readJson, screenDeep } from '@/lib/langflow/api';
import { applyEdits, executionPlan, problemsHaveErrors, toCanvas, type FlowEdit, validateFlow } from '@/lib/langflow/model';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { isValidFlowId, readFlow, saveFlow, StoreConflictError } from '@/lib/langflow/store';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type Params = { params: Promise<{ flowId: string }> };

/** Accepts only the three edit shapes the canvas can make. Anything else is refused before it reaches the model. */
function parseEdit(value: unknown): FlowEdit | null {
  if (!value || typeof value !== 'object') return null;
  const e = value as Record<string, unknown>;
  if (typeof e.nodeId !== 'string' || e.nodeId.length > 200) return null;
  if (e.kind === 'move') {
    const p = e.position as Record<string, unknown> | undefined;
    if (!p || typeof p.x !== 'number' || typeof p.y !== 'number') return null;
    return { kind: 'move', nodeId: e.nodeId, position: { x: p.x, y: p.y } };
  }
  if (e.kind === 'rename' && typeof e.label === 'string') {
    return { kind: 'rename', nodeId: e.nodeId, label: e.label };
  }
  if (e.kind === 'setField' && typeof e.field === 'string' && e.field.length <= 200) {
    const v = e.value;
    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
      return { kind: 'setField', nodeId: e.nodeId, field: e.field, value: v };
    }
  }
  return null;
}

export async function GET(request: Request, { params }: Params) {
  const { flowId } = await params;
  if (!isValidFlowId(flowId)) return fail(404, 'No such flow.');
  const c = resolveCaller(request.headers, loadAccess());
  const read = authorize(c, 'read', flowId);
  if (!read.ok) return fail(read.status, read.reason);
  const stored = readFlow(flowId);
  if (!stored) return fail(404, 'No such flow.');
  const problems = validateFlow(stored.flow);
  const plan = executionPlan(stored.flow);
  const runnable = !problemsHaveErrors(problems) && plan.blockers.length === 0 && plan.hasChatInput && plan.hasChatOutput;
  return ok(
    screenDeep({
      id: flowId,
      hash: stored.hash,
      updatedAt: stored.updatedAt,
      canvas: toCanvas(stored.flow),
      problems,
      plan,
      runnable,
      caller: { canSave: !!c?.ops.includes('save'), canRun: !!c?.ops.includes('run') },
    }),
  );
}

/** All-or-nothing: if any edit is refused, nothing is saved and every refusal is returned. */
export async function PATCH(request: Request, { params }: Params) {
  const { flowId } = await params;
  if (!isValidFlowId(flowId)) return fail(404, 'No such flow.');
  const c = resolveCaller(request.headers, loadAccess());
  const save = authorize(c, 'save', flowId);
  if (!save.ok) return fail(save.status, save.reason);
  const body = await readJson(request);
  if (!body.ok) return fail(body.status, body.message);
  const b = body.value as { expectedHash?: unknown; edits?: unknown };
  if (typeof b.expectedHash !== 'string' || !Array.isArray(b.edits) || b.edits.length > 500) {
    return fail(422, 'Send expectedHash and a list of up to 500 edits.');
  }
  const edits: FlowEdit[] = [];
  for (const raw of b.edits) {
    const parsed = parseEdit(raw);
    if (!parsed) return fail(422, 'One of the edits has an unsupported shape, so nothing was saved.');
    edits.push(parsed);
  }
  const stored = readFlow(flowId);
  if (!stored) return fail(404, 'No such flow.');
  if (stored.hash !== b.expectedHash) {
    return fail(409, 'This flow changed since you opened it. Reload it, then apply your edits again.', { currentHash: stored.hash });
  }
  const { flow, applied, rejected } = applyEdits(stored.flow, edits);
  if (rejected.length > 0) {
    return fail(422, 'Some edits are not allowed, so nothing was saved.', {
      rejected: rejected.map((r) => ({ kind: r.edit.kind, nodeId: r.edit.nodeId, reason: r.reason })),
    });
  }
  if (applied === 0) return ok({ hash: stored.hash, updatedAt: stored.updatedAt, applied: 0, problems: validateFlow(stored.flow) });
  try {
    const saved = saveFlow(flowId, flow, stored.hash);
    return ok(screenDeep({ hash: saved.hash, updatedAt: saved.updatedAt, applied, problems: validateFlow(saved.flow) }));
  } catch (err) {
    if (err instanceof StoreConflictError) {
      return fail(409, err.message, { currentHash: err.currentHash });
    }
    throw err;
  }
}
