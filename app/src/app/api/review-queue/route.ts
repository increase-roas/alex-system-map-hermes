import fs from 'node:fs/promises';

import { NextResponse } from 'next/server';

import { reviewQueuePath } from '@/lib/server/paths';

export const dynamic = 'force-dynamic';

// Read-only: serves exactly one file, the fix-now queue export.
export async function GET() {
  try {
    const raw = await fs.readFile(reviewQueuePath(), 'utf8');
    return NextResponse.json({ available: true, queue: JSON.parse(raw) });
  } catch {
    return NextResponse.json({ available: false, queue: null });
  }
}
