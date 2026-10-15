// Pure helpers for the "Waiting on you" panel (shared by the route and tests).

export type BoardAnswer = { ts: string; source: string; text: string };

export type BoardTicket = {
  id: string;
  title: string;
  status: string;
  owner?: string | null;
  blocked_on?: string | null;
  need?: string | null;
  done_means?: string | null;
  updated?: string;
  progressed?: string;
  answers?: BoardAnswer[];
};

export type WaitingItem = {
  id: string;
  title: string;
  ask: string;
  since: string | null;
  answerable: boolean;
  gate: boolean;
};

export type AnsweredItem = { id: string; title: string; answer: BoardAnswer };

// Alex's gates: spend, messages to real people, production/DNS, deletes.
// Matching is deliberately broad: when unsure, it's a gate.
const GATE_PATTERN = new RegExp(
  [
    // money
    'spend', 'pay', 'paid', 'budget', 'bill', 'buy', 'purchase', 'subscri', 'price', 'cost', 'charge', 'card',
    'invoice', 'refund', 'dollar', 'usd', '\\$', 'money', 'fund', 'order', 'trade', 'transfer', 'upgrade', 'plan tier',
    // real people
    'customer', 'client', 'email', 'mail', 'message', 'send', 'sms', 'text', 'call', 'contact', 'reach out',
    'post', 'publish', 'dm', 'reply', 'invite', 'announce', 'tweet', 'notify', 'outreach', 'jane', 'person', 'people',
    // production / DNS
    'prod', 'live', 'dns', 'domain', 'deploy', 'release', 'launch', 'rotate', 'revoke', 'credential', 'token', 'key',
    'password', 'secret', 'cloudflare', 'vercel', 'server', 'ship',
    // deletes
    'delete', 'remove', 'scrub', 'purge', 'wipe', 'drop', 'erase', 'destroy', 'discard', 'uninstall', 'cancel',
    'clean', 'trash', 'archive', 'overwrite', 'reset', 'rewrite history', 'force',
  ].join('|'),
  'i',
);

// A question too short to judge is treated as a gate ("Proceed?" could mean anything).
const MIN_CLEAR_QUESTION = 40;

export function isGate(ticket: BoardTicket): boolean {
  const ask = (ticket.need ?? '').trim();
  if (ask.length < MIN_CLEAR_QUESTION) return true;
  const text = [ticket.title, ticket.need, ticket.done_means].filter(Boolean).join(' ');
  return GATE_PATTERN.test(text);
}

// When each ticket was last marked blocked on Alex, from board progress lines:
// "- <ts> | <id> | blocked | <owner> | on alex: ...". Notes do not reset it.
export function blockedSince(progress: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of progress.split('\n')) {
    const m = /^- (\S+) \| (\S+) \| blocked \| [^|]* \| on alex/.exec(line);
    if (m) out[m[2]] = m[1];
  }
  return out;
}

export function waitingItems(tickets: BoardTicket[], since: Record<string, string> = {}): WaitingItem[] {
  return tickets
    .filter((t) => t.status !== 'done' && (t.owner === 'alex' || t.blocked_on === 'alex'))
    .map((t) => ({
      id: t.id,
      title: t.title,
      ask: t.need || t.done_means || 'No question written down.',
      // Unknown rather than guessed: progressed/updated move on unrelated notes.
      since: since[t.id] ?? null,
      // board.py answer only unblocks tickets blocked on Alex.
      answerable: t.status === 'blocked' && t.blocked_on === 'alex',
      gate: isGate(t),
    }));
}

export function recentlyAnswered(tickets: BoardTicket[], now = Date.now(), days = 7): AnsweredItem[] {
  const cutoff = now - days * 86_400_000;
  return tickets
    .filter((t) => t.answers?.length)
    .map((t) => ({ id: t.id, title: t.title, answer: t.answers![t.answers!.length - 1] }))
    .filter((a) => Date.parse(a.answer.ts) >= cutoff)
    .sort((a, b) => b.answer.ts.localeCompare(a.answer.ts));
}
