import { NextResponse } from 'next/server';

import { runLocalService } from '@/lib/server/python';

export async function GET(request: Request) {
  const url = new URL(request.url);
  const path = url.searchParams.get('path');
  const recordId = url.searchParams.get('record_id');
  if (!path) {
    return NextResponse.json({ error: 'path query required' }, { status: 400 });
  }
  const state = await runLocalService([
    'catalog-edit-state',
    path,
    ...(recordId ? ['--record-id', recordId] : []),
  ]);
  return NextResponse.json(state);
}
