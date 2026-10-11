import fs from 'node:fs';
import path from 'node:path';

export function foundationRoot(): string {
  const fromEnv = process.env.FOUNDATION_ROOT;
  if (fromEnv) {
    return path.resolve(fromEnv);
  }
  return path.resolve(process.cwd(), '..');
}

export function localDataDir(): string {
  const fromEnv = process.env.LOCAL_DATA_DIR;
  if (fromEnv) {
    return path.resolve(fromEnv);
  }
  return path.join(process.cwd(), '.data');
}

export function sqlitePath(): string {
  const fromEnv = process.env.WORKFLOW_SQLITE_PATH;
  if (fromEnv) {
    return path.resolve(fromEnv);
  }
  return path.join(localDataDir(), 'local.sqlite');
}

export function localServiceScript(): string {
  return path.join(foundationRoot(), 'tools', 'local_service.py');
}

export function workflowTemplatesDir(): string {
  return path.join(foundationRoot(), 'workflows');
}

export function ensureLocalDataDir(): void {
  fs.mkdirSync(localDataDir(), { recursive: true });
}
