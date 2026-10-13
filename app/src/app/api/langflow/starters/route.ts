import { randomUUID } from 'node:crypto';

import { fail, ok, readJson } from '@/lib/langflow/api';
import { componentTemplate } from '@/lib/langflow/catalog';
import { applyEdits, problemsHaveErrors, validateFlow, type LfFlow } from '@/lib/langflow/model';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { runnerConfig } from '@/lib/langflow/runner';
import { STARTERS } from '@/lib/langflow/starters';
import { createFlow } from '@/lib/langflow/store';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const c = resolveCaller(request.headers, loadAccess());
  const read = authorize(c, 'read');
  if (!read.ok) return fail(read.status, read.reason);
  return ok({ starters: STARTERS.map(({ key, title, description, sampleInput }) => ({ key, title, description, sampleInput })) });
}

/** Creates a new saved flow from a starter, built from the installed engine's own templates. */
export async function POST(request: Request) {
  const c = resolveCaller(request.headers, loadAccess());
  const save = authorize(c, 'save');
  if (!save.ok) return fail(save.status, save.reason);
  const body = await readJson(request);
  if (!body.ok) return fail(body.status, body.message);
  const key = (body.value as { key?: unknown }).key;
  const starter = STARTERS.find((s) => s.key === key);
  if (!starter) return fail(422, 'No starter flow with that name.');
  const cfg = runnerConfig();
  const empty: LfFlow = { id: randomUUID(), name: starter.title, description: starter.description, data: { nodes: [], edges: [] } };
  const { flow, rejected } = applyEdits(empty, starter.edits(), { template: (t) => componentTemplate(cfg, t) });
  if (rejected.length) {
    return fail(503, 'This starter cannot be built with the installed engine.', { rejected: rejected.map((r) => r.reason) });
  }
  if (problemsHaveErrors(validateFlow(flow))) return fail(503, 'This starter has errors with the installed engine.');
  const created = createFlow(flow);
  return ok({ id: created.id, hash: created.hash, sampleInput: starter.sampleInput }, 201);
}
