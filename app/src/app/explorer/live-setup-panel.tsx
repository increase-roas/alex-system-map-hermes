'use client';

import { Background, Controls, MiniMap, Panel, ReactFlow, type Edge, type Node, type ReactFlowInstance } from '@xyflow/react';
import { useTheme } from 'next-themes';
import { useCallback, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react';

import { Button } from '@/components/ui/button';
import { usePoll } from '@/hooks/use-poll';

import { BUCKET_TEXT, explainChip, explainNode, explainProblem } from './explain';
import { Meaning } from './meaning';

type Kind = 'app' | 'hub' | 'connector' | 'skill' | 'repo' | 'hook' | 'check' | 'director';
type LiveNode = { id: string; kind: Kind; label: string; meta: Record<string, unknown> };
type LiveEdge = { id: string; source: string; target: string; label: string };
type Severity = 'high' | 'medium' | 'you' | 'watch' | 'setup' | 'low';
type Problem = { severity: Severity; title: string; detail: string; node_ids: string[] };
type Scan = { scanned_at: string; summary: Record<string, number>; nodes: LiveNode[]; edges: LiveEdge[]; problems: Problem[] };
type Mission = { name: string; status: string; updated: string | null; quiet_days: number | null };
type Quiet = { name: string; quiet_days: number; bucket: 'needs me' | 'looks stuck' | 'looks done'; why: string };
type Status = { color: string; word: string } | null;

const KIND_LABEL: Record<Kind, string> = {
  app: 'AI app', hub: 'Shared home', connector: 'Connector', skill: 'Skill', repo: 'Project',
  hook: 'Guard (hook)', check: 'Check', director: 'Director',
};
const SEV_COLOR: Record<Severity, string> = {
  high: '#ff0071', medium: '#ff0071', you: '#f5a524', watch: '#f5a524', setup: '#3b82f6', low: '#8a8a8a',
};
const SEV_WORD: Record<Severity, string> = {
  high: 'broken', medium: 'broken', you: 'needs you', watch: 'watch', setup: 'setup', low: 'tidy',
};
const OK = '#17c964';
const W = 250, GAP = 30, ROW = 118, PER_ROW = 6;

function ago(iso: string | undefined | null): string {
  if (!iso) return '?';
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 90) return `${s}s ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 129600) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

function shortApps(runs: unknown): string {
  const apps = new Set((Array.isArray(runs) ? (runs as string[]) : []).map((r) => r.split(':')[0].replace(' desktop', '')));
  return [...apps].join(', ');
}

/** One line under each card title: what it is doing or what is wrong, in plain words. */
function subtitle(n: LiveNode, scan: Scan, status: Status): string {
  const out = scan.edges.filter((e) => e.source === n.id);
  const into = scan.edges.filter((e) => e.target === n.id);
  switch (n.kind) {
    case 'app':
      return `${out.filter((e) => e.label === 'uses connector').length} connectors · ${out.filter((e) => e.label === 'runs hook').length} guards`;
    case 'hook':
      return n.meta.broken ? 'script missing' : `runs in ${shortApps(n.meta.runs)}`;
    case 'check': {
      const state = String(n.meta.state ?? 'unknown');
      const word = state === 'success' ? 'passed' : state;
      return `${word} · ${ago(n.meta.at as string)}${n.meta.unpushed ? ` · ${n.meta.unpushed} not pushed` : ''}`;
    }
    case 'director': {
      const c = (n.meta.counts ?? {}) as Record<string, number>;
      const quiet = ((n.meta.missions ?? []) as Mission[]).filter((m) => m.status === 'ACTIVE' && (m.quiet_days ?? 0) >= 5).length;
      return `${c.ACTIVE ?? 0} active · ${quiet} quiet 5+ days · ${c.PARKED ?? 0} parked`;
    }
    case 'connector':
      return `used by ${into.filter((e) => e.label === 'uses connector').length} apps`;
    case 'hub':
      return n.id === 'hub:shared-skills' ? `${out.filter((e) => e.label === 'holds skill').length} skills, all apps read it` : 'all apps reach apps through it';
    default:
      return status ? status.word : String(n.meta.path ?? '');
  }
}

function card(n: LiveNode, scan: Scan, status: Status, hot: boolean): ReactNode {
  return (
    <div className="text-left leading-tight">
      <div className="flex items-center gap-1.5 text-[10px] tracking-wide uppercase opacity-60">
        {status && <span className="inline-block size-2 shrink-0 rounded-full" style={{ background: status.color }} />}
        {KIND_LABEL[n.kind]}
        {hot && <span className="ml-auto text-[#ff4d9a] normal-case">selected</span>}
      </div>
      <div className="mt-0.5 truncate text-[14px]">{n.label}</div>
      <div className="text-muted-foreground mt-0.5 truncate text-[11px] tabular-nums">{subtitle(n, scan, status)}</div>
    </div>
  );
}

/** Lanes, top to bottom: AI apps → Director, guards and checks → shared homes and connectors → skills → projects. */
function shape(scan: Scan, focus: Set<string>, statusOf: Map<string, Status>) {
  const linked = new Set(scan.edges.filter((e) => ['points to project', 'reads rules from', 'state kept in'].includes(e.label)).flatMap((e) => [e.source, e.target]));
  const keep = (n: LiveNode) =>
    !['skill', 'repo'].includes(n.kind) || linked.has(n.id) || statusOf.has(n.id) || focus.has(n.id) ||
    Boolean(n.meta.director || n.meta.conductor) || (n.kind === 'skill' && n.meta.scope !== 'shared');
  const shown = scan.nodes.filter(keep);
  const hidden = scan.nodes.filter((n) => !keep(n));

  const style = (n: LiveNode): CSSProperties => {
    const st = statusOf.get(n.id);
    const hot = focus.has(n.id);
    const spot = Boolean(n.meta.director || n.meta.conductor);
    const border = hot ? '#ff0071' : st && st.color !== OK ? st.color : n.kind === 'hub' || spot ? '#ff4d9a' : '#3a3a3a';
    return {
      width: W, borderRadius: 12, padding: '8px 10px', color: 'inherit',
      background: n.kind === 'hub' || n.kind === 'director' ? 'rgba(255,0,113,0.10)' : 'var(--card, #1a1a1a)',
      border: `1.5px solid ${border}`,
      boxShadow: hot || spot ? '0 0 18px rgba(255,0,113,0.35)' : undefined,
      fontWeight: ['hub', 'app', 'director'].includes(n.kind) ? 600 : 400,
    };
  };
  const toNode = (n: LiveNode, position: { x: number; y: number }, extra: Partial<Node> = {}): Node => ({
    id: n.id, position, data: { label: card(n, scan, statusOf.get(n.id) ?? null, focus.has(n.id)) }, style: style(n), ...extra,
  });

  const nodes: Node[] = [];
  const lane = (y: number, text: string) =>
    nodes.push({ id: `lane:${text}`, position: { x: 0, y: y - 26 }, draggable: false, selectable: false, data: { label: text },
      style: { width: 600, border: 'none', background: 'transparent', padding: 0, fontSize: 12, color: '#ff4d9a', textAlign: 'left' } });

  const apps = shown.filter((n) => n.kind === 'app');
  const groupW = apps.length * (W + GAP) + GAP;
  nodes.push({ id: 'group:apps', type: 'group', position: { x: 0, y: 0 }, data: { label: '' }, selectable: false,
    style: { width: groupW, height: 120, borderRadius: 16, border: '2px solid #ff0071', background: 'rgba(255,0,113,0.05)' } });
  nodes.push({ id: 'group:apps:label', position: { x: GAP, y: 6 }, parentId: 'group:apps', draggable: false, selectable: false,
    data: { label: 'Your AI apps (same rules, skills, connectors)' },
    style: { width: groupW - 2 * GAP, fontSize: 12, border: 'none', background: 'transparent', color: '#ff4d9a', padding: 0, textAlign: 'left' } });
  apps.forEach((n, i) => nodes.push(toNode(n, { x: GAP + i * (W + GAP), y: 32 }, { parentId: 'group:apps', extent: 'parent' })));

  let y = 200;
  const row = (list: LiveNode[], title: string) => {
    if (!list.length) return;
    lane(y, title);
    list.forEach((n, i) => nodes.push(toNode(n, { x: (i % PER_ROW) * (W + GAP), y: y + Math.floor(i / PER_ROW) * ROW })));
    y += Math.ceil(list.length / PER_ROW) * ROW + 56;
  };
  const order: Kind[] = ['director', 'check', 'hook'];
  row(shown.filter((n) => order.includes(n.kind)).sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind)), 'Director, guards and checks');
  row(shown.filter((n) => n.kind === 'hub' || n.kind === 'connector').sort((a, b) => (a.kind === 'hub' ? -1 : 1) - (b.kind === 'hub' ? -1 : 1)), 'Shared homes and connectors');
  row(shown.filter((n) => n.kind === 'skill'), 'Skills worth seeing (Director, Conductor, app-only or flagged)');
  row(shown.filter((n) => n.kind === 'repo'), 'Projects those skills point to');
  (['skill', 'repo'] as const).forEach((kind, i) => {
    const count = hidden.filter((n) => n.kind === kind).length;
    if (!count) return;
    nodes.push({ id: `more:${kind}`, position: { x: i * (W + GAP), y: y - 26 }, selectable: false,
      data: { label: `+ ${count} more ${kind === 'skill' ? 'shared skills' : 'projects'}, all fine` },
      style: { width: W, fontSize: 13, borderRadius: 12, padding: 8, border: '1.5px dashed #3a3a3a', opacity: 0.8 } });
  });

  const ids = new Set(nodes.map((n) => n.id));
  const EDGE_COLOR: Record<string, string> = { 'runs hook': '#f5a524', 'guarded by': OK, 'uses connector': '#8b5cf6' };
  const edges: Edge[] = scan.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e) => {
      const on = focus.has(e.source) || focus.has(e.target);
      return {
        id: e.id, source: e.source, target: e.target,
        label: on ? e.label : undefined,
        animated: on,
        style: { stroke: on ? '#ff0071' : EDGE_COLOR[e.label] ?? '#555', strokeWidth: on ? 2 : 1, opacity: focus.size && !on ? 0.15 : 0.7 },
      };
    });
  return { nodes, edges };
}

export function LiveSetupPanel() {
  const { resolvedTheme } = useTheme();
  const [scan, setScan] = useState<Scan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState<Set<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [chipKey, setChipKey] = useState<string | null>(null);
  const flow = useRef<ReactFlowInstance | null>(null);

  const load = useCallback(async function load(rescan: boolean, followUp = true): Promise<void> {
    if (rescan) setBusy(true);
    try {
      const res = await fetch('/api/live-setup', { method: rescan ? 'POST' : 'GET', cache: 'no-store' });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? 'Scan unavailable');
      setScan(body as Scan);
      setError(null);
      // An old scan means the server is refreshing it behind the scenes: pick up the fresh one shortly.
      if (!rescan && followUp && Date.now() - new Date((body as Scan).scanned_at).getTime() > 150_000) {
        window.setTimeout(() => void load(false, false), 6_000);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      if (rescan) setBusy(false);
    }
  }, []);

  // Every minute; the server rescans the Mac itself when the last scan is over 2 minutes old.
  usePoll(() => load(false), 60_000);

  const statusOf = useMemo(() => {
    const m = new Map<string, Status>();
    if (!scan) return m;
    const rank: Severity[] = ['high', 'medium', 'you', 'watch', 'setup', 'low'];
    for (const p of [...scan.problems].sort((a, b) => rank.indexOf(b.severity) - rank.indexOf(a.severity))) {
      for (const id of p.node_ids) m.set(id, { color: SEV_COLOR[p.severity], word: SEV_WORD[p.severity] });
    }
    for (const n of scan.nodes) {
      if (!m.has(n.id) && (n.kind === 'hook' || n.kind === 'check') && !n.meta.broken && n.meta.state !== 'unknown') {
        m.set(n.id, { color: OK, word: 'ok' });
      }
    }
    return m;
  }, [scan]);

  const graph = useMemo(() => (scan ? shape(scan, focus, statusOf) : null), [scan, focus, statusOf]);
  const byId = useMemo(() => new Map((scan?.nodes ?? []).map((n) => [n.id, n])), [scan]);
  const selected = selectedId ? byId.get(selectedId) ?? null : null;

  if (!scan || !graph) {
    return (
      <div className="p-4">
        <p className="text-muted-foreground">{error ?? 'Loading live setup…'}</p>
        <Button className="mt-3" size="sm" onClick={() => void load(true)} disabled={busy}>
          {busy ? 'Scanning…' : 'Rescan my Mac'}
        </Button>
      </div>
    );
  }

  const bySev = (...s: Severity[]) => scan.problems.filter((p) => s.includes(p.severity));
  const broken = bySev('high', 'medium');
  const you = bySev('you');
  const setup = bySev('setup');
  const hooks = scan.nodes.filter((n) => n.kind === 'hook');
  const brokenHooks = hooks.filter((n) => n.meta.broken);
  const gh = byId.get('check:github');
  const director = byId.get('director:now');
  const ghPassed = gh?.meta.state === 'success';
  // Light up the cards and fly the camera to them, so a chip click is readable at once.
  const focusOn = (ids: string[]) => {
    setFocus(new Set(ids));
    setSelectedId(ids[0] ?? null);
    const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.setTimeout(() => {
      void flow.current?.fitView({ nodes: ids.map((id) => ({ id })), padding: 0.5, maxZoom: 1.1, duration: reduce ? 0 : 450 });
    }, 0);
  };
  const clear = () => {
    setFocus(new Set());
    setSelectedId(null);
    void flow.current?.fitView({ padding: 0.08, duration: 300 });
  };

  const chips: { key: string; color: string; text: string; ids: string[] }[] = [
    { key: 'broken', color: broken.length ? '#ff0071' : OK, text: broken.length ? `${broken.length} broken` : 'Nothing broken', ids: broken.flatMap((p) => p.node_ids) },
    ...(you.length ? [{ key: 'you', color: '#f5a524', text: `${you.length} waiting on you`, ids: you.flatMap((p) => p.node_ids) }] : []),
    ...(director ? [{ key: 'director', color: '#ff4d9a', text: `Director: ${subtitle(director, scan, null)}`, ids: [director.id] }] : []),
    { key: 'hooks', color: brokenHooks.length ? '#ff0071' : OK, text: brokenHooks.length ? `${brokenHooks.length} of ${hooks.length} guards broken` : `${hooks.length} guards running`, ids: hooks.map((n) => n.id) },
    ...(gh ? [{ key: 'gh', color: ghPassed ? OK : gh.meta.state === 'unknown' ? '#8a8a8a' : '#ff0071', text: `GitHub check ${ghPassed ? 'passed' : String(gh.meta.state)}`, ids: [gh.id] }] : []),
    ...(setup.length ? [{ key: 'setup', color: '#3b82f6', text: `${setup.length} need one-time setup`, ids: setup.flatMap((p) => p.node_ids) }] : []),
  ];

  const activeChip = chips.find((c) => c.key === chipKey) ?? null;
  const missions = (selected?.meta.missions ?? []) as Mission[];
  const quiet = (selected?.meta.quiet ?? []) as Quiet[];
  const quietNames = new Set(quiet.map((q) => q.name));
  const runs = (selected?.meta.runs ?? []) as string[];
  const scripts = (selected?.meta.scripts ?? []) as string[];

  return (
    <div className="grid h-full min-h-0 grid-cols-1 2xl:grid-cols-[1fr_340px]">
      <div className="flex min-h-[75vh] flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b p-3 text-sm">
          <strong>Live setup</strong>
          <span className="text-muted-foreground tabular-nums">
            {scan.summary.app} apps · {scan.summary.connector} connectors · {scan.summary.skill} skills · {scan.summary.repo} projects ·
            updated {ago(scan.scanned_at)} (auto every 2 min)
          </span>
          <Button size="sm" onClick={() => void load(true)} disabled={busy}>
            {busy ? 'Scanning…' : 'Rescan now'}
          </Button>
          {/* Always takes its space, so the chips below never jump when it appears. */}
          <Button size="sm" variant="outline" onClick={clear} disabled={focus.size === 0} className={focus.size === 0 ? 'invisible' : undefined}>
            Clear highlight
          </Button>
        </div>
        <div className="flex flex-wrap gap-2 border-b px-3 py-2" role="toolbar" aria-label="Status at a glance">
          {chips.map((c) => (
            <button
              key={c.key}
              type="button"
              onClick={() => {
                setChipKey(c.key);
                focusOn(c.ids);
              }}
              aria-pressed={chipKey === c.key}
              className="hover:bg-muted aria-pressed:bg-muted flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition-colors active:scale-[0.97] motion-reduce:transition-none"
              style={{ borderColor: c.color }}
            >
              <span className="size-2 rounded-full" style={{ background: c.color }} aria-hidden />
              {c.text}
            </button>
          ))}
        </div>
        {activeChip && (
          <div className="relative border-b px-3 pb-2">
            <button type="button" aria-label="Close explanation" className="text-muted-foreground hover:text-foreground absolute top-2 right-3 text-sm" onClick={() => setChipKey(null)}>×</button>
            <Meaning e={explainChip(activeChip.key, activeChip.text)} />
          </div>
        )}
        <div className="text-muted-foreground flex flex-wrap gap-x-5 gap-y-1 px-3 pt-2 text-[11px]">
          <span><span style={{ color: '#ff0071' }}>●</span> broken</span>
          <span><span style={{ color: '#f5a524' }}>●</span> needs you or quiet</span>
          <span><span style={{ color: '#3b82f6' }}>●</span> needs setup</span>
          <span><span style={{ color: OK }}>●</span> guard or check ok</span>
          <span>Lines: <span style={{ color: '#f5a524' }}>orange</span> runs a guard · <span style={{ color: '#8b5cf6' }}>purple</span> uses a connector · <span style={{ color: OK }}>green</span> checked by GitHub. Click anything to trace its links.</span>
        </div>
        <ReactFlow
          className="min-h-0 flex-1"
          nodes={graph.nodes}
          edges={graph.edges}
          colorMode={resolvedTheme === 'dark' ? 'dark' : 'light'}
          fitView
          fitViewOptions={{ padding: 0.08 }}
          minZoom={0.05}
          proOptions={{ hideAttribution: true }}
          onInit={(instance) => {
            flow.current = instance;
          }}
          onNodeClick={(_, n) => {
            if (!byId.has(n.id)) return;
            setSelectedId(n.id);
            setFocus(new Set([n.id]));
          }}
          onPaneClick={() => {
            setFocus(new Set());
            setSelectedId(null);
          }}
        >
          <Background />
          <Controls />
          <MiniMap pannable zoomable style={{ width: 150, height: 100 }} bgColor={resolvedTheme === 'dark' ? '#111113' : '#ffffff'} />
          <Panel position="top-right">
          {selected && (
            <div className="bg-background/95 max-h-[70vh] w-[300px] overflow-auto rounded-lg border p-3 text-sm shadow-lg backdrop-blur">
              <div className="flex items-center justify-between">
                <div className="text-muted-foreground text-xs">{KIND_LABEL[selected.kind]}</div>
                <button type="button" aria-label="Close details" className="text-muted-foreground hover:text-foreground px-1 text-sm" onClick={() => setSelectedId(null)}>×</button>
              </div>
              <div className="text-base font-semibold">{selected.label}</div>
              <div className="text-muted-foreground mt-1 text-xs">{subtitle(selected, scan, statusOf.get(selected.id) ?? null)}</div>
              <Meaning e={explainNode(selected, statusOf.get(selected.id)?.word ?? null)} />
              {typeof selected.meta.path === 'string' && <div className="text-muted-foreground mt-1 break-all text-xs">{selected.meta.path}</div>}
              {runs.length > 0 && <ul className="mt-2 space-y-0.5 text-xs">{runs.map((r) => <li key={r}>Runs on {r}</li>)}</ul>}
              {scripts.length > 0 && (
                <ul className="text-muted-foreground mt-2 space-y-0.5 break-all text-[11px]">{scripts.map((s) => <li key={s}>{s}</li>)}</ul>
              )}
              {selected.kind === 'check' && (
                <div className="mt-2 space-y-1 text-xs">
                  <div>Last run: {String(selected.meta.title ?? '?')}</div>
                  <div>Local gate: {String(selected.meta.local_gate ?? '?')}</div>
                  {typeof selected.meta.url === 'string' && (
                    <a className="text-[#ff4d9a] underline" href={selected.meta.url} target="_blank" rel="noreferrer">Open on GitHub</a>
                  )}
                </div>
              )}
              {selected.kind === 'director' && (
                <div className="mt-2 text-xs">
                  <div className="text-muted-foreground">
                    Newest trace: {ago(selected.meta.last_trace as string)} · export file updated {ago(selected.meta.trace_export as string)}
                  </div>
                  {(['needs me', 'looks stuck', 'looks done'] as const).map((bucket) => {
                    const group = quiet.filter((q) => q.bucket === bucket);
                    if (!group.length) return null;
                    return (
                      <section key={bucket} className="mt-3">
                        <h3 className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: BUCKET_TEXT[bucket].color }}>
                          <span className="size-2 rounded-full" style={{ background: BUCKET_TEXT[bucket].color }} aria-hidden />
                          {BUCKET_TEXT[bucket].label} ({group.length})
                        </h3>
                        <p className="text-muted-foreground mt-0.5 text-[11px]">What to do: {BUCKET_TEXT[bucket].todo}</p>
                        <ul className="mt-1 space-y-1.5">
                          {group.map((q) => (
                            <li key={q.name} className="rounded border px-2 py-1">
                              <div>{q.name}</div>
                              <div className="text-muted-foreground tabular-nums">Quiet {q.quiet_days} days. {q.why}</div>
                            </li>
                          ))}
                        </ul>
                      </section>
                    );
                  })}
                  {missions.some((m) => !quietNames.has(m.name)) && (
                    <section className="mt-3">
                      <h3 className="text-xs font-semibold" style={{ color: OK }}>Moving fine</h3>
                      <ul className="mt-1 space-y-1">
                        {missions.filter((m) => !quietNames.has(m.name)).map((m) => (
                          <li key={m.name}>{m.name} <span className="text-muted-foreground tabular-nums">(updated {m.quiet_days ?? '?'}d ago)</span></li>
                        ))}
                      </ul>
                    </section>
                  )}
                </div>
              )}
              {Array.isArray(selected.meta.missing) && (
                <div className="mt-2 text-xs text-[#ff4d9a]">Points to missing: {(selected.meta.missing as string[]).join(', ')}</div>
              )}
              <div className="text-muted-foreground mt-2 text-xs tabular-nums">
                {scan.edges.filter((e) => e.source === selected.id).length} outgoing · {scan.edges.filter((e) => e.target === selected.id).length} incoming links
              </div>
            </div>
          )}
          </Panel>
        </ReactFlow>
      </div>

      <aside className="min-h-0 overflow-auto border-t p-4 2xl:border-t-0 2xl:border-l">
        {(() => {
          const mine = [
            ...(((director?.meta.quiet ?? []) as Quiet[]).filter((q) => q.bucket === 'needs me').map((q) => ({ key: q.name, title: q.name, why: `Quiet ${q.quiet_days} days. ${q.why}`, ids: [director!.id] }))),
            ...scan.problems.filter((p) => p.severity === 'you' || p.severity === 'high' || p.severity === 'medium').map((p) => ({ key: p.title, title: p.title, why: p.detail, ids: p.node_ids })),
          ];
          return (
            <section className="mb-5" aria-label="Needs me">
              <h2 className="font-medium text-[#f5a524]">Needs me ({mine.length})</h2>
              {mine.length === 0 ? (
                <p className="text-muted-foreground mt-1 text-xs">Nothing is waiting on you.</p>
              ) : (
                <>
                  <p className="text-muted-foreground mt-1 text-xs">What to do: answer each one in the Director chat (or tell me to fix the broken ones).</p>
                  <ul className="mt-2 space-y-1.5">
                    {mine.map((m) => (
                      <li key={m.key}>
                        <button type="button" onClick={() => focusOn(m.ids)} className="hover:bg-muted w-full rounded-lg border border-[#f5a524] p-2 text-left text-sm transition-colors">
                          {m.title}
                          <div className="text-muted-foreground mt-0.5 text-xs">{m.why}</div>
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          );
        })()}
        <h2 className="font-medium">Problems and watch list ({scan.problems.length})</h2>
        <p className="text-muted-foreground mt-1 text-xs">Click one to light it up on the map.</p>
        <ul className="mt-3 space-y-2">
          {scan.problems.map((p, i) => (
            <li key={`${p.title}-${i}`} className="rounded-lg border p-2">
              <button type="button" className="hover:bg-muted w-full rounded-md p-1 text-left text-sm transition-colors" onClick={() => focusOn(p.node_ids)}>
                <span className="mr-2 rounded-full px-2 py-0.5 text-xs font-semibold text-white" style={{ background: SEV_COLOR[p.severity] }}>
                  {SEV_WORD[p.severity]}
                </span>
                {p.title}
                <div className="text-muted-foreground mt-1 text-xs break-words">{p.detail}</div>
              </button>
              <Meaning e={explainProblem(p)} collapsible />
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
