// Saved flows: one folder of Langflow flow JSON files. This is the single source of truth the
// dashboard saves to and runs from. Every save first copies the previous version into history/,
// so a bad save can be rolled back by copying a history file back over the flow file.

import { randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

import { localDataDir } from '../server/paths';
import { contentHash, type LfFlow } from './model';

export const FLOW_ID_PATTERN = /^[A-Za-z0-9-]{8,80}$/;
const HISTORY_KEEP = 50;

export class StoreConflictError extends Error {
  readonly currentHash: string | null;

  constructor(currentHash: string | null) {
    super('This flow changed since you opened it. Reload it, then apply your edits again.');
    this.name = 'StoreConflictError';
    this.currentHash = currentHash;
  }
}

export type StoredFlow = { id: string; flow: LfFlow; hash: string; updatedAt: string };

export type FlowSummary = { id: string; name: string; nodeCount: number; hash: string; updatedAt: string };

function rootDir(root?: string): string {
  return root ?? localDataDir();
}

export function flowsDir(root?: string): string {
  return path.join(rootDir(root), 'langflow', 'flows');
}

function historyDir(id: string, root?: string): string {
  return path.join(rootDir(root), 'langflow', 'history', id);
}

export function isValidFlowId(id: string): boolean {
  return FLOW_ID_PATTERN.test(id);
}

function flowFile(id: string, root?: string): string {
  if (!isValidFlowId(id)) throw new Error('invalid flow id');
  return path.join(flowsDir(root), `${id}.json`);
}

function writeAtomic(file: string, text: string): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.${randomUUID()}.tmp`;
  fs.writeFileSync(tmp, text, { mode: 0o600 });
  fs.renameSync(tmp, file);
}

function pruneHistory(id: string, root?: string): void {
  const dir = historyDir(id, root);
  if (!fs.existsSync(dir)) return;
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json')).sort();
  for (const old of files.slice(0, Math.max(0, files.length - HISTORY_KEEP))) {
    fs.unlinkSync(path.join(dir, old));
  }
}

export function listFlows(root?: string): FlowSummary[] {
  const dir = flowsDir(root);
  if (!fs.existsSync(dir)) return [];
  const out: FlowSummary[] = [];
  for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.json'))) {
    const id = file.slice(0, -'.json'.length);
    if (!isValidFlowId(id)) continue;
    const stored = readFlow(id, root);
    if (!stored) continue;
    out.push({
      id,
      name: typeof stored.flow.name === 'string' ? stored.flow.name : 'Untitled flow',
      nodeCount: stored.flow.data.nodes.length,
      hash: stored.hash,
      updatedAt: stored.updatedAt,
    });
  }
  return out.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function readFlow(id: string, root?: string): StoredFlow | null {
  let file: string;
  try {
    file = flowFile(id, root);
  } catch {
    return null;
  }
  if (!fs.existsSync(file)) return null;
  const flow = JSON.parse(fs.readFileSync(file, 'utf8')) as LfFlow;
  return { id, flow, hash: contentHash(flow), updatedAt: fs.statSync(file).mtime.toISOString() };
}

/** Saves a flow. `expectedHash` must match the stored version, or the save is refused. */
export function saveFlow(id: string, flow: LfFlow, expectedHash: string, root?: string): StoredFlow {
  const current = readFlow(id, root);
  if (!current) throw new Error('flow not found');
  if (current.hash !== expectedHash) throw new StoreConflictError(current.hash);
  const dir = historyDir(id, root);
  fs.mkdirSync(dir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  fs.writeFileSync(path.join(dir, `${stamp}-${current.hash.slice(0, 12)}.json`), JSON.stringify(current.flow, null, 2) + '\n', { mode: 0o600 });
  pruneHistory(id, root);
  writeAtomic(flowFile(id, root), JSON.stringify(flow, null, 2) + '\n');
  return { id, flow, hash: contentHash(flow), updatedAt: new Date().toISOString() };
}

/** Creates a new flow with a fresh id. Never overwrites an existing flow. */
export function createFlow(flow: LfFlow, root?: string): StoredFlow {
  const id = randomUUID();
  writeAtomic(flowFile(id, root), JSON.stringify(flow, null, 2) + '\n');
  return { id, flow, hash: contentHash(flow), updatedAt: new Date().toISOString() };
}

export function listHistory(id: string, root?: string): string[] {
  if (!isValidFlowId(id)) return [];
  const dir = historyDir(id, root);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith('.json')).sort();
}

export function flowFilePath(id: string, root?: string): string {
  return flowFile(id, root);
}
