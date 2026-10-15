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
const GATE_PATTERN =
  /\b(spend|spending|pay|payment|paid|budget|bill|billing|buy|purchase|subscription|price|\$\d|cost|customer|client|email|message|send|post|publish|dm|text|prod|production|live|dns|domain|deploy|rotate|delete|deletion|remove|scrub|purge|wipe|drop)\b/i;

export function isGate(ticket: BoardTicket): boolean {
  const text = [ticket.title, ticket.need, ticket.done_means].filter(Boolean).join(' ');
  return GATE_PATTERN.test(text);
}

export function waitingItems(tickets: BoardTicket[]): WaitingItem[] {
  return tickets
    .filter((t) => t.status !== 'done' && (t.owner === 'alex' || t.blocked_on === 'alex'))
    .map((t) => ({
      id: t.id,
      title: t.title,
      ask: t.need || t.done_means || 'No question written down.',
      since: t.progressed || t.updated || null,
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
