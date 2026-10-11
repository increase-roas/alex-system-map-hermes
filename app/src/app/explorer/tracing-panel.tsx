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

export function TracingPanel() {
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
