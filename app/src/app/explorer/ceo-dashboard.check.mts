import { agentPrompt, badges, boardCounts, deepLink, directorMissions, fixNowItem, freshness, needsAlex, parityVerdict, parseParity, progressTail, ROTATION_WHY, SPEND_WHY, type Ticket } from './ceo-dashboard.ts';
let fails = 0;
const assert = (c: unknown, m: string) => { if (!c) { fails++; console.error('FAIL', m); } else console.log('PASS', m); };
const T: Ticket[] = [
  { id: 'm-01', title: 'A', status: 'blocked', blocked_on: 'alex', need: 'Set the cap at https://openrouter.ai/settings/keys.', owner: 'lane-x' },
  { id: 'm-02', title: 'B', status: 'blocked', blocked_on: 'alex', need: 'Decide business vs coaching', owner: 'lane-x' },
  { id: 'm-03', title: 'C', status: 'blocked', blocked_on: 'lane-javar', owner: 'lane-y' },
  { id: 'm-04', title: 'D', status: 'done', blocked_on: 'alex', owner: 'lane-y' },
  { id: 'm-05', title: 'E', status: 'doing', owner: 'lane-y' },
  { id: 'm-06', title: 'F', status: 'open', owner: null },
  { id: 'm-07', title: 'G', status: 'open', owner: 'alex' },
];
const n = needsAlex(T);
assert(n.map((x) => x.id).join() === 'm-01,m-02,m-07', 'open tickets blocked on or owned by alex (board.py rule)');
assert(n[0].link === 'https://openrouter.ai/settings/keys', 'deep link comes from the ticket text, trailing dot trimmed');
assert(n[1].link === null, 'no link in the source means null, never a guessed homepage');
assert(deepLink({ id: 'x', link: 'https://a.example/b/c' }) === 'https://a.example/b/c', 'explicit link field wins');
assert(agentPrompt(T[0]).includes('m-01') && agentPrompt(T[0]).includes('stop before any spend'), 'agent button prompt names the ticket and the gates');
const c = boardCounts(T);
assert(c.total === 7 && c.counts.blocked === 3 && c.counts.open === 2, 'board counts by status');
const b = badges(T);
assert(b.length === 3 && b[0].owner === 'lane-y' && b[0].owner === 'lane-y' && b[0].doing[0] === 'm-05' && b[0].done === 1, 'badges per owner, busiest first, unowned skipped');
const md = '<!--\n## Mission: [template]\nSTATUS:\n-->\n## Mission: One\nPRIORITY: HIGH\nSTATUS: ACTIVE\n## Mission: Two\nnothing\n';
const ms = directorMissions(md);
assert(ms.length === 2 && ms[0].status === 'ACTIVE' && ms[0].priority === 'HIGH', 'mission status as written; template comment ignored');
assert(ms[1].status.startsWith('unknown'), 'missing STATUS line is unknown');
const pm = '# P\n## Table\n\n| Row | Claude Code | Codex |\n|---|---|---|\n| **guard** | **YES-seen**. x | PARTIAL: y |\n| other | NO | ? |\n\n## Counts\n| Column | YES |\n|---|---|\n| x | 1 |\n';
const p = parseParity(pm)!;
assert(p.columns.join() === 'Claude Code,Codex' && p.rows[0].row === 'guard' && p.rows.length === 2, 'parity: first table only');
assert(parityVerdict(p.rows[0].cells['Claude Code']) === 'yes' && parityVerdict(p.rows[0].cells.Codex) === 'partial' && parityVerdict(p.rows[1].cells['Claude Code']) === 'no' && parityVerdict(p.rows[1].cells.Codex) === 'unknown', 'parity verdicts');
assert(parseParity('no table') === null, 'missing parity table is null (unknown)');
assert(fixNowItem('correction', 'abcd1234', '{"ts":"2026-10-14T01:00:00Z","cwd":"/x/repo","excerpt":"no"}')!.text.includes('repo'), 'correction item');
assert(fixNowItem('session', 'i', '{"counts":{"guard_blocks":4}}')!.text.includes('4 guard blocks'), 'session item');
assert(fixNowItem('session', 'i', 'not json') === null, 'bad line skipped');
assert(progressTail('- a\n- b\nx\n- c', 2).join() === '- c,- b', 'newest progress first');
assert(freshness(null, 0, 1) === 'unknown' && freshness(0, 10, 5) === 'stale' && freshness(8, 10, 5) === 'fresh', 'freshness');
assert(SPEND_WHY.includes('-55') && ROTATION_WHY.includes('-72'), 'unknown states name the ticket that wires them');
const em = directorMissions('## Mission: E\nSTATUS:\nPRIORITY: HIGH\n## Mission: F\nPRIORITY:\nSTATUS: ok\n');
assert(em[0].status.startsWith('unknown') && em[0].priority === 'HIGH', 'empty STATUS stays unknown, never borrows the next line');
assert(em[1].priority === null && em[1].status === 'ok', 'empty PRIORITY is null');
if (fails) { console.error(`${fails} failed`); process.exit(1); }
