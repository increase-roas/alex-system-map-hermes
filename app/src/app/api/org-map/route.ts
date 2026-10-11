import { readFile } from 'node:fs/promises';

import { NextResponse } from 'next/server';

import { orgMapFile, refreshLiveScanIfStale } from '@/lib/server/auto-refresh';

/** Org-chart map (live scan + matched catalog). Served instantly; rebuilt with the scan every 2 minutes. */
export async function GET() {
  let body: string | null = await readFile(orgMapFile(), 'utf8').catch(() => null);
  if (!body) {
    await refreshLiveScanIfStale(0).catch(() => undefined);
    body = await readFile(orgMapFile(), 'utf8').catch(() => null);
  } else {
    void refreshLiveScanIfStale(2 * 60_000).catch(() => undefined);
  }
  if (!body) return NextResponse.json({ error: 'Map not built yet. Press Rescan.' }, { status: 404 });
  return new NextResponse(body, { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
}
