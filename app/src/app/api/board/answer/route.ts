import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';

import { NextResponse } from 'next/server';

import { type BoardTicket, waitingItems } from '@/lib/board/waiting';
import { mutationAuthError } from '@/lib/server/local-auth';
import { boardDir, boardScript } from '@/lib/server/paths';

export const dynamic = 'force-dynamic';

function runBoard(args: string[]): Promise<{ code: number; stderr: string }> {
  return new Promise((resolve) => {
    // Arguments go as a list (no shell). Output is not logged: it may contain Alex's words.
    execFile('python3', [boardScript(), ...args], { timeout: 30_000 }, (err, _stdout, stderr) => {
      resolve({ code: err ? ((err as { code?: number }).code ?? 1) : 0, stderr: String(stderr) });
    });
  });
}

export async function POST(request: Request) {
  const denied = await mutationAuthError(request);
  if (denied) return denied;

  let body: { id?: unknown; text?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Body must be JSON' }, { status: 400 });
  }
  const id = typeof body.id === 'string' ? body.id : '';
  const text = typeof body.text === 'string' ? body.text.trim() : '';
  if (!id || !text) {
    return NextResponse.json({ error: 'Need a ticket and an answer' }, { status: 400 });
  }

  // Re-check on the server: only answerable, non-gate tickets may be answered here.
  const raw = await fs.readFile(path.join(boardDir(), 'tasks.json'), 'utf8');
  const tickets = (JSON.parse(raw) as { tickets?: BoardTicket[] }).tickets ?? [];
  const item = waitingItems(tickets).find((w) => w.id === id);
  if (!item || !item.answerable) {
    return NextResponse.json({ error: 'That ticket is not waiting on an answer' }, { status: 409 });
  }
  if (item.gate) {
    return NextResponse.json({ error: 'Say yes in chat for this one.' }, { status: 403 });
  }

  const source = `dashboard (Alex) ${new Date().toISOString()}`;
  const result = await runBoard(['answer', id, '--source', source, '--text', text]);
  if (result.code !== 0) {
    return NextResponse.json({ error: result.stderr.trim().slice(0, 300) || 'board.py failed' }, { status: 502 });
  }
  return NextResponse.json({ ok: true, id, source });
}
