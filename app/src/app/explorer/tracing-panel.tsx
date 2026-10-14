'use client';

import { useEffect, useMemo, useState } from 'react';

import { usePoll } from '@/hooks/use-poll';

import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

type TraceRow = {
  trace_id: string;
  label?: string;
  status?: string;
  synthetic_only?: number;
  started_at?: string;
};

type SpanRow = {
  span_id: string;
  parent_span_id?: string | null;
  name: string;
  agent_identity?: string;
  tool_action?: string;
  status?: string;
  started_at?: string;
  duration_ms?: number;
  component_ids?: string;
  source_ids?: string;
  evidence_ids?: string;
};

function parseIdList(raw?: string): string[] {
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

function TraceGraph({ spans }: { spans: SpanRow[] }) {
  const layout = useMemo(() => {
    const byParent = new Map<string | null, SpanRow[]>();
    for (const span of spans) {
      const key = span.parent_span_id ?? null;
      const list = byParent.get(key) ?? [];
      list.push(span);
      byParent.set(key, list);
    }
    const positions = new Map<string, { x: number; y: number }>();
    let row = 0;
    function walk(parentId: string | null, depth: number) {
      for (const span of byParent.get(parentId) ?? []) {
        positions.set(span.span_id, { x: 40 + depth * 120, y: 30 + row * 56 });
        row += 1;
        walk(span.span_id, depth + 1);
      }
    }
    walk(null, 0);
    const width = Math.max(320, ...[...positions.values()].map((p) => p.x + 100));
    const height = Math.max(120, row * 56 + 40);
    return { positions, width, height };
  }, [spans]);

  if (!spans.length) {
    return null;
  }

  return (
    <svg className="bg-muted/40 mb-3 w-full rounded border" viewBox={`0 0 ${layout.width} ${layout.height}`}>
      {spans.map((span) => {
        if (!span.parent_span_id) {
          return null;
        }
        const from = layout.positions.get(span.parent_span_id);
        const to = layout.positions.get(span.span_id);
        if (!from || !to) {
          return null;
        }
        return (
          <line
            key={`edge-${span.span_id}`}
            x1={from.x + 80}
            y1={from.y + 16}
            x2={to.x}
            y2={to.y + 16}
            stroke="currentColor"
            strokeOpacity={0.35}
          />
        );
      })}
      {spans.map((span) => {
        const pos = layout.positions.get(span.span_id);
        if (!pos) {
          return null;
        }
        return (
          <g key={span.span_id}>
            <rect
              x={pos.x}
              y={pos.y}
              width={110}
              height={32}
              rx={6}
              className="fill-background stroke-border"
              strokeWidth={1}
            />
            <text x={pos.x + 6} y={pos.y + 20} className="fill-foreground text-[10px]">
              {(span.name ?? span.span_id).length > 14
                ? `${(span.name ?? span.span_id).slice(0, 14)}…`
                : (span.name ?? span.span_id)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function LocalTracing() {
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<{ trace: TraceRow; spans: SpanRow[] } | null>(null);

  // Every minute: the server re-imports a changed Director export, then lists traces.
  usePoll(async () => {
    const payload = await fetch('/api/traces', { cache: 'no-store' }).then((r) => r.json()).catch(() => null);
    if (!payload) return;
    const rows: TraceRow[] = payload.traces ?? [];
    setTraces(rows);
    setSelectedId((current) => current ?? rows[0]?.trace_id ?? null);
  }, 60_000);

  useEffect(() => {
    if (!selectedId) {
      return;
    }
    fetch(`/api/traces/${selectedId}`)
      .then((r) => r.json())
      .then((payload) => {
        if (payload.trace && payload.spans) {
          setDetail({ trace: payload.trace, spans: payload.spans });
          return;
        }
        if (payload.payload?.trace) {
          setDetail({ trace: payload.payload.trace, spans: payload.payload.spans ?? [] });
          return;
        }
        setDetail(null);
      });
  }, [selectedId]);

  const sortedSpans = useMemo(() => {
    if (!detail?.spans) {
      return [];
    }
    return [...detail.spans].sort((a, b) => String(a.started_at).localeCompare(String(b.started_at)));
  }, [detail]);

  return (
    <div className="grid h-full grid-cols-1 gap-4 overflow-auto p-4 lg:grid-cols-[280px_1fr]">
      <div>
        <h2 className="font-medium">Agent tracing</h2>
        <p className="text-muted-foreground mt-1 text-xs">
          Timeline and span graph from imported receipts. Synthetic/demo traces are labeled separately from observed
          imports.
        </p>
        <ul className="mt-3 space-y-2">
          {traces.map((trace) => (
            <li key={trace.trace_id}>
              <Button
                variant={trace.trace_id === selectedId ? 'default' : 'outline'}
                size="sm"
                className="h-auto w-full justify-start whitespace-normal py-2 text-left"
                onClick={() => setSelectedId(trace.trace_id)}
              >
                <div>{trace.label ?? trace.trace_id}</div>
                <div className="text-xs opacity-80">
                  {trace.status} · {trace.synthetic_only ? 'synthetic/demo' : 'observed/local'}
                </div>
                <div className="text-muted-foreground text-xs">{trace.started_at}</div>
              </Button>
            </li>
          ))}
        </ul>
      </div>
      <div>
        {detail ? (
          <>
            <h3 className="font-medium">{detail.trace.label ?? detail.trace.trace_id}</h3>
            <p className="text-muted-foreground text-xs">
              {detail.trace.synthetic_only ? 'Synthetic / demo trace' : 'Observed local import'} ·{' '}
              {detail.trace.status}
            </p>
            <Separator className="my-2" />
            <TraceGraph spans={sortedSpans} />
            <div className="space-y-2">
              {sortedSpans.map((span) => {
                const sources = parseIdList(span.source_ids);
                const components = parseIdList(span.component_ids);
                const evidence = parseIdList(span.evidence_ids);
                return (
                  <div key={span.span_id} className="rounded border p-3 text-sm">
                    <div className="font-medium">{span.name}</div>
                    <div className="text-muted-foreground text-xs">
                      {span.started_at} · {span.duration_ms ?? '?'} ms · {span.status}
                    </div>
                    <div className="mt-1 text-xs">
                      Agent: {span.agent_identity ?? 'unknown'} · Tool: {span.tool_action ?? 'unknown'}
                    </div>
                    {span.parent_span_id && (
                      <div className="text-muted-foreground text-xs">Parent span: {span.parent_span_id}</div>
                    )}
                    {(sources.length > 0 || components.length > 0 || evidence.length > 0) && (
                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
                        {sources.map((id) => (
                          <a
                            key={`src-${id}`}
                            className="text-primary underline-offset-2 hover:underline"
                            href={`/api/sources/${encodeURIComponent(id)}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Source {id}
                          </a>
                        ))}
                        {components.map((id) => (
                          <span key={`cmp-${id}`} className="bg-muted rounded px-1.5 py-0.5">
                            Component {id}
                          </span>
                        ))}
                        {evidence.map((id) => (
                          <span key={`ev-${id}`} className="bg-muted rounded px-1.5 py-0.5">
                            Evidence {id}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <p className="text-muted-foreground text-sm">Select a trace.</p>
        )}
      </div>
    </div>
  );
}

type LfRow = {
  traceId: string;
  name: string;
  startTime: string;
  durationMs: number | null;
  totalCost: number | null;
  hasError: boolean;
  observationCount: number;
};
type LfPayload =
  | { ok: true; projectId: string; asOf: string; note: string; truncated: boolean; traces: LfRow[] }
  | { ok: false; state: 'unknown'; reason: string; asOf: string; note: string }
  | { error: string };

type LfProject = 'agents' | 'langflow';
const LF_HOST = 'https://us.cloud.langfuse.com';

function formatDuration(ms: number | null): string {
  if (ms === null) return 'unknown';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`;
}

function SwitchRow<T extends string>({ label, value, options, onChange }: {
  label: string;
  value: T;
  options: Array<[T, string]>;
  onChange: (v: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap items-center gap-1">
      <span className="text-muted-foreground mr-1 text-xs">{label}</span>
      {options.map(([key, text]) => (
        <Button key={key} size="sm" variant={key === value ? 'default' : 'outline'} aria-pressed={key === value} onClick={() => onChange(key)}>
          {text}
        </Button>
      ))}
    </div>
  );
}

function LangfuseTraces() {
  const [project, setProject] = useState<LfProject>('agents');
  const [needsLook, setNeedsLook] = useState(false);
  return (
    <div className="h-full overflow-auto p-4">
      <h2 className="font-medium">Langfuse traces (live)</h2>
      <p className="text-muted-foreground mt-1 text-xs">
        The last 24 hours, newest first, up to 100 runs. Langfuse shows traces a few minutes late.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <SwitchRow label="Project" value={project} options={[['agents', 'Agents'], ['langflow', 'Langflow']]} onChange={setProject} />
        <label className="flex items-center gap-1.5 text-xs">
          <input type="checkbox" checked={needsLook} onChange={(e) => setNeedsLook(e.target.checked)} />
          Needs a look (runs with an error)
        </label>
      </div>
      {/* key remounts the poller so a project change fetches at once */}
      <LangfuseTable key={project} project={project} needsLook={needsLook} />
    </div>
  );
}

function LangfuseTable({ project, needsLook }: { project: LfProject; needsLook: boolean }) {
  const [current, setCurrent] = useState<LfPayload | null>(null);

  usePoll(async () => {
    let token: string | null = null;
    if (['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)) {
      const health = await fetch('/api/health', { cache: 'no-store' }).then((r) => r.json()).catch(() => null);
      token = typeof health?.token === 'string' ? health.token : null;
    }
    const headers: Record<string, string> = token ? { 'x-local-token': token } : {};
    const data = (await fetch(`/api/langfuse/traces?project=${project}`, { cache: 'no-store', headers })
      .then((r) => r.json())
      .catch(() => null)) as LfPayload | null;
    setCurrent(data ?? { ok: false, state: 'unknown', reason: 'The map could not reach its own server.', asOf: new Date().toISOString(), note: '' });
  }, 60_000);

  const rows = current && 'traces' in current ? current.traces : [];
  const shown = needsLook ? rows.filter((r) => r.hasError) : rows;
  const projectId = current && 'projectId' in current ? current.projectId : null;

  return (
    <div>
      {!current ? (
        <p className="text-muted-foreground mt-4 text-sm">Loading from Langfuse...</p>
      ) : 'error' in current ? (
        <p role="alert" className="mt-4 text-sm text-red-700 dark:text-red-400">{current.error}</p>
      ) : !current.ok ? (
        <div role="status" className="mt-4 rounded border p-3 text-sm">
          <div className="font-medium">Unknown: Langfuse did not give an answer.</div>
          <div className="text-muted-foreground mt-1 text-xs">{current.reason}</div>
        </div>
      ) : (
        <>
          <p className="text-muted-foreground mt-3 text-xs">
            As of {new Date(current.asOf).toLocaleTimeString()}. {current.truncated ? 'More runs exist than were loaded. ' : ''}
            {shown.length} of {rows.length} runs shown.
          </p>
          {shown.length === 0 ? (
            <p className="text-muted-foreground mt-3 text-sm">
              {needsLook ? 'No runs with an error in the last 24 hours.' : 'No runs in the last 24 hours.'}
            </p>
          ) : (
            <table className="mt-2 w-full text-left text-xs">
              <thead className="text-muted-foreground border-b">
                <tr>
                  <th className="py-1 pr-3 font-medium">Name</th>
                  <th className="py-1 pr-3 font-medium">Started</th>
                  <th className="py-1 pr-3 font-medium">Duration</th>
                  <th className="py-1 pr-3 font-medium">Cost</th>
                  <th className="py-1 pr-3 font-medium">Errors</th>
                  <th className="py-1 pr-3 font-medium">Steps</th>
                  <th className="py-1 font-medium">Open</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => (
                  <tr key={r.traceId} className="border-b align-top">
                    <td className="py-1.5 pr-3 break-all">{r.name}</td>
                    <td className="py-1.5 pr-3 whitespace-nowrap">{new Date(r.startTime).toLocaleString()}</td>
                    <td className="py-1.5 pr-3 whitespace-nowrap">{formatDuration(r.durationMs)}</td>
                    <td className="py-1.5 pr-3 whitespace-nowrap">{r.totalCost === null ? 'not reported' : `$${r.totalCost.toFixed(4)}`}</td>
                    <td className={`py-1.5 pr-3 ${r.hasError ? 'font-medium text-red-700 dark:text-red-400' : ''}`}>{r.hasError ? 'Yes' : 'No'}</td>
                    <td className="py-1.5 pr-3">{r.observationCount}</td>
                    <td className="py-1.5">
                      {projectId ? (
                        <a className="text-primary underline-offset-2 hover:underline" target="_blank" rel="noopener noreferrer"
                          href={`${LF_HOST}/project/${encodeURIComponent(projectId)}/traces/${encodeURIComponent(r.traceId)}`}>
                          Open in Langfuse
                        </a>
                      ) : (
                        <span className="text-muted-foreground">Link unavailable</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}

export function TracingPanel() {
  const [source, setSource] = useState<'local' | 'langfuse'>('local');
  return (
    <div className="flex h-full flex-col">
      <div className="border-b px-4 py-2">
        <SwitchRow label="Source" value={source} options={[['local', 'Local (Director)'], ['langfuse', 'Langfuse (live)']]} onChange={setSource} />
      </div>
      <div className="min-h-0 flex-1">{source === 'local' ? <LocalTracing /> : <LangfuseTraces />}</div>
    </div>
  );
}
