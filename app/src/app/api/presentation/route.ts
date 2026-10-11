import { NextResponse } from 'next/server';

import { mutationAuthError } from '@/lib/server/local-auth';
import { ensureServiceInitialized, runLocalService } from '@/lib/server/python';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const scope = searchParams.get('scope');
  const key = searchParams.get('key');
  if (!scope || !key) {
    return NextResponse.json({ error: 'scope and key required' }, { status: 400 });
  }
  await ensureServiceInitialized();
  const value = await runLocalService(['presentation-get', scope, key]);
  return NextResponse.json(value);
}

export async function PUT(request: Request) {
  const denied = await mutationAuthError(request);
  if (denied) return denied;
  const body = (await request.json()) as {
    scope: string;
    key: string;
    value: unknown;
  };
  if (!body.scope || !body.key) {
    return NextResponse.json({ error: 'scope and key required' }, { status: 400 });
  }
  await ensureServiceInitialized();
  const saved = await runLocalService([
    'presentation-set',
    body.scope,
    body.key,
    JSON.stringify(body.value),
  ]);
  return NextResponse.json(saved);
}
