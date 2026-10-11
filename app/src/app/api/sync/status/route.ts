import { NextResponse } from 'next/server';

import { ensureServiceInitialized, runLocalService } from '@/lib/server/python';

export async function GET() {
  await ensureServiceInitialized();
  await runLocalService(['sync-observe']);
  const status = await runLocalService(['sync-status']);
  return NextResponse.json(status);
}
