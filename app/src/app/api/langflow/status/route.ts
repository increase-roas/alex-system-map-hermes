import fs from 'node:fs';

import { fail, ok } from '@/lib/langflow/api';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
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
  return ok({
    engine: { name: 'lfx', pinnedLangflowVersion: PINNED_LANGFLOW_VERSION, configured: !!cfg.lfxBin, binaryFound: !!cfg.lfxBin && fs.existsSync(cfg.lfxBin) },
    server: { native_editor: 'not running in this build; advanced editing stays in Langflow' },
    caller: {
      network: caller.network,
      canSave: caller.ops.includes('save'),
      canRun: caller.ops.includes('run'),
      canStop: caller.ops.includes('stop'),
    },
    accessError: access.loadError,
  });
}
