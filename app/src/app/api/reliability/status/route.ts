import { NextResponse } from 'next/server';

import { ensureServiceInitialized, runLocalService } from '@/lib/server/python';

export async function GET() {
  await ensureServiceInitialized();
  const status = await runLocalService(['reliability-status']);
  return NextResponse.json(status);
}
