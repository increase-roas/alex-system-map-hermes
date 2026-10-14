// CEO dashboard (board ticket agent-ops-foundation-81, plan D4/D7): pure derivations over the raw source files.
// The server reads the real files on every request; nothing here stores or copies status.
// Every section carries its source path and freshness; a missing or unreadable source is "unknown", never a guess.

export type Freshness = 'fresh' | 'stale' | 'unknown';

export type Source = { path: string; read: boolean; modified_at: string | null; freshness: Freshness; note?: string };

export type Ticket = {
  id: string;
  mission?: string;
  title?: string;
  status?: string;
  owner?: string | null;
  blocked_on?: string;
  need?: string;
  updated?: string;
  link?: string;
};

export type NeedsAlex = {
  id: string;
  title: string;
  need: string;
  link: string | null; // deepest link from the source itself; null means the source carries none
  agent_prompt: string; // paste line that sends an agent to do it
};

export type AgentBadge = { owner: string; doing: string[]; blocked: string[]; done: number };

export type MissionRow = { name: string; status: string; priority: string | null; source: 'board' | 'director' };

export type ParityRow = { row: string; cells: Record<string, string> };

export type FixNowItem = { id: string; kind: string; text: string };

export type CeoDashboard = {
  generated_at: string;
  sources: Record<string, Source>;
  board: { counts: Record<string, number>; total: number } | null; // null = board unreadable or invalid: needs_alex and badges are unknown too
  missions: MissionRow[];
  needs_alex: NeedsAlex[] | null;
  badges: AgentBadge[] | null;
  progress_tail: string[];
  parity: { columns: string[]; rows: ParityRow[] } | null;
  fix_now: FixNowItem[] | null;
  logins: { total: number; not_active: number; bad: { toolkit: string; name: string; status: string }[] } | null;
  spend: { state: 'unknown'; why: string; langfuse_links: { label: string; url: string }[] };
  rotation: { state: 'unknown'; why: string };
};

export const STALE_MS = { board: 24 * 3600_000, director: 7 * 24 * 3600_000, parity: 7 * 24 * 3600_000, logins: 3600_000, fix_now: 7 * 24 * 3600_000 };

export function freshness(modifiedMs: number | null, nowMs: number, staleAfterMs: number): Freshness {
  if (modifiedMs === null || !Number.isFinite(modifiedMs)) return 'unknown';
  return nowMs - modifiedMs > staleAfterMs ? 'stale' : 'fresh';
}

const URL_RE = /https?:\/\/[^\s)>\]"']+/;

/** The first URL in the ticket's own link or need text. Never built from guesses. */
export function deepLink(t: Ticket): string | null {
  if (t.link && URL_RE.test(t.link)) return t.link.match(URL_RE)![0];
  const m = (t.need ?? '').match(URL_RE);
  return m ? m[0].replace(/[.,;]+$/, '') : null;
}

export function agentPrompt(t: Ticket): string {
  return `Board ticket ${t.id} (${t.title ?? ''}) is waiting on me. Read ~/.agents/board/tasks.json for it, take me to the exact page or do the agent part, and stop before any spend, delete or message to a person.`;
}

export function needsAlex(tickets: Ticket[]): NeedsAlex[] {
  return tickets
    .filter((t) => t.status !== 'done' && (t.owner === 'alex' || t.blocked_on === 'alex')) // same rule as board.py _summary
    .map((t) => ({ id: t.id, title: t.title ?? t.id, need: t.need ?? '(the ticket names no need text)', link: deepLink(t), agent_prompt: agentPrompt(t) }));
}

export function boardCounts(tickets: Ticket[]): { counts: Record<string, number>; total: number } {
  const counts: Record<string, number> = {};
  for (const t of tickets) counts[t.status ?? 'unknown'] = (counts[t.status ?? 'unknown'] ?? 0) + 1;
  return { counts, total: tickets.length };
}

/** One badge per owner (agent or lane), from the board's owner field only. */
export function badges(tickets: Ticket[]): AgentBadge[] {
  const by = new Map<string, AgentBadge>();
  for (const t of tickets) {
    if (!t.owner) continue;
    const b = by.get(t.owner) ?? { owner: t.owner, doing: [], blocked: [], done: 0 };
    if (t.status === 'doing') b.doing.push(t.id);
    else if (t.status === 'blocked') b.blocked.push(t.id);
    else if (t.status === 'done') b.done += 1;
    by.set(t.owner, b);
  }
  return [...by.values()].sort((a, b) => b.doing.length - a.doing.length || b.blocked.length - a.blocked.length || a.owner.localeCompare(b.owner));
}

/** "## Mission: X" blocks in DIRECTOR_STATE.md; the status line is shown as written (no parsing into our own words). */
export function directorMissions(md: string): MissionRow[] {
  const out: MissionRow[] = [];
  const parts = md.replace(/<!--[\s\S]*?-->/g, '').split(/^## Mission: /m).slice(1);
  for (const p of parts) {
    const name = p.split('\n', 1)[0].trim();
    const status = p.match(/^STATUS:[ \t]*(.*)$/m)?.[1].trim() || 'unknown (no STATUS value)';
    const priority = p.match(/^PRIORITY:[ \t]*(.*)$/m)?.[1].trim() || null;
    out.push({ name, status, priority, source: 'director' });
  }
  return out;
}

/** The first markdown table under "## Table" in board/parity.md. */
export function parseParity(md: string): { columns: string[]; rows: ParityRow[] } | null {
  const after = md.split(/^## Table\s*$/m)[1];
  if (!after) return null;
  const lines: string[] = [];
  for (const l of after.split('\n')) {
    if (l.trim().startsWith('|')) lines.push(l);
    else if (lines.length) break; // first contiguous table only
  }
  if (lines.length < 3) return null;
  const split = (l: string) => l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
  const head = split(lines[0]);
  const columns = head.slice(1);
  const rows = lines.slice(2).map((l) => {
    const c = split(l);
    return { row: c[0].replace(/\*\*/g, ''), cells: Object.fromEntries(columns.map((col, i) => [col, c[i + 1] ?? ''])) };
  });
  return { columns, rows };
}

/** Parity cell verdict: the leading word (YES / PARTIAL / NO / UNKNOWN), else unknown. */
export function parityVerdict(cell: string): 'yes' | 'partial' | 'no' | 'unknown' {
  const w = cell.replace(/\*/g, '').trim().toUpperCase();
  if (w.startsWith('YES')) return 'yes';
  if (w.startsWith('PARTIAL')) return 'partial';
  if (w.startsWith('NO')) return 'no';
  return 'unknown';
}

/** Open fix-now items: every parseable line of the review queues (review_queue.py moves closed ones to *.done.jsonl).
 * `id` is supplied by the server (sha1 of the stripped line, first 8 hex, same as review_queue.py). */
export function fixNowItem(kind: string, id: string, line: string): FixNowItem | null {
  let r: Record<string, unknown>;
  try {
    r = JSON.parse(line) as Record<string, unknown>;
  } catch {
    return null;
  }
  const where = String(r.cwd ?? '').split('/').pop() || '?';
  const day = String(r.ts ?? '').slice(0, 10);
  if (kind === 'correction') return { id, kind, text: `correction ${day} in ${where}: ${String(r.excerpt ?? '').slice(0, 160)}` };
  const c = (r.counts ?? {}) as Record<string, number>;
  return { id, kind, text: `session ${day} in ${where}: ${c.corrections ?? 0} corrections, ${c.test_failures ?? 0} failed tests, ${c.guard_blocks ?? 0} guard blocks, ${c.tool_errors ?? 0} tool errors` };
}

export function progressTail(md: string, n = 12): string[] {
  return md.split('\n').filter((l) => l.startsWith('- ')).slice(-n).reverse();
}

export const SPEND_WHY = 'Not wired yet: the spend check is board ticket agent-ops-foundation-55 (design) then -82 (live). Until it lands this stays unknown; no number is shown that a source did not give.';
export const ROTATION_WHY = 'Not wired yet: the rotation script is board ticket agent-ops-foundation-72, proven end to end in -83. Until it lands every key\'s rotation state is unknown.';
