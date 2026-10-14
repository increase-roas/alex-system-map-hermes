'use client';

import {
  Background, Controls, Handle, MiniMap, Panel, Position, ReactFlow, ReactFlowProvider, applyEdgeChanges, applyNodeChanges, useReactFlow,
  type Edge, type Node, type NodeProps, type OnEdgesChange, type OnNodesChange, type ReactFlowInstance,
} from '@xyflow/react';
import Shape from './pro/shape';
import type { ShapeType } from './pro/shape/types';
import { useHelperLines } from './pro/helper-lines/useHelperLines';
import { RoutableEdgeComponent } from './pro/edge-routing/RoutableEdge';
import { useLibavoid } from './pro/edge-routing/use-libavoid';
import { useTheme } from 'next-themes';
import { useCallback, useEffect, useMemo, useRef, useState, type ComponentProps, type CSSProperties, type ReactNode } from 'react';

import { Button } from '@/components/ui/button';
import { usePoll } from '@/hooks/use-poll';

import { Meaning } from './meaning';
import type { Explanation } from './explain';

type Status = 'ok' | 'watch' | 'you' | 'broken' | 'conflict' | 'unknown';
type OrgNode = {
  id: string; layer: string; kind: string; label: string; purpose: string; explain: Explanation;
  status: Status; sources: string[]; meta: Record<string, unknown>;
};
type OrgEdge = { id: string; source: string; target: string; kind: string; label: string; evidence: string; proven?: boolean; state?: string };
type Sender = { name: string; state: string; env: string; how: string; proof: string; node: string | null };
type SdkStep = { step: number; title: string; status: 'proven' | 'partial' | 'gap'; why: string; proof: string };
type Rail = { layer: string; title: string; running: number; stuck: number; watch: number; unknown: number; total: number };
type NeedsMe = { title: string; why: string; todo: string; node_id: string };
type Counts = { total: number; matched: number; connected: number; purposed: number };
type OrgMap = {
  built_at: string; scanned_at: string; evidence?: { lines: number; proven: number; unproven: { from: string; to: string; kind: string }[] }; layers: [string, string][]; nodes: OrgNode[]; edges: OrgEdge[];
  sdk: SdkStep[]; sdk_plan: { file: string; missing_live_copy: boolean }; rail: Rail[]; needs_me: NeedsMe[];
  rule_audit: { tool_pairs: number; unreviewed: { file: string; new_pairs: number }[]; conflicts: { id: string; title: string }[]; one_agent: { agent: string; rule: string; source: string }[] };
  catalog: { before: Counts; after: Counts; hidden_historical: number; unmatched: { name: string; kind: string; drawer: 'gone' | 'cloud'; purpose: string }[]; map_nodes: number; map_nodes_purposed: number; mission_skill_links: number };
};

const STATUS_COLOR: Record<Status, string> = {
  ok: '#17c964', watch: '#f5a524', you: '#f5a524', broken: '#ff0071', conflict: '#ff0071', unknown: '#6b6b6b',
};
const STATUS_WORD: Record<Status, string> = {
  ok: 'running', watch: 'watch', you: 'needs you', broken: 'stuck', conflict: 'rule conflict', unknown: 'not checked',
};
const SDK_COLOR = { proven: '#17c964', partial: '#f5a524', gap: '#ff0071' } as const;
const W = 214, GAP = 22, ROW = 92, PER_ROW = 9, BAND_GAP = 70;
const RAIL_X = PER_ROW * (W + GAP) + 80;
/** Lines always drawn (the org chart's backbone); everything else appears when you click a box. */
const BACKBONE = new Set(['talks', 'dispatches', 'runs-on', 'runs', 'reaches', 'reviews', 'verdict', 'sendback', 'traces']);
/** Sender badges on the Observability box: live = traces seen landing, planned = drawn dashed until it is live. */
const SENDER_COLOR: Record<string, string> = { live: '#17c964', planned: '#f5a524', 'not wired': '#6b6b6b', unknown: '#6b6b6b' };
function SenderBadge({ state }: { state: string }) {
  const c = SENDER_COLOR[state] ?? '#6b6b6b';
  return <span className="inline-block shrink-0 rounded border px-1 text-[9px] font-semibold uppercase" style={{ color: c, borderColor: c }}>{state}</span>;
}
const RAIL_LEFT_X = -(W + 90);

function ago(iso?: string | null) {
  if (!iso) return '?';
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return s < 90 ? `${s}s ago` : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 129600 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`;
}

function reviewBadge(n: OrgNode) {
  if (n.kind !== 'mission') return null;
  const review = n.meta.review as { verdict?: string; path?: string; at?: string } | undefined;
  const badge = review?.verdict === 'PASS' ? ['PASS', '#17c964']
    : (review?.verdict === 'FAIL' || review?.verdict === 'fail') ? ['FAIL', '#ff0071']
      : review?.verdict === 'verified_without_review' ? ['no review', '#f5a524'] : null;
  return badge ? <span className="ml-1 inline-block shrink-0 rounded border px-1 text-[10px] font-semibold"
    style={{ color: badge[1], borderColor: badge[1] }} title={[review?.path, review?.at].filter(Boolean).join(' ')}>{badge[0]}</span> : null;
}

function card(n: OrgNode) {
  return (
    <div className="text-left leading-tight">
      <div className="flex items-center gap-1.5 text-[9px] tracking-wide uppercase opacity-60">
        <span className="inline-block size-2 shrink-0 rounded-full" style={{ background: STATUS_COLOR[n.status] }} />
        {n.kind}
        <span className="ml-auto normal-case">{STATUS_WORD[n.status]}</span>
      </div>
      <div className="mt-0.5 flex items-center text-[13px]"><span className="truncate">{n.label}</span>{reviewBadge(n)}</div>
      <div className="text-muted-foreground mt-0.5 line-clamp-2 text-[10px]">
        {n.kind === 'app' && Array.isArray(n.meta.differences)
          ? ((n.meta.differences as string[]).join(' · ') || 'nothing different from the shared setup')
          : n.kind === 'observability' && Array.isArray(n.meta.senders)
            ? <span className="flex flex-wrap gap-1">{(n.meta.senders as Sender[]).map((x) => <span key={x.name} className="inline-flex items-center gap-0.5">{x.name}<SenderBadge state={x.state} /></span>)}</span>
          : Array.isArray(n.meta.logins_missing) && (n.meta.logins_missing as string[]).length
            ? `card login gone: ${(n.meta.logins_missing as string[]).join(', ')}`
            : n.purpose}
      </div>
    </div>
  );
}

/** React Flow Pro "Shapes": each kind of box gets its own outline so you can tell them apart at a glance. */
const SHAPE: Record<string, [ShapeType, number, number, string]> = {
  director: ['diamond', 320, 132, '30px 70px'],
  conductor: ['hexagon', 290, 96, '14px 40px'],
  reviewer: ['hexagon', 230, 88, '10px 30px'],
  hub: ['circle', W, 86, '18px 34px'],
  toolkit: ['cylinder', W, 84, '20px 14px 6px'],
  local: ['cylinder', W, 84, '20px 14px 6px'],
  skill: ['parallelogram', W, 72, '8px 30px'],
  rule: ['arrow-rectangle', W, 76, '8px 30px 8px 12px'],
  hook: ['arrow-rectangle', W, 76, '8px 30px 8px 12px'],
  check: ['arrow-rectangle', W, 76, '8px 30px 8px 12px'],
};
type OrgNodeData = { label: ReactNode; shape?: ShapeType; stroke?: string; fill?: string; open?: boolean; pad?: string };
function OrgNodeView({ data, width, height }: NodeProps) {
  const d = data as OrgNodeData;
  return (
    <div className="relative h-full w-full">
      {d.shape && width && height ? (
        <div className="pointer-events-none absolute" style={{ left: 0, top: 0 }} aria-hidden>
          <Shape type={d.shape} width={width} height={height} strokeWidth={1.5} style={{ fill: d.fill, stroke: d.stroke }} />
        </div>
      ) : null}
      <div className="relative" style={d.pad ? { padding: d.pad } : undefined}>{d.label}</div>
      <Handle id="1" type="target" position={Position.Top} isConnectable={false} style={{ opacity: 0, pointerEvents: 'none' }} />
      <Handle id="2" type="source" position={Position.Bottom} isConnectable={false} style={{ opacity: 0, pointerEvents: 'none' }} />
    </div>
  );
}
const NODE_TYPES = { org: OrgNodeView };
const EDGE_TYPES = { routable: RoutableEdgeComponent };

function finish(nodes: Node[], byId: Map<string, OrgNode>) {
  for (const n of nodes) {
    if (n.id.startsWith('lane:')) continue;
    n.type = 'org';
    const o = byId.get(n.id);
    const sh = o ? SHAPE[o.kind] : undefined;
    if (!sh) continue;
    const st = (n.style ?? {}) as CSSProperties;
    const [type, w, h, pad] = sh;
    n.data = { ...n.data, shape: type, pad, stroke: String(st.border ?? '').match(/#[0-9a-f]{3,8}/i)?.[0] ?? '#3a3a3a',
      fill: ['director', 'conductor', 'reviewer', 'hub'].includes(o!.kind) ? 'rgba(255,0,113,0.10)' : 'hsl(var(--card))' };
    n.style = { ...st, width: w, height: h, padding: 0, border: 'none', background: 'transparent', borderRadius: 0,
      filter: st.boxShadow ? 'drop-shadow(0 0 10px rgba(255,0,113,0.55))' : undefined, boxShadow: undefined };
  }
  return nodes;
}

function layout(map: OrgMap, focus: Set<string>, open: Set<string>) {
  const nodes: Node[] = [];
  const bandY: Record<string, number> = {};
  const neighbors = new Set<string>();
  for (const e of map.edges) {
    if (focus.has(e.source)) neighbors.add(e.target);
    if (focus.has(e.target)) neighbors.add(e.source);
  }
  const dim = focus.size > 0;
  const style = (n: OrgNode): CSSProperties => {
    const hot = focus.has(n.id);
    const near = neighbors.has(n.id);
    const bad = n.status === 'broken' || n.status === 'conflict';
    return {
      width: W, borderRadius: ['director', 'conductor'].includes(n.kind) ? 999 : ['hub', 'toolkit', 'local'].includes(n.kind) ? 22 : 10, padding: '6px 9px', color: 'inherit',
      background: ['you', 'director', 'conductor', 'hub'].includes(n.kind) ? 'rgba(255,0,113,0.10)' : 'hsl(var(--card))',
      border: `1.5px solid ${hot ? '#ff0071' : bad ? '#ff0071' : n.status === 'you' || n.status === 'watch' ? '#f5a524' : '#3a3a3a'}`,
      boxShadow: hot ? '0 0 18px rgba(255,0,113,0.45)' : undefined,
      opacity: dim && !hot && !near ? 0.25 : 1,
      transition: 'opacity 150ms ease-out',
    };
  };
  let y = 0;
  const placedX = new Map<string, number>();
  for (const [layer, title] of map.layers) {
    const list = map.nodes.filter((n) => n.layer === layer);
    if (layer === 'engine') {
      bandY.engine = y;
      nodes.push({ id: 'lane:engine', position: { x: 0, y: y - 24 }, selectable: false, draggable: false, data: { label: title },
        style: { width: 600, border: 'none', background: 'transparent', padding: 0, fontSize: 12, color: '#ff4d9a', textAlign: 'left' } });
      nodes.push({
        id: 'sdk', position: { x: 0, y }, draggable: false,
        data: { label: (
          <div className="text-left">
            <div className="flex items-center justify-between text-[11px] font-semibold">
              <span>Master Agent Operations SDK: 8 parts of the build plan</span>
              <span className="text-muted-foreground font-normal">graded from the SDK’s own test and verification files{map.sdk_plan.missing_live_copy ? ' + Oct 8 plan backup' : ' + current plan'}</span>
            </div>
            <div className="mt-1.5 grid grid-cols-8 gap-1.5">
              {map.sdk.map((s) => (
                <div key={s.step} className="rounded-md border p-1.5" style={{ borderColor: SDK_COLOR[s.status], background: `${SDK_COLOR[s.status]}18` }} title={`${s.why}\nProof: ${s.proof}`}>
                  <div className="text-[9px] font-semibold uppercase" style={{ color: SDK_COLOR[s.status] }}>{s.step}. {s.status}</div>
                  <div className="text-[11px] leading-tight">{s.title}</div>
                </div>
              ))}
            </div>
          </div>
        ) },
        style: { width: PER_ROW * (W + GAP) - GAP, borderRadius: 12, padding: 10, border: '1.5px dashed #ff4d9a', background: 'rgba(255,0,113,0.04)', color: 'inherit' },
      });
      y += 120 + BAND_GAP;
      continue;
    }
    if (!list.length) continue;
    bandY[layer] = y;
    if (layer === 'missions') {
      // Customer / project boxes (React Flow Pro: parent-child + expand/collapse). Missions live inside their box.
      nodes.push({ id: `lane:${layer}`, position: { x: 0, y: y - 24 }, selectable: false, draggable: false, data: { label: title },
        style: { width: 600, border: 'none', background: 'transparent', padding: 0, fontSize: 12, color: '#ff4d9a', textAlign: 'left' } });
      const groups = new Map<string, OrgNode[]>();
      for (const n of list) {
        const p = String(n.meta.project ?? (n.id === 'mission:parked' ? 'Parked' : 'Personal / system'));
        groups.set(p, [...(groups.get(p) ?? []), n]);
      }
      const names = [...groups.keys()].sort((a, b) => (a === 'Personal / system' || a === 'Parked' ? 1 : 0) - (b === 'Personal / system' || b === 'Parked' ? 1 : 0) || a.localeCompare(b));
      const maxW = PER_ROW * (W + GAP) - GAP;
      let gx = 0, gy = y, rowH = 0;
      for (const name of names) {
        const ms = groups.get(name)!;
        const isOpen = open.has(name);
        const cols = isOpen ? Math.min(3, ms.length) : 1;
        const gw = isOpen ? cols * (W + GAP) + GAP : W + 30;
        const gh = isOpen ? 44 + Math.ceil(ms.length / cols) * ROW : 78;
        if (gx > 0 && gx + gw > maxW) { gx = 0; gy += rowH + GAP; rowH = 0; }
        const bad = ms.filter((m) => m.status === 'broken' || m.status === 'you').length;
        const gid = `project:${name}`;
        nodes.push({
          id: gid, position: { x: gx, y: gy },
          data: { open: isOpen, label: (
            <div className="text-left">
              <div className="flex items-center gap-2 text-[12px] font-semibold"><span aria-hidden>{isOpen ? '▾' : '▸'}</span>{name}</div>
              <div className="text-muted-foreground text-[10px] tabular-nums">{ms.length} mission{ms.length === 1 ? '' : 's'}{bad ? ` · ${bad} stuck or need you` : ''}{isOpen ? '' : ' · click to open'}</div>
            </div>
          ) },
          style: { width: gw, height: gh, borderRadius: 14, padding: '8px 12px', color: 'inherit', cursor: 'pointer',
            border: `1.5px dashed ${bad ? '#f5a524' : '#555'}`, background: 'rgba(255,255,255,0.025)',
            opacity: focus.size && !focus.has(gid) && !ms.some((m) => focus.has(m.id) || neighbors.has(m.id)) ? 0.35 : 1 },
        });
        if (isOpen) ms.forEach((m, i) => nodes.push({
          id: m.id, parentId: gid, extent: 'parent',
          position: { x: GAP + (i % cols) * (W + GAP), y: 40 + Math.floor(i / cols) * ROW },
          data: { label: card(m) }, style: style(m),
        }));
        gx += gw + GAP; rowH = Math.max(rowH, gh);
      }
      y = gy + rowH + BAND_GAP;
      continue;
    }
    nodes.push({ id: `lane:${layer}`, position: { x: 0, y: y - 24 }, selectable: false, draggable: false, data: { label: title },
      style: { width: 600, border: 'none', background: 'transparent', padding: 0, fontSize: 12, color: '#ff4d9a', textAlign: 'left' } });
    const order = ['rule', 'hook', 'check', 'card', 'director', 'conductor', 'reviewer', 'mission', 'skill', 'agent', 'observability', 'hub', 'toolkit', 'local'];
    // Auto-layout ordering (the idea behind the Pro "Auto Layout" layered engines): put each box under the
    // boxes it connects to above it, so lines run short and straight instead of crossing the whole map.
    const bary = (n: OrgNode) => {
      const xs = map.edges.filter((e) => e.source === n.id || e.target === n.id)
        .map((e) => placedX.get(e.source === n.id ? e.target : e.source)).filter((v): v is number => v !== undefined);
      return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : Number.POSITIVE_INFINITY;
    };
    const sorted = [...list].sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind) || bary(a) - bary(b) || a.label.localeCompare(b.label));
    const columnStep = layer === 'conductor' ? Math.max(W, ...sorted.map((n) => SHAPE[n.kind]?.[1] ?? W)) + GAP : W + GAP;
    const rows = Math.ceil(sorted.length / PER_ROW);
    const rowH = Math.max(ROW, ...sorted.map((n) => (SHAPE[n.kind]?.[2] ?? 72) + 18));
    sorted.forEach((n, i) => {
      const r = Math.floor(i / PER_ROW);
      const inRow = r === rows - 1 ? sorted.length - r * PER_ROW : PER_ROW;
      // Short rows are centred on the same column grid, so every column lines up top to bottom.
      const offset = Math.floor((PER_ROW - inRow) / 2) * (W + GAP);
      const w = SHAPE[n.kind]?.[1] ?? W;
      const x = offset + (i % PER_ROW) * columnStep - (w - W) / 2;
      placedX.set(n.id, x + w / 2);
      nodes.push({ id: n.id, position: { x, y: y + r * rowH }, data: { label: card(n) }, style: style(n) });
    });
    y += rows * rowH + BAND_GAP;
  }
  // Shared rules and guards: one column on the left, the same for every app (no wires to each app).
  const shared = map.nodes.filter((n) => n.layer === 'rail-rules')
    .sort((a, b) => ['rule', 'hook', 'check'].indexOf(a.kind) - ['rule', 'hook', 'check'].indexOf(b.kind));
  const top = bandY.apps ?? 0;
  nodes.push({ id: 'lane:shared', position: { x: RAIL_LEFT_X, y: top - 50 }, selectable: false, draggable: false,
    data: { label: 'Shared rules and guards: the same for every app. Differences show on each app box.' },
    style: { width: W, border: 'none', background: 'transparent', padding: 0, fontSize: 12, color: '#ff4d9a', textAlign: 'left' } });
  shared.forEach((n, i) => nodes.push({ id: n.id, position: { x: RAIL_LEFT_X, y: top + i * (ROW - 8) }, data: { label: card(n) }, style: style(n) }));

  // Observatory rail: one box per layer down the right side.
  nodes.push({ id: 'observatory', position: { x: RAIL_X, y: -60 }, data: { label: <div className="text-left text-xs font-semibold">Observatory: running · stuck · proven</div> },
    style: { width: 250, border: '1.5px solid #ff4d9a', borderRadius: 10, background: 'rgba(255,0,113,0.10)', padding: 8, color: 'inherit' } });
  for (const r of map.rail) {
    const ry = bandY[r.layer];
    if (ry === undefined) continue;
    nodes.push({
      id: `rail:${r.layer}`, position: { x: RAIL_X, y: ry }, selectable: false, draggable: false,
      data: { label: (
        <div className="text-left text-[11px] tabular-nums">
          <div className="font-semibold">{r.title}</div>
          <div className="mt-1 flex flex-wrap gap-x-2">
            {r.layer === 'engine' ? (
              <><span style={{ color: SDK_COLOR.proven }}>{(r as Rail & { proven?: number }).proven ?? 0} proven</span><span style={{ color: SDK_COLOR.partial }}>{r.watch} partial</span><span style={{ color: SDK_COLOR.gap }}>{r.stuck} gaps</span></>
            ) : (
              <><span style={{ color: STATUS_COLOR.ok }}>{r.running} running</span>{r.stuck > 0 && <span style={{ color: STATUS_COLOR.broken }}>{r.stuck} stuck/needs you</span>}{r.watch > 0 && <span style={{ color: STATUS_COLOR.watch }}>{r.watch} watch</span>}{r.unknown > 0 && <span className="text-muted-foreground">{r.unknown} not checked</span>}</>
            )}
          </div>
        </div>
      ) },
      style: { width: 250, borderRadius: 10, padding: 8, border: '1px solid #3a3a3a', background: 'hsl(var(--card))', color: 'inherit' },
    });
  }
  const ids = new Set(nodes.map((n) => n.id));
  const projectEdges: Edge[] = nodes.filter((n) => n.id.startsWith('project:')).map((n) => ({
    id: `runs:director->${n.id}`, source: 'director', target: n.id, style: { stroke: '#555', strokeWidth: 1, opacity: 0.35 },
  }));
  const edges: Edge[] = [...projectEdges, ...map.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .filter((e) => !(e.kind === 'runs' && e.source === 'director' && e.target.startsWith('mission:')))
    .filter((e) => BACKBONE.has(e.kind) || focus.has(e.source) || focus.has(e.target))
    .map((e) => {
      const on = focus.has(e.source) || focus.has(e.target);
      const red = e.kind === 'conflict' || e.kind === 'one-agent';
      const planned = e.state === 'planned';
      const live = e.kind === 'traces' && e.state === 'live';
      return {
        id: e.id, source: e.source, target: e.target,
        label: on || e.kind === 'conflict' || e.kind === 'traces' ? e.label : undefined,
        animated: on && !red,
        style: {
          stroke: red ? '#ff0071' : on ? '#ff4d9a' : live ? '#17c964' : planned ? '#f5a524' : '#555',
          strokeWidth: red ? 2.5 : on ? 2 : 1,
          // A line with no proof file is drawn grey and dashed: the map is claiming something it can't show.
          // A planned line (not sending yet) is dashed too, until its first trace lands.
          strokeDasharray: e.kind === 'one-agent' || e.proven === false || planned ? '6 4' : undefined,
          ...(e.proven === false ? { stroke: '#777' } : {}),
          opacity: dim && !on && !red ? 0.08 : red ? 0.95 : on ? 0.95 : e.kind === 'traces' ? 0.8 : 0.35,
        },
        labelStyle: red ? { fill: '#ff4d9a', fontSize: 11 } : { fontSize: 10 },
      };
    })];
  return { nodes: finish(nodes, new Map(map.nodes.map((n) => [n.id, n]))), edges };
}

/** Draggable map with Pro helper lines (snap guides) and Pro edge routing (lines go around boxes). */
function MapFlow({ graph, routed, onReady, children, ...rest }: {
  graph: { nodes: Node[]; edges: Edge[] }; routed: boolean; onReady: (i: ReactFlowInstance) => void; children: ReactNode;
} & Partial<ComponentProps<typeof ReactFlow>>) {
  const [nodes, setNodes] = useState<Node[]>(graph.nodes);
  const [edges, setEdges] = useState<Edge[]>(graph.edges);
  const moved = useRef(new Map<string, { x: number; y: number }>());
  const { rebuildIndex, updateHelperLines, HelperLines } = useHelperLines();
  const { getNodes } = useReactFlow();
  useEffect(() => {
    const target = graph.nodes.map((n) => (moved.current.has(n.id) ? { ...n, position: moved.current.get(n.id)! } : n));
    let frame = 0;
    setNodes((prev) => {
      const old = new Map(prev.map((n) => [n.id, n]));
      // Keep each box's measured size so React Flow does not hide and re-measure it (that was the flashing).
      const keep = target.map((n) => { const o = old.get(n.id); return o?.measured ? { ...n, measured: o.measured } : n; });
      const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const moves = keep.filter((n) => { const o = old.get(n.id); return o && (o.position.x !== n.position.x || o.position.y !== n.position.y); });
      if (reduce || !moves.length || !prev.length) return keep;
      // Slide boxes to their new spot over 300ms instead of jumping.
      const start = performance.now();
      const step = (t: number) => {
        const k = Math.min(1, (t - start) / 300), e = 1 - (1 - k) ** 3;
        setNodes((cur) => cur.map((n) => {
          const o = old.get(n.id), to = keep.find((x) => x.id === n.id);
          if (!o || !to) return n;
          return { ...n, position: { x: o.position.x + (to.position.x - o.position.x) * e, y: o.position.y + (to.position.y - o.position.y) * e } };
        }));
        if (k < 1) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
      return keep.map((n) => { const o = old.get(n.id); return o ? { ...n, position: o.position } : n; });
    });
    return () => cancelAnimationFrame(frame);
  }, [graph.nodes]);
  useEffect(() => {
    setEdges((prev) => {
      const pts = new Map(prev.map((e) => [e.id, e.data]));
      return graph.edges.map((e) => ({ ...e, sourceHandle: '2', targetHandle: '1', type: routed ? 'routable' : 'default', data: routed ? pts.get(e.id) : undefined }));
    });
  }, [graph.edges, routed]);
  useLibavoid(routed);
  const onNodesChange: OnNodesChange = useCallback((ch) => setNodes((ns) => applyNodeChanges(updateHelperLines(ch, ns), ns)), [updateHelperLines]);
  const onEdgesChange: OnEdgesChange = useCallback((ch) => setEdges((es) => applyEdgeChanges(ch, es)), []);
  return (
    <ReactFlow {...rest} nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} edgeTypes={EDGE_TYPES}
      onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} nodesConnectable={false}
      onInit={onReady}
      onNodeDragStop={(_, n) => { moved.current.set(n.id, n.position); rebuildIndex(getNodes()); }}>
      {children}
      <HelperLines />
    </ReactFlow>
  );
}

export function OrgMapPanel() {
  const { resolvedTheme } = useTheme();
  const [map, setMap] = useState<OrgMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [routed, setRouted] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const flow = useRef<ReactFlowInstance | null>(null);

  const load = useCallback(async (rescan: boolean) => {
    if (rescan) setBusy(true);
    try {
      if (rescan) {
        const r = await fetch('/api/live-setup', { method: 'POST' });
        if (!r.ok) throw new Error('Rescan failed');
      }
      const res = await fetch('/api/org-map', { cache: 'no-store' });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? 'Map unavailable');
      const next = body as OrgMap;
      setMap((prev) => (prev && prev.built_at === next.built_at && prev.nodes.length === next.nodes.length ? prev : next));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      if (rescan) setBusy(false);
    }
  }, []);
  usePoll(() => load(false), 60_000);

  const graph = useMemo(() => (map ? layout(map, focus, open) : null), [map, focus, open]);
  const byId = useMemo(() => new Map((map?.nodes ?? []).map((n) => [n.id, n])), [map]);
  const selected = selectedId ? byId.get(selectedId) ?? null : null;

  const focusOn = (id: string) => {
    if (!byId.has(id)) return;
    const proj = byId.get(id)!.meta.project;
    if (typeof proj === 'string') setOpen((o) => new Set(o).add(proj));
    setSelectedId(id);
    setFocus(new Set([id]));
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const near = map!.edges.filter((e) => e.source === id || e.target === id).map((e) => (e.source === id ? e.target : e.source));
    window.setTimeout(() => void flow.current?.fitView({ nodes: [id, ...near].map((x) => ({ id: x })), padding: 0.35, maxZoom: 1.1, duration: reduce ? 0 : 450 }), 0);
  };

  if (!map || !graph) {
    return (
      <div className="p-4">
        <p className="text-muted-foreground">{error ?? 'Building your map…'}</p>
        <Button className="mt-3" size="sm" onClick={() => void load(true)} disabled={busy}>{busy ? 'Scanning…' : 'Rescan my Mac'}</Button>
      </div>
    );
  }

  const c = map.catalog;
  const gone = c.unmatched.filter((u) => u.drawer === 'gone');
  const cloud = c.unmatched.filter((u) => u.drawer === 'cloud');
  const links = selected ? map.edges.filter((e) => e.source === selected.id || e.target === selected.id) : [];
  const conflicts = selected ? map.edges.filter((e) => e.kind === 'conflict' && (e.source === selected.id || e.target === selected.id)) : [];

  return (
    <div className="grid h-full min-h-0 grid-cols-1 2xl:grid-cols-[1fr_360px]">
      <div className="flex min-h-[80vh] flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b p-3 text-sm">
          <strong>Your system, top down</strong>
          <span className="text-muted-foreground tabular-nums">
            {c.map_nodes} boxes · {map.evidence ? `${map.evidence.proven} of ${map.evidence.lines} lines backed by a proof file` : `${map.edges.length} lines`} · updated {ago(map.built_at)} (auto every 2 min)
          </span>
          <Button size="sm" onClick={() => void load(true)} disabled={busy}>{busy ? 'Scanning…' : 'Rescan now'}</Button>
          <Button size="sm" variant="outline" disabled={focus.size === 0} className={focus.size === 0 ? 'invisible' : undefined}
            onClick={() => { setFocus(new Set()); setSelectedId(null); void flow.current?.fitView({ padding: 0.05, duration: 300 }); }}>
            Clear highlight
          </Button>
          <Button size="sm" variant="outline" onClick={() => setRouted((r) => !r)} aria-pressed={routed}>
            {routed ? 'Lines go around boxes' : 'Straight lines'}
          </Button>
          <Button size="sm" variant="outline" onClick={() => setOpen(new Set(map.nodes.map((n) => n.meta.project).filter((p): p is string => typeof p === 'string')))}>Open all customers</Button>
          <Button size="sm" variant="outline" disabled={open.size === 0} onClick={() => setOpen(new Set())}>Close all</Button>
        </div>

        <p className="text-muted-foreground border-b px-3 py-2 text-xs" title="~/.agents/skills/alex-reviewer/SKILL.md; ~/.agents/skills/alex-director/references/ledger.md">
          Reviewer badge: green passed, red failed, amber marked done with no review
        </p>

        {map.needs_me.length > 0 && (
          <section className="border-b px-3 py-2" aria-label="Needs me">
            <h2 className="text-xs font-semibold text-[#f5a524]">Needs me ({map.needs_me.length})</h2>
            <ul className="mt-1.5 flex flex-wrap gap-2">
              {map.needs_me.map((x, i) => (
                <li key={`${i}-${x.title}`}>
                  <button type="button" onClick={() => focusOn(x.node_id)} title={`${x.why}\nWhat to do: ${x.todo}`}
                    className="hover:bg-muted rounded-full border border-[#f5a524] px-3 py-1 text-left text-xs transition-colors active:scale-[0.97] motion-reduce:transition-none">
                    {x.title}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="text-muted-foreground flex flex-wrap gap-x-5 gap-y-1 px-3 pt-2 text-[11px]">
          <span><span style={{ color: STATUS_COLOR.ok }}>●</span> running</span>
          <span><span style={{ color: STATUS_COLOR.watch }}>●</span> needs you / watch</span>
          <span><span style={{ color: STATUS_COLOR.broken }}>●</span> stuck or rule conflict</span>
          <span><span style={{ color: STATUS_COLOR.unknown }}>●</span> not checked (cloud)</span>
          <span><span style={{ color: '#ff0071' }}>━</span> red line: rules that clash · <span style={{ color: '#ff0071' }}>┅</span> dashed: a rule only one app sees</span>
          <span><span style={{ color: '#17c964' }}>━</span> sends traces to Langfuse (live) · <span style={{ color: '#f5a524' }}>┅</span> planned, not sending yet</span>
          <span>Click any box for what it is, should I care, what to do.</span>
        </div>

        <ReactFlowProvider>
        <MapFlow
          className="min-h-0 flex-1"
          graph={graph}
          routed={routed}
          colorMode={resolvedTheme === 'dark' ? 'dark' : 'light'}
          fitView
          fitViewOptions={{ padding: 0.05 }}
          minZoom={0.05}
          proOptions={{ hideAttribution: true }}
          onReady={(i) => { flow.current = i; }}
          onNodeClick={(_, n) => {
            if (n.id.startsWith('project:')) {
              const name = n.id.slice(8);
              setOpen((o) => { const x = new Set(o); if (x.has(name)) x.delete(name); else x.add(name); return x; });
              return;
            }
            focusOn(n.id);
          }}
          onPaneClick={() => { setFocus(new Set()); setSelectedId(null); }}
        >
          <Background />
          <Controls />
          <MiniMap pannable zoomable style={{ width: 150, height: 100 }} bgColor={resolvedTheme === 'dark' ? '#111113' : '#ffffff'} />
          {selected && (
            <Panel position="top-right">
              <div className="bg-background/95 max-h-[70vh] w-[320px] overflow-auto rounded-lg border p-3 text-sm shadow-lg backdrop-blur">
                <div className="flex items-center justify-between">
                  <div className="text-muted-foreground text-xs capitalize">{selected.kind} · {STATUS_WORD[selected.status]}</div>
                  <button type="button" aria-label="Close details" className="text-muted-foreground hover:text-foreground px-1" onClick={() => setSelectedId(null)}>×</button>
                </div>
                <div className="text-base font-semibold">{selected.label}</div>
                <Meaning e={selected.explain} />
                {conflicts.map((e) => (
                  <div key={e.id} className="mt-2 rounded-md border border-[#ff0071] p-2 text-xs">
                    <div className="font-semibold text-[#ff4d9a]">Rule conflict: {e.label}</div>
                    <div className="text-muted-foreground mt-1 break-all">{e.evidence}</div>
                  </div>
                ))}
                {selected.kind === 'card' && Array.isArray(selected.meta.rule_lines) && (
                  <div className="mt-2 text-xs">
                    <div className="text-muted-foreground text-[10px] uppercase">Which job goes where</div>
                    <ul className="mt-1 list-disc space-y-0.5 pl-4">
                      {(selected.meta.rule_lines as string[]).map((l, i) => <li key={i}>{l}</li>)}
                    </ul>
                  </div>
                )}
                {typeof selected.meta.url === 'string' && (
                  <a className="mt-2 inline-block text-xs text-[#ff4d9a] underline underline-offset-2" href={selected.meta.url} target="_blank" rel="noreferrer">
                    Open the Langfuse project ↗
                  </a>
                )}
                {typeof selected.meta.dashboard === 'string' && (
                  <a className="mt-1 ml-3 inline-block text-xs text-[#ff4d9a] underline underline-offset-2" href={selected.meta.dashboard} target="_blank" rel="noreferrer">
                    Agent fleet stats ↗
                  </a>
                )}
                {Array.isArray(selected.meta.senders) && (
                  <div className="mt-2 text-xs">
                    <div className="text-muted-foreground text-[10px] uppercase">Who sends traces</div>
                    <ul className="mt-1 space-y-1">
                      {(selected.meta.senders as Sender[]).map((x) => (
                        <li key={x.name} className="flex items-start gap-1.5">
                          <SenderBadge state={x.state} />
                          <span><span className="font-medium">{x.name}</span>{x.env ? <span className="text-muted-foreground"> · env {x.env}</span> : null}<br />
                            <span className="text-muted-foreground">{x.how}; {x.proof}</span></span>
                        </li>
                      ))}
                    </ul>
                    {typeof selected.meta.plan === 'string' && <div className="text-muted-foreground mt-1 text-[10px]">Plan: {selected.meta.plan}</div>}
                  </div>
                )}
                {Array.isArray(selected.meta.loaded_by) && (
                  <div className="mt-2 text-xs">Loaded by: {(selected.meta.loaded_by as string[]).join(', ') || 'no app'}</div>
                )}
                {Array.isArray(selected.meta.followed_by) && (
                  <div className="mt-2 text-xs">Followed by: {(selected.meta.followed_by as string[]).map((x) => x[0].toUpperCase() + x.slice(1)).join(', ')}</div>
                )}
                {Array.isArray(selected.meta.catalog) && (
                  <div className="mt-2 text-xs">
                    <div className="text-muted-foreground text-[10px] uppercase">Also in your workbook</div>
                    {(selected.meta.catalog as { name: string; kind: string }[]).slice(0, 4).map((x, i) => <div key={`${i}-${x.name}`}>{x.name} <span className="text-muted-foreground">({x.kind})</span></div>)}
                  </div>
                )}
                {links.length > 0 && (
                  <div className="mt-2 text-xs">
                    <div className="text-muted-foreground text-[10px] uppercase">Connected to ({links.length})</div>
                    <ul className="mt-1 space-y-0.5">
                      {links.slice(0, 14).map((e) => {
                        const other = byId.get(e.source === selected.id ? e.target : e.source);
                        return other ? (
                          <li key={e.id}>
                            <button type="button" className="hover:text-foreground text-left underline-offset-2 hover:underline" onClick={() => focusOn(other.id)}>
                              {e.label} → {other.label}
                            </button>
                          </li>
                        ) : null;
                      })}
                    </ul>
                  </div>
                )}
                {selected.sources.length > 0 && (
                  <div className="text-muted-foreground mt-2 break-all text-[10px]">Source: {selected.sources.join(' · ')}</div>
                )}
              </div>
            </Panel>
          )}
        </MapFlow>
        </ReactFlowProvider>
      </div>

      <aside className="min-h-0 space-y-4 overflow-auto border-t p-4 text-sm 2xl:border-t-0 2xl:border-l">
        <section>
          <h2 className="font-medium">Workbook merged into the live map</h2>
          <table className="mt-2 w-full text-xs tabular-nums">
            <thead className="text-muted-foreground"><tr><th className="text-left font-normal">of {c.before.total} workbook items</th><th className="text-right font-normal">before</th><th className="text-right font-normal">after</th></tr></thead>
            <tbody>
              <tr><td>matched to something live</td><td className="text-right">{c.before.matched}</td><td className="text-right">{c.after.matched}</td></tr>
              <tr><td>connected by evidence</td><td className="text-right">{c.before.connected}</td><td className="text-right">{c.after.connected}</td></tr>
              <tr><td>with a real purpose line</td><td className="text-right">{c.before.purposed}</td><td className="text-right">{c.after.purposed}</td></tr>
            </tbody>
          </table>
          <p className="text-muted-foreground mt-1 text-[11px]">Boxes on this map: {c.map_nodes}, all {c.map_nodes_purposed} with a purpose. Mission → skill links from Director’s files: {c.mission_skill_links}. Historical items hidden: {c.hidden_historical}.</p>
        </section>
        <section>
          <h2 className="font-medium">Rule check</h2>
          <p className="text-muted-foreground mt-1 text-xs">
            The rule checker flagged {map.rule_audit.tool_pairs} pairs; all were read by hand and are word matches, not real clashes
            {map.rule_audit.unreviewed.length ? `, except ${map.rule_audit.unreviewed.map((u) => `${u.new_pairs} new in ${u.file}`).join(', ')} (not reviewed yet)` : ''}.
            Real clashes between files: {map.rule_audit.conflicts.length} (red lines). Rules only one app sees: {map.rule_audit.one_agent.length}.
          </p>
          <ul className="mt-2 space-y-1 text-xs">
            {map.rule_audit.one_agent.map((r, i) => (
              <li key={`${i}-${r.agent}`} className="rounded border px-2 py-1"><span className="font-semibold">{r.agent} only:</span> {r.rule}</li>
            ))}
          </ul>
        </section>
        <details className="rounded-md border p-2">
          <summary className="cursor-pointer text-xs font-semibold">Not seen on my Mac anymore ({gone.length})</summary>
          <ul className="mt-2 max-h-72 space-y-0.5 overflow-auto text-[11px]">
            {gone.slice(0, 400).map((u, i) => <li key={`${i}-${u.name}`}>{u.name} <span className="text-muted-foreground">({u.kind})</span></li>)}
          </ul>
        </details>
        <details className="rounded-md border p-2">
          <summary className="cursor-pointer text-xs font-semibold">Cloud records the Mac scan can’t check ({cloud.length})</summary>
          <p className="text-muted-foreground mt-1 text-[11px]">GHL sub-accounts, ad accounts, 1Password items and similar. They live in online accounts, so a Mac scan can’t confirm them.</p>
          <ul className="mt-2 max-h-72 space-y-0.5 overflow-auto text-[11px]">
            {cloud.slice(0, 400).map((u, i) => <li key={`${i}-${u.name}`}>{u.name} <span className="text-muted-foreground">({u.kind})</span></li>)}
          </ul>
        </details>
      </aside>
    </div>
  );
}
