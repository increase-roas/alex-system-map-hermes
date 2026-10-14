import { FIX_TEXT, accountName, groupBad, headline, isBad, visibleGroups, type LoginGroup, type LoginRow, type LoginSnapshot } from './connector-logins.ts';
let fails = 0;
const assert = (c: unknown, m: string) => { if (!c) { fails++; console.error('FAIL', m); } else console.log('PASS', m); };
const row = (toolkit: string, id: string, status: string, extra: Partial<LoginRow> = {}): LoginRow => ({
  toolkit, account_id: id, alias: null, word_id: `${toolkit}_${id}`, status, updated_at: '2026-10-13T00:00:00Z',
  status_reason: null, card: toolkit, ok: status === 'ACTIVE', fix: status === 'ACTIVE' ? null : FIX_TEXT, ...extra,
});
const groups: LoginGroup[] = [
  { toolkit: 'apify', card: 'apify', accounts: [row('apify', 'ca_1', 'ACTIVE')] },
  { toolkit: 'gmail', card: 'google-workspace', accounts: [row('gmail', 'ca_2', 'ACTIVE'), row('gmail', 'ca_3', 'EXPIRED')] },
  { toolkit: 'zoom', card: null, accounts: [row('zoom', 'ca_4', 'FAILED', { alias: 'old zoom' })] },
];
assert(!isBad({ status: 'ACTIVE' }) && isBad({ status: 'EXPIRED' }) && isBad({ status: 'FAILED' }) && isBad({ status: 'INITIATED' }), 'only ACTIVE is healthy');
assert(groupBad(groups[1]) === 1 && groupBad(groups[0]) === 0, 'bad count per toolkit');
const v = visibleGroups(groups);
assert(v.map((g) => g.toolkit).join() === 'gmail,zoom,apify', 'toolkits with dead logins sort first: ' + v.map((g) => g.toolkit).join());
assert(visibleGroups(groups, '', true).flatMap((g) => g.accounts).every(isBad), 'Not ACTIVE only hides healthy rows');
assert(visibleGroups(groups, '', true).length === 2, 'Not ACTIVE only drops all-healthy toolkits');
assert(visibleGroups(groups, 'google-work').map((g) => g.toolkit).join() === 'gmail', 'filter matches the card name');
assert(visibleGroups(groups, 'old zoom').length === 1, 'filter matches the alias');
assert(accountName(groups[2].accounts[0]) === 'old zoom' && accountName(groups[0].accounts[0]) === 'apify_ca_1', 'alias first, then word id');
const snap = (bad: number): LoginSnapshot => ({ generated_at: '', source: '', card_source: '', alarm: '', groups,
  summary: { total: 4, toolkits: 3, not_active: bad, by_status: {} } });
assert(headline(snap(0)) === 'All 4 logins are ACTIVE across 3 apps.', 'all-good headline');
assert(headline(snap(2)).includes('2 of 4') && headline(snap(2)).includes(FIX_TEXT), 'bad headline carries the fix');
assert(FIX_TEXT === 'reconnect, or back up to ~/Backups and delete', 'fix wording matches the alarm');
if (fails) { console.error(`${fails} failed`); process.exit(1); }
