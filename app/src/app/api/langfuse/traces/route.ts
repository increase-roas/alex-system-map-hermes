// Read-only. Owner on this Mac only (same rule as server.langflow in /api/langflow/status: the caller needs the
// "save" operation and must be local). Tailnet viewers get 403, because the data holds run names and cost.
import { fail, ok } from '@/lib/langflow/api';
import { loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { isProject, loadTraces } from '@/lib/server/langfuse';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const caller = resolveCaller(request.headers, loadAccess());
  if (!caller || caller.network !== 'local' || !caller.ops.includes('save')) {
    return fail(403, 'Langfuse traces are only shown to the owner on this Mac.');
  }
  const project = new URL(request.url).searchParams.get('project');
  if (!isProject(project)) return fail(400, 'project must be agents or langflow.');
  return ok(await loadTraces(project));
}
