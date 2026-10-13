import { fail, ok, readJson, screenDeep } from '@/lib/langflow/api';
import { parseFlowInput, problemsHaveErrors, stripSecretsForImport, validateFlow } from '@/lib/langflow/model';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { createFlow, listFlows } from '@/lib/langflow/store';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function caller(request: Request) {
  return resolveCaller(request.headers, loadAccess());
}

export async function GET(request: Request) {
  const c = caller(request);
  const read = authorize(c, 'read');
  if (!read.ok) return fail(read.status, read.reason);
  const allowed = listFlows().filter((f) => c && (c.flows === '*' || c.flows.includes(f.id)));
  return ok({ flows: screenDeep(allowed), caller: { canSave: !!c?.ops.includes('save') } });
}

export async function POST(request: Request) {
  const c = caller(request);
  const save = authorize(c, 'save');
  if (!save.ok) return fail(save.status, save.reason);
  const body = await readJson(request);
  if (!body.ok) return fail(body.status, body.message);
  const parsed = parseFlowInput(body.value);
  if (!parsed.ok) return fail(422, parsed.error);
  const stripped = stripSecretsForImport(parsed.flow);
  const problems = validateFlow(stripped.flow);
  if (problemsHaveErrors(problems)) {
    return fail(422, 'This file has errors that must be fixed before it can be saved.', { problems: screenDeep(problems) });
  }
  const created = createFlow(stripped.flow);
  return ok(
    {
      id: created.id,
      hash: created.hash,
      updatedAt: created.updatedAt,
      secretsRemoved: stripped.removed,
      problems: screenDeep(problems),
    },
    201,
  );
}
