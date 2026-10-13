import fs from 'node:fs';

import { fail, ok } from '@/lib/langflow/api';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { loadCatalog } from '@/lib/langflow/catalog';
import { langflowReachable, langflowServer } from '@/lib/langflow/langflow-server';
import { PINNED_LANGFLOW_VERSION, runnerConfig } from '@/lib/langflow/runner';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const access = loadAccess();
  const caller = resolveCaller(request.headers, access);
  if (!caller || !authorize(caller, 'read').ok) {
    return fail(403, 'This device is not allowed to use the Langflow panel.');
  }
  const cfg = runnerConfig();
  const catalog = loadCatalog(cfg);
  const installed = catalog.ok ? catalog.catalog.engine : null;
  return ok({
    engine: {
      name: 'lfx',
      pinnedLangflowVersion: PINNED_LANGFLOW_VERSION,
      configured: !!cfg.lfxBin,
      binaryFound: !!cfg.lfxBin && fs.existsSync(cfg.lfxBin),
      lfxVersion: installed?.lfxVersion ?? null,
      langflowVersion: installed?.langflowVersion ?? null,
      versionDrift: !!installed && installed.lfxVersion !== PINNED_LANGFLOW_VERSION,
      catalogError: catalog.ok ? null : catalog.reason,
    },
    // Only the owner on this Mac can open flows in Langflow, so only the owner is told whether it is running.
    server: caller.ops.includes('save')
      ? { langflow: { configured: !!langflowServer().url, reachable: await langflowReachable() } }
      : { langflow: null },
    caller: {
      network: caller.network,
      canSave: caller.ops.includes('save'),
      canRun: caller.ops.includes('run'),
      canStop: caller.ops.includes('stop'),
    },
    accessError: access.loadError,
  });
}
