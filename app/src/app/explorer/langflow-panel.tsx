'use client';

/**
 * Langflow tab: pick a saved flow, see its canvas, change the settings the dashboard supports,
 * save with a version check, import and export its JSON, and run it with Langflow's engine.
 *
 * Three things, kept apart: the saved flow (the file on disk, the only copy that runs), the canvas
 * (what you see and drag), and run state (each run's own record). Nothing here invents progress:
 * the panel shows the status the backend recorded, and nothing more.
 */
import '@xyflow/react/dist/style.css';

import { Background, Controls, Handle, Position, ReactFlow, useEdgesState, useNodesState, type Connection, type Edge, type Node, type NodeProps } from '@xyflow/react';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { queueEditInto } from '@/lib/langflow/queue';
import type { CanvasEdge, CanvasField, CanvasFlow, CanvasNode, CanvasPort, ExecutionPlan, FlowEdit, JsonValue, Problem } from '@/lib/langflow/model';

type Status = {
  engine: { name: string; pinnedLangflowVersion: string; configured: boolean; binaryFound: boolean };
  caller: { network: 'local' | 'tailnet'; canSave: boolean; canRun: boolean; canStop: boolean };
  accessError: string | null;
};
type FlowSummary = { id: string; name: string; nodeCount: number; hash: string; updatedAt: string };
type Detail = {
  id: string;
  hash: string;
  updatedAt: string;
  canvas: CanvasFlow;
  problems: Problem[];
  plan: ExecutionPlan;
  runnable: boolean;
  caller: { canSave: boolean; canRun: boolean };
};
type RunRecord = {
  id: string;
  status: 'running' | 'succeeded' | 'failed' | 'stopped' | 'unknown';
  input: string;
  output: string | null;
  error: string | null;
  errorCode: string | null;
  flowHash: string;
  flowUpdatedAt: string;
  engineVersion: string;
  startedAt: string;
  finishedAt: string | null;
};
type Rejection = { kind: string; nodeId: string; reason: string; index?: number };
type PaletteItem = {
  type: string;
  displayName: string;
  category: string;
  description: string;
  tier: string;
  tierLabel: string;
  runs: boolean;
  runNote: string | null;
};
type Catalog = { engine: { lfxVersion: string; langflowVersion: string | null }; count: number; components: PaletteItem[] };
type Preview = { canvas: CanvasFlow; problems: Problem[]; plan: ExecutionPlan };

const CATEGORY_LABEL: Record<string, string> = {
  agentics: 'Agentics',
  custom_component: 'Custom',
  data_source: 'Data sources',
  files_and_knowledge: 'Files and knowledge',
  files_ingestion: 'File ingestion',
  flow_controls: 'Flow controls',
  input_output: 'Input and output',
  langchain_utilities: 'LangChain utilities',
  llm_operations: 'LLM operations',
  models_and_agents: 'Models and agents',
  processing: 'Processing',
  utilities: 'Utilities',
};

function newNodeId(componentType: string): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  const bytes = new Uint8Array(5);
  crypto.getRandomValues(bytes);
  return `${componentType}-${Array.from(bytes, (b) => chars[b % chars.length]).join('')}`;
}


function describeEdit(e: FlowEdit, label: (id: string) => string): string {
  switch (e.kind) {
    case 'move': return `Move ${label(e.nodeId)}`;
    case 'rename': return `Rename ${label(e.nodeId)}`;
    case 'setField': return `Set "${e.field}" on ${label(e.nodeId)}`;
    case 'addNode': return `Add ${label(e.nodeId)}`;
    case 'deleteNode': return `Delete ${label(e.nodeId)}`;
    case 'connect': return `Connect ${label(e.nodeId)} → ${label(e.target)} (${e.sourceOutput} → ${e.targetInput})`;
    case 'disconnect': return 'Disconnect a connection';
    default: return 'Change';
  }
}

/** Searchable component list. Arrow keys move between items, Enter or click adds, Escape returns to the search box. */
function Palette({ catalog, disabled, onAdd }: { catalog: Catalog; disabled: boolean; onAdd: (item: PaletteItem) => void }) {
  const [query, setQuery] = useState('');
  const listRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const q = query.trim().toLowerCase();
  const matches = catalog.components.filter((c) => !q || `${c.displayName} ${c.type} ${c.category} ${c.description}`.toLowerCase().includes(q));
  const groups = new Map<string, PaletteItem[]>();
  for (const c of matches) groups.set(c.category, [...(groups.get(c.category) ?? []), c]);
  const items = () => Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('[data-palette-item]') ?? []);
  const onListKey = (e: React.KeyboardEvent) => {
    const all = items();
    const at = all.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const next = e.key === 'ArrowDown' ? Math.min(all.length - 1, at + 1) : at - 1;
      if (next < 0) searchRef.current?.focus();
      else all[next]?.focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      all[0]?.focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      all[all.length - 1]?.focus();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      searchRef.current?.focus();
    }
  };
  return (
    <div className="space-y-2">
      <input
        ref={searchRef}
        type="search"
        aria-label="Search components"
        aria-describedby="lf-palette-count"
        placeholder="Search components, for example split or date"
        className="w-full rounded border bg-background px-2 py-1 text-sm"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            items()[0]?.focus();
          } else if (e.key === 'Enter' && matches.length === 1 && !disabled) {
            e.preventDefault();
            onAdd(matches[0]);
          }
        }}
      />
      <p id="lf-palette-count" aria-live="polite" className="text-[11px] text-muted-foreground">
        {matches.length} of {catalog.count} components from engine lfx {catalog.engine.lfxVersion}.{disabled ? ' Adding is off: changes stay with the owner on the Mac.' : ' Enter or click adds one to the flow.'}
      </p>
      <div ref={listRef} onKeyDown={onListKey} className="max-h-64 space-y-2 overflow-y-auto pr-1" data-testid="lf-palette">
        {[...groups.entries()].map(([category, list]) => (
          <section key={category} aria-label={CATEGORY_LABEL[category] ?? category}>
            <h3 className="sticky top-0 bg-background py-0.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{CATEGORY_LABEL[category] ?? category}</h3>
            <ul className="grid gap-1 sm:grid-cols-2">
              {list.map((c) => (
                <li key={c.type}>
                  <button
                    type="button"
                    data-palette-item
                    disabled={disabled}
                    title={c.description}
                    aria-label={`Add ${c.displayName}. ${c.tierLabel}.`}
                    className="flex w-full items-center justify-between gap-2 rounded border px-2 py-1.5 text-left text-xs hover:bg-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
                    onClick={() => onAdd(c)}
                  >
                    <span className="truncate font-medium">{c.displayName}</span>
                    <span className={`shrink-0 text-[10px] ${c.runs ? 'text-green-700 dark:text-green-400' : 'text-muted-foreground'}`}>{c.tierLabel}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
        {matches.length === 0 ? <p className="text-xs text-muted-foreground">No component matches &quot;{query}&quot;.</p> : null}
      </div>
    </div>
  );
}

const SESSION_KEY = 'langflow-browser-session';
const STATUS_LABEL: Record<RunRecord['status'], string> = {
  running: 'Running',
  succeeded: 'Finished',
  failed: 'Failed',
  stopped: 'Stopped',
  unknown: 'Unknown',
};

function browserSession(): string {
  try {
    const existing = window.sessionStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const created = crypto.randomUUID();
    window.sessionStorage.setItem(SESSION_KEY, created);
    return created;
  } catch {
    return 'session-unavailable-' + Math.random().toString(36).slice(2, 10);
  }
}

async function api<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<{ ok: true; data: T } | { ok: false; status: number; error: string; body: Record<string, unknown> }> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('content-type')) headers.set('content-type', 'application/json');
  if (token) headers.set('x-local-token', token);
  try {
    const res = await fetch(path, { ...init, headers, cache: 'no-store' });
    const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (!res.ok) return { ok: false, status: res.status, error: String(body.error ?? `Request failed (${res.status}).`), body };
    return { ok: true, data: body as T };
  } catch {
    return { ok: false, status: 0, error: 'The dashboard backend did not answer. Check that the app is running on this Mac.', body: {} };
  }
}

const LAYOUT_NODE_WIDTH = 230;

/** Handle ids on the canvas: inputs "in:<field>", outputs "out:<output>", a loop's feedback point "loop:<output>". */
const inHandle = (name: string) => `in:${name}`;
const outHandle = (name: string) => `out:${name}`;
const loopHandle = (name: string) => `loop:${name}`;

function typesMatch(out: CanvasPort, accepts: string[]): boolean {
  return accepts.includes('Any') || out.types.some((t) => accepts.includes(t));
}

/** Types a loop's feedback point accepts: its own types plus its loop types (same rule as the server). */
function loopAccepts(p: CanvasPort): string[] {
  return [...p.types, ...(p.loopTypes ?? [])];
}

const LangflowNode = memo(function LangflowNode({ data, selected }: NodeProps<Node<{ node: CanvasNode }>>) {
  const node = data.node;
  const shown = node.fields.filter((f) => f.value !== null && f.value !== '' && typeof f.value !== 'object' && f.name !== 'code').slice(0, 2);
  return (
    <div
      data-testid={`lf-node-${node.id}`}
      className={`rounded-lg border bg-card text-card-foreground shadow-sm ${selected ? 'ring-2 ring-offset-1' : ''} ${node.isNote ? 'bg-yellow-50 dark:bg-yellow-950/40' : ''}`}
      style={{ width: LAYOUT_NODE_WIDTH }}
    >
      <div className="border-b px-3 py-2">
        <div className="truncate text-[13px] font-semibold">{node.label}</div>
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-wide text-muted-foreground">
          <span>{node.componentType || 'unknown'}</span>
          {node.executable ? <span className="text-green-700 dark:text-green-400">runs here</span> : node.isNote ? null : <span className="text-amber-700 dark:text-amber-400">not runnable here</span>}
        </div>
      </div>
      <div className="space-y-0.5 px-3 py-2 text-[11px] text-muted-foreground">
        {node.isNote ? <div className="text-foreground">Note</div> : shown.length ? shown.map((f) => (
          <div key={f.name} className="truncate"><span className="font-medium text-foreground">{f.label}:</span> {String(f.value)}</div>
        )) : <div>No settings to show</div>}
      </div>
      {node.inputs.length || node.outputs.length ? (
        <div className="space-y-1 border-t py-1.5 text-[10px]">
          {node.inputs.map((p) => (
            <div key={`i-${p.name}`} className="relative px-3" title={`Input: takes ${p.types.join(' or ')}`}>
              <Handle type="target" id={inHandle(p.name)} position={Position.Left} className="!size-2.5 !bg-sky-500" />
              <span className="text-muted-foreground">{p.label}</span>
            </div>
          ))}
          {node.outputs.map((p) => (
            <div key={`o-${p.name}`} className="relative px-3 text-right" title={`Output: sends ${p.types.join(' or ')}`}>
              {p.loop ? <Handle type="target" id={loopHandle(p.name)} position={Position.Left} className="!size-2.5 !bg-violet-500" /> : null}
              <span className="font-medium">{p.label}</span>
              <Handle type="source" id={outHandle(p.name)} position={Position.Right} className="!size-2.5 !bg-emerald-500" />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
});

const nodeTypes = { lf: LangflowNode };

const inputClass = 'w-full rounded border bg-background px-2 py-1 text-sm';

/** JSON setting (dict or table): edits as text, queues a change only when the text is valid JSON. */
function JsonEditor({ id, value, onChange, hint }: { id: string; value: JsonValue; onChange: (v: JsonValue) => void; hint: string }) {
  const [text, setText] = useState(() => JSON.stringify(value ?? null, null, 2));
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  // An undo or a server refusal changes the value from outside: show it, unless the person is typing here.
  useEffect(() => {
    if (document.activeElement === box.current) return;
    let same = false;
    try {
      same = JSON.stringify(JSON.parse(text)) === JSON.stringify(value ?? null);
    } catch {
      same = false;
    }
    if (!same) {
      setText(JSON.stringify(value ?? null, null, 2));
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only an outside change of value should resync
  }, [value]);
  return (
    <>
      <textarea
        ref={box}
        id={id}
        className={`${inputClass} font-mono text-xs`}
        rows={Math.min(10, Math.max(3, text.split('\n').length))}
        value={text}
        aria-invalid={!!error}
        aria-describedby={`${id}-hint`}
        spellCheck={false}
        onChange={(e) => {
          setText(e.target.value);
          try {
            const parsed = JSON.parse(e.target.value) as JsonValue;
            if (parsed === null || typeof parsed !== 'object') {
              setError('Use a JSON object or a list. Nothing is queued until it is.');
              return;
            }
            setError(null);
            onChange(parsed);
          } catch {
            setError('Not valid JSON yet. Nothing is queued until it is.');
          }
        }}
      />
      <p id={`${id}-hint`} className={`text-[11px] ${error ? 'text-red-700 dark:text-red-400' : 'text-muted-foreground'}`}>{error ?? hint}</p>
    </>
  );
}

/**
 * Long text and prompts: the box keeps what is being typed, even while a half-typed value is refused
 * (for example "{my var" in a prompt). When focus leaves, it shows the value that is actually queued or saved.
 */
function TextAreaEditor({ id, value, rows, onChange }: { id: string; value: string; rows: number; onChange: (v: string) => void }) {
  const [text, setText] = useState(value);
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    if (!editing) setText(value);
  }, [value, editing]);
  return (
    <textarea
      id={id}
      className={inputClass}
      rows={rows}
      value={text}
      onFocus={() => setEditing(true)}
      onBlur={() => setEditing(false)}
      onChange={(e) => {
        setText(e.target.value);
        onChange(e.target.value);
      }}
    />
  );
}

function FieldEditorInput({ field, value, onChange, id }: { field: CanvasField; value: JsonValue; onChange: (v: JsonValue) => void; id: string }) {
  const text = value === null || typeof value === 'object' ? '' : String(value);
  switch (field.editor) {
    case 'bool':
      return <input id={id} type="checkbox" className="size-4" checked={value === true} onChange={(e) => onChange(e.target.checked)} />;
    case 'select':
      return (
        <select id={id} className={inputClass} value={text} onChange={(e) => onChange(e.target.value)}>
          {field.options.includes(text) ? null : <option value={text}>{text || '(not set)'}</option>}
          {field.options.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      );
    case 'number':
      return (
        <>
          <input
            id={id}
            type="number"
            className={inputClass}
            step={field.range?.step ?? (field.fieldType === 'int' ? 1 : 'any')}
            min={field.range?.min}
            max={field.range?.max}
            value={text}
            onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          />
          {field.range ? <p className="text-[11px] text-muted-foreground">From {field.range.min} to {field.range.max}.</p> : null}
        </>
      );
    case 'multiline':
      return (
        <>
          <TextAreaEditor id={id} rows={field.fieldType === 'prompt' ? 6 : 4} value={text} onChange={onChange} />
          {field.fieldType === 'prompt' ? <p className="text-[11px] text-muted-foreground">Each {'{name}'} becomes an input that takes a message, as in Langflow.</p> : null}
        </>
      );
    case 'json':
      return (
        <JsonEditor
          id={id}
          value={value}
          onChange={onChange}
          hint={field.fieldType === 'table' ? `A list of rows${field.columns ? ` with the columns ${field.columns.join(', ')}` : ''}.` : 'A JSON object, like {"key": "value"}.'}
        />
      );
    default:
      return <input id={id} type="text" className={inputClass} value={text} onChange={(e) => onChange(e.target.value)} />;
  }
}

function shownValue(field: CanvasField): string {
  if (field.summary) return field.summary;
  if (field.value === null || field.value === '') return '(empty)';
  return typeof field.value === 'object' ? JSON.stringify(field.value) : String(field.value);
}

/** Keyboard and touch way to wire, unwire and delete the selected component (the canvas needs a mouse). */
function NodeConnections({ node, view, canEdit, onEdit }: { node: CanvasNode; view: CanvasFlow; canEdit: boolean; onEdit: (e: FlowEdit) => void }) {
  const [output, setOutput] = useState('');
  const [dest, setDest] = useState('');
  const label = (id: string) => view.nodes.find((n) => n.id === id)?.label ?? id;
  const mine = view.edges.filter((e) => e.source === node.id || e.target === node.id);
  const out = node.outputs.find((p) => p.name === output) ?? node.outputs[0];
  const destinations = out
    ? view.nodes.filter((n) => n.id !== node.id).flatMap((n) => [
      ...n.inputs.filter((p) => typesMatch(out, p.types)).map((p) => ({ value: `${n.id}|in|${p.name}`, text: `${n.label} → ${p.label}` })),
      ...n.outputs.filter((p) => p.loop && typesMatch(out, loopAccepts(p))).map((p) => ({ value: `${n.id}|loop|${p.name}`, text: `${n.label} → ${p.label} (loop feedback)` })),
    ])
    : [];
  const chosen = destinations.find((d) => d.value === dest) ?? destinations[0];
  return (
    <div className="mt-3 space-y-2 border-t pt-2">
      <h3 className="text-xs font-semibold">Connections</h3>
      {mine.length === 0 ? <p className="text-[11px] text-muted-foreground">Not connected.</p> : (
        <ul className="space-y-1 text-[11px]">
          {mine.map((e) => (
            <li key={e.id} className="flex items-center justify-between gap-2">
              <span>{e.source === node.id ? `${e.sourceOutput} → ${label(e.target)} (${e.targetInput})` : `${label(e.source)} (${e.sourceOutput}) → ${e.targetInput}`}</span>
              {canEdit ? <button type="button" className="rounded border px-1.5 py-0.5 hover:bg-muted" onClick={() => onEdit({ kind: 'disconnect', edgeId: e.id })}>Disconnect</button> : null}
            </li>
          ))}
        </ul>
      )}
      {canEdit && node.outputs.length ? (
        <div className="space-y-1">
          <label htmlFor="lf-connect-output" className="block text-[11px] font-medium">Connect output</label>
          <select id="lf-connect-output" className="w-full rounded border bg-background px-2 py-1 text-xs" value={out?.name ?? ''} onChange={(e) => { setOutput(e.target.value); setDest(''); }}>
            {node.outputs.map((p) => <option key={p.name} value={p.name}>{p.label} (sends {p.types.join(' or ')})</option>)}
          </select>
          <label htmlFor="lf-connect-dest" className="block text-[11px] font-medium">To</label>
          <select id="lf-connect-dest" className="w-full rounded border bg-background px-2 py-1 text-xs" value={chosen?.value ?? ''} onChange={(e) => setDest(e.target.value)} disabled={destinations.length === 0}>
            {destinations.length === 0 ? <option value="">No input in this flow takes this type</option> : destinations.map((d) => <option key={d.value} value={d.value}>{d.text}</option>)}
          </select>
          <button
            type="button"
            className="rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
            disabled={!out || !chosen}
            onClick={() => {
              if (!out || !chosen) return;
              const [target, kind, input] = chosen.value.split('|');
              onEdit({ kind: 'connect', nodeId: node.id, sourceOutput: out.name, target, targetInput: input, ...(kind === 'loop' ? { targetLoop: true } : {}) });
            }}
          >
            Connect
          </button>
        </div>
      ) : null}
      {canEdit ? (
        <button type="button" className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/40" onClick={() => onEdit({ kind: 'deleteNode', nodeId: node.id })}>
          Delete this component
        </button>
      ) : null}
    </div>
  );
}

export function LangflowPanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [accessReady, setAccessReady] = useState(false);
  const [flows, setFlows] = useState<FlowSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<{ node: CanvasNode }>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [pending, setPending] = useState<FlowEdit[]>([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [rejections, setRejections] = useState<Rejection[]>([]);
  const [conflict, setConflict] = useState(false);
  const [runInput, setRunInput] = useState('Hello from the dashboard');
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [starting, setStarting] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [runBlockers, setRunBlockers] = useState<string[]>([]);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const previewSeq = useRef(0);
  const session = useRef<string>('');
  const flowsRequested = useRef(false);
  const importInput = useRef<HTMLInputElement>(null);

  const canImport = status?.caller.network === 'local' && !!status.caller.canSave && !!token;
  const canSave = !!status?.caller.canSave && !!detail?.caller.canSave && !!token;
  const canRun = !!status?.caller.canRun && !!detail?.caller.canRun && !!token && !!status?.engine.configured;
  const hasRunning = runs.some((r) => r.status === 'running');

  useEffect(() => {
    session.current = browserSession();
    let cancelled = false;
    const loadAccess = async () => {
      let localToken: string | null = null;
      if (['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)) {
        const health = await api<{ token?: string }>('/api/health');
        if (health.ok) localToken = health.data.token ?? null;
      }
      if (cancelled) return;
      setToken(localToken);
      // Permission reads must use the same token as mutations, after health has answered.
      const result = await api<Status>('/api/langflow/status', {}, localToken);
      if (cancelled) return;
      if (result.ok) setStatus(result.data);
      else setLoadError(result.error);
      setAccessReady(true);
    };
    void loadAccess();
    return () => { cancelled = true; };
  }, []);

  const loadFlows = useCallback(async () => {
    const r = await api<{ flows: FlowSummary[] }>('/api/langflow/flows');
    if (r.ok) {
      setFlows(r.data.flows);
      setSelectedId((current) => current ?? r.data.flows[0]?.id ?? null);
    } else {
      setLoadError(r.error);
    }
  }, []);

  useEffect(() => {
    if (flowsRequested.current) return;
    flowsRequested.current = true;
    void loadFlows();
  }, [loadFlows]);

  const showCanvas = useCallback((canvas: CanvasFlow) => {
    setNodes(canvas.nodes.map((n) => ({ id: n.id, type: 'lf', position: n.position, data: { node: n } })));
    setEdges(canvas.edges.map((e: CanvasEdge) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceOutput ? outHandle(e.sourceOutput) : undefined,
      targetHandle: e.targetInput ? (e.targetLoop ? loopHandle(e.targetInput) : inHandle(e.targetInput)) : undefined,
      ariaLabel: `Connection ${e.sourceOutput ?? '?'} to ${e.targetInput ?? '?'}`,
      label: e.sourceOutput && e.targetInput ? `${e.sourceOutput} → ${e.targetInput}` : undefined,
      style: e.decodeError ? { stroke: '#dc2626', strokeDasharray: '4 4' } : undefined,
    })));
  }, [setEdges, setNodes]);

  const loadDetail = useCallback(async (id: string) => {
    const r = await api<Detail>(`/api/langflow/flows/${encodeURIComponent(id)}`, {}, token);
    if (!r.ok) {
      setDetail(null);
      setLoadError(r.error);
      return;
    }
    setLoadError(null);
    setDetail(r.data);
    setPending([]);
    setRejections([]);
    setConflict(false);
    setSelectedNode(null);
    setPreview(null);
    showCanvas(r.data.canvas);
  }, [showCanvas, token]);

  // Run history belongs to the owner: without the local token the server returns none, so the token is sent.
  const loadRuns = useCallback(async (id: string, tok: string | null) => {
    const r = await api<{ runs: RunRecord[] }>(`/api/langflow/flows/${encodeURIComponent(id)}/runs`, { headers: { 'x-browser-session': session.current } }, tok);
    if (r.ok) setRuns(r.data.runs);
  }, []);

  useEffect(() => {
    if (!selectedId || !accessReady) return;
    void loadDetail(selectedId);
  }, [selectedId, accessReady, loadDetail]);

  useEffect(() => {
    if (selectedId) void loadRuns(selectedId, token);
  }, [selectedId, token, loadRuns]);

  useEffect(() => {
    if (!accessReady) return;
    let cancelled = false;
    void api<Catalog>('/api/langflow/components', {}, token).then((r) => {
      if (cancelled) return;
      if (r.ok) setCatalog(r.data);
      else setCatalogError(r.error);
    });
    return () => { cancelled = true; };
  }, [accessReady, token]);

  // Unsaved changes are previewed by the server with the same rules as a save (dry run, nothing written).
  // An edit the server refuses is taken back out of the list, with its reason shown.
  useEffect(() => {
    if (!detail || !token || !canSave) return;
    const seq = ++previewSeq.current;
    if (pending.length === 0) {
      setPreview(null);
      showCanvas(detail.canvas);
      return;
    }
    setPreviewing(true);
    void api<Preview & { applied: number }>(
      `/api/langflow/flows/${encodeURIComponent(detail.id)}`,
      { method: 'PATCH', body: JSON.stringify({ expectedHash: detail.hash, edits: pending, dryRun: true }) },
      token,
    ).then((r) => {
      if (seq !== previewSeq.current) return;
      setPreviewing(false);
      if (r.ok) {
        setPreview(r.data);
        showCanvas(r.data.canvas);
        return;
      }
      if (r.status === 409) {
        setConflict(true);
        setSaveMessage(r.error);
        return;
      }
      const list = Array.isArray(r.body.rejected) ? (r.body.rejected as Rejection[]) : [];
      if (list.length) {
        const drop = new Set(list.map((x) => x.index).filter((i): i is number => typeof i === 'number'));
        setRejections(list);
        setSaveMessage('That change is not allowed, so it was taken back out. The reason is below.');
        setPending((cur) => (cur === pending ? cur.filter((_, i) => !drop.has(i)) : cur));
      } else {
        setSaveMessage(r.error);
      }
    });
  }, [pending, detail, token, canSave, showCanvas]);

  useEffect(() => {
    if (!selectedId || !hasRunning) return;
    const timer = window.setInterval(() => void loadRuns(selectedId, token), 2000);
    return () => window.clearInterval(timer);
  }, [selectedId, hasRunning, loadRuns, token]);

  const queueEdit = useCallback((edit: FlowEdit) => {
    setRejections([]);
    setSaveMessage(null);
    setPending((list) => queueEditInto(list, edit));
  }, []);

  const addComponent = useCallback((item: PaletteItem) => {
    const shown = preview?.canvas.nodes ?? detail?.canvas.nodes ?? [];
    const maxX = shown.reduce((m, n) => Math.max(m, n.position.x), -320);
    const minY = shown.reduce((m, n) => Math.min(m, n.position.y), Number.POSITIVE_INFINITY);
    const nodeId = newNodeId(item.type);
    queueEdit({ kind: 'addNode', nodeId, componentType: item.type, position: { x: maxX + 320, y: Number.isFinite(minY) ? minY : 0 } });
    setSelectedNode(nodeId);
  }, [detail, preview, queueEdit]);

  const portOf = useCallback((nodeId: string, handleId: string | null | undefined) => {
    const node = (preview?.canvas ?? detail?.canvas)?.nodes.find((n) => n.id === nodeId);
    if (!node || !handleId) return null;
    const [kind, name] = [handleId.slice(0, handleId.indexOf(':')), handleId.slice(handleId.indexOf(':') + 1)];
    if (kind === 'out') return { kind, port: node.outputs.find((p) => p.name === name) };
    if (kind === 'in') return { kind, port: node.inputs.find((p) => p.name === name) };
    if (kind === 'loop') return { kind, port: node.outputs.find((p) => p.name === name && p.loop) };
    return null;
  }, [detail, preview]);

  // Fast check while dragging; the server makes the final decision with the same rule.
  const isValidConnection = useCallback((c: Connection | Edge) => {
    if (!c.source || !c.target || c.source === c.target) return false;
    const from = portOf(c.source, c.sourceHandle);
    const to = portOf(c.target, c.targetHandle);
    if (!from?.port || from.kind !== 'out' || !to?.port) return false;
    return typesMatch(from.port, to.kind === 'loop' ? loopAccepts(to.port) : to.port.types);
  }, [portOf]);

  const onConnect = useCallback((c: Connection) => {
    if (!canSave || !c.sourceHandle || !c.targetHandle) return;
    const targetLoop = c.targetHandle.startsWith('loop:');
    queueEdit({
      kind: 'connect',
      nodeId: c.source,
      sourceOutput: c.sourceHandle.slice('out:'.length),
      target: c.target,
      targetInput: c.targetHandle.slice(c.targetHandle.indexOf(':') + 1),
      ...(targetLoop ? { targetLoop: true } : {}),
    });
  }, [canSave, queueEdit]);

  const onNodesDelete = useCallback((deleted: Node[]) => {
    if (!canSave) return;
    for (const n of deleted) queueEdit({ kind: 'deleteNode', nodeId: n.id });
    setSelectedNode(null);
  }, [canSave, queueEdit]);

  const onEdgesDelete = useCallback((deleted: Edge[]) => {
    if (!canSave) return;
    // Connections of a deleted component go with it; only queue the ones removed on their own.
    const gone = new Set(nodes.filter((n) => n.selected).map((n) => n.id));
    for (const e of deleted) if (!gone.has(e.source) && !gone.has(e.target)) queueEdit({ kind: 'disconnect', edgeId: e.id });
  }, [canSave, nodes, queueEdit]);

  const onNodeDragStop = useCallback((_: unknown, node: Node) => {
    queueEdit({ kind: 'move', nodeId: node.id, position: { x: node.position.x, y: node.position.y } });
  }, [queueEdit]);

  const view: CanvasFlow | undefined = preview?.canvas ?? detail?.canvas;
  const selected: CanvasNode | undefined = useMemo(() => view?.nodes.find((n) => n.id === selectedNode), [view, selectedNode]);
  const labelFor = (id: string) => view?.nodes.find((n) => n.id === id)?.label ?? detail?.canvas.nodes.find((n) => n.id === id)?.label ?? id;

  const valueOf = (field: CanvasField): JsonValue => {
    const edit = pending.find((e) => e.kind === 'setField' && e.nodeId === selectedNode && e.field === field.name);
    return edit && edit.kind === 'setField' ? edit.value : field.value;
  };

  const save = async () => {
    if (!detail || !token || saving || pending.length === 0) return;
    setSaving(true);
    setSaveMessage(null);
    setRejections([]);
    const r = await api<{ hash: string; updatedAt: string; applied: number }>(
      `/api/langflow/flows/${encodeURIComponent(detail.id)}`,
      { method: 'PATCH', body: JSON.stringify({ expectedHash: detail.hash, edits: pending }) },
      token,
    );
    setSaving(false);
    if (r.ok) {
      setSaveMessage(`Saved ${r.data.applied} change${r.data.applied === 1 ? '' : 's'}. New version ${r.data.hash.slice(0, 10)}.`);
      await loadDetail(detail.id);
      await loadFlows();
      return;
    }
    if (r.status === 409) {
      setConflict(true);
      setSaveMessage(r.error);
      return;
    }
    const list = Array.isArray(r.body.rejected) ? (r.body.rejected as Rejection[]) : [];
    setRejections(list);
    setSaveMessage(list.length ? 'Nothing was saved. Fix the items below, then save again.' : r.error);
  };

  const onImport = async (file: File | undefined) => {
    if (!file || !canImport) return;
    setImportMessage(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      setImportMessage('That file is not JSON.');
      return;
    }
    const r = await api<{ id: string; secretsRemoved: number; problems: Problem[] }>('/api/langflow/flows', { method: 'POST', body: JSON.stringify(parsed) }, token);
    if (!r.ok) {
      setImportMessage(r.error);
      return;
    }
    const note = r.data.secretsRemoved > 0 ? ` ${r.data.secretsRemoved} secret value${r.data.secretsRemoved === 1 ? ' was' : 's were'} removed; set ${r.data.secretsRemoved === 1 ? 'it' : 'them'} in Langflow's native editor.` : '';
    setImportMessage(`Imported.${note}`);
    await loadFlows();
    setSelectedId(r.data.id);
  };

  const startRun = async () => {
    if (!detail || starting || !canRun || pending.length > 0) return;
    setStarting(true);
    setRunMessage(null);
    setRunBlockers([]);
    const key = `run-${detail.id}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    const r = await api<{ run: RunRecord; duplicate?: boolean }>(
      `/api/langflow/flows/${encodeURIComponent(detail.id)}/runs`,
      { method: 'POST', body: JSON.stringify({ input: runInput }), headers: { 'x-browser-session': session.current, 'idempotency-key': key } },
      token,
    );
    setStarting(false);
    if (!r.ok) {
      const blockers = Array.isArray(r.body.blockers) ? (r.body.blockers as Array<{ reason: string }>).map((b) => b.reason) : [];
      setRunBlockers(blockers);
      setRunMessage(r.error);
      return;
    }
    setRunMessage(r.data.duplicate ? 'That run was already started. Showing it below.' : 'Run started.');
    await loadRuns(detail.id, token);
  };

  const stopRun = async (runId: string) => {
    if (!token) return;
    const r = await api<{ stopped: boolean }>(`/api/langflow/runs/${runId}/stop`, { method: 'POST', body: '{}' }, token);
    setRunMessage(r.ok ? 'Stop sent. The engine process is being killed; the run shows Stopped when it exits.' : r.error);
    if (detail) await loadRuns(detail.id, token);
  };

  const problems = preview?.problems ?? detail?.problems;

  const flowOptions = flows.map((f) => (
    <option key={f.id} value={f.id}>{f.name}</option>
  ));

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-3 lg:flex-row lg:overflow-hidden">
      <section className="flex min-w-0 shrink-0 flex-col gap-2 lg:min-h-0 lg:flex-1 lg:shrink">
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="lf-flow" className="text-xs uppercase tracking-wide text-muted-foreground">Saved flow</label>
          <select id="lf-flow" className="min-w-[180px] rounded border bg-background px-2 py-1 text-sm" value={selectedId ?? ''} onChange={(e) => setSelectedId(e.target.value || null)} disabled={flows.length === 0}>
            {flows.length === 0 ? <option value="">No saved flows yet</option> : flowOptions}
          </select>
          {detail ? (
            <>
              <span className="text-xs text-muted-foreground">version {detail.hash.slice(0, 10)} · saved {new Date(detail.updatedAt).toLocaleString()}</span>
              <a className="rounded border px-2 py-1 text-xs hover:bg-muted" href={`/api/langflow/flows/${encodeURIComponent(detail.id)}/export`} download>Export JSON</a>
            </>
          ) : null}
          <button type="button" className="rounded border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50" disabled={!canImport} onClick={() => importInput.current?.click()}>
            Import JSON
          </button>
          <input ref={importInput} type="file" aria-label="Import Langflow JSON file" accept="application/json,.json" className="hidden" disabled={!canImport} onChange={(e) => {
            void onImport(e.target.files?.[0]);
            e.target.value = '';
          }} />
        </div>

        {status ? (
          <div className="space-y-1 text-xs text-muted-foreground">
            {!status.engine.configured ? <p className="text-amber-700 dark:text-amber-400">Engine not configured: running is off until LANGFLOW_LFX_BIN points at the pinned Langflow {status.engine.pinnedLangflowVersion} engine.</p> : null}
            {status.caller.network === 'tailnet' ? <p>Read-only from this device. Changes and runs stay on the Mac (Alex, 2026-10-12).</p> : null}
            {status.caller.network === 'local' && !token ? <p>Read-only until the local token loads. Reload this page on the Mac.</p> : null}
            {status.accessError ? <p className="text-red-700 dark:text-red-400">{status.accessError}</p> : null}
            <p>Langflow&apos;s own editor is not running in this build, so advanced edits stay in Langflow for now.</p>
          </div>
        ) : null}
        {loadError ? <p role="alert" className="text-sm text-red-700 dark:text-red-400">{loadError}</p> : null}
        {importMessage ? <p role="status" className="text-sm">{importMessage}</p> : null}

        {detail ? (
          <details className="shrink-0 rounded border p-2 text-sm" open={paletteOpen} onToggle={(e) => setPaletteOpen((e.currentTarget as HTMLDetailsElement).open)}>
            <summary className="cursor-pointer font-medium">Add a component {catalog ? `(${catalog.count})` : ''}</summary>
            <div className="mt-2">
              {catalog ? <Palette catalog={catalog} disabled={!canSave} onAdd={addComponent} /> : <p className="text-xs text-muted-foreground">{catalogError ?? 'Loading the component list from the engine…'}</p>}
            </div>
          </details>
        ) : null}

        <div className="h-[55vh] min-h-[320px] shrink-0 rounded border bg-background lg:h-auto lg:min-h-0 lg:flex-1 lg:shrink">
          {detail ? (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeDragStop={onNodeDragStop}
              onNodeClick={(_, n) => setSelectedNode(n.id)}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              nodesDraggable={canSave}
              nodesConnectable={canSave}
              onConnect={onConnect}
              isValidConnection={isValidConnection}
              onNodesDelete={onNodesDelete}
              onEdgesDelete={onEdgesDelete}
              deleteKeyCode={canSave ? ['Backspace', 'Delete'] : null}
              elementsSelectable
              edgesFocusable
              nodesFocusable
              proOptions={{ hideAttribution: true }}
            >
              <Background />
              <Controls showInteractive={false} />
            </ReactFlow>
          ) : (
            <p className="p-4 text-sm text-muted-foreground">{flows.length ? 'Loading the flow…' : 'Import a Langflow flow JSON to start. Use the Export button in Langflow, then Import JSON here.'}</p>
          )}
        </div>

        <details className="shrink-0 rounded border p-2 text-sm lg:max-h-[30vh] lg:overflow-y-auto">
          <summary className="cursor-pointer font-medium">Components ({view?.nodes.length ?? 0})</summary>
          <ul className="mt-2 grid gap-1 sm:grid-cols-2">
            {view?.nodes.map((n) => (
              <li key={n.id}>
                <button type="button" className={`w-full rounded px-2 py-1 text-left text-xs hover:bg-muted ${selectedNode === n.id ? 'bg-muted font-semibold' : ''}`} onClick={() => setSelectedNode(n.id)}>
                  {n.label} <span className="text-muted-foreground">({n.componentType || 'unknown'})</span>
                </button>
              </li>
            ))}
          </ul>
        </details>
      </section>

      <aside className="flex w-full shrink-0 flex-col gap-3 lg:min-h-0 lg:w-[380px] lg:overflow-y-auto">
        <div className="rounded border p-3">
          <h2 className="mb-2 text-sm font-semibold">Settings {selected ? `· ${selected.label}` : ''}</h2>
          {!selected ? <p className="text-xs text-muted-foreground">Select a component on the canvas or in the list.</p> : (
            <div className="space-y-2">
              {selected.fields.length === 0 ? <p className="text-xs text-muted-foreground">No settings for this component.</p> : null}
              {selected.fields.map((f) => {
                const id = `lf-field-${selected.id}-${f.name}`;
                const value = valueOf(f);
                return (
                  <div key={f.name} className="space-y-1">
                    <label htmlFor={id} className="block text-xs font-medium">
                      {f.label}{f.required ? ' *' : ''}
                    </label>
                    {f.editable && canSave && !f.connected ? (
                      <FieldEditorInput key={`${selected.id}-${f.name}`} field={f} value={value} id={id} onChange={(v) => queueEdit({ kind: 'setField', nodeId: selected.id, field: f.name, value: v })} />
                    ) : (
                      <p id={id} className="break-words text-xs text-muted-foreground">{f.connected ? 'Set by its connection.' : shownValue(f)}</p>
                    )}
                    {!f.editable && f.readOnlyReason ? <p className="text-[11px] text-muted-foreground">{f.readOnlyReason}</p> : null}
                  </div>
                );
              })}
              {view && !selected.isNote ? <NodeConnections key={selected.id} node={selected} view={view} canEdit={canSave} onEdit={(e) => { queueEdit(e); if (e.kind === 'deleteNode') setSelectedNode(null); }} /> : null}
            </div>
          )}
        </div>

        <div className="rounded border p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Changes {pending.length ? `(${pending.length})` : ''}</h2>
            <button type="button" className="rounded bg-primary px-3 py-1 text-xs text-primary-foreground disabled:opacity-50" disabled={!canSave || saving || pending.length === 0} onClick={() => void save()}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
          {pending.length === 0 ? <p className="text-xs text-muted-foreground">No unsaved changes. Moving a component or changing a setting queues a change.</p> : (
            <ul className="space-y-1 text-xs">
              {pending.map((e, i) => (
                <li key={`${e.kind}-${i}`} className="flex items-center justify-between gap-2">
                  <span>{describeEdit(e, labelFor)}</span>
                  <button type="button" className="rounded border px-1.5 py-0.5 text-[11px] hover:bg-muted" aria-label={`Undo: ${describeEdit(e, labelFor)}`} onClick={() => setPending((list) => list.filter((_, j) => j !== i))}>Undo</button>
                </li>
              ))}
              {previewing ? <li className="text-muted-foreground">Checking the change…</li> : null}
            </ul>
          )}
          {saveMessage ? <p role="status" className="mt-2 text-xs">{saveMessage}</p> : null}
          {conflict ? <button type="button" className="mt-2 rounded border px-2 py-1 text-xs hover:bg-muted" onClick={() => selectedId && void loadDetail(selectedId)}>Reload the flow</button> : null}
          {rejections.length ? (
            <ul className="mt-2 space-y-1 text-xs text-red-700 dark:text-red-400">
              {rejections.map((r, i) => <li key={i}>{r.reason}</li>)}
            </ul>
          ) : null}
        </div>

        <div className="rounded border p-3">
          <h2 className="mb-2 text-sm font-semibold">Problems {problems ? `(${problems.length})` : ''}{preview ? ' · with unsaved changes' : ''}</h2>
          {!problems || problems.length === 0 ? <p className="text-xs text-muted-foreground">No problems found.</p> : (
            <ul className="space-y-1 text-xs">
              {problems.map((p, i) => (
                <li key={i} className={p.level === 'error' ? 'text-red-700 dark:text-red-400' : 'text-amber-700 dark:text-amber-400'}>
                  <span className="font-medium">{p.level === 'error' ? 'Error' : 'Warning'}:</span> {p.message}
                  {p.nodeId ? <button type="button" className="ml-2 underline" onClick={() => setSelectedNode(p.nodeId ?? null)}>show</button> : null}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded border p-3">
          <h2 className="mb-2 text-sm font-semibold">Run</h2>
          {detail && !detail.runnable ? (
            <p className="mb-2 text-xs text-muted-foreground">This flow cannot run here yet. It needs a Chat Output, no errors, and only components that run here (runs stay local: no AI model, internet, code, file or server steps). </p>
          ) : null}
          {detail && !detail.runnable && !runBlockers.length && detail.plan.blockers.length ? (
            <ul className="mb-2 space-y-1 text-xs text-amber-700 dark:text-amber-400" aria-label="Why this flow does not run here">
              {detail.plan.blockers.slice(0, 6).map((b) => <li key={b.nodeId}>{b.reason}</li>)}
              {detail.plan.blockers.length > 6 ? <li>and {detail.plan.blockers.length - 6} more.</li> : null}
            </ul>
          ) : null}
          {runBlockers.length ? <ul className="mb-2 space-y-1 text-xs text-red-700 dark:text-red-400">{runBlockers.map((b, i) => <li key={i}>{b}</li>)}</ul> : null}
          {detail && detail.runnable && !detail.plan.hasChatInput ? <p className="mb-2 text-xs text-muted-foreground">This flow has no Chat Input, so the message below is not used.</p> : null}
          <label htmlFor="lf-run-input" className="block text-xs font-medium">Message to the flow</label>
          <textarea id="lf-run-input" className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm" rows={2} maxLength={2000} value={runInput} onChange={(e) => setRunInput(e.target.value)} />
          <div className="mt-2 flex items-center gap-2">
            <button type="button" className="rounded bg-primary px-3 py-1 text-xs text-primary-foreground disabled:opacity-50" disabled={!canRun || starting || pending.length > 0 || runInput.trim() === '' || (!!detail && !detail.runnable)} onClick={() => void startRun()}>
              {starting ? 'Starting…' : 'Run flow'}
            </button>
            {pending.length > 0 ? <span className="text-xs text-muted-foreground">Save your changes first: a run uses the saved version.</span> : null}
          </div>
          {runMessage ? <p role="status" className="mt-2 text-xs">{runMessage}</p> : null}

          <h3 className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Runs in this browser session</h3>
          {runs.length === 0 ? <p className="text-xs text-muted-foreground">No runs yet in this session.</p> : (
            <ul className="space-y-2">
              {runs.map((r) => (
                <li key={r.id} className="rounded border p-2 text-xs" data-testid={`run-${r.id}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{STATUS_LABEL[r.status]}</span>
                    <span className="text-muted-foreground">{new Date(r.startedAt).toLocaleTimeString()}</span>
                    <span className="text-muted-foreground">run {r.id.slice(0, 8)}</span>
                    <span className="text-muted-foreground">flow {r.flowHash.slice(0, 10)} · engine {r.engineVersion}</span>
                    {r.status === 'running' && canRun ? <button type="button" className="ml-auto rounded border px-2 py-0.5 hover:bg-muted" onClick={() => void stopRun(r.id)}>Stop</button> : null}
                  </div>
                  <p className="mt-1 text-muted-foreground">Input: {r.input}</p>
                  {r.output !== null ? <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted p-2">{r.output}</pre> : null}
                  {r.error ? <p className="mt-1 text-red-700 dark:text-red-400">{r.error}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
