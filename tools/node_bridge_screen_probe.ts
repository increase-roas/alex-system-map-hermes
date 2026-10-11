import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { LocalServiceError, runLocalService } from '../app/src/lib/server/python.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const CANARY = 'FAKE-canary-token-res0722-emitted';
const BENIGN = 'LOCAL-SCREENING-OK';

async function main() {
  const db = path.join(ROOT, 'app/.data/recovery-screening-real-paths-0738/bridge-probe.sqlite');
  process.env.FOUNDATION_ROOT = ROOT;
  process.env.LOCAL_DATA_DIR = path.dirname(db);
  process.env.WORKFLOW_SQLITE_PATH = db;
  const init = spawnSync('python3', [path.join(ROOT, 'tools/local_service.py'), '--db', db, 'init'], {
    cwd: ROOT,
    encoding: 'utf8',
  });
  let readSourceOk = false;
  let readSourceBenign = false;
  let readSourceExit: number | null = null;
  try {
    await runLocalService(['read-source', 'synthetic/canary-error-boundary']);
  } catch (err) {
    const lse = err instanceof LocalServiceError ? err : null;
    const payload = (lse?.payload ?? {}) as Record<string, unknown>;
    const msg = `${lse?.message ?? String(err)} ${JSON.stringify(payload)}`;
    readSourceOk = !msg.includes(CANARY);
    readSourceBenign =
      msg.includes(BENIGN) ||
      msg.includes('[REDACTED test-canary]') ||
      payload.diagnostic_marker === BENIGN;
    readSourceExit = lse?.exitCode ?? 1;
    if (readSourceExit === 0) readSourceExit = 1;
  }
  let nonzeroJsonRejected = false;
  let nonzeroExit: number | null = null;
  try {
    await runLocalService(['trace-get', 'trace-missing-nonzero-0754']);
  } catch (err) {
    const lse = err instanceof LocalServiceError ? err : null;
    nonzeroJsonRejected = Boolean(lse);
    nonzeroExit = lse?.exitCode ?? null;
  }
  const invalid = spawnSync(
    'python3',
    [path.join(ROOT, 'tools/local_service.py'), '--db', db, 'not-a-real-command'],
    { cwd: ROOT, encoding: 'utf8' },
  );
  const combined = `${invalid.stdout}${invalid.stderr}`;
  const invalidJson = (() => {
    try {
      JSON.parse(invalid.stdout.trim());
      return true;
    } catch {
      return false;
    }
  })();
  const result = {
    read_source_canary_removed: readSourceOk,
    read_source_benign: readSourceBenign,
    read_source_intended_error: readSourceExit !== null && readSourceExit !== 0,
    invalid_command_json_stdout: invalidJson,
    invalid_command_canary_removed: !combined.includes(CANARY),
    invalid_command_nonempty: combined.trim().length > 0,
    invalid_command_benign: combined.includes(BENIGN) || invalid.stdout.includes(BENIGN),
    init_ok: init.status === 0,
    nonzero_json_rejected: nonzeroJsonRejected,
    nonzero_exit: nonzeroExit,
    benign: readSourceBenign && (combined.includes(BENIGN) || invalid.stdout.includes(BENIGN)),
    screened: readSourceOk && !combined.includes(CANARY),
    nonempty: Boolean(invalid.stdout.trim()) && readSourceExit !== 0,
  };
  console.log(JSON.stringify(result, null, 2));
  const pass =
    result.benign &&
    result.screened &&
    result.nonempty &&
    result.read_source_benign &&
    result.invalid_command_json_stdout &&
    result.nonzero_json_rejected &&
    result.nonzero_exit !== 0;
  process.exit(pass ? 0 : 1);
}

void main();
