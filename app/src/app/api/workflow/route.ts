import { NextResponse } from 'next/server';

import { assertMutationAuthorized } from '@/lib/server/local-auth';
import { LocalServiceError, ensureServiceInitialized, runLocalService } from '@/lib/server/python';

function jsonError(message: string, status: number, extra?: Record<string, unknown>) {
  return NextResponse.json(
    { error: message, screened: true, ...extra },
    { status, headers: { 'Content-Type': 'application/json' } },
  );
}

export async function GET() {
  await ensureServiceInitialized();
  const payload = await runLocalService(['list-jobs']);
  if (payload && typeof payload === 'object' && 'jobs' in (payload as object)) {
    return NextResponse.json(payload, { headers: { 'Content-Type': 'application/json' } });
  }
  return NextResponse.json(
    { jobs: payload, diagnostic_marker: 'LOCAL-SCREENING-OK' },
    { headers: { 'Content-Type': 'application/json' } },
  );
}

export async function POST(request: Request) {
  try {
    assertMutationAuthorized(request);
  } catch (err) {
    if (err instanceof Response) {
      const text = await err.text();
      return jsonError(text || 'authorization failed', err.status);
    }
    return jsonError(err instanceof Error ? err.message : 'authorization failed', 401);
  }
  try {
    await ensureServiceInitialized();
    const body = await request.text();
    const result = await runLocalService(['apply'], body);
    return NextResponse.json(result, { headers: { 'Content-Type': 'application/json' } });
  } catch (err) {
    if (err instanceof LocalServiceError) {
      return jsonError(err.message, err.exitCode && err.exitCode >= 400 ? err.exitCode : 502, {
        payload: err.payload,
      });
    }
    return jsonError(err instanceof Error ? err.message : 'workflow apply failed', 500);
  }
}
