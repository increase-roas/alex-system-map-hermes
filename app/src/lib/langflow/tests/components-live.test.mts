// LIVE: every current component of the installed engine can be added through the real save route,
// and the engine's own validator accepts the saved file. Skipped unless enabled:
//   LANGFLOW_LIVE_ENGINE=1 LANGFLOW_LFX_BIN=<lfx> LANGFLOW_CONFIG_DIR=<dir> \
//     node --import ./src/lib/langflow/tests/register.mjs --test src/lib/langflow/tests/components-live.test.mts
//
// Two validator runs per saved file, both with their exit status checked:
//   A. `lfx validate --level 3 --skip-components --strict`: structure (level 1) and edge types (level 3) with
//      warnings treated as errors. Must exit 0 with no issues.
//   B. `lfx validate` (all levels, default): exit status and every issue recorded. A lone component cannot pass
//      level 4 when it has a required input (nothing is wired into it), so exit 1 is accepted only when every
//      error is "Required input ... has no value". Components without required inputs must exit 0.
//   Level 2 (component exists) cannot run in this engine: lfx/cli/validation/semantic.py imports
//   initialize_components, which lfx/interface/utils.py lacks (seen on 1.12.6rc3 and 1.12.5). Instead the test
//   proves registry identity itself: every saved component's code is byte-identical (sha256) to the engine's
//   built-in component of that type. Fully wired flows pass all levels strictly: live-components.test.mts.
//
// Issue categories in run B (levels from `lfx validate --help`):
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
import { builtinCodeHash, codeHash, loadCatalog } from '../catalog';
import type { LfFlow } from '../model';
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

function validateRun(file: string, extra: string[] = []): { status: number | null; issues: Issue[] } {
  const cfg = runnerConfig();
  const r = spawnSync(cfg.lfxBin!, ['validate', ...extra, '-f', 'json', file], { env: engineEnv(cfg) as NodeJS.ProcessEnv, encoding: 'utf8', timeout: 120_000 });
  const start = r.stdout.indexOf('[');
  assert.ok(start >= 0, `validate printed no JSON (exit ${r.status}): ${r.stderr.slice(-300)}`);
  const report = JSON.parse(r.stdout.slice(start)) as Array<{ issues: Issue[] }>;
  return { status: r.status, issues: report[0].issues };
}

const STRICT_STRUCTURE = ['--level', '3', '--skip-components', '--strict'];

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
    const stored = JSON.parse(fs.readFileSync(flowFilePath(id), 'utf8')) as LfFlow;
    assert.equal(stored.data.nodes.length, 1);
    assert.equal(stored.data.nodes[0].data?.type, comp.type);
    // Registry identity (stands in for the engine's level 2, which cannot run): the saved code is the engine's.
    const code = (stored.data.nodes[0].data?.node?.template?.code as { value?: unknown } | undefined)?.value;
    const identical = typeof code === 'string' && codeHash(code) === builtinCodeHash(runnerConfig(), comp.type);
    // Run A: structure and edge types, strict, exit status checked.
    const a = validateRun(flowFilePath(id), STRICT_STRUCTURE);
    // Run B: all levels, exit status and issues recorded.
    const b = validateRun(flowFilePath(id));
    const { bad, requiredEmpty, secretsEmpty, registryGap } = grade(b.issues);
    if (registryGap) registryGapSeen += 1;
    const expectedB = requiredEmpty > 0 ? 1 : 0;
    const problems = [
      ...(identical ? [] : ['saved code is not the engine built-in']),
      ...(a.status === 0 && a.issues.length === 0 ? [] : [`run A exit ${a.status}: ${a.issues.map((i) => `L${i.level} ${i.severity}: ${i.message}`).join(' | ')}`]),
      ...(b.status === expectedB ? [] : [`run B exit ${b.status}, expected ${expectedB}`]),
      ...bad.map((i) => `run B L${i.level} ${i.severity}: ${i.message}`),
    ];
    if (problems.length) failures.push(`${comp.type}: ${problems.join(' | ')}`);
    rows.push(`${problems.length ? 'FAIL' : 'PASS'} ${comp.category}/${comp.type}: engine code identical; strict levels 1+3 exit ${a.status}; all levels exit ${b.status} (required inputs empty: ${requiredEmpty}, empty secret fields: ${secretsEmpty})`);
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
  // Exit status checked on both runs. 63 unconnected components side by side: the engine warns that each one
  // is orphaned or unused (level 1 warnings). Counted, not hidden.
  const unconnected = (i: Issue) => i.level === 1 && i.severity === 'warning' && /^(Orphaned node|Unused node)/.test(i.message);
  const a = validateRun(flowFilePath(id), ['--level', '3', '--skip-components']);
  const aOther = a.issues.filter((i) => !unconnected(i));
  const b = validateRun(flowFilePath(id));
  const graded = grade(b.issues);
  const orphaned = graded.bad.filter(unconnected);
  const bad = graded.bad.filter((i) => !unconnected(i));
  console.log(`ALL-IN-ONE flow: 63 components saved; levels 1+3 exit ${a.status}, other issues ${aOther.length}, unconnected warnings ${a.issues.length - aOther.length}; all levels exit ${b.status}, other issues ${bad.length}, unconnected warnings ${orphaned.length}, L4 empty required inputs ${graded.requiredEmpty}, L4 empty secret fields ${graded.secretsEmpty}`);
  assert.equal(a.status, 0, 'levels 1 and 3 exit 0');
  assert.deepEqual(aOther, []);
  assert.equal(b.status, graded.requiredEmpty > 0 ? 1 : 0, 'all levels exit 1 only because of empty required inputs');
  assert.deepEqual(bad, []);
});

test('LIVE negative controls: a broken file makes the validator exit non-zero and the grading reports it', { skip: !enabled && 'set LANGFLOW_LIVE_ENGINE=1 and LANGFLOW_LFX_BIN to run', timeout: 120_000 }, () => {
  const file = path.join(tmp, 'broken-edge.json');
  fs.writeFileSync(file, JSON.stringify({ id: randomUUID(), name: 'broken', data: { nodes: [], edges: [{ id: 'e1', source: 'Missing-aaaaa', target: 'Missing-bbbbb', data: { sourceHandle: {}, targetHandle: {} } }] } }));
  const a = validateRun(file, STRICT_STRUCTURE);
  const b = validateRun(file);
  assert.notEqual(a.status, 0, 'strict levels 1+3 fail on an edge to a missing component');
  assert.notEqual(b.status, 0);
  assert.ok(grade(b.issues).bad.length > 0, 'the grading does not accept the error');
  const noId = path.join(tmp, 'no-id.json');
  fs.writeFileSync(noId, JSON.stringify({ name: 'no id', data: { nodes: [], edges: [] } }));
  const c = validateRun(noId, STRICT_STRUCTURE);
  assert.notEqual(c.status, 0, 'a flow without a top-level id fails level 1');
  console.log(`NEGATIVE controls: broken edge strict exit ${a.status}, all levels exit ${b.status} (${grade(b.issues).bad.length} unaccepted issues); missing id strict exit ${c.status}`);
});
