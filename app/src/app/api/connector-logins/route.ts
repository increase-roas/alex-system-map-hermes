import {
  connectorLoginsAgeMs,
  readConnectorLogins,
  runConnectorLoginsExport,
} from '@/lib/server/connector-logins';
import { mutationAuthError } from '@/lib/server/local-auth';

// The alarm (health_check.py) runs every 30 min; the view refreshes a little faster when someone looks.
const STALE_AFTER_MS = 10 * 60_000;

/** Latest Composio login snapshot (no secrets: toolkit, ids, alias, status, dates). Refreshes itself when stale. */
export async function GET() {
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
