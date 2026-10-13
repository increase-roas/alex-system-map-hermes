import crypto from 'node:crypto';
import fs from 'node:fs';

import { ensureLocalDataDir, localDataDir } from './paths';
import { isLocalRequest } from './request-origin';

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
  fs.writeFileSync(file, JSON.stringify({ token, created_at: new Date().toISOString() }), { mode: 0o600 });
  return token;
}

export function assertMutationAuthorized(request: Request): void {
  if (!isLocalRequest(request)) {
    throw new Response('Mutations allowed on loopback only', { status: 403 });
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
