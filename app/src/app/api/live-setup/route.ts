import { readFile } from 'node:fs/promises';

import { NextResponse } from 'next/server';

import { liveScanFile, refreshLiveScanIfStale, runLiveScan } from '@/lib/server/auto-refresh';

const STALE_AFTER_MS = 2 * 60_000;

async function readScan() {
  try {
    return JSON.parse(await readFile(liveScanFile(), 'utf8'));
  } catch {
    return null;
  }
}

/** Latest live scan of Alex's Mac (names and paths only). Served instantly; refreshes itself when older than 2 minutes. */
export async function GET() {
  let scan = await readScan();
  if (!scan) {
    await refreshLiveScanIfStale(0).catch(() => undefined); // first ever load: wait for one scan
    scan = await readScan();
  } else {
    // Serve the last scan at once; refresh it in the background when it is over 2 minutes old.
    void refreshLiveScanIfStale(STALE_AFTER_MS).catch(() => undefined);
  }
  if (!scan) {
    return NextResponse.json({ error: 'No scan yet. Press Rescan.' }, { status: 404 });
  }
  return NextResponse.json(scan, { headers: { 'Cache-Control': 'no-store' } });
}

/** Rescan now. Read-only on the Mac; only rewrites .data/live-setup.json. */
export async function POST() {
  try {
    await runLiveScan();
  } catch (error) {
    return NextResponse.json({ error: `Scan failed: ${(error as Error).message.slice(0, 300)}` }, { status: 500 });
  }
  return NextResponse.json(await readScan());
}
