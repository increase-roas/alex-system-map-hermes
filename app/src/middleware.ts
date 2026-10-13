import { NextResponse, type NextRequest } from 'next/server';
import { isLocalRequest, requestHost } from './lib/server/request-origin';

// The server must bind loopback. Tailscale Serve is the trusted identity proxy.
export function middleware(request: NextRequest) {
  if (request.headers.has('tailscale-user-login')) {
    const host = requestHost(request.headers.get('host'));
    const read = request.method === 'GET' || request.method === 'HEAD';
    if (host?.endsWith('.ts.net') && request.headers.get('tailscale-user-login') && read) {
      return NextResponse.next();
    }
    return NextResponse.json({ error: 'Tailnet access is read-only' }, { status: 403 });
  }
  if (!isLocalRequest(request)) {
    return NextResponse.json({ error: 'local access only' }, { status: 403 });
  }
  return NextResponse.next();
}
export const config = { matcher: '/api/:path*' };
