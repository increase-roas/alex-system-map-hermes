import { NextResponse } from 'next/server';

import { runLocalService } from '@/lib/server/python';

type Params = { params: Promise<{ sourceId: string }> };

export async function GET(_request: Request, { params }: Params) {
  const { sourceId } = await params;
  try {
    const payload = await runLocalService(['read-source', sourceId]);
    return NextResponse.json(payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'read failed';
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
