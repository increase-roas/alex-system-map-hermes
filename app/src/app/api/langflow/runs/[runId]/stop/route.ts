import { fail, ok } from '@/lib/langflow/api';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { stopRun } from '@/lib/langflow/runs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const RUN_ID = /^[0-9a-f-]{36}$/;

export async function POST(request: Request, { params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  if (!RUN_ID.test(runId)) return fail(404, 'No such run.');
  const c = resolveCaller(request.headers, loadAccess());
  const stop = authorize(c, 'stop');
  if (!stop.ok) return fail(stop.status, stop.reason);
  const stopped = stopRun(runId, c!.id);
  if (!stopped) return fail(404, 'That run is not running any more.');
  // The engine process was killed. The run record becomes "stopped" when the process exits.
  return ok({ stopped: true });
}
