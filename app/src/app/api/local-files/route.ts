import { localFileContent, localFileIndex } from '@/lib/server/local-files';
import { mutationAuthError } from '@/lib/server/local-auth';
import { isLocalRequest } from '@/lib/server/request-origin';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
const headers = { 'Cache-Control': 'no-store' };

export async function GET(request: Request) {
  if (!isLocalRequest(request)) return Response.json({ error: 'Local files are available on loopback only' }, { status: 403, headers });
  const url = new URL(request.url);
  if ([...url.searchParams.keys()].some((key) => key !== 'id')) {
    return Response.json({ error: 'Only indexed file IDs are accepted' }, { status: 400, headers });
  }
  try {
    if (url.searchParams.has('id')) {
      const value = await localFileContent(url.searchParams.get('id') || '');
      return value ? Response.json(value, { headers }) : Response.json({ error: 'Unknown indexed file ID' }, { status: 404, headers });
    }
    return Response.json(await localFileIndex(), { headers });
  } catch {
    return Response.json({ error: 'Unable to read the bounded local file inventory' }, { status: 500, headers });
  }
}

export async function POST(request: Request) {
  const denied = await mutationAuthError(request);
  if (denied) return denied;
  try {
    return Response.json(await localFileIndex(true), { headers });
  } catch {
    return Response.json({ error: 'Unable to refresh the bounded local file inventory' }, { status: 500, headers });
  }
}
