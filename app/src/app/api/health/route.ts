import fs from 'node:fs';
import path from 'node:path';

import { NextResponse } from 'next/server';

import { getOrCreateLocalToken } from '@/lib/server/local-auth';
import { ensureServiceInitialized, runLocalService } from '@/lib/server/python';
import { foundationRoot, localDataDir, sqlitePath } from '@/lib/server/paths';

function readBuildId(): string | null {
  const buildIdPath = path.join(process.cwd(), '.next', 'BUILD_ID');
  if (!fs.existsSync(buildIdPath)) {
    return null;
  }
  return fs.readFileSync(buildIdPath, 'utf8').trim();
}

export async function GET() {
  await ensureServiceInitialized();
  const [completeness, sync] = await Promise.all([
    runLocalService(['catalog-completeness']),
    runLocalService(['sync-status']),
  ]);
  const dbPath = sqlitePath();
  let dbSha256: string | null = null;
  if (fs.existsSync(dbPath)) {
    const crypto = await import('node:crypto');
    dbSha256 = crypto.createHash('sha256').update(fs.readFileSync(dbPath)).digest('hex');
  }
  return NextResponse.json({
    ok: true,
    loopback_only: true,
    local_token_hint: 'Send X-Local-Token for mutations',
    token: getOrCreateLocalToken(),
    build_id: readBuildId(),
    process: { pid: process.pid },
    runtime: {
      foundation_root: foundationRoot(),
      local_data_dir: localDataDir(),
      workflow_sqlite_path: dbPath,
      workflow_db_sha256: dbSha256,
      catalog_fixture_root: process.env.CATALOG_FIXTURE_ROOT ?? null,
    },
    completeness,
    sync,
  });
}
