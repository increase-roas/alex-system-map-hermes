import { createHash } from 'node:crypto';
import { readFile, stat } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import {
  ROTATION_WHY,
  STALE_MS,
  badges,
  boardCounts,
  directorMissions,
  fixNowItem,
  freshness,
  needsAlex,
  parseParity,
  progressTail,
  spendView,
  type CeoDashboard,
  type FixNowItem,
  type Source,
  type Ticket,
} from '@/app/explorer/ceo-dashboard';

import { readConnectorLogins } from './connector-logins';
import { LANGFUSE_HOST, PROJECTS } from './langfuse';
import { screenParsedValue, screenServiceText } from './python';

// Read-only: every file is read fresh on each request and never written. Paths can be pointed at fixtures by env.
const agentsHome = () => path.resolve(process.env.AGENTS_HOME ?? path.join(os.homedir(), '.agents'));
const directorHome = () => path.resolve(process.env.DIRECTOR_HOME ?? path.join(os.homedir(), 'Alex-Director'));

const display = (p: string) => p.replace(os.homedir(), '~');

async function readSource(file: string, staleAfterMs: number): Promise<{ text: string | null; source: Source }> {
  try {
    const [text, st] = await Promise.all([readFile(file, 'utf8'), stat(file)]);
    const modified = st.mtimeMs;
    return { text, source: { path: display(file), read: true, modified_at: new Date(modified).toISOString(), freshness: freshness(modified, Date.now(), staleAfterMs) } };
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code ?? 'read failed';
    return { text: null, source: { path: display(file), read: false, modified_at: null, freshness: 'unknown', note: `could not read (${code})` } };
  }
}

const sha8 = (line: string) => createHash('sha1').update(line.trim()).digest('hex').slice(0, 8);

function safeSpend(doc: unknown) {
  try {
    return spendView(doc);
  } catch {
    return spendView(null); // a snapshot that breaks the view is unknown, never a crashed dashboard
  }
}

export async function buildCeoDashboard(): Promise<CeoDashboard> {
  const A = agentsHome();
  const sources: Record<string, Source> = {};

  const board = await readSource(path.join(A, 'board', 'tasks.json'), STALE_MS.board);
  sources.board = board.source;
  let tickets: Ticket[] | null = null; // stays null unless the board parses and has a tickets array
  let boardMissions: CeoDashboard['missions'] = [];
  if (board.text) {
    try {
      const parsed = screenParsedValue(JSON.parse(board.text)) as { tickets?: Ticket[]; missions?: Record<string, { status?: string }> };
      if (Array.isArray(parsed.tickets) && parsed.tickets.every((t) => t && typeof t === 'object' && typeof t.id === 'string')) tickets = parsed.tickets;
      else sources.board = { ...board.source, freshness: 'unknown', note: 'no valid tickets array' };
      boardMissions = Object.entries(parsed.missions ?? {}).map(([name, m]) => ({ name, status: String(m?.status ?? 'unknown'), priority: null, source: 'board' as const }));
    } catch {
      sources.board = { ...board.source, read: false, freshness: 'unknown', note: 'not valid JSON' };
    }
  }

  const progress = await readSource(path.join(A, 'board', 'progress.md'), STALE_MS.board);
  sources.progress = progress.source;

  const director = await readSource(path.join(directorHome(), 'DIRECTOR_STATE.md'), STALE_MS.director);
  sources.director = director.source;

  const parity = await readSource(path.join(A, 'board', 'parity.md'), STALE_MS.parity);
  sources.parity = parity.source;

  let fixNow: FixNowItem[] | null = [];
  const queues: [string, string][] = [['correction', 'lesson-candidates.jsonl'], ['session', 'session-reviews.jsonl']];
  for (const [kind, name] of queues) {
    const q = await readSource(path.join(A, 'runtime', name), STALE_MS.fix_now);
    sources[`fix_now_${kind}`] = q.source;
    if (q.text === null) {
      fixNow = null; // one queue unreadable: the count is unknown, not zero
      continue;
    }
    for (const line of q.text.split('\n')) {
      if (!line.trim() || fixNow === null) continue;
      const item = fixNowItem(kind, sha8(line), line);
      if (item) fixNow.push({ ...item, text: screenServiceText(item.text) });
    }
  }

  const spendFile = await readSource(path.join(A, 'runtime', 'spend', 'latest.json'), STALE_MS.spend);
  sources.spend = spendFile.source;
  let spendDoc: unknown = null;
  if (spendFile.text) {
    try {
      spendDoc = screenParsedValue(JSON.parse(spendFile.text));
    } catch {
      sources.spend = { ...spendFile.source, freshness: 'unknown', note: 'not valid JSON' };
    }
  }

  let logins: CeoDashboard['logins'] = null;
  const snap = (await readConnectorLogins()) as {
    generated_at?: string;
    summary?: { total: number; not_active: number };
    groups?: { toolkit: string; accounts: { alias: string | null; word_id: string; status: string }[] }[];
  } | null;
  if (snap?.summary && Array.isArray(snap.groups)) {
    const at = snap.generated_at ? Date.parse(snap.generated_at) : NaN;
    sources.logins = { path: 'app/.data/connector-logins.json (Composio connected_accounts)', read: true, modified_at: snap.generated_at ?? null, freshness: freshness(Number.isFinite(at) ? at : null, Date.now(), STALE_MS.logins) };
    logins = {
      total: snap.summary.total,
      not_active: snap.summary.not_active,
      bad: snap.groups.flatMap((g) => g.accounts.filter((a) => a.status !== 'ACTIVE').map((a) => ({ toolkit: g.toolkit, name: a.alias || a.word_id, status: a.status }))),
    };
  } else {
    sources.logins = { path: 'app/.data/connector-logins.json', read: false, modified_at: null, freshness: 'unknown', note: 'no snapshot yet; open the Connector logins tab to build one' };
  }

  return {
    generated_at: new Date().toISOString(),
    sources,
    board: tickets ? boardCounts(tickets) : null,
    missions: [...boardMissions, ...(director.text ? directorMissions(director.text) : [])],
    needs_alex: tickets ? needsAlex(tickets) : null,
    badges: tickets ? badges(tickets) : null,
    progress_tail: progress.text ? progressTail(progress.text) : [],
    parity: parity.text ? parseParity(parity.text) : null,
    fix_now: fixNow,
    logins,
    spend: {
      ...safeSpend(spendDoc),
      langfuse_links: Object.values(PROJECTS).map((p) => ({ label: `Langfuse ${p.label}: cost dashboard`, url: `${LANGFUSE_HOST}/project/${p.projectId}/dashboards` })),
    },
    rotation: { state: 'unknown', why: ROTATION_WHY },
  };
}
