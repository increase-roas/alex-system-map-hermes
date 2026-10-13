// Component catalog: read from the installed engine's own component index, never invented.
//
// Source: <venv>/lib/python3.*/site-packages/lfx/_assets/component_index.json, found next to the
// configured LANGFLOW_LFX_BIN (LANGFLOW_COMPONENT_INDEX overrides the path, used by tests).
// Legacy components are left out. The parsed index is cached per file path, size and modified time,
// so a new engine version is picked up without a restart.
// Server only: reads files. Nothing here returns a filesystem path to a caller.

import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

import type { JsonObject } from './model';
import type { RunnerConfig } from './runner';
import { isExecutable, LOCAL_NOT_ENABLED, tierOf, TIER_LABEL, type RunTier } from './tiers';

export type CatalogPort = { name: string; label: string; types: string[]; list: boolean; loop: boolean };

export type CatalogComponent = {
  type: string;
  displayName: string;
  category: string;
  description: string;
  icon: string;
  beta: boolean;
  tier: RunTier;
  tierLabel: string;
  runs: boolean;
  runNote: string | null;
  outputs: CatalogPort[];
  inputs: CatalogPort[];
};

export type EngineInfo = { lfxVersion: string; langflowVersion: string | null; indexSha256: string };

export type Catalog = {
  engine: EngineInfo;
  totalInIndex: number;
  legacyCount: number;
  components: CatalogComponent[];
};

export type CatalogResult = { ok: true; catalog: Catalog } | { ok: false; reason: string };

type IndexEntry = JsonObject & {
  display_name?: unknown;
  description?: unknown;
  icon?: unknown;
  beta?: unknown;
  legacy?: unknown;
  outputs?: unknown;
  template?: Record<string, unknown>;
  metadata?: JsonObject;
};

type Loaded = {
  key: string;
  catalog: Catalog;
  entries: Map<string, IndexEntry>;
};

let cache: Loaded | null = null;

function sitePackagesFor(lfxBin: string): string | null {
  const libDir = path.join(path.dirname(lfxBin), '..', 'lib');
  let pythons: string[];
  try {
    pythons = fs.readdirSync(libDir).filter((d) => d.startsWith('python3'));
  } catch {
    return null;
  }
  for (const py of pythons.sort().reverse()) {
    const sp = path.join(libDir, py, 'site-packages');
    if (fs.existsSync(path.join(sp, 'lfx'))) return sp;
  }
  return null;
}

/** Where the engine's component index lives, or null when it cannot be found. */
export function componentIndexPath(config: RunnerConfig, env: NodeJS.ProcessEnv = process.env): string | null {
  if (env.LANGFLOW_COMPONENT_INDEX) return path.resolve(env.LANGFLOW_COMPONENT_INDEX);
  if (!config.lfxBin) return null;
  const sp = sitePackagesFor(config.lfxBin);
  return sp ? path.join(sp, 'lfx', '_assets', 'component_index.json') : null;
}

function langflowVersionNear(indexPath: string): string | null {
  // site-packages/lfx/_assets/component_index.json -> site-packages
  const sp = path.resolve(path.dirname(indexPath), '..', '..');
  try {
    const dist = fs.readdirSync(sp).find((d) => /^langflow-\d[^/]*\.dist-info$/.test(d));
    return dist ? dist.slice('langflow-'.length, -'.dist-info'.length) : null;
  } catch {
    return null;
  }
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];
}

function portsOf(entry: IndexEntry): { outputs: CatalogPort[]; inputs: CatalogPort[] } {
  const outputs: CatalogPort[] = [];
  for (const raw of Array.isArray(entry.outputs) ? entry.outputs : []) {
    if (!raw || typeof raw !== 'object') continue;
    const o = raw as JsonObject;
    if (typeof o.name !== 'string') continue;
    outputs.push({
      name: o.name,
      label: typeof o.display_name === 'string' ? o.display_name : o.name,
      types: stringList(o.types),
      list: false,
      loop: o.allows_loop === true,
    });
  }
  const inputs: CatalogPort[] = [];
  for (const [name, raw] of Object.entries(entry.template ?? {})) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) continue;
    const f = raw as JsonObject;
    const types = stringList(f.input_types);
    if (f.show === false || types.length === 0) continue;
    inputs.push({ name, label: typeof f.display_name === 'string' ? f.display_name : name, types, list: f.list === true, loop: false });
  }
  return { outputs, inputs };
}

function summarize(type: string, category: string, entry: IndexEntry): CatalogComponent {
  const tier = tierOf(type);
  const runs = isExecutable(type);
  return {
    type,
    displayName: typeof entry.display_name === 'string' ? entry.display_name : type,
    category,
    description: typeof entry.description === 'string' ? entry.description : '',
    icon: typeof entry.icon === 'string' ? entry.icon : '',
    beta: entry.beta === true,
    tier,
    tierLabel: runs ? 'Runs here' : tier === 'local' ? 'Local: not enabled' : TIER_LABEL[tier],
    runNote: runs ? null : tier === 'local' ? (LOCAL_NOT_ENABLED[type] ?? 'No live engine proof yet.') : null,
    runs,
    ...portsOf(entry),
  };
}

function parseIndex(text: string): { catalog: Catalog; entries: Map<string, IndexEntry> } | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return null;
  }
  const index = parsed as { entries?: unknown; version?: unknown };
  if (!index || typeof index !== 'object' || !Array.isArray(index.entries)) return null;
  const entries = new Map<string, IndexEntry>();
  const components: CatalogComponent[] = [];
  let total = 0;
  let legacy = 0;
  for (const pair of index.entries) {
    if (!Array.isArray(pair) || typeof pair[0] !== 'string' || !pair[1] || typeof pair[1] !== 'object') continue;
    const [category, group] = pair as [string, Record<string, IndexEntry>];
    for (const [type, entry] of Object.entries(group)) {
      if (!entry || typeof entry !== 'object' || !entry.template || typeof entry.template !== 'object') continue;
      total += 1;
      if (entry.legacy === true) {
        legacy += 1;
        continue;
      }
      entries.set(type, entry);
      components.push(summarize(type, category, entry));
    }
  }
  components.sort((a, b) => a.category.localeCompare(b.category) || a.displayName.localeCompare(b.displayName));
  return {
    entries,
    catalog: {
      engine: {
        lfxVersion: typeof index.version === 'string' ? index.version : 'unknown',
        langflowVersion: null,
        indexSha256: createHash('sha256').update(text).digest('hex'),
      },
      totalInIndex: total,
      legacyCount: legacy,
      components,
    },
  };
}

function load(config: RunnerConfig): Loaded | { error: string } {
  const file = componentIndexPath(config);
  if (!file) return { error: 'The Langflow engine is not configured, so its component list is not available.' };
  let stat: fs.Stats;
  try {
    stat = fs.statSync(file);
  } catch {
    return { error: "The engine's component list was not found next to the configured engine." };
  }
  const key = `${file}|${stat.size}|${stat.mtimeMs}`;
  if (cache?.key === key) return cache;
  const parsed = parseIndex(fs.readFileSync(file, 'utf8'));
  if (!parsed) return { error: "The engine's component list could not be read." };
  parsed.catalog.engine.langflowVersion = langflowVersionNear(file);
  cache = { key, ...parsed };
  return cache;
}

export function loadCatalog(config: RunnerConfig): CatalogResult {
  const loaded = load(config);
  return 'error' in loaded ? { ok: false, reason: loaded.error } : { ok: true, catalog: loaded.catalog };
}

/** A fresh copy of the engine's own node template for a current component, or null. */
export function componentTemplate(config: RunnerConfig, componentType: string): JsonObject | null {
  const loaded = load(config);
  if ('error' in loaded) return null;
  const entry = loaded.entries.get(componentType);
  return entry ? (structuredClone(entry) as JsonObject) : null;
}

/** sha256 of the engine's built-in code for a component, first 12 hex characters (the index's own code_hash scheme). */
export function builtinCodeHash(config: RunnerConfig, componentType: string): string | null {
  const loaded = load(config);
  if ('error' in loaded) return null;
  const code = (loaded.entries.get(componentType)?.template?.code as JsonObject | undefined)?.value;
  return typeof code === 'string' ? codeHash(code) : null;
}

export function codeHash(code: string): string {
  return createHash('sha256').update(code).digest('hex').slice(0, 12);
}

/** Human label for the engine that actually runs, e.g. "lfx 1.12.6rc3". */
export function engineLabel(config: RunnerConfig): string {
  const loaded = load(config);
  return 'error' in loaded ? 'unknown (component list not found)' : `lfx ${loaded.catalog.engine.lfxVersion}`;
}

/** Test hook: forget the cached index. */
export function resetCatalogCache(): void {
  cache = null;
}
