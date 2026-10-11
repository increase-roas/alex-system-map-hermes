'use client';

import { useEffect, useState } from 'react';

type RequirementRow = {
  id: string;
  owner?: string | null;
  last_verified_at?: string | null;
  status: string;
  evidence?: Record<string, unknown> | null;
  next_unresolved_step?: string;
  documented_path?: string | null;
  installed_path?: string | null;
  actually_used_evidence?: string | null;
};

type ReliabilityStatus = {
  delivery_id?: string;
  revision?: number;
  acknowledgment?: string;
  overall_rel_status?: string;
  requirements?: RequirementRow[];
  synthetic_sync_trace_e2e?: { label?: string; passed?: boolean; dataset?: string };
  browser_proof?: { status?: string; reason?: string };
  note?: string;
};

export function ReliabilityPanel() {
  const [status, setStatus] = useState<ReliabilityStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const payload = (await fetch('/api/reliability/status').then((r) => r.json())) as ReliabilityStatus;
        setStatus(payload);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'load failed');
      }
    }
    void load();
  }, []);

  if (error) {
    return <div className="p-4 text-sm text-red-600">{error}</div>;
  }
  if (!status) {
    return <div className="text-muted-foreground p-4 text-sm">Loading reliability status…</div>;
  }

  return (
    <div className="h-full overflow-auto p-4">
      <h2 className="mb-1 font-medium">Reliability (revision {status.revision ?? 2})</h2>
      <p className="text-muted-foreground mb-4 text-xs">
        Delivery {status.delivery_id ?? '—'} · overall {status.overall_rel_status ?? 'not-run'}
      </p>
      {status.acknowledgment ? (
        <p className="mb-4 rounded border bg-muted/40 px-3 py-2 text-xs">{status.acknowledgment}</p>
      ) : null}
      <ul className="space-y-3">
        {(status.requirements ?? []).map((req) => (
          <li key={req.id} className="rounded border px-3 py-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{req.id}</span>
              <span
                className={
                  req.status === 'passed'
                    ? 'text-green-700 dark:text-green-400'
                    : req.status === 'failed'
                      ? 'text-red-700 dark:text-red-400'
                      : 'text-muted-foreground'
                }
              >
                {req.status}
              </span>
            </div>
            <div className="text-muted-foreground mt-1 text-xs">
              Owner: {req.owner ?? '—'} · Last verified: {req.last_verified_at ?? '—'}
            </div>
            {req.documented_path ? (
              <div className="text-muted-foreground text-xs">Documented: {req.documented_path}</div>
            ) : null}
            {req.installed_path ? (
              <div className="text-muted-foreground text-xs">Installed: {req.installed_path}</div>
            ) : null}
            {req.actually_used_evidence ? (
              <div className="text-muted-foreground text-xs">Used: {req.actually_used_evidence}</div>
            ) : null}
            {req.next_unresolved_step ? (
              <div className="mt-1 text-xs text-amber-800 dark:text-amber-200">
                Next: {req.next_unresolved_step}
              </div>
            ) : null}
            {req.evidence ? (
              <pre
                data-testid={`${req.id}-evidence`}
                className="bg-muted/50 mt-2 max-h-48 max-w-full overflow-x-auto overflow-y-auto whitespace-pre-wrap break-words rounded p-2 text-sm leading-normal"
              >
                {JSON.stringify(req.evidence, null, 2)}
              </pre>
            ) : null}
          </li>
        ))}
      </ul>
      {status.synthetic_sync_trace_e2e ? (
        <div className="mt-4 rounded border border-dashed px-3 py-2 text-xs">
          <div className="font-medium">{status.synthetic_sync_trace_e2e.label ?? 'SYNTHETIC/TEST'} E2E</div>
          <div>
            {status.synthetic_sync_trace_e2e.passed ? 'passed' : 'failed'} ·{' '}
            {status.synthetic_sync_trace_e2e.dataset}
          </div>
        </div>
      ) : null}
      {status.browser_proof?.status === 'blocked' ? (
        <div className="mt-3 text-xs text-amber-800 dark:text-amber-200">
          Browser proof blocked: {status.browser_proof.reason}
        </div>
      ) : null}
      {status.note ? <p className="text-muted-foreground mt-3 text-xs">{status.note}</p> : null}
    </div>
  );
}
