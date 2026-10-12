import { NextResponse, type NextRequest } from 'next/server';

// Every API route is local-only. Blocks DNS-rebinding reads (e.g. the token in
// /api/health) and cross-site POSTs (e.g. /api/live-setup Rescan).
const LOCAL_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]']);

function hostName(value: string | null): string | null {
  if (!value) return null;
  try {
    return new URL(value.includes('://') ? value : `http://${value}`).hostname;
  } catch {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const host = hostName(request.headers.get('host'));
  if (!host || !LOCAL_HOSTS.has(host)) {
    return NextResponse.json({ error: 'local access only' }, { status: 403 });
  }
  const origin = request.headers.get('origin');
  if (origin && origin !== 'null' && !LOCAL_HOSTS.has(hostName(origin) ?? '')) {
    return NextResponse.json({ error: 'origin not allowed' }, { status: 403 });
  }
  if (origin === 'null' && request.method !== 'GET') {
    return NextResponse.json({ error: 'origin not allowed' }, { status: 403 });
  }
  return NextResponse.next();
}

export const config = { matcher: '/api/:path*' };
