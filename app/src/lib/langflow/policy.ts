// Who may do what, to which flow, from which network.
//
// Rules, in order:
//   1. Tailnet devices (requests carrying Tailscale-User-Login through `tailscale serve`) are read-only.
//      That is Alex's rule from 2026-10-12, enforced in src/middleware.ts for every other route.
//   2. Local callers on loopback are the owner when they send the local token. Without the token
//      they can read, not change.
//   3. Anything not granted is denied. A missing access file grants the owner everything on this Mac and nobody else.
//   4. Origin must be loopback when a browser sends one (blocks cross-site POSTs).

import fs from 'node:fs';
import path from 'node:path';

import { getOrCreateLocalToken } from '../server/local-auth';
import { localDataDir } from '../server/paths';

export type Operation = 'read' | 'save' | 'run' | 'stop';
export const ALL_OPERATIONS: Operation[] = ['read', 'save', 'run', 'stop'];
const TAILNET_OPERATIONS: Operation[] = ['read'];
const LOCAL_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]']);

export type AccessEntry = { ops: Operation[]; flows: string[] | '*' };
export type AccessConfig = { owner: AccessEntry; tailnet: Record<string, AccessEntry>; loadError: string | null };

export const DEFAULT_ACCESS: AccessConfig = {
  owner: { ops: ALL_OPERATIONS, flows: '*' },
  tailnet: {},
  loadError: null,
};

export function accessFile(root = localDataDir()): string {
  return path.join(root, 'langflow', 'access.json');
}

/** Missing file: defaults. Unreadable or malformed file: deny everything and say why. */
export function loadAccess(root = localDataDir()): AccessConfig {
  const file = accessFile(root);
  if (!fs.existsSync(file)) return DEFAULT_ACCESS;
  try {
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8')) as Partial<AccessConfig>;
    const owner = normalizeEntry(parsed.owner);
    const tailnet: Record<string, AccessEntry> = {};
    for (const [login, entry] of Object.entries(parsed.tailnet ?? {})) {
      tailnet[login.toLowerCase()] = normalizeEntry(entry, TAILNET_OPERATIONS);
    }
    return { owner, tailnet, loadError: null };
  } catch {
    return { owner: { ops: [], flows: [] }, tailnet: {}, loadError: 'access.json is unreadable, so every operation is denied until it is fixed.' };
  }
}

function normalizeEntry(entry: unknown, allowed: Operation[] = ALL_OPERATIONS): AccessEntry {
  const e = (entry ?? {}) as { ops?: unknown; flows?: unknown };
  const ops = Array.isArray(e.ops) ? e.ops.filter((o): o is Operation => (ALL_OPERATIONS as string[]).includes(String(o))) : [];
  const flows = e.flows === '*' ? '*' : Array.isArray(e.flows) ? e.flows.filter((f): f is string => typeof f === 'string') : [];
  return { ops: ops.filter((o) => allowed.includes(o)), flows };
}

export type Caller = {
  id: string;
  network: 'local' | 'tailnet';
  ops: Operation[];
  flows: string[] | '*';
};

function hostName(value: string | null): string | null {
  if (!value) return null;
  try {
    return new URL(value.includes('://') ? value : `http://${value}`).hostname;
  } catch {
    return null;
  }
}

export function resolveCaller(headers: Headers, config: AccessConfig = loadAccess()): Caller | null {
  if (config.loadError) return null;
  const login = headers.get('tailscale-user-login');
  if (login) {
    const entry = config.tailnet[login.toLowerCase()];
    if (!entry) return null;
    return { id: `tailnet:${login.toLowerCase()}`, network: 'tailnet', ops: entry.ops.filter((o) => TAILNET_OPERATIONS.includes(o)), flows: entry.flows };
  }
  const host = hostName(headers.get('host'));
  if (!host || !LOCAL_HOSTS.has(host)) return null;
  const origin = headers.get('origin');
  if (origin && origin !== 'null' && !LOCAL_HOSTS.has(hostName(origin) ?? '')) return null;
  if (origin === 'null') return null;
  const token = headers.get('x-local-token');
  if (token && token === getOrCreateLocalToken()) {
    return { id: 'owner', network: 'local', ops: config.owner.ops, flows: config.owner.flows };
  }
  // Loopback without the token: read only.
  return { id: 'local-reader', network: 'local', ops: ['read'], flows: '*' };
}

export type Decision = { ok: true } | { ok: false; status: number; reason: string };

export function authorize(caller: Caller | null, op: Operation, flowId?: string): Decision {
  if (!caller) {
    return { ok: false, status: 403, reason: 'This device is not allowed to use the Langflow panel.' };
  }
  if (!caller.ops.includes(op)) {
    if (caller.network === 'tailnet' && op !== 'read') {
      return { ok: false, status: 403, reason: 'Tailnet access is read-only (Alex, 2026-10-12). Changes and runs stay on the Mac.' };
    }
    if (caller.id === 'local-reader' && op !== 'read') {
      return { ok: false, status: 403, reason: 'Sign in to the local panel to change or run flows.' };
    }
    return { ok: false, status: 403, reason: `Not allowed to ${op} here.` };
  }
  if (flowId && caller.flows !== '*' && !caller.flows.includes(flowId)) {
    return { ok: false, status: 403, reason: 'Not allowed for this flow.' };
  }
  return { ok: true };
}
