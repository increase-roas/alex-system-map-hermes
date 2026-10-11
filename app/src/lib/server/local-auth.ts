import crypto from 'node:crypto';
import fs from 'node:fs';

import { ensureLocalDataDir, localDataDir } from './paths';

const TOKEN_FILE = 'local-token.json';

function tokenPath(): string {
  return `${localDataDir()}/${TOKEN_FILE}`;
}

export function getOrCreateLocalToken(): string {
  ensureLocalDataDir();
  const file = tokenPath();
  if (fs.existsSync(file)) {
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8')) as { token: string };
    return parsed.token;
  }
  const token = crypto.randomBytes(24).toString('hex');
  fs.writeFileSync(file, JSON.stringify({ token, created_at: new Date().toISOString() }));
  return token;
}

const LOCAL_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]']);

function hostName(value: string): string | null {
  try {
    return new URL(value.includes('://') ? value : `http://${value}`).hostname;
  } catch {
    return null;
  }
}

export function assertMutationAuthorized(request: Request): void {
  const host = hostName(request.headers.get('host') ?? '');
  if (!host || !LOCAL_HOSTS.has(host)) {
    throw new Response('Mutations allowed on loopback only', { status: 403 });
  }
  const origin = request.headers.get('origin');
  if (origin && !LOCAL_HOSTS.has(hostName(origin) ?? '')) {
    throw new Response('Origin not allowed', { status: 403 });
  }
  const token = request.headers.get('x-local-token');
  if (!token || token !== getOrCreateLocalToken()) {
    throw new Response('Missing or invalid local token', { status: 401 });
  }
}

/** Same check, returned as a JSON response instead of thrown (Next turns a thrown Response into a 500). */
export async function mutationAuthError(request: Request): Promise<Response | null> {
  try {
    assertMutationAuthorized(request);
    return null;
  } catch (err) {
    if (err instanceof Response) {
      return Response.json({ error: (await err.text()) || 'authorization failed' }, { status: err.status });
    }
    return Response.json({ error: 'authorization failed' }, { status: 401 });
  }
}
