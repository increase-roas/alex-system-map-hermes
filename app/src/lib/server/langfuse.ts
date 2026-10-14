// Read-only Langfuse traces for the Tracing tab. Server only: keys never leave this file.
//
// Data source: Observations API v2, GET /api/public/v2/observations. Langfuse v4 cloud answers 410 on
// GET /api/public/traces, and v2 observations is a real-time read path (no 10 minute delay).
// Parameter names (fields, limit, cursor, fromStartTime, toStartTime) and the field groups core, basic, usage,
// trace_context come from the OpenAPI spec https://cloud.langfuse.com/generated/api/openapi.yml
// (operation observations_getMany; reference https://api.reference.langfuse.com), read 2026-10-14.
// Cursor pagination: the next page cursor is in meta.cursor and is omitted on the last page.
import { execFile } from 'node:child_process';

import { screenText } from '@/lib/langflow/redact';

export const LANGFUSE_HOST = 'https://us.cloud.langfuse.com';
export const FETCH_TIMEOUT_MS = 10_000;
export const MAX_TRACES = 100;
const WINDOW_MS = 24 * 60 * 60 * 1000;
const PAGE_LIMIT = 1000;
const MAX_PAGES = 5;
const VAULT = 'r6z62bjyy3c5ipilbgs4lyakwi';

export type LangfuseProject = 'agents' | 'langflow';

export const PROJECTS: Record<LangfuseProject, { item: string; publicField: string; secretField: string; projectId: string; label: string }> = {
  // Item "Langfuse — Agents": field labels read from ~/.agents/tools/connectors/langfuse_otel_headers.py.
  agents: { item: 'xvpwk4vkwbmogmld2hxcq4pply', publicField: 'public_key', secretField: 'secret_key', projectId: 'cmv733aoq01e7ad0mfeqexnrx', label: 'Agents' },
  langflow: { item: 'rxoo6lpuxbca67oj4yofie45sm', publicField: 'public key', secretField: 'credential', projectId: 'cmv7mth3h01tjad0j3q7b0okl', label: 'Langflow' },
};

export const LATE_NOTE = 'Langfuse shows traces up to about 15 minutes late, so the newest runs may not be here yet.';

export function isProject(value: unknown): value is LangfuseProject {
  return value === 'agents' || value === 'langflow';
}

/** Strips anything shaped like a Langfuse key or an auth header, then the shared credential screen. */
export function redactLangfuse(value: string): string {
  const stripped = value
    .replace(/\b(?:sk|pk)-lf-[A-Za-z0-9_-]*/g, '[redacted key]')
    .replace(/\bBasic\s+[A-Za-z0-9+/=]{8,}/g, 'Basic [redacted]');
  return screenText(stripped);
}

/** Only the Langfuse US cloud host is ever called. */
export function assertAllowedHost(url: string): URL {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error('Blocked: not a valid URL.');
  }
  if (parsed.origin !== LANGFUSE_HOST) throw new Error('Blocked: only https://us.cloud.langfuse.com is allowed.');
  return parsed;
}

type KeyPair = { publicKey: string; secretKey: string };
const keyCache = new Map<LangfuseProject, KeyPair>();

export function clearKeyCache(): void {
  keyCache.clear();
}

function run(file: string, args: string[], env: Record<string, string | undefined>): Promise<string> {
  return new Promise((resolve, reject) => {
    // No shell. stderr is dropped so no secret-bearing text can come back through an error.
    execFile(file, args, { env: env as NodeJS.ProcessEnv, timeout: FETCH_TIMEOUT_MS, maxBuffer: 1_000_000, encoding: 'utf8' }, (err, stdout) => {
      if (err) reject(new Error('Could not read the Langfuse keys from 1Password.'));
      else resolve(String(stdout).trim());
    });
  });
}

async function readKeyPair(project: LangfuseProject): Promise<KeyPair> {
  const upper = project.toUpperCase();
  const envPublic = process.env[`LANGFUSE_${upper}_PUBLIC_KEY`];
  const envSecret = process.env[`LANGFUSE_${upper}_SECRET_KEY`];
  if (envPublic && envSecret) return { publicKey: envPublic, secretKey: envSecret };

  const cfg = PROJECTS[project];
  // Absolute path so a writable PATH entry cannot stand in for op and receive the service account token.
  const OP_BIN = process.env.LANGFUSE_OP_BIN ?? '/opt/homebrew/bin/op';
  const token = await run('/usr/bin/security', ['find-generic-password', '-a', 'connectors-sync', '-s', 'op-service-account-connectors-sync', '-w'], process.env);
  const home = process.env.HOME ?? '';
  const env: Record<string, string | undefined> = {
    PATH: '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin',
    HOME: home,
    OP_SERVICE_ACCOUNT_TOKEN: token,
    OP_BIOMETRIC_UNLOCK_ENABLED: 'false',
  };
  const publicKey = await run(OP_BIN, ['read', `op://${VAULT}/${cfg.item}/${cfg.publicField}`], env);
  const secretKey = await run(OP_BIN, ['read', `op://${VAULT}/${cfg.item}/${cfg.secretField}`], env);
  if (!publicKey.startsWith('pk-lf-') || !secretKey.startsWith('sk-lf-')) {
    throw new Error('The Langfuse keys in 1Password do not look right.');
  }
  return { publicKey, secretKey };
}

async function getKeys(project: LangfuseProject, refresh: boolean): Promise<KeyPair> {
  if (refresh) keyCache.delete(project);
  const cached = keyCache.get(project);
  if (cached) return cached;
  const pair = await readKeyPair(project);
  keyCache.set(project, pair);
  return pair;
}

export type Observation = {
  id?: string;
  traceId?: string | null;
  name?: string | null;
  traceName?: string | null;
  startTime?: string | null;
  endTime?: string | null;
  level?: string | null;
  totalCost?: number | null;
  parentObservationId?: string | null;
  isRootObservation?: boolean | null;
};

export type TraceRow = {
  traceId: string;
  name: string;
  startTime: string;
  durationMs: number | null;
  totalCost: number | null;
  hasError: boolean;
  observationCount: number;
};

const ms = (v?: string | null): number => {
  const t = v ? Date.parse(v) : NaN;
  return t;
};

/** Groups observations by trace id into one row per trace, newest first, at most `max` rows. */
export function buildTraceRows(observations: Observation[], max = MAX_TRACES): TraceRow[] {
  const groups = new Map<string, Observation[]>();
  for (const o of observations) {
    if (!o || typeof o.traceId !== 'string' || !o.traceId) continue;
    const list = groups.get(o.traceId) ?? [];
    list.push(o);
    groups.set(o.traceId, list);
  }
  const rows: TraceRow[] = [];
  for (const [traceId, list] of groups) {
    const starts = list.map((o) => ms(o.startTime)).filter((n) => Number.isFinite(n));
    if (!starts.length) continue;
    const first = Math.min(...starts);
    const ends = list.map((o) => ms(o.endTime)).filter((n) => Number.isFinite(n));
    const last = ends.length ? Math.max(...ends, ...starts) : null;
    const costs = list.map((o) => o.totalCost).filter((c): c is number => typeof c === 'number' && Number.isFinite(c));
    const rootObs = list.find((o) => o.isRootObservation === true) ?? list.find((o) => !o.parentObservationId);
    const earliest = [...list].sort((a, b) => ms(a.startTime) - ms(b.startTime))[0];
    const name = rootObs?.name || list.find((o) => o.traceName)?.traceName || earliest?.name || 'unnamed';
    rows.push({
      traceId,
      // Span names can carry prompt text: screen key-shaped strings and cap the length.
      name: redactLangfuse(typeof name === 'string' ? name : 'unnamed').slice(0, 200),
      startTime: new Date(first).toISOString(),
      durationMs: last === null ? null : Math.max(0, last - first),
      totalCost: costs.length ? Math.round(costs.reduce((a, b) => a + b, 0) * 1e6) / 1e6 : null,
      hasError: list.some((o) => (o.level ?? '').toUpperCase() === 'ERROR'),
      observationCount: list.length,
    });
  }
  rows.sort((a, b) => Date.parse(b.startTime) - Date.parse(a.startTime));
  return rows.slice(0, max);
}

export type TracesResult =
  | { ok: true; project: LangfuseProject; projectId: string; asOf: string; note: string; truncated: boolean; traces: TraceRow[] }
  | { ok: false; state: 'unknown'; reason: string; asOf: string; note: string };

const unknown = (reason: string): TracesResult => ({ ok: false, state: 'unknown', reason: redactLangfuse(reason), asOf: new Date().toISOString(), note: LATE_NOTE });

class AuthError extends Error {}

async function fetchPages(keys: KeyPair, now: number): Promise<{ observations: Observation[]; truncated: boolean }> {
  const auth = 'Basic ' + Buffer.from(`${keys.publicKey}:${keys.secretKey}`).toString('base64');
  const observations: Observation[] = [];
  let cursor: string | null = null;
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const url = assertAllowedHost(`${LANGFUSE_HOST}/api/public/v2/observations`);
    url.searchParams.set('fields', 'core,basic,usage,trace_context');
    url.searchParams.set('limit', String(PAGE_LIMIT));
    url.searchParams.set('fromStartTime', new Date(now - WINDOW_MS).toISOString());
    url.searchParams.set('toStartTime', new Date(now + 60_000).toISOString());
    if (cursor) url.searchParams.set('cursor', cursor);
    const res = await fetch(url, {
      headers: { Authorization: auth, Accept: 'application/json' },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
      cache: 'no-store',
    });
    if (res.status === 401 || res.status === 403) throw new AuthError();
    if (!res.ok) throw new Error(`Langfuse answered with status ${res.status}.`);
    const body = (await res.json()) as { data?: Observation[]; meta?: { cursor?: string | null } };
    if (Array.isArray(body.data)) observations.push(...body.data);
    cursor = body.meta?.cursor ?? null;
    if (!cursor) return { observations, truncated: false };
  }
  return { observations, truncated: true };
}

export async function loadTraces(project: LangfuseProject): Promise<TracesResult> {
  const now = Date.now();
  try {
    let keys: KeyPair;
    try {
      keys = await getKeys(project, false);
    } catch (e) {
      return unknown(e instanceof Error ? e.message : 'Could not read the Langfuse keys.');
    }
    let data: { observations: Observation[]; truncated: boolean };
    try {
      data = await fetchPages(keys, now);
    } catch (e) {
      if (!(e instanceof AuthError)) throw e;
      // 401: the cached keys may have been rotated. Read them again once.
      keys = await getKeys(project, true);
      data = await fetchPages(keys, now);
    }
    return {
      ok: true,
      project,
      projectId: PROJECTS[project].projectId,
      asOf: new Date().toISOString(),
      note: LATE_NOTE,
      truncated: data.truncated,
      traces: buildTraceRows(data.observations),
    };
  } catch (e) {
    if (e instanceof AuthError) return unknown('Langfuse refused the keys (401).');
    const name = e instanceof Error ? e.name : '';
    if (name === 'TimeoutError' || name === 'AbortError') return unknown('Langfuse did not answer within 10 seconds.');
    return unknown(e instanceof Error ? e.message : 'Langfuse could not be reached.');
  }
}
