'use client';

import { useCallback, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { usePoll } from '@/hooks/use-poll';

import {
  FIX_TEXT,
  accountName,
  groupBad,
  headline,
  isBad,
  visibleGroups,
  type LoginSnapshot,
} from './connector-logins';

function ago(iso: string | null | undefined): string {
  if (!iso) return '?';
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 90) return `${s}s ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 129600) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

/** Every Composio login, grouped by toolkit, with its card; anything not ACTIVE is red with its fix. */
export function ConnectorLoginsPanel({ localToken }: { localToken: string }) {
  const [snap, setSnap] = useState<LoginSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [badOnly, setBadOnly] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch('/api/connector-logins', { cache: 'no-store', headers: localToken ? { 'x-local-token': localToken } : {} });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setSnap(body as LoginSnapshot);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'load failed');
    }
  }, []);
  usePoll(load, 60_000);

  async function refresh() {
    setBusy(true);
    try {
      const res = await fetch('/api/connector-logins', { method: 'POST', headers: { 'x-local-token': localToken } });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setSnap(body as LoginSnapshot);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'refresh failed');
    } finally {
      setBusy(false);
    }
  }

  const groups = useMemo(() => (snap ? visibleGroups(snap.groups, query, badOnly) : []), [snap, query, badOnly]);

  if (!snap) {
    return error ? (
      <div className="p-4 text-sm text-red-600">{error}</div>
    ) : (
      <div className="text-muted-foreground p-4 text-sm">Loading connector logins…</div>
    );
  }

  const bad = snap.summary.not_active;
  return (
    <div className="h-full overflow-auto p-4" data-testid="connector-logins">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="font-medium">Connector logins</h2>
        <span className="text-muted-foreground text-xs">
          Composio · checked {ago(snap.generated_at)} · {snap.summary.total} logins · {snap.summary.toolkits} apps
        </span>
        <div className="ml-auto flex items-center gap-2">
          <input
            className="bg-background h-8 w-48 rounded border px-2 text-sm"
            placeholder="Filter app, card, login"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button size="sm" variant={badOnly ? 'default' : 'outline'} aria-pressed={badOnly} onClick={() => setBadOnly((v) => !v)}>
            Not ACTIVE only
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => void refresh()}>
            {busy ? 'Refreshing…' : 'Refresh'}
          </Button>
        </div>
      </div>

      <p
        data-testid="connector-logins-headline"
        className={`mb-2 rounded border px-3 py-2 text-sm ${
          bad ? 'border-red-500 bg-red-50 text-red-800 dark:bg-red-950/40 dark:text-red-200' : 'border-emerald-500/60 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100'
        }`}
      >
        {headline(snap)}
      </p>
      <p className="text-muted-foreground mb-4 text-xs">
        Read-only. Nothing here changes or deletes a login. Server alarm: <code>composio:no-expired-logins</code> (every 30 min,
        texts and emails Alex on change).
        {error ? <span className="ml-2 text-red-600">Last refresh failed: {error}</span> : null}
      </p>

      {groups.length === 0 ? (
        <div className="text-muted-foreground text-sm">{badOnly ? 'No logins outside ACTIVE.' : 'No logins match.'}</div>
      ) : (
        <ul className="space-y-3">
          {groups.map((g) => {
            const n = groupBad(g);
            return (
              <li
                key={g.toolkit}
                data-toolkit={g.toolkit}
                className={`rounded border ${n ? 'border-red-500' : ''}`}
              >
                <div className="bg-muted/40 flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                  <span className="font-medium">{g.toolkit}</span>
                  <span className="text-muted-foreground text-xs">
                    card: {g.card ? <code>~/.agents/tools/cards/{g.card}.md</code> : <span className="text-amber-600">no card</span>}
                  </span>
                  <span className={`ml-auto text-xs ${n ? 'font-medium text-red-600' : 'text-muted-foreground'}`}>
                    {n ? `${n} not ACTIVE` : `${g.accounts.length} ACTIVE`}
                  </span>
                </div>
                <table className="w-full text-left text-xs">
                  <tbody>
                    {g.accounts.map((a) => {
                      const red = isBad(a);
                      return (
                        <tr
                          key={a.account_id}
                          data-status={a.status}
                          className={`border-t ${red ? 'bg-red-50 text-red-800 dark:bg-red-950/40 dark:text-red-200' : ''}`}
                        >
                          <td className="w-28 px-3 py-1.5">
                            <span
                              className={`rounded px-1.5 py-0.5 font-mono text-[11px] ${
                                red ? 'bg-red-600 text-white' : 'bg-emerald-600/15 text-emerald-700 dark:text-emerald-300'
                              }`}
                            >
                              {a.status}
                            </span>
                          </td>
                          <td className="px-3 py-1.5 font-mono">{accountName(a)}</td>
                          <td className="text-muted-foreground px-3 py-1.5 font-mono">{a.account_id}</td>
                          <td className="text-muted-foreground px-3 py-1.5 tabular-nums" title={a.updated_at ?? ''}>
                            updated {ago(a.updated_at)}
                          </td>
                          <td className="px-3 py-1.5">
                            {red ? (
                              <span className="font-medium">
                                Fix: {a.fix ?? FIX_TEXT}
                                {a.status_reason ? <span className="block font-normal opacity-80">{a.status_reason}</span> : null}
                              </span>
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-muted-foreground mt-4 text-xs">
        Sources: {snap.source}; cards from {snap.card_source}.
      </p>
    </div>
  );
}
