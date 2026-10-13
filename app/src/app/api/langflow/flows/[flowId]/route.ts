import { fail, ok, readJson, screenDeep } from '@/lib/langflow/api';
import { builtinCodeHash, componentTemplate } from '@/lib/langflow/catalog';
import { applyEdits, editSubject, executionPlan, problemsHaveErrors, toCanvas, type EditContext, type FlowEdit, type JsonValue, type RunContext, validateFlow } from '@/lib/langflow/model';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { runnerConfig } from '@/lib/langflow/runner';
import { isValidFlowId, readFlow, saveFlow, StoreConflictError } from '@/lib/langflow/store';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type Params = { params: Promise<{ flowId: string }> };

function editContext(): EditContext {
  const cfg = runnerConfig();
  return { template: (type) => componentTemplate(cfg, type) };
}

function runContext(): RunContext {
  const cfg = runnerConfig();
  return { builtinCodeHash: (type) => builtinCodeHash(cfg, type) };
}

function position(value: unknown): { x: number; y: number } | null {
  const p = value as Record<string, unknown> | undefined;
  if (!p || typeof p !== 'object' || typeof p.x !== 'number' || typeof p.y !== 'number') return null;
  return { x: p.x, y: p.y };
}

/** Accepts only the edit shapes the canvas can make. Anything else is refused before it reaches the model. */
function parseEdit(value: unknown): FlowEdit | null {
  if (!value || typeof value !== 'object') return null;
  const e = value as Record<string, unknown>;
  if (e.kind === 'disconnect') {
    return typeof e.edgeId === 'string' && e.edgeId.length <= 2000 ? { kind: 'disconnect', edgeId: e.edgeId } : null;
  }
  if (typeof e.nodeId !== 'string' || e.nodeId.length > 200) return null;
  if (e.kind === 'deleteNode') return { kind: 'deleteNode', nodeId: e.nodeId };
  if (e.kind === 'connect') {
    const ok = [e.sourceOutput, e.target, e.targetInput].every((v) => typeof v === 'string' && v.length > 0 && v.length <= 200);
    if (!ok || (e.targetLoop !== undefined && typeof e.targetLoop !== 'boolean')) return null;
    return { kind: 'connect', nodeId: e.nodeId, sourceOutput: e.sourceOutput as string, target: e.target as string, targetInput: e.targetInput as string, ...(e.targetLoop === true ? { targetLoop: true } : {}) };
  }
  if (e.kind === 'move') {
    const p = position(e.position);
    return p ? { kind: 'move', nodeId: e.nodeId, position: p } : null;
  }
  if (e.kind === 'addNode' && typeof e.componentType === 'string' && e.componentType.length <= 120) {
    const p = position(e.position);
    return p ? { kind: 'addNode', nodeId: e.nodeId, componentType: e.componentType, position: p } : null;
  }
  if (e.kind === 'rename' && typeof e.label === 'string') {
    return { kind: 'rename', nodeId: e.nodeId, label: e.label };
  }
  if (e.kind === 'setField' && typeof e.field === 'string' && e.field.length <= 200) {
    const v = e.value;
    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
      return { kind: 'setField', nodeId: e.nodeId, field: e.field, value: v };
    }
    // JSON settings (dict, table): an object or a list, already parsed from the request body.
    if (v !== null && typeof v === 'object') return { kind: 'setField', nodeId: e.nodeId, field: e.field, value: v as JsonValue };
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
  const plan = executionPlan(stored.flow, runContext());
  const runnable = !problemsHaveErrors(problems) && plan.blockers.length === 0 && plan.hasChatOutput;
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
  const b = body.value as { expectedHash?: unknown; edits?: unknown; dryRun?: unknown };
  if (typeof b.expectedHash !== 'string' || !Array.isArray(b.edits) || b.edits.length > 500 || (b.dryRun !== undefined && typeof b.dryRun !== 'boolean')) {
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
  const { flow, applied, rejected } = applyEdits(stored.flow, edits, editContext());
  if (rejected.length > 0) {
    return fail(422, 'Some edits are not allowed, so nothing was saved.', {
      rejected: rejected.map((r) => ({ kind: r.edit.kind, nodeId: editSubject(r.edit), index: edits.indexOf(r.edit), reason: r.reason })),
    });
  }
  if (b.dryRun === true) {
    // Preview only: the same rules as a save, nothing written.
    return ok(screenDeep({ hash: stored.hash, applied, dryRun: true, canvas: toCanvas(flow), problems: validateFlow(flow), plan: executionPlan(flow, runContext()) }));
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
