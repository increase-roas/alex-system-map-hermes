import { NextResponse } from 'next/server';

import { ensureServiceInitialized, runLocalService } from '@/lib/server/python';

type Params = { params: Promise<{ jobId: string }> };

export async function GET(_request: Request, { params }: Params) {
  const { jobId } = await params;
  await ensureServiceInitialized();
  const events = await runLocalService(['events', jobId]);
  return NextResponse.json({ events });
}
