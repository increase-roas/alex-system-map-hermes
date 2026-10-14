// The real Langflow app, running on this Mac, so a flow built here can be opened and run there
// (including AI, internet and file components, which never run in the dashboard).
//
// Only a loopback address is accepted (LANGFLOW_SERVER_URL, default http://127.0.0.1:7860): flows are never
// sent off this machine. Langflow must run with LANGFLOW_AUTO_LOGIN=True (single local user); the dashboard
// takes a session token from its /api/v1/auto_login and keeps no credential. Secrets are emptied before sending.
// Server only.

import { stripSecretsForImport, type LfFlow } from './model';

const LOOPBACK = new Set(['127.0.0.1', 'localhost', '[::1]']);
const TIMEOUT_MS = 8_000;

export type LangflowServer = { url: string } | { url: null; reason: string };

export function langflowServer(env: NodeJS.ProcessEnv = process.env): LangflowServer {
  const raw = env.LANGFLOW_SERVER_URL || 'http://127.0.0.1:7860';
  let u: URL;
  try {
    u = new URL(raw);
  } catch {
    return { url: null, reason: 'LANGFLOW_SERVER_URL is not a valid address.' };
  }
  if (!['http:', 'https:'].includes(u.protocol) || !LOOPBACK.has(u.hostname)) {
    return { url: null, reason: 'Langflow must run on this Mac (127.0.0.1); flows are never sent anywhere else.' };
  }
  return { url: u.origin };
}

async function call(url: string, init: RequestInit = {}): Promise<Response> {
  return fetch(url, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS), cache: 'no-store' });
}

/** True when Langflow answers its health check. */
export async function langflowReachable(server = langflowServer()): Promise<boolean> {
  if (!server.url) return false;
  try {
    const res = await call(`${server.url}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export type SendResult = { ok: true; id: string; url: string } | { ok: false; status: number; reason: string };

/** Sends a copy of the flow to Langflow as a new flow and returns the address of its editor page. */
export async function sendToLangflow(flow: LfFlow, name: string, server = langflowServer()): Promise<SendResult> {
  if (server.url === null) return { ok: false, status: 503, reason: server.reason };
  let token: string;
  try {
    const login = await call(`${server.url}/api/v1/auto_login`);
    const body = (await login.json().catch(() => ({}))) as { access_token?: unknown };
    if (!login.ok || typeof body.access_token !== 'string') {
      return { ok: false, status: 502, reason: 'Langflow is running but asks for a login. Start it with LANGFLOW_AUTO_LOGIN=True (see docs/LANGFLOW_DASHBOARD.md).' };
    }
    token = body.access_token;
  } catch {
    return { ok: false, status: 503, reason: "Langflow isn't running on this Mac. Start it with tools/langflow_server.sh, then try again." };
  }
  const clean = stripSecretsForImport(flow).flow;
  try {
    const res = await call(`${server.url}/api/v1/flows/`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
      body: JSON.stringify({ name, description: typeof clean.description === 'string' ? clean.description : '', data: clean.data }),
    });
    const body = (await res.json().catch(() => ({}))) as { id?: unknown; detail?: unknown };
    if (!res.ok || typeof body.id !== 'string') {
      return { ok: false, status: 502, reason: `Langflow did not accept the flow (HTTP ${res.status}).` };
    }
    return { ok: true, id: body.id, url: `${server.url}/flow/${encodeURIComponent(body.id)}` };
  } catch {
    return { ok: false, status: 503, reason: 'Langflow stopped answering while the flow was being sent.' };
  }
}
