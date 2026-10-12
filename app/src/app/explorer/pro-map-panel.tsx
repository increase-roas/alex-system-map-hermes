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
      <span className="text-muted-foreground">Top to bottom = the order it happens. Left: Anthropic's way (Anthropic sources only). Right: yours, same 13 steps. Click a box, then a tile to open it. Anthropic side re-checked live 2026-10-12.</span>
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

type TileKey = 'limits' | 'build' | 'pros' | 'noobs' | 'extra' | 'trace' | 'sources';
const TILES: { key: TileKey; title: string; tone: string }[] = [
  { key: 'limits', title: 'Size limits', tone: '#0ea5e9' },
  { key: 'build', title: 'How to build it', tone: '#7f77dd' },
  { key: 'pros', title: 'Pros always do this', tone: '#17c964' },
  { key: 'noobs', title: 'Beginner mistakes', tone: '#ff0071' },
  { key: 'extra', title: 'They also do this (not on your map yet)', tone: '#f5a524' },
  { key: 'trace', title: 'What the trace records here', tone: '#8a8a8a' },
  { key: 'sources', title: 'Sources', tone: '#8a8a8a' },
];

function itemsFor(n: ProNode, k: TileKey): string[] {
  if (k === 'trace') return n.trace ? [n.trace] : [];
  if (k === 'sources') return n.sources;
  return n.detail?.[k] ?? [];
}

function Item({ text }: { text: string }) {
  return text.startsWith('http')
    ? <a className="break-all underline" href={text} target="_blank" rel="noreferrer">{text}</a>
    : <span>{text}</span>;
}

function DetailCard({ node, onClose }: { node: ProNode; onClose: () => void }) {
  const [open, setOpen] = useState<TileKey | null>(null);
  const tile = TILES.find((t) => t.key === open);
  const shell = 'max-h-[78vh] w-[440px] overflow-auto rounded-xl border bg-card/95 p-4 text-card-foreground shadow-lg backdrop-blur';
  const head = (
    <div className="flex items-start gap-2">
      <span className="mt-1.5 inline-block size-2.5 shrink-0 rounded-full" style={{ background: COLOR[node.status] }} />
      <div className="min-w-0 flex-1">
        <div className="text-base font-semibold leading-tight">{node.label}</div>
        <div className="text-xs text-muted-foreground">{WORD[node.status]}{node.sub ? ` · ${node.sub}` : ''}</div>
      </div>
      <button type="button" className="rounded px-1.5 text-muted-foreground hover:bg-muted" onClick={onClose} aria-label="Close">x</button>
    </div>
  );
  if (tile) {
    const items = itemsFor(node, tile.key);
    return (
      <div className={shell} data-testid="pro-map-detail">
        <button type="button" className="mb-2 text-xs text-muted-foreground hover:underline" onClick={() => setOpen(null)}>{'<'} Back to {node.label}</button>
        {head}
        <div className="mt-3 text-sm font-semibold" style={{ color: tile.tone }}>{tile.title}</div>
        <ul className="mt-2 space-y-2 text-sm leading-snug">
          {items.map((t) => (
            <li key={t} className="rounded-md border-l-4 bg-muted/40 px-3 py-2" style={{ borderLeftColor: tile.tone }}><Item text={t} /></li>
          ))}
        </ul>
      </div>
    );
  }
  const tiles = TILES.filter((t) => itemsFor(node, t.key).length > 0);
  return (
    <div className={shell} data-testid="pro-map-detail">
      {head}
      <p className="mt-3 text-sm leading-snug">{node.why}</p>
      <div className="mt-3 space-y-2">
        {tiles.map((t) => {
          const items = itemsFor(node, t.key);
          return (
            <button
              key={t.key}
              type="button"
              data-testid={`tile-${t.key}`}
              className="block w-full rounded-lg border bg-background/60 px-3 py-2 text-left transition hover:bg-muted"
              style={{ borderLeftColor: t.tone, borderLeftWidth: 4 }}
              onClick={() => setOpen(t.key)}
            >
              <div className="flex items-center justify-between text-sm font-medium">
                <span>{t.title}</span>
                <span className="text-xs text-muted-foreground">{items.length} {'>'}</span>
              </div>
              <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{items[0]}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
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
        <Panel position="top-right" className="m-0">
          <DetailCard key={picked.id} node={picked} onClose={() => setPicked(null)} />
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
