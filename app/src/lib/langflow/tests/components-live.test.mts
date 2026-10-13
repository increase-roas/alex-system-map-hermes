// LIVE: every current component of the installed engine can be added through the real save route,
// and the engine's own validator accepts the saved file. Skipped unless enabled:
//   LANGFLOW_LIVE_ENGINE=1 LANGFLOW_LFX_BIN=<lfx> LANGFLOW_CONFIG_DIR=<dir> \
//     node --import ./src/lib/langflow/tests/register.mjs --test src/lib/langflow/tests/components-live.test.mts
//
// Grading of `lfx validate -f json` (levels from `lfx validate --help`):
//   level 1 (structure) and level 3 (edge types): must be clean.
//   level 2 (component exists): this engine build cannot load its registry
//     (lfx/cli/validation/semantic.py imports initialize_components, which lfx/interface/utils.py lacks),
//     so level 2 is skipped by the engine itself. That one warning is reported, nothing else is accepted.
//   level 4 (required inputs): a lone component with an empty required input is correctly flagged;
//     only "Required input ... has no value" errors are accepted, and they are counted.
//     "Credential field ... has no value" warnings are accepted and counted: the dashboard never stores
//     secrets, so a key field is always empty here by design.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

import { getOrCreateLocalToken } from '../../server/local-auth';
import * as flowsRoute from '../../../app/api/langflow/flows/route';
import * as flowRoute from '../../../app/api/langflow/flows/[flowId]/route';
import { loadCatalog } from '../catalog';
import { engineEnv, runnerConfig } from '../runner';
import { flowFilePath } from '../store';

const enabled = process.env.LANGFLOW_LIVE_ENGINE === '1' && !!process.env.LANGFLOW_LFX_BIN;
const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-components-'));
const REGISTRY_GAP = /Could not load component registry/;
const REQUIRED_EMPTY = /^Required input '[^']+' has no value and no incoming edge$/;
const SECRET_EMPTY = /^Credential field '[^']+' has no value /;

type Issue = { level: number; severity: string; message: string };

function headers(extra: Record<string, string> = {}): Headers {
  return new Headers({ host: '127.0.0.1:3200', 'x-local-token': getOrCreateLocalToken(), 'content-type': 'application/json', ...extra });
}

function rand5(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  return Array.from({ length: 5 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
}

async function newEmptyFlow(name: string): Promise<{ id: string; hash: string }> {
  const res = await flowsRoute.POST(new Request('http://127.0.0.1:3200/api/langflow/flows', {
    method: 'POST', headers: headers(), body: JSON.stringify({ id: randomUUID(), name, description: '', data: { nodes: [], edges: [] } }),
  }));
  assert.equal(res.status, 201);
  return (await res.json()) as { id: string; hash: string };
}

async function patch(id: string, body: unknown): Promise<{ status: number; body: Record<string, unknown> }> {
  const res = await flowRoute.PATCH(new Request(`http://127.0.0.1:3200/api/langflow/flows/${id}`, { method: 'PATCH', headers: headers(), body: JSON.stringify(body) }), { params: Promise.resolve({ flowId: id }) });
  return { status: res.status, body: (await res.json()) as Record<string, unknown> };
}

function validate(file: string): Issue[] {
  const cfg = runnerConfig();
  const r = spawnSync(cfg.lfxBin!, ['validate', '-f', 'json', file], { env: engineEnv(cfg) as NodeJS.ProcessEnv, encoding: 'utf8', timeout: 120_000 });
  const start = r.stdout.indexOf('[');
  assert.ok(start >= 0, `validate printed no JSON: ${r.stderr.slice(-300)}`);
  const report = JSON.parse(r.stdout.slice(start)) as Array<{ issues: Issue[] }>;
  return report[0].issues;
}

function grade(issues: Issue[]): { bad: Issue[]; requiredEmpty: number; secretsEmpty: number; registryGap: boolean } {
  const bad: Issue[] = [];
  let requiredEmpty = 0;
  let secretsEmpty = 0;
  let registryGap = false;
  for (const i of issues) {
    if (i.level === 2 && i.severity === 'warning' && REGISTRY_GAP.test(i.message)) registryGap = true;
    else if (i.level === 4 && i.severity === 'error' && REQUIRED_EMPTY.test(i.message)) requiredEmpty += 1;
    else if (i.level === 4 && i.severity === 'warning' && SECRET_EMPTY.test(i.message)) secretsEmpty += 1;
    else bad.push(i);
  }
  return { bad, requiredEmpty, secretsEmpty, registryGap };
}

test('LIVE: each of the current components is added through the save route and passes the engine validator', { skip: !enabled && 'set LANGFLOW_LIVE_ENGINE=1 and LANGFLOW_LFX_BIN to run', timeout: 1_800_000 }, async () => {
  process.env.LOCAL_DATA_DIR = tmp;
  const catalog = loadCatalog(runnerConfig());
  assert.ok(catalog.ok);
  const components = catalog.catalog.components;
  assert.equal(components.length, 63);
  const rows: string[] = [];
  const failures: string[] = [];
  let registryGapSeen = 0;
  for (const comp of components) {
    const { id, hash } = await newEmptyFlow(`add ${comp.type}`);
    const nodeId = `${comp.type}-${rand5()}`;
    const saved = await patch(id, { expectedHash: hash, edits: [{ kind: 'addNode', nodeId, componentType: comp.type, position: { x: 100, y: 100 } }] });
    if (saved.status !== 200) {
      failures.push(`${comp.type}: save returned ${saved.status} ${JSON.stringify(saved.body).slice(0, 200)}`);
      continue;
    }
    const stored = JSON.parse(fs.readFileSync(flowFilePath(id), 'utf8')) as { data: { nodes: Array<{ id: string; data: { type: string } }> } };
    assert.equal(stored.data.nodes.length, 1);
    assert.equal(stored.data.nodes[0].data.type, comp.type);
    const { bad, requiredEmpty, secretsEmpty, registryGap } = grade(validate(flowFilePath(id)));
    if (registryGap) registryGapSeen += 1;
    if (bad.length) failures.push(`${comp.type}: ${bad.map((b) => `L${b.level} ${b.severity}: ${b.message}`).join(' | ')}`);
    rows.push(`${bad.length ? 'FAIL' : 'PASS'} ${comp.category}/${comp.type}: saved, L1 and L3 clean, L4 empty required inputs: ${requiredEmpty}, L4 empty secret fields: ${secretsEmpty}`);
  }
  for (const row of rows) console.log(row);
  console.log(`SUMMARY added ${rows.length}/63, validator failures ${failures.length}, engine skipped level 2 (registry gap) on ${registryGapSeen} files`);
  assert.deepEqual(failures, []);
});

test('LIVE: all current components in one flow save together and pass the engine validator', { skip: !enabled && 'set LANGFLOW_LIVE_ENGINE=1 and LANGFLOW_LFX_BIN to run', timeout: 600_000 }, async () => {
  process.env.LOCAL_DATA_DIR = tmp;
  const catalog = loadCatalog(runnerConfig());
  assert.ok(catalog.ok);
  const { id, hash } = await newEmptyFlow('all components');
  const edits = catalog.catalog.components.map((c, i) => ({ kind: 'addNode', nodeId: `${c.type}-${rand5()}`, componentType: c.type, position: { x: (i % 8) * 360, y: Math.floor(i / 8) * 420 } }));
  const preview = await patch(id, { expectedHash: hash, edits, dryRun: true });
  assert.equal(preview.status, 200);
  assert.equal((preview.body.canvas as { nodes: unknown[] }).nodes.length, 63);
  const before = fs.readFileSync(flowFilePath(id), 'utf8');
  assert.equal(JSON.parse(before).data.nodes.length, 0, 'a dry run writes nothing');
  const saved = await patch(id, { expectedHash: hash, edits });
  assert.equal(saved.status, 200);
  assert.equal(saved.body.applied, 63);
  const graded = grade(validate(flowFilePath(id)));
  // 63 unconnected components side by side: the engine warns that each one is orphaned or unused. Counted, not hidden.
  const orphaned = graded.bad.filter((i) => i.level === 1 && i.severity === 'warning' && /^(Orphaned node|Unused node)/.test(i.message));
  const bad = graded.bad.filter((i) => !orphaned.includes(i));
  console.log(`ALL-IN-ONE flow: 63 components saved, other issues: ${bad.length}, L1 orphaned or unused warnings: ${orphaned.length}, L4 empty required inputs: ${graded.requiredEmpty}, L4 empty secret fields: ${graded.secretsEmpty}`);
  assert.deepEqual(bad, []);
});
