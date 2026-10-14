/** Pure helpers for the Connector logins view (tested by connector-logins.check.mts). */

export type LoginRow = {
  toolkit: string;
  account_id: string;
  alias: string | null;
  word_id: string | null;
  status: string;
  updated_at: string | null;
  status_reason: string | null;
  card: string | null;
  ok: boolean;
  fix: string | null;
};
export type LoginGroup = { toolkit: string; card: string | null; accounts: LoginRow[] };
export type LoginSnapshot = {
  generated_at: string;
  source: string;
  card_source: string;
  alarm: string;
  summary: { total: number; toolkits: number; not_active: number; by_status: Record<string, number> };
  groups: LoginGroup[];
};

export const FIX_TEXT = 'reconnect, or back up to ~/Backups and delete';

/** Anything not ACTIVE is a problem (the alarm breaks on EXPIRED and FAILED; INITIATED and the rest are half-done). */
export const isBad = (row: Pick<LoginRow, 'status'>) => row.status.toUpperCase() !== 'ACTIVE';

export const groupBad = (g: LoginGroup) => g.accounts.filter(isBad).length;

/** Bad groups first, then by toolkit name; optional text filter on toolkit, card, alias, word id or account id. */
export function visibleGroups(groups: LoginGroup[], query = '', badOnly = false): LoginGroup[] {
  const q = query.trim().toLowerCase();
  return groups
    .map((g) => {
      const accounts = g.accounts.filter((a) => {
        if (badOnly && !isBad(a)) return false;
        if (!q) return true;
        return [g.toolkit, g.card, a.alias, a.word_id, a.account_id].some((v) => v?.toLowerCase().includes(q));
      });
      return { ...g, accounts };
    })
    .filter((g) => g.accounts.length > 0)
    .sort((a, b) => Number(groupBad(b) > 0) - Number(groupBad(a) > 0) || a.toolkit.localeCompare(b.toolkit));
}

/** Plain-words label for the account: alias when set, else the word id used with --account, else the raw id. */
export const accountName = (a: LoginRow) => a.alias || a.word_id || a.account_id;

export function headline(s: LoginSnapshot): string {
  const bad = s.summary.not_active;
  return bad === 0
    ? `All ${s.summary.total} logins are ACTIVE across ${s.summary.toolkits} apps.`
    : `${bad} of ${s.summary.total} logins are not ACTIVE. Fix: ${FIX_TEXT}.`;
}
