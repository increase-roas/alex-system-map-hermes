'use client';

import { useCallback, useState } from 'react';

import { Button } from '@/components/ui/button';
import { usePoll } from '@/hooks/use-poll';

import { parityVerdict, type CeoDashboard, type Source } from './ceo-dashboard';

const FRESH_CLS: Record<Source['freshness'], string> = {
  fresh: 'bg-emerald-100 text-emerald-900',
  stale: 'bg-amber-100 text-amber-900',
  unknown: 'bg-zinc-200 text-zinc-800',
};

const VERDICT_CLS = { yes: 'bg-emerald-100', partial: 'bg-amber-100', no: 'bg-red-100', unknown: 'bg-zinc-100' } as const;

function SourceTag({ s }: { s: Source | undefined }) {
  if (!s) return <span className={`rounded px-1.5 py-0.5 text-[11px] ${FRESH_CLS.unknown}`}>unknown: no source</span>;
  const when = s.modified_at ? new Date(s.modified_at).toLocaleString() : 'never read';
  return (
    <span className={`rounded px-1.5 py-0.5 text-[11px] ${FRESH_CLS[s.freshness]}`} title={s.note ?? s.path}>
      {s.freshness}: {s.path} ({s.note ?? when})
    </span>
  );
}

function Section({ title, src, children }: { title: string; src?: (Source | undefined)[]; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {src?.map((s, i) => <SourceTag key={i} s={s} />)}
      </div>
      {children}
    </section>
  );
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      size="sm"
      variant="outline"
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => setDone(true));
      }}
    >
      {done ? 'Copied: paste to an agent' : 'Send an agent (copy prompt)'}
    </Button>
  );
}

/** Alex's one screen: what needs him first, then board, missions, agents, logins, parity, spend and key rotation. */
export function CeoDashboardPanel({ localToken }: { localToken: string }) {
  const [d, setD] = useState<CeoDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const res = await fetch('/api/ceo-dashboard', { cache: 'no-store', headers: localToken ? { 'x-local-token': localToken } : {} });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setD(body as CeoDashboard);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [localToken]);
  usePoll(load, 60_000);

  if (error) return <div className="p-4 text-sm text-red-700">Dashboard unavailable: {error}</div>;
  if (!d) return <div className="p-4 text-sm">Reading the sources...</div>;

  return (
    <div className="h-full space-y-3 overflow-auto p-4 text-sm">
      <p className="text-xs text-zinc-600">Read live from the source files at {new Date(d.generated_at).toLocaleTimeString()}; refreshes every minute. Grey means unknown, amber means the source is old.</p>

      <Section title={`Needs you (${d.needs_alex ? d.needs_alex.length : 'unknown'})`} src={[d.sources.board]}>
        {d.needs_alex === null ? (
          <p className="rounded bg-zinc-200 p-2">Unknown: the board could not be read, so this is not an all-clear.</p>
        ) : d.needs_alex.length === 0 ? (
          <p>Nothing on the board is waiting on you.</p>
        ) : (
          <ul className="space-y-2">
            {d.needs_alex.map((n) => (
              <li key={n.id} className="rounded border border-red-200 bg-red-50 p-2">
                <div className="font-medium">{n.id}: {n.title}</div>
                <div className="my-1">{n.need}</div>
                <div className="flex flex-wrap gap-2">
                  {n.link ? (
                    <a className="rounded bg-zinc-900 px-2 py-1 text-xs text-white" href={n.link} target="_blank" rel="noreferrer">Open the exact page</a>
                  ) : (
                    <span className="rounded bg-zinc-200 px-2 py-1 text-xs">No deep link in the ticket yet</span>
                  )}
                  <CopyButton text={n.agent_prompt} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Logins (expired or failed first)" src={[d.sources.logins]}>
        {!d.logins ? (
          <p>Unknown: no logins snapshot yet.</p>
        ) : d.logins.not_active === 0 ? (
          <p>All {d.logins.total} Composio logins are ACTIVE.</p>
        ) : (
          <ul className="space-y-1">
            {d.logins.bad.map((b) => (
              <li key={b.toolkit + b.name} className="flex flex-wrap items-center gap-2 text-red-800">
                <span>{b.toolkit} / {b.name}: {b.status}</span>
                <CopyButton text={`Composio login ${b.toolkit} (${b.name}) is ${b.status}. Follow its card in ~/.agents/tools/cards and send me the Connect Link; or back it up to ~/Backups and ask me before deleting.`} />
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Board" src={[d.sources.board, d.sources.progress]}>
        {d.board ? (
          <div className="flex flex-wrap gap-2">
            {Object.entries(d.board.counts).map(([k, v]) => (
              <span key={k} className="rounded bg-zinc-100 px-2 py-1">{k}: {v}</span>
            ))}
            <span className="rounded bg-zinc-100 px-2 py-1">total: {d.board.total}</span>
          </div>
        ) : (
          <p>Unknown: board not readable.</p>
        )}
        {d.progress_tail.length > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer">Latest progress lines</summary>
            <ul className="mt-1 space-y-0.5 font-mono text-[11px]">{d.progress_tail.map((l, i) => <li key={i}>{l}</li>)}</ul>
          </details>
        )}
      </Section>

      <Section title="Missions and lanes" src={[d.sources.board, d.sources.director]}>
        <ul className="space-y-1">
          {d.missions.map((m) => (
            <li key={m.source + m.name}>
              <span className="mr-1 rounded bg-zinc-100 px-1 text-[11px]">{m.source}</span>
              <b>{m.name}</b>: {m.status}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Agent badges (from the board's owner field)" src={[d.sources.board]}>
        {d.badges === null ? <p>Unknown: board not readable.</p> : <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {d.badges.map((b) => (
            <div key={b.owner} className="rounded border p-2">
              <div className="font-medium">{b.owner}</div>
              <div className="text-xs">doing {b.doing.length}, blocked {b.blocked.length}, done {b.done}</div>
              {b.doing.length > 0 && <div className="text-[11px] text-zinc-600">{b.doing.join(', ')}</div>}
            </div>
          ))}
        </div>}
      </Section>

      <Section title={`Fix-now queue (${d.fix_now === null ? 'unknown' : d.fix_now.length})`} src={[d.sources.fix_now_correction, d.sources.fix_now_session]}>
        {d.fix_now === null ? (
          <p>Unknown: a queue file could not be read.</p>
        ) : (
          <ul className="space-y-0.5 text-xs">{d.fix_now.map((f) => <li key={f.id}><code>{f.id}</code> {f.text}</li>)}</ul>
        )}
      </Section>

      <Section title="Hook parity" src={[d.sources.parity]}>
        {!d.parity ? (
          <p>Unknown: parity table not readable.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="text-[11px]">
              <thead>
                <tr><th className="p-1 text-left">Row</th>{d.parity.columns.map((c) => <th key={c} className="p-1 text-left">{c}</th>)}</tr>
              </thead>
              <tbody>
                {d.parity.rows.map((r) => (
                  <tr key={r.row}>
                    <td className="p-1 font-medium">{r.row}</td>
                    {d.parity!.columns.map((c) => (
                      <td key={c} className={`p-1 ${VERDICT_CLS[parityVerdict(r.cells[c] ?? '')]}`} title={r.cells[c]}>
                        {(r.cells[c] ?? '').replace(/\*/g, '').split(/[.;]/)[0].slice(0, 30)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title={`Spend (${d.spend.alerts.length} alerts)`} src={[d.sources.spend]}>
        {d.spend.state === 'unknown' ? (
          <p className="rounded bg-zinc-200 p-2">Unknown. {d.spend.why}</p>
        ) : (
          <>
            {d.spend.alerts.length > 0 && (
              <ul className="mb-2 space-y-1">
                {d.spend.alerts.map((a) => (
                  <li key={a} className="flex flex-wrap items-center gap-2 rounded border border-red-200 bg-red-50 p-2 text-red-900">
                    <span>{a}</span>
                    <CopyButton text={`Spend alert: "${a}". Check it on the vendor's billing page, tell me the exact page and what to do, and ask me before any payment or purchase.`} />
                  </li>
                ))}
              </ul>
            )}
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {d.spend.rows.map((r) => (
                <div key={r.name} className={`rounded border p-2 ${r.state === 'ok' ? '' : 'bg-zinc-100'}`}>
                  <div className="font-medium">{r.name} <span className="text-[11px] text-zinc-500">{r.kind}</span></div>
                  {r.state === 'ok' ? (
                    <ul className="text-xs">{r.figures.map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul>
                  ) : (
                    <p className="text-xs text-zinc-600">Unknown: {r.why}</p>
                  )}
                </div>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-zinc-600">ROI per agent needs Langfuse cost per agent and the sales feed; both show unknown until wired. No caps are set yet (you said: track first).</p>
          </>
        )}
        <div className="mt-2 flex flex-wrap gap-2">
          {d.spend.langfuse_links.map((l) => (
            <a key={l.url} className="rounded border px-2 py-1 text-xs underline" href={l.url} target="_blank" rel="noreferrer">{l.label}</a>
          ))}
        </div>
      </Section>

      <Section title="Key rotation">
        <p className="rounded bg-zinc-200 p-2">Unknown. {d.rotation.why}</p>
      </Section>
    </div>
  );
}
