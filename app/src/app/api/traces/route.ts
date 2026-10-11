import { NextResponse } from 'next/server';

import { refreshDirectorTracesIfChanged } from '@/lib/server/auto-refresh';
import { ensureServiceInitialized, runLocalService } from '@/lib/server/python';

export async function GET() {
  await ensureServiceInitialized();
  // New Director export on disk? Load it before listing (no script to run by hand).
  await refreshDirectorTracesIfChanged().catch(() => undefined);
  const payload = await runLocalService(['trace-list']);
  if (payload && typeof payload === 'object' && 'traces' in (payload as object)) {
    return NextResponse.json(payload);
  }
  return NextResponse.json({ traces: payload, diagnostic_marker: 'LOCAL-SCREENING-OK' });
}
