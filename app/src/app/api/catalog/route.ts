import { NextResponse } from 'next/server';

import { ensureServiceInitialized, runLocalService } from '@/lib/server/python';

export async function GET() {
  await ensureServiceInitialized();
  const bundle = await runLocalService(['catalog-export']);
  return NextResponse.json(bundle);
}
