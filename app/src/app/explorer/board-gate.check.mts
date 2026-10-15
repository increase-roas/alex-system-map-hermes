import { blockedSince, isGate, waitingItems, type BoardTicket } from '../../lib/board/waiting.ts';
let fails = 0;
const assert = (c: unknown, m: string) => { if (!c) { fails++; console.error('FAIL', m); } else console.log('PASS', m); };
const t = (need: string, title = 'Question for Alex'): BoardTicket => ({ id: 'x', title, status: 'blocked', blocked_on: 'alex', need });
// Reviewer's bypass examples (Codex review 2026-10-15) must all be gates.
for (const need of ['Charge the card 50 dollars?', 'Contact Jane by SMS?', 'Erase the backup?', 'Proceed?']) {
  assert(isGate(t(need)), `gate: ${need}`);
}
for (const need of [
  'Can we charge the client card for the next month of hosting fees?',
  'Should I reach out to the vendor rep about the integration timeline?',
  'OK to erase the old export folder now that the new one is verified?',
]) {
  assert(isGate(t(need)), `gate: ${need}`);
}
assert(!isGate(t('Which layout do you prefer for the map header, the left one or the top one?', 'Map header layout')), 'plain design question is answerable');
assert(isGate({ id: 'x', title: 'No question', status: 'blocked', blocked_on: 'alex' }), 'missing question is a gate');
const progress = [
  '- 2026-10-14T12:08:48Z | t-1 | blocked | a | on alex: question',
  '- 2026-10-14T13:00:37Z | t-1 | note | a | later note',
].join('\n');
assert(blockedSince(progress)['t-1'] === '2026-10-14T12:08:48Z', 'a note does not reset the waiting start');
const [w] = waitingItems([{ ...t('x'), id: 't-2', progressed: '2026-10-14T13:00:37Z' }], {});
assert(w.since === null, 'no blocked line means unknown, not progressed');
if (fails) process.exit(1);
