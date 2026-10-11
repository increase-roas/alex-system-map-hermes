import { NextResponse } from 'next/server';

import { ensureServiceInitialized, runLocalService } from '@/lib/server/python';

export async function GET() {
  await ensureServiceInitialized();
  const payload = await runLocalService(['workflow-templates']);
  return NextResponse.json(payload);
}
