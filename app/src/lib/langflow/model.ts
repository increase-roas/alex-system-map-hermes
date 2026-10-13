// Langflow flow JSON (1.12.x) <-> canvas model.
//
// Three different things, kept apart on purpose:
//   1. the saved configuration: the Langflow flow JSON, stored as-is (unknown fields preserved);
//   2. the visual graph: the canvas model derived from it (positions, labels, visible settings);
//   3. execution state: run records, kept in runs.ts, never written into the flow.
// Only the edits listed in FlowEdit can change a saved flow. Anything else is rejected with a reason.

import { createHash } from 'node:crypto';

import { decodeHandle, encodeHandle, HandleDecodeError, type HandleObject } from './handles';
import { EXECUTABLE_COMPONENTS, runBlockReason } from './tiers';

export { EXECUTABLE_COMPONENTS };

export type JsonObject = Record<string, unknown>;

export const REDACTED = '[redacted]';

/** Settings the dashboard never edits. */
const READ_ONLY_REASON: Record<string, string> = {
  code: "Python code that Langflow runs. Edit it in Langflow's native editor, not here.",
  _type: 'Internal field.',
};

/** How the panel edits a setting. "readonly" settings come with the reason. */
export type FieldEditor = 'text' | 'multiline' | 'number' | 'bool' | 'select' | 'json' | 'readonly';

/** Settings of these types the dashboard can edit. Everything else stays read-only with a reason. */
const EDITOR_BY_TYPE: Record<string, FieldEditor> = {
  str: 'text',
  prompt: 'multiline',
  int: 'number',
  float: 'number',
  slider: 'number',
  bool: 'bool',
  tab: 'select',
  dict: 'json',
  NestedDict: 'json',
  table: 'json',
};

const READ_ONLY_BY_TYPE: Record<string, string> = {
  file: 'File setting. Reading files is off in this app, so it is set in Langflow.',
  model: 'Model picker. Running AI models is off in this app, so it is set in Langflow.',
  mcp: 'MCP server setting. Tools are off in this app, so it is set in Langflow.',
  sortableList: "Picker that changes the component's own settings through a running Langflow server. Set it in Langflow.",
  actionPicker: 'Action picker that needs a running Langflow server. Set it in Langflow.',
  query: 'Query setting. Set it in Langflow.',
  duration: 'Duration setting. Set it in Langflow.',
  data_display: 'Display only.',
};

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

/** Keys whose values are treated as secrets inside JSON settings (headers, tables, dictionaries). */
const SECRET_KEY = /authorization|cookie|token|secret|passw|api[_-]?key|private[_-]?key|credential|bearer/i;

type SecretHolder = Record<string, unknown> | unknown[];

function isSecretLeaf(v: unknown): boolean {
  return (typeof v === 'string' && v !== '' && v !== REDACTED) || (typeof v === 'number' && Number.isFinite(v));
}

/**
 * Calls fn on every secret leaf in a JSON value and returns the count. A leaf is secret when it is a non-empty
 * string or a number anywhere under a secret-looking key (at any depth, in objects and lists), or the "value" of
 * a row whose "key" or "name" is secret-looking ({"key": "Authorization", "value": ...}).
 */
function visitSecretValues(value: unknown, fn: (holder: SecretHolder, key: string | number) => void): number {
  let count = 0;
  const walk = (v: unknown, inSecret: boolean) => {
    if (Array.isArray(v)) {
      v.forEach((item, i) => {
        if (inSecret && isSecretLeaf(item)) {
          fn(v, i);
          count += 1;
        } else walk(item, inSecret);
      });
    } else if (v && typeof v === 'object') {
      const obj = v as Record<string, unknown>;
      const named = typeof obj.key === 'string' ? obj.key : typeof obj.name === 'string' ? obj.name : null;
      for (const [k, inner] of Object.entries(obj)) {
        const secret = inSecret || SECRET_KEY.test(k) || (k === 'value' && named !== null && SECRET_KEY.test(named));
        if (secret && isSecretLeaf(inner)) {
          fn(obj, k);
          count += 1;
        } else walk(inner, secret);
      }
    }
  };
  walk(value, false);
  return count;
}

function hasSecretValues(value: unknown): boolean {
  return visitSecretValues(structuredClone(value), () => {}) > 0;
}

export type LfTemplateField = JsonObject & {
  type?: string;
  value?: unknown;
  required?: boolean;
  show?: boolean;
  password?: boolean;
  options?: unknown;
  display_name?: string;
};

export type LfNode = JsonObject & {
  id: string;
  type?: string;
  position?: { x: number; y: number };
  positionAbsolute?: { x: number; y: number };
  data?: JsonObject & {
    type?: string;
    display_name?: string;
    node?: JsonObject & { template?: Record<string, unknown> };
  };
};

export type LfEdge = JsonObject & {
  id: string;
  source: string;
  target: string;
  sourceHandle: unknown;
  targetHandle: unknown;
};

export type LfFlow = JsonObject & {
  name?: unknown;
  description?: unknown;
  data: JsonObject & { nodes: LfNode[]; edges: LfEdge[] };
};

export type CanvasField = {
  name: string;
  label: string;
  fieldType: string;
  /** Primitive for text, number and choice settings; object or list for JSON settings; null when hidden or empty. */
  value: JsonValue;
  required: boolean;
  editable: boolean;
  editor: FieldEditor;
  secret: boolean;
  readOnlyReason?: string;
  /** Short stand-in shown instead of a long read-only value (for example "42 lines of Python"). */
  summary?: string;
  options: string[];
  range?: { min: number; max: number; step: number };
  /** Column names a table setting accepts. */
  columns?: string[];
  connected: boolean;
};

/** A connection point: an output (source) or an input field that accepts connections (target). */
export type CanvasPort = { name: string; label: string; types: string[]; list: boolean; loop: boolean; /** Extra types a loop's feedback point accepts. */ loopTypes?: string[] };

export type CanvasNode = {
  id: string;
  componentType: string;
  label: string;
  position: { x: number; y: number };
  isNote: boolean;
  executable: boolean;
  fields: CanvasField[];
  outputs: CanvasPort[];
  inputs: CanvasPort[];
};

export type CanvasEdge = {
  id: string;
  source: string;
  target: string;
  sourceOutput: string | null;
  targetInput: string | null;
  /** True for a loop's feedback connection: it lands on the loop's output, not on an input field. */
  targetLoop: boolean;
  sourceTypes: string[];
  targetTypes: string[];
  decodeError?: string;
};

export type Problem = {
  level: 'error' | 'warning';
  message: string;
  nodeId?: string;
  edgeId?: string;
};

export type CanvasFlow = {
  name: string;
  description: string;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
};

export type FlowEdit =
  | { kind: 'move'; nodeId: string; position: { x: number; y: number } }
  | { kind: 'setField'; nodeId: string; field: string; value: JsonValue }
  | { kind: 'rename'; nodeId: string; label: string }
  | { kind: 'addNode'; nodeId: string; componentType: string; position: { x: number; y: number } }
  | { kind: 'deleteNode'; nodeId: string }
  /** nodeId is the source component. targetLoop: connect into a loop's feedback (an output that allows loops). */
  | { kind: 'connect'; nodeId: string; sourceOutput: string; target: string; targetInput: string; targetLoop?: boolean }
  | { kind: 'disconnect'; edgeId: string };

/** The component or connection an edit is about, for messages. */
export function editSubject(edit: FlowEdit): string {
  return edit.kind === 'disconnect' ? edit.edgeId : edit.nodeId;
}

/** What applyEdits needs from the engine. Server side it is backed by catalog.ts. */
export type EditContext = {
  /** A fresh copy of the engine's node template for a current component, or null when it is not offered. */
  template?: (componentType: string) => JsonObject | null;
};

/** What executionPlan needs from the engine: the built-in code hash per component (catalog.ts builtinCodeHash). */
export type RunContext = { builtinCodeHash?: (componentType: string) => string | null };

/** Langflow's own id style for a new component: "<Type>-<5 letters or digits>". */
export function newNodeIdPattern(componentType: string): RegExp {
  return new RegExp(`^${componentType.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}-[A-Za-z0-9]{5}$`);
}

export type EditRejection = { edit: FlowEdit; reason: string };

export type ExecutionBlocker = {
  nodeId: string;
  componentType: string;
  label: string;
  reason: string;
};

export type ExecutionPlan = {
  hasChatInput: boolean;
  hasChatOutput: boolean;
  blockers: ExecutionBlocker[];
};

/** Deterministic JSON: object keys sorted at every level. */
function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((v) => stableStringify(v)).join(',')}]`;
  }
  if (value && typeof value === 'object') {
    const entries = Object.keys(value as JsonObject)
      .sort()
      .map((k) => `${JSON.stringify(k)}:${stableStringify((value as JsonObject)[k])}`);
    return `{${entries.join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}

/** Version stamp for a saved flow: changes whenever any saved byte changes. */
export function contentHash(raw: LfFlow): string {
  return createHash('sha256').update(stableStringify(raw)).digest('hex');
}

export function parseFlowInput(value: unknown): { ok: true; flow: LfFlow } | { ok: false; error: string } {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { ok: false, error: 'The file is not a Langflow flow (expected a JSON object).' };
  }
  const flow = value as LfFlow;
  const data = flow.data as unknown;
  if (!data || typeof data !== 'object' || !Array.isArray((data as JsonObject).nodes) || !Array.isArray((data as JsonObject).edges)) {
    return { ok: false, error: 'The file is not a Langflow flow (missing data.nodes or data.edges).' };
  }
  return { ok: true, flow };
}

function isNoteNode(node: LfNode): boolean {
  return node.type === 'noteNode';
}

function componentTypeOf(node: LfNode): string {
  // Only node.type decides, exactly as the engine does (lfx graph/base.py skips type == "noteNode" and builds
  // everything else). A real component whose data.type says "note" is still a component and must be gated.
  if (isNoteNode(node)) return 'note';
  return typeof node.data?.type === 'string' ? node.data.type : '';
}

function templateOf(node: LfNode): Record<string, LfTemplateField> {
  const template = node.data?.node?.template;
  return template && typeof template === 'object' ? (template as Record<string, LfTemplateField>) : {};
}

function isEmpty(value: unknown): boolean {
  if (value === undefined || value === null || value === '') return true;
  return Array.isArray(value) && value.length === 0;
}

function asPrimitive(value: unknown): string | number | boolean | null {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value;
  return null;
}

function labelOf(node: LfNode): string {
  const display = node.data?.display_name;
  if (typeof display === 'string' && display.trim()) return display;
  const fromTemplate = node.data?.node?.display_name;
  if (typeof fromTemplate === 'string' && fromTemplate.trim()) return fromTemplate;
  return componentTypeOf(node) || node.id;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function rangeOf(field: JsonObject): CanvasField['range'] {
  const r = field.range_spec;
  if (!isPlainObject(r)) return undefined;
  const min = Number(r.min);
  const max = Number(r.max);
  const step = Number(r.step);
  return Number.isFinite(min) && Number.isFinite(max) ? { min, max, step: Number.isFinite(step) && step > 0 ? step : 1 } : undefined;
}

function columnsOf(field: JsonObject): string[] | undefined {
  if (!Array.isArray(field.table_schema)) return undefined;
  const names = field.table_schema.map((c) => (isPlainObject(c) && typeof c.name === 'string' ? c.name : null)).filter((n): n is string => !!n);
  return names.length ? names : undefined;
}

function fieldsOf(node: LfNode, connected: Set<string>): CanvasField[] {
  const out: CanvasField[] = [];
  for (const [name, raw] of Object.entries(templateOf(node))) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) continue;
    const field = raw as LfTemplateField & { list?: unknown; multiline?: unknown; input_types?: unknown };
    if (field.show === false) continue;
    const fieldType = typeof field.type === 'string' ? field.type : '';
    const options = Array.isArray(field.options) ? field.options.filter((o): o is string => typeof o === 'string') : [];
    const isConnected = connected.has(`${node.id}:${name}`);
    const secret = field.password === true;
    let editor: FieldEditor = EDITOR_BY_TYPE[fieldType] ?? 'readonly';
    let readOnlyReason: string | undefined = READ_ONLY_REASON[name];
    if (!readOnlyReason && secret) {
      readOnlyReason = 'Secret. Set it in Langflow\'s native editor; the dashboard never stores secrets.';
    }
    if (!readOnlyReason && fieldType === 'str' && (field.list === true || Array.isArray(field.value))) {
      readOnlyReason = 'List setting. Edit it in Langflow\'s native editor.';
    }
    if (!readOnlyReason && editor === 'readonly') {
      readOnlyReason = READ_ONLY_BY_TYPE[fieldType]
        ?? (stringList(field.input_types).length ? 'Takes a connection. Connect a component to it on the canvas.' : 'Structured setting. Edit it in Langflow\'s native editor.');
    }
    if (readOnlyReason) editor = 'readonly';
    else if (editor === 'text' && (field.multiline === true || (typeof field.value === 'string' && field.value.includes('\n')))) editor = 'multiline';
    else if ((editor === 'text' || editor === 'select') && options.length > 0) editor = 'select';
    let value: JsonValue;
    let summary: string | undefined;
    if (secret) value = isEmpty(field.value) ? '' : REDACTED;
    else if (name === 'code' && typeof field.value === 'string') {
      value = null;
      summary = `${field.value.split('\n').length} lines of Python`;
    } else if (editor === 'json' || (editor === 'readonly' && (Array.isArray(field.value) || isPlainObject(field.value)))) {
      value = structuredClone(field.value ?? null) as JsonValue;
      visitSecretValues(value, (holder, key) => { (holder as Record<string | number, unknown>)[key] = REDACTED; });
    } else value = asPrimitive(field.value);
    out.push({
      name,
      label: typeof field.display_name === 'string' && field.display_name ? field.display_name : name,
      fieldType,
      value,
      required: field.required === true,
      editable: !readOnlyReason,
      editor,
      secret,
      readOnlyReason,
      ...(summary ? { summary } : {}),
      options,
      ...(fieldType === 'slider' ? { range: rangeOf(field) } : {}),
      ...(fieldType === 'table' ? { columns: columnsOf(field) } : {}),
      connected: isConnected,
    });
  }
  return out;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];
}

type LfOutput = JsonObject & { name?: unknown; display_name?: unknown; types?: unknown; selected?: unknown; allows_loop?: unknown; loop_types?: unknown; hidden?: unknown };

function outputsOf(node: LfNode): LfOutput[] {
  const outputs = node.data?.node?.outputs;
  return Array.isArray(outputs) ? outputs.filter((o): o is LfOutput => !!o && typeof o === 'object' && typeof (o as LfOutput).name === 'string') : [];
}

function portsOf(node: LfNode): { outputs: CanvasPort[]; inputs: CanvasPort[] } {
  const outputs: CanvasPort[] = outputsOf(node)
    .filter((o) => o.hidden !== true)
    .map((o) => ({
      name: String(o.name),
      label: typeof o.display_name === 'string' ? o.display_name : String(o.name),
      types: stringList(o.types),
      list: false,
      loop: o.allows_loop === true,
      ...(o.allows_loop === true ? { loopTypes: stringList(o.loop_types) } : {}),
    }));
  const inputs: CanvasPort[] = [];
  for (const [name, raw] of Object.entries(templateOf(node))) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) continue;
    const f = raw as LfTemplateField & { input_types?: unknown; list?: unknown };
    const types = stringList(f.input_types);
    if (f.show === false || types.length === 0) continue;
    inputs.push({ name, label: typeof f.display_name === 'string' && f.display_name ? f.display_name : name, types, list: f.list === true, loop: false });
  }
  return { outputs, inputs };
}

function connectedInputs(raw: LfFlow): Set<string> {
  const set = new Set<string>();
  for (const edge of raw.data.edges) {
    try {
      const target = decodeHandle(edge.targetHandle);
      if (typeof target.fieldName === 'string') set.add(`${edge.target}:${target.fieldName}`);
    } catch {
      // reported by validateFlow
    }
  }
  return set;
}

export function toCanvas(raw: LfFlow): CanvasFlow {
  const connected = connectedInputs(raw);
  const nodes: CanvasNode[] = raw.data.nodes.map((node) => {
    const componentType = componentTypeOf(node);
    const isNote = isNoteNode(node);
    const position = node.position ?? node.positionAbsolute ?? { x: 0, y: 0 };
    return {
      id: String(node.id),
      componentType,
      label: labelOf(node),
      position: { x: Number(position.x) || 0, y: Number(position.y) || 0 },
      isNote,
      executable: (EXECUTABLE_COMPONENTS as readonly string[]).includes(componentType),
      fields: isNote ? [] : fieldsOf(node, connected),
      ...(isNote ? { outputs: [], inputs: [] } : portsOf(node)),
    };
  });
  const edges: CanvasEdge[] = raw.data.edges.map((edge) => {
    const base = {
      id: String(edge.id),
      source: String(edge.source),
      target: String(edge.target),
      sourceOutput: null as string | null,
      targetInput: null as string | null,
      targetLoop: false,
      sourceTypes: [] as string[],
      targetTypes: [] as string[],
    };
    try {
      const s = decodeHandle(edge.sourceHandle);
      const t = decodeHandle(edge.targetHandle);
      base.sourceOutput = typeof s.name === 'string' ? s.name : null;
      base.sourceTypes = Array.isArray(s.output_types) ? s.output_types.filter((x): x is string => typeof x === 'string') : [];
      if (typeof t.fieldName === 'string') {
        base.targetInput = t.fieldName;
        base.targetTypes = stringList(t.inputTypes);
      } else if (typeof t.name === 'string') {
        base.targetInput = t.name;
        base.targetLoop = true;
        base.targetTypes = stringList(t.output_types);
      }
    } catch (err) {
      return { ...base, decodeError: err instanceof HandleDecodeError ? err.message : 'handle could not be read' };
    }
    return base;
  });
  return {
    name: typeof raw.name === 'string' ? raw.name : 'Untitled flow',
    description: typeof raw.description === 'string' ? raw.description : '',
    nodes,
    edges,
  };
}

function findNode(raw: LfFlow, id: string): LfNode | undefined {
  return raw.data.nodes.find((n) => String(n.id) === id);
}

function coerce(field: CanvasField, value: JsonValue): { ok: true; value: JsonValue } | { ok: false; reason: string } {
  if (field.editor === 'json') {
    if (hasSecretValues(value)) {
      return { ok: false, reason: `"${field.label}" holds a value under a secret-looking name (token, key, password, authorization). The dashboard never stores secrets: set it in Langflow's native editor.` };
    }
    if (field.fieldType === 'table') {
      if (!Array.isArray(value) || !value.every((row) => isPlainObject(row))) return { ok: false, reason: `"${field.label}" takes a list of rows, like [{"name": "value"}].` };
      if (field.columns) {
        const unknown = value.flatMap((row) => Object.keys(row as object)).filter((k) => !field.columns!.includes(k));
        if (unknown.length) return { ok: false, reason: `"${field.label}" has no column named ${[...new Set(unknown)].map((k) => `"${k}"`).join(', ')}. Columns: ${field.columns.join(', ')}.` };
      }
      return { ok: true, value };
    }
    if (!isPlainObject(value)) return { ok: false, reason: `"${field.label}" takes a JSON object, like {"key": "value"}.` };
    return { ok: true, value };
  }
  if (typeof value === 'object' && value !== null) return { ok: false, reason: `"${field.label}" takes a single value, not a list or object.` };
  if (value === null) return { ok: false, reason: `"${field.label}" needs a value.` };
  const NUMERIC = /^\s*-?(\d+\.?\d*|\.\d+)\s*$/;
  const isNumberField = field.fieldType === 'slider' || field.fieldType === 'int' || field.fieldType === 'float';
  // An optional number may be left empty, the way Langflow stores it (""). A required one may not.
  if (isNumberField && typeof value === 'string' && value.trim() === '' && !field.required) return { ok: true, value: '' };
  if (isNumberField && (typeof value === 'boolean' || (typeof value === 'string' && !NUMERIC.test(value)))) {
    return { ok: false, reason: `"${field.label}" takes a ${field.fieldType === 'int' ? 'whole number' : 'number'}.` };
  }
  if (field.fieldType === 'slider') {
    const n = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(n)) return { ok: false, reason: `"${field.label}" takes a number.` };
    if (field.range && (n < field.range.min || n > field.range.max)) return { ok: false, reason: `"${field.label}" takes a number from ${field.range.min} to ${field.range.max}.` };
    return { ok: true, value: n };
  }
  if (field.fieldType === 'bool') {
    if (typeof value === 'boolean') return { ok: true, value };
    if (value === 'true' || value === 'false') return { ok: true, value: value === 'true' };
    return { ok: false, reason: `"${field.label}" takes true or false.` };
  }
  if (field.fieldType === 'int' || field.fieldType === 'float') {
    const n = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(n) || (field.fieldType === 'int' && !Number.isInteger(n))) {
      return { ok: false, reason: `"${field.label}" takes a ${field.fieldType === 'int' ? 'whole number' : 'number'}.` };
    }
    return { ok: true, value: n };
  }
  return { ok: true, value: String(value) };
}

/** Applies supported edits to a copy of the flow. Unknown fields and metadata pass through untouched. */
export function applyEdits(raw: LfFlow, edits: FlowEdit[], ctx: EditContext = {}): { flow: LfFlow; applied: number; rejected: EditRejection[] } {
  const flow = structuredClone(raw) as LfFlow;
  const rejected: EditRejection[] = [];
  let applied = 0;
  for (const edit of edits) {
    if (edit.kind === 'addNode' || edit.kind === 'deleteNode' || edit.kind === 'connect' || edit.kind === 'disconnect') {
      const reason =
        edit.kind === 'addNode' ? addNode(flow, edit, ctx)
          : edit.kind === 'deleteNode' ? deleteNode(flow, edit)
            : edit.kind === 'connect' ? connect(flow, edit)
              : disconnect(flow, edit);
      if (reason) rejected.push({ edit, reason });
      else applied += 1;
      continue;
    }
    const node = findNode(flow, edit.nodeId);
    if (!node) {
      rejected.push({ edit, reason: `No component with id "${edit.nodeId}" in this flow.` });
      continue;
    }
    const label = labelOf(node);
    if (edit.kind === 'move') {
      const { x, y } = edit.position;
      if (!Number.isFinite(x) || !Number.isFinite(y)) {
        rejected.push({ edit, reason: `Position for "${label}" must be finite numbers.` });
        continue;
      }
      node.position = { x, y };
      if (node.positionAbsolute) node.positionAbsolute = { x, y };
      applied += 1;
      continue;
    }
    if (edit.kind === 'rename') {
      const text = edit.label.trim();
      if (!text || text.length > 80) {
        rejected.push({ edit, reason: 'A component name must be 1 to 80 characters.' });
        continue;
      }
      node.data = { ...(node.data ?? {}), display_name: text };
      applied += 1;
      continue;
    }
    // setField
    const template = templateOf(node);
    const rawField = template[edit.field];
    if (!rawField || typeof rawField !== 'object') {
      rejected.push({ edit, reason: `"${label}" has no setting named "${edit.field}".` });
      continue;
    }
    const field = fieldsOf(node, new Set()).find((f) => f.name === edit.field);
    if (!field) {
      rejected.push({ edit, reason: `"${label}" setting "${edit.field}" is hidden in this Langflow version.` });
      continue;
    }
    if (!field.editable) {
      rejected.push({ edit, reason: `"${label}" → "${field.label}": ${field.readOnlyReason}` });
      continue;
    }
    // "No value" sent back for a setting that has no value is no change at all (nothing is written).
    if (edit.value === null && ((rawField as LfTemplateField).value === undefined || (rawField as LfTemplateField).value === null)) {
      applied += 1;
      continue;
    }
    if (typeof edit.value === 'string' && edit.value === REDACTED) {
      rejected.push({ edit, reason: `"${field.label}" was not changed (the placeholder cannot be saved back).` });
      continue;
    }
    const result = coerce(field, edit.value);
    if (!result.ok) {
      rejected.push({ edit, reason: `"${label}" → ${result.reason}` });
      continue;
    }
    if (field.options.length > 0 && typeof result.value === 'string' && !field.options.includes(result.value)) {
      rejected.push({ edit, reason: `"${field.label}" must be one of: ${field.options.join(', ')}.` });
      continue;
    }
    const promptField = Object.entries(template).find(([, f]) => (f as LfTemplateField | undefined)?.type === 'prompt');
    if (edit.field === 'use_double_brackets' && promptField && typeof (promptField[1] as LfTemplateField).value === 'string') {
      (rawField as LfTemplateField).value = result.value;
      const sync = syncPromptVariables(flow, node, (promptField[1] as LfTemplateField).value as string);
      if (sync) {
        (rawField as LfTemplateField).value = (field.value as JsonValue);
        rejected.push({ edit, reason: `"${label}" → ${sync}` });
        continue;
      }
    }
    if (field.fieldType === 'prompt' && typeof result.value === 'string') {
      const sync = syncPromptVariables(flow, node, result.value);
      if (sync) {
        rejected.push({ edit, reason: `"${label}" → ${sync}` });
        continue;
      }
    }
    (rawField as LfTemplateField).value = result.value;
    applied += 1;
  }
  return { flow, applied, rejected };
}

const VARIABLE_NAME = /^[A-Za-z_][A-Za-z0-9_]*$/;
const MAX_PROMPT_CHARS = 50_000;
const MAX_PROMPT_VARIABLES = 100;

/** The {variables} of a prompt, in order (or {{variables}} when the component uses double brackets). */
export function promptVariables(text: string, doubleBrackets = false): string[] {
  const pattern = doubleBrackets ? /\{\{([^{}]+)\}\}/g : /(?<!\{)\{([^{}]+)\}(?!\})/g;
  const out = new Set<string>();
  for (const m of text.matchAll(pattern)) out.add(m[1].trim());
  return [...out];
}

/**
 * Langflow gives each {variable} of a prompt its own text input that takes a Message, and lists them in
 * custom_fields.template. Its server does this when the prompt is edited; the dashboard does the same so the
 * engine can fill the prompt. Returns a reason when the edit must be refused.
 */
function syncPromptVariables(flow: LfFlow, node: LfNode, text: string): string | null {
  const template = templateOf(node);
  const double = (template.use_double_brackets as LfTemplateField | undefined)?.value === true;
  if (text.length > MAX_PROMPT_CHARS) return `the prompt is longer than ${MAX_PROMPT_CHARS} characters.`;
  const wanted = promptVariables(text, double);
  if (wanted.length > MAX_PROMPT_VARIABLES) return `the prompt has more than ${MAX_PROMPT_VARIABLES} {variables}.`;
  const bad = wanted.find((v) => !VARIABLE_NAME.test(v));
  if (bad) return `"{${bad}}" is not a usable variable name: use letters, digits and _ only.`;
  const nodeData = node.data!.node!;
  const custom = isPlainObject(nodeData.custom_fields) ? (nodeData.custom_fields as Record<string, unknown>) : {};
  const previous = stringList(custom.template);
  for (const v of wanted) {
    if (!previous.includes(v) && template[v] !== undefined) return `"{${v}}" clashes with the existing setting "${v}". Pick another name.`;
  }
  if (wanted.length === previous.length && wanted.every((v, i) => v === previous[i])) return null;
  const removed = previous.filter((v) => !wanted.includes(v));
  const connected = connectedInputs(flow);
  const stillWired = removed.find((v) => connected.has(`${String(node.id)}:${v}`));
  if (stillWired) return `"{${stillWired}}" is still connected. Disconnect it before removing it from the prompt.`;
  for (const v of removed) delete template[v];
  for (const v of wanted) {
    if (template[v] !== undefined) continue;
    template[v] = {
      _input_type: 'MessageTextInput', advanced: false, display_name: v, dynamic: false, field_type: 'str', fileTypes: [],
      file_path: '', info: '', input_types: ['Message'], list: false, load_from_db: false, multiline: true, name: v,
      placeholder: '', required: false, show: true, title_case: false, type: 'str', value: '',
    };
  }
  nodeData.custom_fields = { ...custom, template: wanted };
  if (Array.isArray(nodeData.field_order)) {
    nodeData.field_order = [...(nodeData.field_order as unknown[]).filter((f) => typeof f !== 'string' || !removed.includes(f)), ...wanted.filter((v) => !(nodeData.field_order as unknown[]).includes(v))];
  }
  return null;
}

function addNode(flow: LfFlow, edit: Extract<FlowEdit, { kind: 'addNode' }>, ctx: EditContext): string | null {
  const { x, y } = edit.position;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return 'A new component needs a finite position.';
  const template = ctx.template?.(edit.componentType) ?? null;
  if (!template) return `"${edit.componentType}" is not a current component of the installed engine, so it cannot be added.`;
  if (!newNodeIdPattern(edit.componentType).test(edit.nodeId)) {
    return `The new component id must look like "${edit.componentType}-" plus 5 letters or digits.`;
  }
  if (findNode(flow, edit.nodeId)) return `The id "${edit.nodeId}" is already used in this flow.`;
  flow.data.nodes.push({
    id: edit.nodeId,
    type: 'genericNode',
    position: { x, y },
    data: { id: edit.nodeId, type: edit.componentType, node: template, showNode: template.minimized !== true },
  });
  return null;
}

function deleteNode(flow: LfFlow, edit: Extract<FlowEdit, { kind: 'deleteNode' }>): string | null {
  const node = findNode(flow, edit.nodeId);
  if (!node) return `No component with id "${edit.nodeId}" in this flow.`;
  flow.data.nodes = flow.data.nodes.filter((n) => n !== node);
  flow.data.edges = flow.data.edges.filter((e) => String(e.source) !== edit.nodeId && String(e.target) !== edit.nodeId);
  return null;
}

function disconnect(flow: LfFlow, edit: Extract<FlowEdit, { kind: 'disconnect' }>): string | null {
  const before = flow.data.edges.length;
  flow.data.edges = flow.data.edges.filter((e) => String(e.id) !== edit.edgeId);
  return flow.data.edges.length === before ? 'That connection is not in this flow.' : null;
}

/** A loop's feedback connection lands on the loop's output handle (no fieldName). It is not a cycle. */
function isFeedbackEdge(edge: LfEdge): boolean {
  try {
    const t = decodeHandle(edge.targetHandle);
    return typeof t.fieldName !== 'string' && typeof t.name === 'string';
  } catch {
    return false;
  }
}

function reaches(flow: LfFlow, from: string, to: string): boolean {
  const next = new Map<string, string[]>();
  for (const e of flow.data.edges) {
    if (isFeedbackEdge(e)) continue;
    next.set(String(e.source), [...(next.get(String(e.source)) ?? []), String(e.target)]);
  }
  const seen = new Set<string>();
  const stack = [from];
  while (stack.length) {
    const id = stack.pop()!;
    if (id === to) return true;
    if (seen.has(id)) continue;
    seen.add(id);
    stack.push(...(next.get(id) ?? []));
  }
  return false;
}

function connect(flow: LfFlow, edit: Extract<FlowEdit, { kind: 'connect' }>): string | null {
  const source = findNode(flow, edit.nodeId);
  const target = findNode(flow, edit.target);
  if (!source) return `No component with id "${edit.nodeId}" in this flow.`;
  if (!target) return `No component with id "${edit.target}" in this flow.`;
  if (source === target) return 'A component cannot connect to itself.';
  if (isNoteNode(source) || isNoteNode(target)) return 'Notes cannot be connected.';
  const sLabel = labelOf(source);
  const tLabel = labelOf(target);
  const output = outputsOf(source).find((o) => o.name === edit.sourceOutput && o.hidden !== true);
  if (!output) return `"${sLabel}" has no output named "${edit.sourceOutput}".`;
  const sendTypes = stringList(output.types);
  const selected = typeof output.selected === 'string' && output.selected ? output.selected : null;
  const outputTypes = selected ? [selected] : sendTypes;
  const sendAll = Array.from(new Set([...sendTypes, ...outputTypes]));
  const sourceHandle: HandleObject = { dataType: componentTypeOf(source), id: String(source.id), name: String(output.name), output_types: outputTypes };

  let targetHandle: HandleObject;
  let accepts: string[];
  let multiple = false;
  if (edit.targetLoop) {
    const loopOut = outputsOf(target).find((o) => o.name === edit.targetInput && o.allows_loop === true);
    if (!loopOut) return `"${tLabel}" has no loop output named "${edit.targetInput}".`;
    const loopSelected = typeof loopOut.selected === 'string' && loopOut.selected ? [loopOut.selected] : stringList(loopOut.types);
    targetHandle = { dataType: componentTypeOf(target), id: String(target.id), name: String(loopOut.name), output_types: loopSelected };
    accepts = Array.from(new Set([...stringList(loopOut.types), ...stringList(loopOut.loop_types)]));
  } else {
    const field = templateOf(target)[edit.targetInput] as (LfTemplateField & { input_types?: unknown; list?: unknown }) | undefined;
    if (!field || typeof field !== 'object' || field.show === false) return `"${tLabel}" has no input named "${edit.targetInput}".`;
    accepts = stringList(field.input_types);
    if (accepts.length === 0) return `"${tLabel}" → "${field.display_name ?? edit.targetInput}" is a setting, not an input that takes a connection.`;
    multiple = field.list === true;
    targetHandle = { fieldName: edit.targetInput, id: String(target.id), inputTypes: accepts, type: typeof field.type === 'string' ? field.type : 'str' };
    if (typeof field.type === 'string') accepts = [...accepts, field.type];
  }
  const compatible = accepts.includes('Any') || sendAll.some((t) => accepts.includes(t));
  if (!compatible) {
    return `Types do not match: "${sLabel}" → "${String(output.name)}" sends ${sendAll.join(' or ') || 'nothing typed'}, but "${tLabel}" → "${edit.targetInput}" takes ${accepts.join(' or ')}.`;
  }
  const sh = encodeHandle(sourceHandle);
  const th = encodeHandle(targetHandle);
  const incoming = flow.data.edges.filter((e) => {
    if (String(e.target) !== String(target.id)) return false;
    try {
      const t = decodeHandle(e.targetHandle);
      return edit.targetLoop ? t.name === edit.targetInput && t.fieldName === undefined : t.fieldName === edit.targetInput;
    } catch {
      return false;
    }
  });
  if (incoming.some((e) => String(e.source) === String(source.id) && e.sourceHandle === sh)) return 'That connection already exists.';
  if (incoming.length > 0 && !multiple && !edit.targetLoop) {
    return `"${tLabel}" → "${edit.targetInput}" already has a connection and takes only one. Disconnect it first.`;
  }
  if (!edit.targetLoop && reaches(flow, String(target.id), String(source.id))) {
    return 'That connection would make the flow loop back on itself. Only a Loop component may feed back.';
  }
  flow.data.edges.push({
    id: `xy-edge__${String(source.id)}${sh}-${String(target.id)}${th}`,
    source: String(source.id),
    target: String(target.id),
    sourceHandle: sh,
    targetHandle: th,
    data: { sourceHandle, targetHandle },
    animated: false,
    className: '',
    selected: false,
  });
  return null;
}

export function validateFlow(raw: LfFlow): Problem[] {
  const problems: Problem[] = [];
  if (typeof raw.id !== 'string' || !raw.id) {
    problems.push({ level: 'warning', message: "The flow has no top-level id, so Langflow's own validator will refuse it. Export it from Langflow again to get one." });
  }
  const ids = new Set<string>();
  for (const node of raw.data.nodes) {
    const id = typeof node.id === 'string' ? node.id : '';
    if (!id) {
      problems.push({ level: 'error', message: 'A component has no id.' });
      continue;
    }
    if (ids.has(id)) problems.push({ level: 'error', message: `Two components share the id "${id}".`, nodeId: id });
    ids.add(id);
    if (!componentTypeOf(node)) {
      problems.push({ level: 'error', message: `"${id}" has no component type, so it cannot run or be checked.`, nodeId: id });
    }
  }
  const connectedNodes = new Set<string>();
  const adjacency = new Map<string, string[]>();
  for (const edge of raw.data.edges) {
    const edgeId = String(edge.id);
    const sourceOk = ids.has(String(edge.source));
    const targetOk = ids.has(String(edge.target));
    if (!sourceOk || !targetOk) {
      problems.push({ level: 'error', edgeId, message: 'A connection points at a component that is not in this flow.' });
      continue;
    }
    connectedNodes.add(String(edge.source));
    connectedNodes.add(String(edge.target));
    if (!isFeedbackEdge(edge)) {
      const list = adjacency.get(String(edge.source)) ?? [];
      list.push(String(edge.target));
      adjacency.set(String(edge.source), list);
    }
    try {
      const s = decodeHandle(edge.sourceHandle);
      const t = decodeHandle(edge.targetHandle);
      const sourceTypes = Array.isArray(s.output_types) ? (s.output_types as unknown[]).map(String) : [];
      const targetTypes = Array.isArray(t.inputTypes) ? (t.inputTypes as unknown[]).map(String) : [];
      const compatible = targetTypes.includes('Any') || sourceTypes.some((x) => targetTypes.includes(x));
      if (!compatible && sourceTypes.length && targetTypes.length) {
        problems.push({
          level: 'warning',
          edgeId,
          message: `Type may not match: "${String(s.name)}" sends ${sourceTypes.join(' or ')}, but "${String(t.fieldName)}" expects ${targetTypes.join(' or ')}.`,
        });
      }
    } catch (err) {
      problems.push({
        level: 'error',
        edgeId,
        message: err instanceof HandleDecodeError ? `Connection data is unreadable: ${err.message}.` : 'Connection data is unreadable.',
      });
    }
  }
  const connected = connectedInputs(raw);
  for (const node of raw.data.nodes) {
    const id = String(node.id);
    if (isNoteNode(node)) continue;
    if (node.data?.type === 'note') {
      problems.push({ level: 'error', nodeId: id, message: `"${id}" is labelled as a note but is a real component that the engine would run. Remove it, or export the flow from Langflow again.` });
    }
    const label = labelOf(node);
    for (const field of fieldsOf(node, connected)) {
      if (field.required && !field.connected && field.name !== 'code' && isEmpty(field.value)) {
        problems.push({ level: 'error', nodeId: id, message: `"${label}": setting "${field.label}" is required but empty.` });
      }
    }
    if (!connectedNodes.has(id)) {
      problems.push({ level: 'warning', nodeId: id, message: `"${label}" is not connected to anything.` });
    }
  }
  if (hasCycle(adjacency)) {
    problems.push({ level: 'warning', message: 'The flow loops back on itself. Check that the loop has a stop condition.' });
  }
  return problems;
}

export function problemsHaveErrors(problems: Problem[]): boolean {
  return problems.some((p) => p.level === 'error');
}

function hasCycle(adjacency: Map<string, string[]>): boolean {
  const state = new Map<string, 'visiting' | 'done'>();
  const visit = (node: string): boolean => {
    const s = state.get(node);
    if (s === 'visiting') return true;
    if (s === 'done') return false;
    state.set(node, 'visiting');
    for (const next of adjacency.get(node) ?? []) {
      if (visit(next)) return true;
    }
    state.set(node, 'done');
    return false;
  };
  for (const node of adjacency.keys()) {
    if (visit(node)) return true;
  }
  return false;
}

function nodeCodeHash(node: LfNode): string | null {
  const code = (templateOf(node).code as LfTemplateField | undefined)?.value;
  return typeof code === 'string' ? createHash('sha256').update(code).digest('hex') : null;
}

/**
 * What a dashboard run would execute, and what blocks it. A component runs only when its type is enabled
 * AND its code is byte-identical (full sha256) to the installed engine's built-in component: the engine runs the code
 * in the file, so a renamed or edited component must never pass as an enabled one.
 */
export function executionPlan(raw: LfFlow, ctx: RunContext = {}): ExecutionPlan {
  const blockers: ExecutionBlocker[] = [];
  let hasChatInput = false;
  let hasChatOutput = false;
  for (const node of raw.data.nodes) {
    const componentType = componentTypeOf(node);
    if (isNoteNode(node)) continue;
    if (componentType === 'ChatInput') hasChatInput = true;
    if (componentType === 'ChatOutput') hasChatOutput = true;
    const label = labelOf(node);
    const block = (reason: string) => blockers.push({ nodeId: String(node.id), componentType: componentType || 'unknown', label, reason });
    if (!(EXECUTABLE_COMPONENTS as readonly string[]).includes(componentType)) {
      block(runBlockReason(componentType, label) ?? `"${label}" does not run here.`);
      continue;
    }
    const builtin = ctx.builtinCodeHash?.(componentType) ?? null;
    if (!builtin) {
      block(`"${label}" cannot be checked against the installed engine's built-in component, so it does not run.`);
    } else if (nodeCodeHash(node) !== builtin) {
      block(`"${label}" has code that differs from the installed engine's built-in ${componentType}. Edited or older component code does not run here. Add it again from the palette to get the engine's version.`);
    }
  }
  return { hasChatInput, hasChatOutput, blockers };
}

/** Import copy: secret values are emptied so the dashboard never stores them. The count is reported to the user. */
export function stripSecretsForImport(raw: LfFlow): { flow: LfFlow; removed: number } {
  const flow = structuredClone(raw) as LfFlow;
  let removed = 0;
  for (const node of flow.data.nodes) {
    for (const field of Object.values(templateOf(node))) {
      if (field && typeof field === 'object' && (field as LfTemplateField).password === true && !isEmpty((field as LfTemplateField).value)) {
        (field as LfTemplateField).value = '';
        removed += 1;
      } else if (field && typeof field === 'object') {
        removed += visitSecretValues((field as LfTemplateField).value, (holder, key) => { (holder as Record<string | number, unknown>)[key] = ''; });
      }
    }
  }
  return { flow, removed };
}

/** Copy for export or display: every secret value is replaced by the placeholder. */
export function redactForExport(raw: LfFlow): { flow: LfFlow; redacted: number } {
  const flow = structuredClone(raw) as LfFlow;
  let redacted = 0;
  for (const node of flow.data.nodes) {
    for (const field of Object.values(templateOf(node))) {
      if (field && typeof field === 'object' && (field as LfTemplateField).password === true && !isEmpty((field as LfTemplateField).value)) {
        (field as LfTemplateField).value = REDACTED;
        redacted += 1;
      } else if (field && typeof field === 'object') {
        redacted += visitSecretValues((field as LfTemplateField).value, (holder, key) => { (holder as Record<string | number, unknown>)[key] = REDACTED; });
      }
    }
  }
  return { flow, redacted };
}
