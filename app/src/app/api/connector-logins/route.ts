import {
  connectorLoginsAgeMs,
  readConnectorLogins,
  runConnectorLoginsExport,
} from '@/lib/server/connector-logins';
import { fail } from '@/lib/langflow/api';
import { loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { mutationAuthError } from '@/lib/server/local-auth';

// The alarm (health_check.py) runs every 30 min; the view refreshes a little faster when someone looks.
const STALE_AFTER_MS = 10 * 60_000;

/** Latest Composio login snapshot (no secrets: toolkit, ids, alias, status, dates). Refreshes itself when stale. */
export async function GET(request: Request) {
  // Owner on this Mac only (same gate as /api/ceo-dashboard): aliases, ids and login status stay off the tailnet.
  const caller = resolveCaller(request.headers, loadAccess());
  if (!caller || caller.network !== 'local' || !caller.ops.includes('save')) {
    return fail(403, 'Connector logins are only shown to the owner on this Mac.');
  }
  let snapshot = await readConnectorLogins();
  if (!snapshot) {
    try {
      await runConnectorLoginsExport(); // first ever load: wait for one export
    } catch (error) {
      return Response.json({ error: (error as Error).message }, { status: 500 });
    }
    snapshot = await readConnectorLogins();
  } else if ((await connectorLoginsAgeMs()) > STALE_AFTER_MS) {
    void runConnectorLoginsExport().catch(() => undefined); // serve now, refresh in the background
  }
  if (!snapshot) {
    return Response.json({ error: 'No snapshot yet. Press Refresh.' }, { status: 404 });
  }
  return Response.json(snapshot, { headers: { 'Cache-Control': 'no-store' } });
}

/** Refresh now. Read-only on Composio; only rewrites .data/connector-logins.json. */
export async function POST(request: Request) {
  const denied = await mutationAuthError(request);
  if (denied) return denied;
  try {
    await runConnectorLoginsExport();
  } catch (error) {
    return Response.json({ error: `Refresh failed: ${(error as Error).message}` }, { status: 500 });
  }
  return Response.json(await readConnectorLogins(), { headers: { 'Cache-Control': 'no-store' } });
}
