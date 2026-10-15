import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

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

export function reviewQueuePath(): string {
  const fromEnv = process.env.REVIEW_QUEUE_PATH;
  if (fromEnv) {
    return path.resolve(fromEnv);
  }
  return path.join(os.homedir(), '.agents', 'runtime', 'review-queue.json');
}

export function boardDir(): string {
  const fromEnv = process.env.AGENTS_BOARD_DIR;
  if (fromEnv) {
    return path.resolve(fromEnv);
  }
  return path.join(os.homedir(), '.agents', 'board');
}

export function boardScript(): string {
  const fromEnv = process.env.AGENTS_BOARD_SCRIPT;
  if (fromEnv) {
    return path.resolve(fromEnv);
  }
  return path.join(os.homedir(), '.agents', 'tools', 'board', 'board.py');
}
