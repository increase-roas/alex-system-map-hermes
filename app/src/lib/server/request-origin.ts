// Pure request-boundary checks, shared by Edge middleware and Node routes.
const LOCAL_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]']);
export function requestHost(value: string | null): string | null {
  if (!value) return null;
  try { return new URL(value.includes('://') ? value : `http://${value}`).hostname; }
  catch { return null; }
}
export function isLocalRequest(request: Request): boolean {
  // A proxied identity stays remote even if the client spoofs the Host header.
  if (request.headers.has('tailscale-user-login')) return false;
  if (!LOCAL_HOSTS.has(requestHost(request.headers.get('host')) ?? '')) return false;
  if (request.headers.get('sec-fetch-site') === 'cross-site') return false;
  const origin = request.headers.get('origin');
  return !origin || LOCAL_HOSTS.has(requestHost(origin) ?? '');
}
