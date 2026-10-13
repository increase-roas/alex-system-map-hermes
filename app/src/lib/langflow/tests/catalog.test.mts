// Component catalog: unit tests on a real-entry subset of the engine index, plus a LIVE check on the
// installed engine's full index (skipped unless LANGFLOW_LFX_BIN points at the real lfx).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

import { getOrCreateLocalToken } from '../../server/local-auth';
import * as componentsRoute from '../../../app/api/langflow/components/route';
import { builtinCodeHash, componentIndexPath, componentTemplate, loadCatalog, resetCatalogCache } from '../catalog';
import { runnerConfig } from '../runner';
import { COMPONENT_TIERS } from '../tiers';

const SUBSET = fileURLToPath(new URL('../fixtures/component-index.subset.json', import.meta.url));
const tmp = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-catalog-'));

function withIndex<T>(file: string | undefined, fn: () => T): T {
  const before = process.env.LANGFLOW_COMPONENT_INDEX;
  if (file === undefined) delete process.env.LANGFLOW_COMPONENT_INDEX;
  else process.env.LANGFLOW_COMPONENT_INDEX = file;
  resetCatalogCache();
  try {
    return fn();
  } finally {
    if (before === undefined) delete process.env.LANGFLOW_COMPONENT_INDEX;
    else process.env.LANGFLOW_COMPONENT_INDEX = before;
    resetCatalogCache();
  }
}

const req = (headers: Record<string, string>) => new Request('http://127.0.0.1:3200/api/langflow/components', { headers: new Headers({ host: '127.0.0.1:3200', ...headers }) });

test('catalog: legacy components are left out and every entry carries ports and a tier', () => {
  withIndex(SUBSET, () => {
    const result = loadCatalog(runnerConfig({}));
    assert.ok(result.ok);
    const { catalog } = result;
    assert.equal(catalog.totalInIndex, 13);
    assert.equal(catalog.legacyCount, 1);
    assert.equal(catalog.components.length, 12);
    assert.ok(!catalog.components.some((c) => c.type === 'CrewAIAgentComponent'), 'legacy entry is not offered');
    const calc = catalog.components.find((c) => c.type === 'CalculatorComponent')!;
    assert.equal(calc.tier, 'local');
    assert.deepEqual(calc.outputs.map((o) => o.name), ['result']);
    assert.deepEqual(calc.inputs.map((i) => i.name), ['expression']);
    const lm = catalog.components.find((c) => c.type === 'LanguageModelComponent')!;
    assert.equal(lm.tier, 'ai');
    assert.equal(lm.runs, false);
    const loop = catalog.components.find((c) => c.type === 'LoopComponent')!;
    assert.equal(loop.outputs.find((o) => o.name === 'item')?.loop, true);
    assert.match(catalog.engine.lfxVersion, /^1\.12\./);
  });
});

test('catalog: templates are fresh copies and code hashes follow the index scheme', () => {
  withIndex(SUBSET, () => {
    const cfg = runnerConfig({});
    const a = componentTemplate(cfg, 'CalculatorComponent')!;
    (a.template as Record<string, { value: unknown }>).expression.value = 'changed';
    const b = componentTemplate(cfg, 'CalculatorComponent')!;
    assert.equal((b.template as Record<string, { value: unknown }>).expression.value, '', 'editing one copy never changes the cache');
    const indexHash = (b.metadata as { code_hash: string }).code_hash;
    assert.ok(builtinCodeHash(cfg, 'CalculatorComponent')!.startsWith(indexHash), 'full sha256 whose first 12 characters are the index code_hash');
    assert.equal(builtinCodeHash(cfg, 'CalculatorComponent')!.length, 64);
    assert.equal(componentTemplate(cfg, 'CrewAIAgentComponent'), null, 'legacy is not addable');
    assert.equal(componentTemplate(cfg, 'NoSuchComponent'), null);
  });
});

test('catalog: missing or broken index is reported, not invented', () => {
  withIndex(undefined, () => {
    const r = loadCatalog(runnerConfig({}));
    assert.equal(r.ok, false);
  });
  const broken = path.join(tmp, 'broken.json');
  fs.writeFileSync(broken, '{not json');
  withIndex(broken, () => {
    const r = loadCatalog(runnerConfig({}));
    assert.equal(r.ok, false);
    if (!r.ok) assert.match(r.reason, /could not be read/);
  });
});

test('catalog route: owner and listed tailnet read; unlisted tailnet is refused; no file paths leak', async () => {
  process.env.LOCAL_DATA_DIR = tmp;
  await withIndex(SUBSET, async () => {
    const owner = await componentsRoute.GET(req({ 'x-local-token': getOrCreateLocalToken() }));
    assert.equal(owner.status, 200);
    const text = await owner.text();
    assert.ok(!text.includes(tmp) && !text.includes('site-packages') && !text.includes('.venvs'), 'no filesystem paths in the response');
    const body = JSON.parse(text) as { count: number; tierCounts: Record<string, number> };
    assert.equal(body.count, 12);
    const stranger = await componentsRoute.GET(req({ host: 'mac.tailnet.ts.net', 'tailscale-user-login': 'stranger@example.com' }));
    assert.equal(stranger.status, 403);
  });
  const bin = process.env.LANGFLOW_LFX_BIN;
  delete process.env.LANGFLOW_LFX_BIN;
  try {
    await withIndex(undefined, async () => {
      const res = await componentsRoute.GET(req({ 'x-local-token': getOrCreateLocalToken() }));
      assert.equal(res.status, 503, 'no engine configured: the list is unavailable, not guessed');
    });
  } finally {
    if (bin !== undefined) process.env.LANGFLOW_LFX_BIN = bin;
  }
});

const live = !!process.env.LANGFLOW_LFX_BIN && fs.existsSync(process.env.LANGFLOW_LFX_BIN);

test('LIVE catalog: the installed engine offers 63 current components in the audited tiers', { skip: !live && 'set LANGFLOW_LFX_BIN to the real lfx' }, () => {
  withIndex(undefined, () => {
    const cfg = runnerConfig();
    const file = componentIndexPath(cfg);
    assert.ok(file && fs.existsSync(file), 'index found next to the engine');
    const r = loadCatalog(cfg);
    assert.ok(r.ok);
    const { catalog } = r;
    assert.equal(catalog.totalInIndex, 128);
    assert.equal(catalog.legacyCount, 65);
    assert.equal(catalog.components.length, 63);
    const counts: Record<string, number> = {};
    for (const c of catalog.components) counts[c.tier] = (counts[c.tier] ?? 0) + 1;
    assert.equal(counts.unknown ?? 0, 0, 'every current component is in the audited tier list');
    assert.equal(counts.local, 22, 'local tier: Chat Input, Chat Output and the 20 approved local components');
    assert.equal((counts.ai ?? 0) + (counts.internet ?? 0) + (counts.code_files ?? 0) + (counts.server ?? 0), 41, 'show and edit only');
    assert.equal(Object.keys(COMPONENT_TIERS).length, 63);
    for (const type of Object.keys(COMPONENT_TIERS)) {
      assert.ok(catalog.components.some((c) => c.type === type), `${type} is in the engine`);
    }
    console.log(`LIVE catalog: lfx ${catalog.engine.lfxVersion}, langflow ${catalog.engine.langflowVersion}, ${catalog.components.length} current, tiers ${JSON.stringify(counts)}, runs ${catalog.components.filter((c) => c.runs).length}`);
  });
});
