import fs from 'node:fs/promises';
import path from 'node:path';

import { NextResponse } from 'next/server';

import { type BoardTicket, blockedSince, recentlyAnswered, waitingItems } from '@/lib/board/waiting';
import { getOrCreateLocalToken } from '@/lib/server/local-auth';
import { boardDir } from '@/lib/server/paths';
import { isLocalRequest } from '@/lib/server/request-origin';

export const dynamic = 'force-dynamic';

// Read-only view of the task board. Writes go through /api/board/answer -> board.py.
async function readProgress(): Promise<string> {
  try {
    return await fs.readFile(path.join(boardDir(), 'progress.md'), 'utf8');
  } catch {
    return '';
  }
}

export async function GET(request: Request) {
  // Only loopback viewers get the write token; tailnet viewers are read-only.
  const token = isLocalRequest(request) ? getOrCreateLocalToken() : '';
  try {
    const raw = await fs.readFile(path.join(boardDir(), 'tasks.json'), 'utf8');
    const tickets = (JSON.parse(raw) as { tickets?: BoardTicket[] }).tickets ?? [];
    return NextResponse.json({
      available: true,
      waiting: waitingItems(tickets, blockedSince(await readProgress())),
      answered: recentlyAnswered(tickets),
      token,
    });
  } catch {
    return NextResponse.json({ available: false, waiting: [], answered: [], token });
  }
}
