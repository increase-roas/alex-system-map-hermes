'use client';

/**
 * Flow Builder tab: drag-and-connect editor for agent flows using the node kit in flow-node-kit.ts
 * (Agentflow's 15 node types + Judge, Compare, Promote, Route to customer). Draws and checks flows;
 * it does not run them. GEPA and routing run from agency-os-kit (gepa.py, route.py).
 */
import {
  addEdge, Background, Controls, Handle, MiniMap, Position, ReactFlow, ReactFlowProvider, useEdgesState, useNodesState, useReactFlow,
  type Connection, type Edge, type Node, type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Bot, Brain, Code, Database, Gavel, GitBranch, Globe, MessageSquare, Play, Repeat, Rocket, RotateCcw, Route, Scale, Split, StickyNote,
  UserCheck, Workflow, Wrench, type LucideIcon,
} from 'lucide-react';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { checkFlow, gepaPreset, GROUPS, KIT, KIT_BY_TYPE, routingPreset, type Flow, type FlowEdge, type FlowNode } from './flow-node-kit';

const ICONS: Record<string, LucideIcon> = {
  Play, Brain, Bot, Wrench, Database, Globe, GitBranch, Split, Repeat, RotateCcw, UserCheck, MessageSquare, Code, Workflow, StickyNote, Gavel, Scale, Rocket, Route,
};
type KitData = FlowNode['data'];
const STORE = 'flow-builder:v1';

const KitNode = memo(function KitNode({ data, selected }: NodeProps<Node<KitData>>) {
  const k = KIT_BY_TYPE[data.kind];
  if (!k) return <div className="rounded border p-2 text-xs">Unknown: {data.kind}</div>;
  const Icon = ICONS[k.icon] ?? Wrench;
  const sticky = k.type === 'stickyNote';
  const filled = k.fields.filter((f) => data.values[f.key]).slice(0, 2);
  return (
    <div
      data-testid={`kit-node-${k.type}`}
      className={`w-[230px] rounded-lg border bg-card text-card-foreground shadow-sm ${selected ? 'ring-2 ring-offset-1' : ''} ${sticky ? 'bg-yellow-50 dark:bg-yellow-950/40' : ''}`}
      style={{ borderColor: k.color }}
    >
      <div className="flex items-center gap-2 border-b px-3 py-2" style={{ borderColor: `${k.color}55` }}>
        <Icon className="size-4 shrink-0" style={{ color: k.color }} aria-hidden />
        <div className="min-w-0">
          <div className="truncate text-[13px] font-semibold">{data.label}</div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{k.label}{k.source === 'alex' ? ' · yours' : ''}</div>
        </div>
      </div>
      <div className="space-y-0.5 px-3 py-2 text-[11px] text-muted-foreground">
        {sticky ? <div className="whitespace-pre-wrap text-foreground">{data.values.text}</div>
          : filled.length ? filled.map((f) => <div key={f.key} className="truncate"><span className="font-medium text-foreground">{f.label}:</span> {data.values[f.key]}</div>)
          : <div className="line-clamp-2">{k.what}</div>}
      </div>
      {k.inputs.map((h, i) => (
        <Handle key={`in-${h}`} id={k.inputs.length > 1 ? h : undefined} type="target" position={Position.Top}
          style={{ left: `${((i + 1) / (k.inputs.length + 1)) * 100}%`, background: k.color }} />
      ))}
      {k.inputs.length > 1 && (
        <div className="pointer-events-none absolute -top-4 left-0 flex w-full justify-around text-[9px] text-muted-foreground">{k.inputs.map((h) => <span key={h}>{h}</span>)}</div>
      )}
      {k.outputs.map((h, i) => (
        <Handle key={`out-${h}`} id={k.outputs.length > 1 ? h : undefined} type="source" position={Position.Bottom}
          style={{ left: `${((i + 1) / (k.outputs.length + 1)) * 100}%`, background: k.color }} />
      ))}
      {k.outputs.length > 1 && (
        <div className="pointer-events-none absolute -bottom-4 left-0 flex w-full justify-around text-[9px] text-muted-foreground">{k.outputs.map((h) => <span key={h}>{h}</span>)}</div>
      )}
    </div>
  );
});

const nodeTypes = { kit: KitNode };

function toRf(flow: Flow): { nodes: Node<KitData>[]; edges: Edge[] } {
  return {
    nodes: flow.nodes.map((n) => ({ ...n })),
    edges: flow.edges.map((e) => ({ ...e, sourceHandle: e.sourceHandle ?? undefined, targetHandle: e.targetHandle ?? undefined, label: e.label ?? e.sourceHandle ?? undefined })),
  };
}
function fromRf(name: string, nodes: Node<KitData>[], edges: Edge[]): Flow {
  return {
    name,
    nodes: nodes.map((n) => ({ id: n.id, type: 'kit', position: n.position, data: n.data })),
    edges: edges.map((e): FlowEdge => ({ id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle ?? null, targetHandle: e.targetHandle ?? null, label: typeof e.label === 'string' ? e.label : undefined })),
  };
}
function load(): Flow {
  try {
    const raw = localStorage.getItem(STORE);
    const saved = raw ? (JSON.parse(raw) as Flow) : null;
    if (saved?.nodes?.length) return saved;
  } catch { /* storage unavailable: start from the preset */ }
  return gepaPreset();
}

function Builder() {
  const [name, setName] = useState('GEPA feedback loop');
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<KitData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const rf = useReactFlow();
  const loaded = useRef(false);

  const show = useCallback((flow: Flow) => {
    const { nodes: n, edges: e } = toRf(flow);
    setName(flow.name); setNodes(n); setEdges(e); setSelected(null);
    loaded.current = true;
    setTimeout(() => rf.fitView({ padding: 0.15, duration: 300 }), 50);
  }, [rf, setEdges, setNodes]);

  useEffect(() => { show(load()); }, [show]);
  useEffect(() => {
    if (!loaded.current) return;
    try { localStorage.setItem(STORE, JSON.stringify(fromRf(name, nodes, edges))); } catch { /* ignore */ }
  }, [name, nodes, edges]);

  const issues = useMemo(() => checkFlow(fromRf(name, nodes, edges)), [name, nodes, edges]);
  const onConnect = useCallback((c: Connection) => setEdges((es) => addEdge({ ...c, label: c.sourceHandle ?? undefined }, es)), [setEdges]);

  const add = (kind: string) => {
    const k = KIT_BY_TYPE[kind];
    const center = rf.screenToFlowPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
    const id = `${kind}-${Date.now().toString(36)}`;
    setNodes((ns) => [...ns, { id, type: 'kit', position: { x: center.x - 115 + ns.length * 6, y: center.y - 40 + ns.length * 6 }, data: { kind, label: k.label, values: {} } }]);
    setSelected(id);
  };
  const sel = nodes.find((n) => n.id === selected);
  const selKind = sel ? KIT_BY_TYPE[sel.data.kind] : undefined;
  const setVal = (key: string, v: string) => setNodes((ns) => ns.map((n) => (n.id === selected ? { ...n, data: { ...n.data, values: { ...n.data.values, [key]: v } } } : n)));
  const setLabel = (v: string) => setNodes((ns) => ns.map((n) => (n.id === selected ? { ...n, data: { ...n.data, label: v } } : n)));

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(fromRf(name, nodes, edges), null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.flow.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const importJson = async (file?: File) => {
    if (!file) return;
    try { show(JSON.parse(await file.text()) as Flow); } catch { alert('That file is not a flow JSON.'); }
  };

  return (
    <div className="flex h-full min-h-0">
      <aside className="w-[220px] shrink-0 overflow-y-auto border-r p-3 text-sm" data-testid="flow-palette">
        <div className="mb-2 font-semibold">Node kit ({KIT.length})</div>
        {GROUPS.map((g) => (
          <div key={g} className="mb-3">
            <div className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">{g}</div>
            {KIT.filter((k) => k.group === g).map((k) => {
              const Icon = ICONS[k.icon] ?? Wrench;
              return (
                <button key={k.type} type="button" title={k.what} onClick={() => add(k.type)}
                  className="mb-1 flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-muted">
                  <Icon className="size-3.5" style={{ color: k.color }} aria-hidden />
                  <span>{k.label}</span>
                  {k.source === 'alex' && <span className="ml-auto text-[9px] text-muted-foreground">yours</span>}
                </button>
              );
            })}
          </div>
        ))}
        <p className="text-[11px] text-muted-foreground">15 from Flowise Agentflow (open source, Apache 2.0) plus 4 of yours.</p>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2 text-sm">
          <input value={name} onChange={(e) => setName(e.target.value)} className="w-56 rounded border bg-background px-2 py-1" aria-label="Flow name" />
          <select className="rounded border bg-background px-2 py-1" aria-label="Load a template" value=""
            onChange={(e) => { const v = e.target.value; if (v === 'gepa') show(gepaPreset()); if (v === 'route') show(routingPreset()); if (v === 'blank') show({ name: 'New flow', nodes: [], edges: [] }); }}>
            <option value="">Load template…</option>
            <option value="gepa">GEPA feedback loop</option>
            <option value="route">Lead routing (if/else)</option>
            <option value="blank">Blank</option>
          </select>
          <button type="button" className="rounded border px-2 py-1 hover:bg-muted" onClick={exportJson}>Export JSON</button>
          <label className="cursor-pointer rounded border px-2 py-1 hover:bg-muted">Import JSON
            <input type="file" accept="application/json" className="hidden" onChange={(e) => importJson(e.target.files?.[0])} />
          </label>
          <span data-testid="flow-check" className={`ml-auto rounded px-2 py-1 text-xs font-medium ${issues.length ? 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100' : 'bg-green-100 text-green-900 dark:bg-green-900/40 dark:text-green-100'}`}>
            {issues.length ? `${issues.length} thing(s) to fix` : 'Flow check: OK'}
          </span>
        </div>
        <div className="relative min-h-0 flex-1">
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onConnect={onConnect} onNodeClick={(_, n) => setSelected(n.id)} onPaneClick={() => setSelected(null)} fitView
            defaultEdgeOptions={{ type: 'smoothstep' }} deleteKeyCode={['Backspace', 'Delete']}>
            <Background />
            <Controls />
            <MiniMap pannable zoomable />
          </ReactFlow>
        </div>
      </div>
      <aside className="w-[290px] shrink-0 overflow-y-auto border-l p-3 text-sm" data-testid="flow-inspector">
        {sel && selKind ? (
          <div className="space-y-3">
            <div>
              <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{selKind.label}</div>
              <p className="text-xs text-muted-foreground">{selKind.what}</p>
            </div>
            <label className="block text-xs font-medium">Name
              <input value={sel.data.label} onChange={(e) => setLabel(e.target.value)} className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm" />
            </label>
            {selKind.fields.map((f) => (
              <label key={f.key} className="block text-xs font-medium">{f.label}
                {f.kind === 'textarea' ? (
                  <textarea value={sel.data.values[f.key] ?? ''} placeholder={f.placeholder} onChange={(e) => setVal(f.key, e.target.value)} rows={4} className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm" />
                ) : f.kind === 'select' ? (
                  <select value={sel.data.values[f.key] ?? ''} onChange={(e) => setVal(f.key, e.target.value)} className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm">
                    <option value="">Choose…</option>
                    {f.options?.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                ) : (
                  <input type={f.kind === 'number' ? 'number' : 'text'} value={sel.data.values[f.key] ?? ''} placeholder={f.placeholder} onChange={(e) => setVal(f.key, e.target.value)} className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm" />
                )}
              </label>
            ))}
            <p className="text-[11px] text-muted-foreground">Delete: select and press Backspace.</p>
          </div>
        ) : (
          <div>
            <div className="mb-2 font-semibold">Flow check</div>
            {issues.length ? (
              <ul className="list-disc space-y-1 pl-4 text-xs">{issues.map((i) => <li key={i}>{i}</li>)}</ul>
            ) : (
              <p className="text-xs text-muted-foreground">No problems: one Start, every node reachable and wired, settings filled, every loop limited to 20 rounds, agents with tools come after the customer is known, every tool names its connector card, and nothing that spends, deletes, messages a customer, deploys or promotes can be reached without Alex&apos;s yes.</p>
            )}
            <p className="mt-4 text-[11px] text-muted-foreground">This tab draws and checks flows. To run them: agency-os-kit (gepa.py for the GEPA loop, route.py for routing).</p>
          </div>
        )}
      </aside>
    </div>
  );
}

export function FlowBuilderPanel() {
  return (
    <ReactFlowProvider>
      <Builder />
    </ReactFlowProvider>
  );
}
