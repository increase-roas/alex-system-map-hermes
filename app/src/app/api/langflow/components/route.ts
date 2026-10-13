import { fail, ok } from '@/lib/langflow/api';
import { loadCatalog } from '@/lib/langflow/catalog';
import { authorize, loadAccess, resolveCaller } from '@/lib/langflow/policy';
import { runnerConfig } from '@/lib/langflow/runner';
import type { RunTier } from '@/lib/langflow/tiers';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** The current (non-legacy) components of the installed engine, with their run tier. Read only. */
export async function GET(request: Request) {
  const c = resolveCaller(request.headers, loadAccess());
  const read = authorize(c, 'read');
  if (!read.ok) return fail(read.status, read.reason);
  const result = loadCatalog(runnerConfig());
  if (!result.ok) return fail(503, result.reason);
  const { catalog } = result;
  const tierCounts: Record<RunTier | 'runs', number> = { runs: 0, local: 0, ai: 0, internet: 0, code_files: 0, server: 0, unknown: 0 };
  for (const comp of catalog.components) {
    tierCounts[comp.tier] += 1;
    if (comp.runs) tierCounts.runs += 1;
  }
  return ok({
    engine: catalog.engine,
    totalInIndex: catalog.totalInIndex,
    legacyCount: catalog.legacyCount,
    count: catalog.components.length,
    tierCounts,
    components: catalog.components,
  });
}
