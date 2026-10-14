// Read-only. Owner on this Mac only (same rule as /api/langfuse/traces): the board holds needs, owners and
// mission state, so tailnet viewers get 403.
import { fail, ok } from '@/lib/langflow/api';
import { loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { buildCeoDashboard } from '@/lib/server/ceo-dashboard';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const caller = resolveCaller(request.headers, loadAccess());
  if (!caller || caller.network !== 'local' || !caller.ops.includes('save')) {
    return fail(403, 'The CEO dashboard is only shown to the owner on this Mac.');
  }
  return ok(await buildCeoDashboard());
}
