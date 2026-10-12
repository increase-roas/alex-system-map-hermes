'use client';

import {
  Background, Controls, Handle, MarkerType, Panel, Position, ReactFlow, ReactFlowProvider, useReactFlow,
  type Edge, type Node, type NodeProps,
} from '@xyflow/react';
import { useEffect, useMemo, useState } from 'react';

import { PRO_EDGES, PRO_NODES } from './pro-map-all';
import { type ProNode, type ProStatus } from './pro-map-data';
import type { Example, FlowStep, Picture, Rule, TreeNode } from './pro-map-examples';
import { JOBS, type CallStatus } from './pro-map-jobs';

const COLOR: Record<ProStatus, string> = { ok: '#17c964', partial: '#f5a524', gap: '#ff0071', reference: '#7f77dd', hermes: '#0d9488' };
const WORD: Record<ProStatus, string> = { ok: 'have it', partial: 'partly', gap: 'missing', reference: 'Anthropic way', hermes: 'Hermes way' };
const CARD_W = 130;
const hidden = { opacity: 0, width: 6, height: 6 };

type CardData = ProNode & { selected?: boolean; hl?: string; dim?: boolean };
const HL: Record<string, string> = { on: '#f59e0b', problem: '#ef4444', fix: '#3b82f6', done: '#22c55e' };

function Card({ data }: NodeProps<Node<CardData>>) {
  const c = COLOR[data.status];
  return (
    <div
      className="rounded-md border bg-card px-2.5 py-2 text-card-foreground shadow-sm transition-all duration-300"
      style={{ width: data.w ?? CARD_W, borderColor: c, borderLeftWidth: 4, opacity: data.dim ? 0.25 : 1,
        boxShadow: data.hl ? `0 0 0 3px ${HL[data.hl]}, 0 0 18px ${HL[data.hl]}` : undefined }}
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
        {data.badge ? <span className="ml-auto rounded bg-amber-500/15 px-1 text-[9px] font-medium text-amber-600">{data.badge}</span> : null}
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
      <span className="text-muted-foreground">Top to bottom = the order it happens. Left: version 1 (original 13 steps). Middle: version 2 (Codex review, 12 steps). Right: yours, 12 steps. Far right: version 4, Hermes Agent (Nous Research). Click a box, then a tile to open it. Anthropic side re-checked live 2026-10-12.</span>
      {(['ok', 'partial', 'gap', 'reference', 'hermes'] as ProStatus[]).map((s) => (
        <span key={s} className="flex items-center gap-1"><span className="inline-block size-2 rounded-full" style={{ background: COLOR[s] }} />{WORD[s]}</span>
      ))}
      <span className="text-muted-foreground">moving gray line = work flows</span>
      <span style={{ color: '#7f77dd' }}>dashed purple = reads from the library</span>
      <span style={{ color: '#ff0071' }}>dashed red = goes around the SDK</span>
      <span style={{ color: '#f5a524' }}>dotted orange = loops back</span>
      <span className="font-medium">Yours: {counts.ok} have it, {counts.partial} partly, {counts.gap} missing</span>
    </div>
  );
}

const ROW_Y = new Map(PRO_NODES.map((n) => [n.id, n.y]));

function edgeFor(e: (typeof PRO_EDGES)[number]): Edge {
  const sameRow = e.kind === 'flow' && !e.source.includes('_band_') && !e.target.includes('_band_') && ROW_Y.get(e.source) === ROW_Y.get(e.target);
  const color = e.kind === 'bypass' ? '#ff0071' : e.kind === 'link' ? '#7f77dd' : e.kind === 'loop' ? '#f5a524' : '#8a8a8a';
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    type: 'smoothstep',
    animated: e.kind === 'flow' || e.kind === 'loop',
    sourceHandle: e.sh ?? (sameRow ? 'rs' : undefined),
    targetHandle: e.th ?? (sameRow ? 'l' : undefined),
    style: { stroke: color, strokeWidth: e.kind === 'flow' ? 1.4 : e.kind === 'loop' ? 2 : 1.3, strokeDasharray: e.kind === 'flow' ? undefined : e.kind === 'loop' ? '3 3' : '6 4' },
    ...(e.offset ? { pathOptions: { offset: e.offset } } : {}),
    markerEnd: { type: MarkerType.ArrowClosed, color, width: e.kind === 'loop' ? 18 : 14, height: e.kind === 'loop' ? 18 : 14 },
    labelStyle: { fontSize: 11, fill: color },
    labelBgStyle: e.kind === 'flow' || e.kind === 'loop' ? { fill: 'hsl(var(--background))', fillOpacity: 0.92 } : { fillOpacity: 0 },
    labelBgPadding: [4, 2] as [number, number],
    zIndex: 1,
  };
}

type TileKey = 'myths' | 'plain' | 'pictures' | 'examples' | 'decide' | 'limits' | 'build' | 'pros' | 'noobs' | 'extra' | 'trace' | 'sources';
const TILES: { key: TileKey; title: string; tone: string }[] = [
  { key: 'plain', title: 'In plain steps', tone: '#22d3ee' },
  { key: 'myths', title: 'Myth vs reality', tone: '#fb7185' },
  { key: 'pictures', title: 'Pictures', tone: '#a78bfa' },
  { key: 'examples', title: 'Examples', tone: '#38bdf8' },
  { key: 'decide', title: 'If this, then that', tone: '#facc15' },
  { key: 'limits', title: 'Size limits', tone: '#0ea5e9' },
  { key: 'build', title: 'How to build it', tone: '#7f77dd' },
  { key: 'pros', title: 'Pros always do this', tone: '#17c964' },
  { key: 'noobs', title: 'Beginner mistakes', tone: '#ff0071' },
  { key: 'extra', title: 'They also do this (not on your map yet)', tone: '#f5a524' },
  { key: 'trace', title: 'What the trace records here', tone: '#8a8a8a' },
  { key: 'sources', title: 'Sources', tone: '#8a8a8a' },
];

function countFor(n: ProNode, k: TileKey): number {
  const d = n.detail;
  if (k === 'pictures') return d?.pictures?.length ?? 0;
  if (k === 'examples') return d?.examples?.length ?? 0;
  if (k === 'decide') return d?.decide?.length ?? 0;
  if (k === 'myths') return d?.myths?.length ?? 0;
  return itemsFor(n, k).length;
}
function previewFor(n: ProNode, k: TileKey): string {
  const d = n.detail;
  if (k === 'pictures') return (d?.pictures ?? []).map((p) => p.title).join(' · ');
  if (k === 'examples') return (d?.examples ?? []).map((e) => e.title).join(' · ');
  if (k === 'decide') return d?.decide?.[0] ? `If ${d.decide[0].if}: ${d.decide[0].then}` : '';
  if (k === 'myths') return d?.myths?.[0] ? `Myth: ${d.myths[0].myth}` : '';
  return itemsFor(n, k)[0] ?? '';
}
function itemsFor(n: ProNode, k: TileKey): string[] {
  if (k === 'trace') return n.trace ? [n.trace] : [];
  if (k === 'sources') return n.sources;
  if (k === 'pictures' || k === 'examples' || k === 'decide' || k === 'myths') return [];
  return n.detail?.[k] ?? [];
}

function Item({ text }: { text: string }) {
  return text.startsWith('http')
    ? <a className="break-all underline" href={text} target="_blank" rel="noreferrer">{text}</a>
    : <span>{text}</span>;
}

const TONE: Record<string, string> = { good: '#17c964', bad: '#ff0071', neutral: '#8a8a8a' };

function Box({ label, note, tone }: { label: string; note?: string; tone?: string }) {
  const c = tone ? TONE[tone] : '#7f77dd';
  return (
    <div className="rounded-md border bg-background/70 px-2.5 py-1.5 text-center" style={{ borderColor: c, borderLeftWidth: 3 }}>
      <div className="whitespace-nowrap font-mono text-[12px] leading-tight">{label}</div>
      {note ? <div className="text-[11px] leading-tight text-muted-foreground">{note}</div> : null}
    </div>
  );
}

function TreeView({ node }: { node: TreeNode }) {
  return (
    <div className="flex flex-col items-center">
      <Box label={node.label} note={node.note} tone={node.tone} />
      {node.children?.length ? (
        <>
          <div className="h-3 w-px bg-muted-foreground/50" />
          <div className="flex justify-center gap-2 border-t border-muted-foreground/50">
            {node.children.map((c) => (
              <div key={c.label} className="flex flex-col items-center">
                <div className="h-3 w-px bg-muted-foreground/50" />
                <TreeView node={c} />
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

function fileRows(node: TreeNode, prefix = '', last = true, root = true): { line: string; note?: string; tone?: string }[] {
  const me = { line: root ? node.label : `${prefix}${last ? '└─ ' : '├─ '}${node.label}`, note: node.note, tone: node.tone };
  const kids = node.children ?? [];
  const next = root ? '' : `${prefix}${last ? '   ' : '│  '}`;
  return [me, ...kids.flatMap((c, i) => fileRows(c, next, i === kids.length - 1, false))];
}

function FilesView({ node }: { node: TreeNode }) {
  return (
    <div className="overflow-x-auto rounded-md bg-black/30 p-3">
      {fileRows(node).map((r, i) => (
        <div key={i} className="flex items-baseline gap-3 whitespace-pre">
          <span className="font-mono text-[12px]" style={{ color: r.tone ? TONE[r.tone] : undefined }}>{r.line}</span>
          {r.note ? <span className="text-[11px] text-muted-foreground">{r.note}</span> : null}
        </div>
      ))}
    </div>
  );
}

function FlowView({ steps }: { steps: FlowStep[] }) {
  return (
    <div className="flex flex-col items-center">
      {steps.map((st, i) => (
        <div key={st.label} className="flex w-full flex-col items-center">
          {i > 0 ? <div className="text-muted-foreground">↓</div> : null}
          <div className="w-full max-w-[460px]"><Box label={st.label} note={st.note} tone={st.tone} /></div>
          {st.many?.length ? (
            <div className="mt-1 flex flex-wrap justify-center gap-1.5">
              {st.many.map((m) => <span key={m} className="rounded border border-dashed px-2 py-0.5 font-mono text-[11px] text-muted-foreground">{m}</span>)}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function PictureView({ p }: { p: Picture }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="mb-2 text-sm font-semibold">{p.title}</div>
      <div className="overflow-x-auto">
        {p.kind === 'tree' ? <div className="mx-auto w-max"><TreeView node={p.root} /></div> : p.kind === 'files' ? <FilesView node={p.root} /> : <FlowView steps={p.steps} />}
      </div>
      {p.caption ? <div className="mt-2 text-xs text-muted-foreground">{p.caption}</div> : null}
    </div>
  );
}

function ExampleView({ e }: { e: Example }) {
  const c = e.tone ? TONE[e.tone] : '#38bdf8';
  return (
    <div className="rounded-lg border p-3" style={{ borderLeftColor: c, borderLeftWidth: 4 }}>
      <div className="text-sm font-semibold">{e.title}</div>
      <div className="mt-0.5 text-xs leading-snug text-muted-foreground">{e.why}</div>
      {e.file ? <div className="mt-2 font-mono text-[11px]" style={{ color: c }}>{e.file}</div> : null}
      <pre className="mt-1 overflow-x-auto rounded-md bg-black/40 p-3 font-mono text-[12px] leading-snug">{e.code}</pre>
      {e.sticky?.length ? <StickyNote notes={e.sticky} /> : null}
    </div>
  );
}

function StickyNote({ notes }: { notes: { text: string; src: string }[] }) {
  return (
    <div data-testid="sticky-note" className="mt-2 rounded-md border border-yellow-400/60 bg-yellow-200/90 p-2.5 text-[12px] leading-snug text-yellow-950 shadow-sm" style={{ transform: 'rotate(-0.4deg)' }}>
      <div className="mb-1 text-[10px] font-bold uppercase tracking-wide">Sticky note: don't forget</div>
      {notes.map((s) => (
        <div key={s.text} className="mt-1">
          {s.text} <a href={s.src} target="_blank" rel="noreferrer" className="underline opacity-70">source</a>
        </div>
      ))}
    </div>
  );
}

function RuleView({ r }: { r: Rule }) {
  return (
    <div className="rounded-lg border px-3 py-2 text-sm leading-snug">
      <div><span className="mr-1.5 font-semibold text-yellow-500">IF</span>{r.if}</div>
      <div className="mt-0.5"><span className="mr-1.5 font-semibold text-emerald-500">THEN</span>{r.then}</div>
    </div>
  );
}

function DetailCard({ node, onClose }: { node: ProNode; onClose: () => void }) {
  const [open, setOpen] = useState<TileKey | null>(null);
  const tile = TILES.find((t) => t.key === open);
  const shell = `max-h-[80vh] ${open ? 'w-[640px]' : 'w-[440px]'} overflow-auto rounded-xl border bg-card/95 p-4 text-card-foreground shadow-lg backdrop-blur`;
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
        {tile.key === 'pictures' ? (
          <div className="mt-2 space-y-3">{(node.detail?.pictures ?? []).map((p) => <PictureView key={p.title} p={p} />)}</div>
        ) : tile.key === 'examples' ? (
          <div className="mt-2 space-y-3">{(node.detail?.examples ?? []).map((e) => <ExampleView key={e.title} e={e} />)}</div>
        ) : tile.key === 'myths' ? (
          <div className="mt-2 space-y-2">
            {(node.detail?.myths ?? []).map((m) => (
              <div key={m.myth} className="rounded-lg border px-3 py-2 text-sm leading-snug">
                <div><span className="mr-1.5 font-semibold text-rose-500">MYTH</span>{m.myth}</div>
                <div className="mt-1"><span className="mr-1.5 font-semibold text-emerald-500">REALITY</span>{m.truth}</div>
                {m.fix ? <div className="mt-1.5 rounded-md bg-sky-500/10 px-2 py-1.5"><span className="mr-1.5 font-semibold text-sky-500">FIX</span>{m.fix}</div> : null}
              </div>
            ))}
          </div>
        ) : tile.key === 'decide' ? (
          <div className="mt-2 space-y-2">{(node.detail?.decide ?? []).map((r) => <RuleView key={r.if} r={r} />)}</div>
        ) : (
          <ul className="mt-2 space-y-2 text-sm leading-snug">
            {items.map((t, i) => (
              <li key={t} className="flex gap-2 rounded-md border-l-4 bg-muted/40 px-3 py-2" style={{ borderLeftColor: tile.tone }}>
                {tile.key === 'plain' ? <span className="font-semibold" style={{ color: tile.tone }}>{i + 1}.</span> : null}
                <Item text={t} />
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  const tiles = TILES.filter((t) => countFor(node, t.key) > 0);
  return (
    <div className={shell} data-testid="pro-map-detail">
      {head}
      <p className="mt-3 text-sm leading-snug">{node.why}</p>
      {node.detail?.sticky?.length ? <StickyNote notes={node.detail.sticky} /> : null}
      {(() => {
        const n = (node.detail?.examples ?? []).reduce((a, e) => a + (e.sticky?.length ?? 0), 0);
        return n ? <div className="mt-2 text-xs font-medium text-yellow-600">{n} sticky {n === 1 ? 'note' : 'notes'} inside Examples</div> : null;
      })()}
      <div className="mt-3 space-y-2">
        {tiles.map((t) => {
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
                <span className="text-xs text-muted-foreground">{countFor(node, t.key)} {'>'}</span>
              </div>
              <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{previewFor(node, t.key)}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

const CALL_COLOR: Record<CallStatus, string> = { ok: '#22c55e', fail: '#ef4444', ask: '#f59e0b', fixed: '#3b82f6', info: '#8a8a8a' };

function Walkthrough({ on, setOn, jobId, setJobId, beat, setBeat, playing, setPlaying }: {
  on: boolean; setOn: (v: boolean) => void; jobId: string; setJobId: (v: string) => void;
  beat: number; setBeat: (f: (b: number) => number) => void; playing: boolean; setPlaying: (v: boolean) => void;
}) {
  const job = JOBS.find((j) => j.id === jobId) ?? JOBS[0];
  const b = job.beats[beat];
  const calls = job.beats.slice(0, beat + 1).flatMap((x, i) => (x.calls ?? []).map((c) => ({ ...c, step: i + 1 })));
  return (
    <div className="w-[400px] rounded-xl border bg-card/95 p-3 text-xs shadow-lg backdrop-blur" data-testid="walkthrough">
      <div className="flex items-center gap-2">
        <button type="button" data-testid="wt-toggle" onClick={() => { setOn(!on); setPlaying(false); setBeat(() => 0); }}
          className={`rounded-full px-3 py-1 text-xs font-semibold ${on ? 'bg-emerald-500 text-white' : 'bg-muted text-foreground'}`}>
          Walkthrough: {on ? 'ON' : 'OFF'}
        </button>
        <select className="min-w-0 flex-1 rounded border bg-background px-1 py-1" value={job.id} onChange={(e) => { setJobId(e.target.value); setBeat(() => 0); setPlaying(false); }}>
          {JOBS.map((j) => <option key={j.id} value={j.id}>{j.name}</option>)}
        </select>
      </div>
      {on && b ? (
        <>
          <div className="mt-2 rounded-md bg-muted/50 px-2 py-1.5 text-[11px] leading-snug"><span className="font-semibold">Job:</span> {job.ask}</div>
          <div className="mt-2 flex items-center gap-1.5">
            <button type="button" className="rounded border px-2 py-0.5" onClick={() => { setBeat(() => 0); setPlaying(false); }}>Restart</button>
            <button type="button" className="rounded border px-2 py-0.5" onClick={() => setBeat((x) => Math.max(0, x - 1))}>Back</button>
            <button type="button" data-testid="wt-play" className="rounded border bg-foreground px-2 py-0.5 text-background" onClick={() => setPlaying(!playing)}>{playing ? 'Pause' : 'Play'}</button>
            <button type="button" data-testid="wt-next" className="rounded border px-2 py-0.5" onClick={() => setBeat((x) => Math.min(job.beats.length - 1, x + 1))}>Next</button>
            <span className="ml-auto text-muted-foreground">Step {beat + 1} of {job.beats.length}</span>
          </div>
          <div className="mt-2 rounded-md border-l-4 px-2 py-1.5" style={{ borderLeftColor: HL[b.tone ?? 'on'] }}>
            <div className="text-sm font-semibold" style={{ color: HL[b.tone ?? 'on'] }}>{b.title}</div>
            <div className="mt-0.5 text-[12px] leading-snug">{b.say}</div>
          </div>
          <div className="mt-2 font-semibold">Call list (trace), newest first</div>
          <div className="mt-1 max-h-[180px] overflow-auto rounded-md border">
            {calls.length ? [...calls].reverse().map((c, i) => (
              <div key={i} className="flex items-baseline gap-1.5 border-b px-2 py-1 font-mono text-[10.5px] last:border-b-0">
                <span className="text-muted-foreground">{c.step}</span>
                <span className="inline-block size-2 shrink-0 rounded-full" style={{ background: CALL_COLOR[c.status] }} />
                <span className="text-muted-foreground">{c.agent}</span>
                <span className="font-semibold">{c.action}</span>
                <span className="ml-auto text-right" style={{ color: CALL_COLOR[c.status] }}>{c.result}{c.ms ? ` ${c.ms}ms` : ''}{c.cost ? ` ${c.cost}` : ''}</span>
              </div>
            )) : <div className="px-2 py-1 text-muted-foreground">No calls yet.</div>}
          </div>
          <div className="mt-1.5 text-[10px] text-muted-foreground">DEMO: scripted walkthrough. Nothing is called or changed.</div>
        </>
      ) : <div className="mt-1.5 text-[11px] text-muted-foreground">Turn it on to watch one job move through the middle map, break, and fix itself.</div>}
    </div>
  );
}

function ProMap() {
  const rf = useReactFlow();
  const [wtOn, setWtOn] = useState(false);
  const [jobId, setJobId] = useState(JOBS[0].id);
  const [beat, setBeat] = useState(0);
  const [playing, setPlaying] = useState(false);
  const job = JOBS.find((j) => j.id === jobId) ?? JOBS[0];
  const active = wtOn ? job.beats[beat] : undefined;
  useEffect(() => {
    if (!playing || !wtOn) return;
    const t = setTimeout(() => {
      if (beat >= job.beats.length - 1) setPlaying(false); else setBeat((x) => x + 1);
    }, 4200);
    return () => clearTimeout(t);
  }, [playing, wtOn, beat, job]);
  useEffect(() => {
    if (active) rf.fitView({ nodes: active.ids.map((id) => ({ id })), duration: 700, padding: 0.6, maxZoom: 1.1 });
    else rf.fitView({ duration: 500, padding: 0.04 });
  }, [active, rf]);
  const [picked, setPicked] = useState<ProNode | null>(null);
  const nodes = useMemo<Node<CardData>[]>(
    () =>
      PRO_NODES.map((n) => ({
        id: n.id,
        type: n.band ? 'band' : 'card',
        position: { x: n.x, y: n.y },
        data: active && !n.band
          ? { ...n, hl: active.ids.includes(n.id) ? (active.tone ?? 'on') : undefined, dim: n.id.startsWith('p_') && !active.ids.includes(n.id) }
          : n,
        draggable: !n.band,
        selectable: !n.band,
        zIndex: n.band ? -1 : 2,
      })),
    [active],
  );
  const baseEdges = useMemo(() => PRO_EDGES.map(edgeFor), []);
  const edges = useMemo<Edge[]>(() => {
    if (!wtOn) return baseEdges;
    const faded = baseEdges.map((e) => ({ ...e, style: { ...e.style, opacity: 0.18 }, labelStyle: { ...e.labelStyle, opacity: 0.25 } }));
    const green: Edge[] = [];
    let prevLast: string | undefined;
    job.beats.slice(0, beat + 1).forEach((b, bi) => {
      let pairs: [string, string][] = b.path ?? b.ids.slice(1).map((id, i) => [b.ids[i], id] as [string, string]);
      if (!b.path && prevLast && prevLast !== b.ids[0]) pairs = [[prevLast, b.ids[0]], ...pairs];
      prevLast = b.ids[b.ids.length - 1];
      const now = bi === beat;
      pairs.forEach(([a, c], k) => {
        const same = ROW_Y.get(a) === ROW_Y.get(c);
        green.push({
          id: `wt-${bi}-${k}-${a}-${c}`, source: a, target: c, type: 'smoothstep', animated: true,
          sourceHandle: same ? 'rs' : undefined, targetHandle: same ? 'l' : undefined,
          style: { stroke: '#22c55e', strokeWidth: now ? 5 : 3, opacity: now ? 1 : 0.75, filter: now ? 'drop-shadow(0 0 6px #22c55e)' : undefined },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#22c55e', width: 22, height: 22 },
          zIndex: 5,
        });
      });
    });
    return [...faded, ...green];
  }, [wtOn, job, beat, baseEdges]);
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
      <Panel position="top-left" className="m-2">
        <Walkthrough on={wtOn} setOn={setWtOn} jobId={jobId} setJobId={setJobId} beat={beat} setBeat={setBeat} playing={playing} setPlaying={setPlaying} />
      </Panel>
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
