import { NextResponse } from 'next/server';

import { ensureServiceInitialized, runLocalService } from '@/lib/server/python';

type Params = { params: Promise<{ traceId: string }> };

export async function GET(_request: Request, { params }: Params) {
  const { traceId } = await params;
  await ensureServiceInitialized();
  try {
    const payload = await runLocalService(['trace-get', traceId]);
    return NextResponse.json(payload);
  } catch {
    return NextResponse.json({ error: 'unknown trace' }, { status: 404 });
  }
}
