'use client';

import {
  Background, Controls, Handle, MarkerType, Panel, Position, ReactFlow, ReactFlowProvider,
  type Edge, type Node, type NodeProps,
} from '@xyflow/react';
import { useMemo, useState } from 'react';

import { PRO_EDGES, PRO_NODES, type ProNode, type ProStatus } from './pro-map-data';

const COLOR: Record<ProStatus, string> = { ok: '#17c964', partial: '#f5a524', gap: '#ff0071', reference: '#7f77dd' };
const WORD: Record<ProStatus, string> = { ok: 'have it', partial: 'partly', gap: 'missing', reference: 'Anthropic way' };
const CARD_W = 130;
const hidden = { opacity: 0, width: 6, height: 6 };

type CardData = ProNode & { selected?: boolean };

function Card({ data }: NodeProps<Node<CardData>>) {
  const c = COLOR[data.status];
  return (
    <div
      className="rounded-md border bg-card px-2.5 py-2 text-card-foreground shadow-sm"
      style={{ width: data.w ?? CARD_W, borderColor: c, borderLeftWidth: 4 }}
    >
      <Handle type="target" position={Position.Top} style={hidden} />
      <Handle type="source" position={Position.Bottom} style={hidden} />
      <Handle id="l" type="target" position={Position.Left} style={hidden} />
      <Handle id="ls" type="source" position={Position.Left} style={hidden} />
      <Handle id="r" type="target" position={Position.Right} style={hidden} />
      <Handle id="rs" type="source" position={Position.Right} style={hidden} />
      <div className="flex items-center gap-1.5">
        <span className="inline-block size-2 shrink-0 rounded-full" style={{ background: c }} />
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{WORD[data.status]}</span>
      </div>
      <div className="mt-0.5 text-sm font-medium leading-tight">{data.label}</div>
      <div className="text-xs leading-tight text-muted-foreground">{data.sub}</div>
    </div>
  );
}

function Band({ data }: NodeProps<Node<CardData>>) {
  const c = COLOR[data.status];
  const title = data.id.endsWith('_title');
  return (
    <div
      className="rounded-xl border border-dashed"
      style={{ width: data.w ?? 740, height: data.h ?? 110, borderColor: c, background: `${c}10` }}
    >
      <Handle type="target" position={Position.Top} style={hidden} />
      <Handle type="source" position={Position.Bottom} style={hidden} />
      <Handle id="ls" type="source" position={Position.Left} style={hidden} />
      <Handle id="l" type="target" position={Position.Left} style={hidden} />
      <Handle id="r" type="target" position={Position.Right} style={hidden} />
      <Handle id="rs" type="source" position={Position.Right} style={hidden} />
      <div className={`flex items-baseline justify-between gap-2 px-3 pt-2 font-semibold ${title ? 'text-base' : 'text-xs'}`} style={{ color: c }}>
        <span>{data.label}</span>
        {data.tag ? <span className="text-[10px] font-normal text-muted-foreground">trace: {data.tag}</span> : null}
      </div>
      {title ? <div className="px-3 text-xs text-muted-foreground">{data.sub}</div> : null}
    </div>
  );
}

const nodeTypes = { card: Card, band: Band };

function Legend({ counts }: { counts: { ok: number; partial: number; gap: number } }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-3 py-2 text-xs">
      <span className="text-sm font-semibold">Pro Map</span>
      <span className="text-muted-foreground">Top to bottom = the order it happens. Left: Anthropic's way (Anthropic sources only). Right: yours, same 13 steps. Click a box for how to build it; click a band for what the trace records.</span>
      {(['ok', 'partial', 'gap', 'reference'] as ProStatus[]).map((s) => (
        <span key={s} className="flex items-center gap-1"><span className="inline-block size-2 rounded-full" style={{ background: COLOR[s] }} />{WORD[s]}</span>
      ))}
      <span className="text-muted-foreground">moving gray line = work flows</span>
      <span style={{ color: '#7f77dd' }}>dashed purple = reads from the library</span>
      <span style={{ color: '#ff0071' }}>dashed red = goes around the SDK</span>
      <span className="font-medium">Yours: {counts.ok} have it, {counts.partial} partly, {counts.gap} missing</span>
    </div>
  );
}

const ROW_Y = new Map(PRO_NODES.map((n) => [n.id, n.y]));

function edgeFor(e: (typeof PRO_EDGES)[number]): Edge {
  const sameRow = e.kind === 'flow' && !e.source.includes('_band_') && !e.target.includes('_band_') && ROW_Y.get(e.source) === ROW_Y.get(e.target);
  const color = e.kind === 'bypass' ? '#ff0071' : e.kind === 'link' ? '#7f77dd' : '#8a8a8a';
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    type: 'smoothstep',
    animated: e.kind === 'flow',
    sourceHandle: e.sh ?? (sameRow ? 'rs' : undefined),
    targetHandle: e.th ?? (sameRow ? 'l' : undefined),
    style: { stroke: color, strokeWidth: e.kind === 'flow' ? 1.4 : 1.3, strokeDasharray: e.kind === 'flow' ? undefined : '6 4' },
    markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
    labelStyle: { fontSize: 11, fill: color },
    labelBgStyle: { fillOpacity: 0 },
    zIndex: 1,
  };
}

function ProMap() {
  const [picked, setPicked] = useState<ProNode | null>(null);
  const nodes = useMemo<Node<CardData>[]>(
    () =>
      PRO_NODES.map((n) => ({
        id: n.id,
        type: n.band ? 'band' : 'card',
        position: { x: n.x, y: n.y },
        data: n,
        draggable: !n.band,
        selectable: !n.band,
        zIndex: n.band ? -1 : 2,
      })),
    [],
  );
  const edges = useMemo(() => PRO_EDGES.map(edgeFor), []);
  const counts = useMemo(() => {
    const mine = PRO_NODES.filter((n) => n.id.startsWith('y_') && !n.band);
    return { ok: mine.filter((n) => n.status === 'ok').length, partial: mine.filter((n) => n.status === 'partial').length, gap: mine.filter((n) => n.status === 'gap').length };
  }, []);

  return (
    <div className="flex h-full flex-col">
      <Legend counts={counts} />
      <div className="min-h-0 flex-1">
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.04 }}
      minZoom={0.2}
      onNodeClick={(_, n) => setPicked(n.data as CardData)}
      onPaneClick={() => setPicked(null)}
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={24} size={1} />
      <Controls showInteractive={false} />
      {picked ? (
        <Panel position="top-right" className="max-h-[70vh] w-[360px] overflow-auto rounded-md border bg-card/95 p-3 text-xs shadow-sm" data-testid="pro-map-detail">
          <div className="flex items-center gap-2">
            <span className="inline-block size-2.5 rounded-full" style={{ background: COLOR[picked.status] }} />
            <span className="text-sm font-semibold">{picked.label}</span>
            <span className="text-muted-foreground">{WORD[picked.status]}</span>
          </div>
          <div className="mt-1.5">{picked.why}</div>
          {picked.how?.length ? (
            <>
              <div className="mt-2 font-medium">How to build it</div>
              <ul className="mt-0.5 list-disc space-y-0.5 pl-4">{picked.how.map((h) => <li key={h}>{h}</li>)}</ul>
            </>
          ) : null}
          {picked.trace ? (
            <>
              <div className="mt-2 font-medium">What the trace records here</div>
              <div className="mt-0.5">{picked.trace}</div>
            </>
          ) : null}
          <div className="mt-2 font-medium">Source</div>
          <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-muted-foreground">
            {picked.sources.map((s) => (
              <li key={s} className="break-all">{s.startsWith('http') ? <a className="underline" href={s} target="_blank" rel="noreferrer">{s}</a> : s}</li>
            ))}
          </ul>
        </Panel>
      ) : null}
    </ReactFlow>
      </div>
    </div>
  );
}

export function ProMapPanel() {
  return (
    <div className="w-full" style={{ height: '82vh' }} data-testid="pro-map">
      <ReactFlowProvider>
        <ProMap />
      </ReactFlowProvider>
    </div>
  );
}
