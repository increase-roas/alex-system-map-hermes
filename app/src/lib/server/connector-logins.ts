import { execFile } from 'node:child_process';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { promisify } from 'node:util';

import { foundationRoot, localDataDir } from './paths';
import { screenParsedValue, screenServiceText } from './python';

const run = promisify(execFile);

export const connectorLoginsFile = () => path.join(localDataDir(), 'connector-logins.json');

let inflight: Promise<void> | null = null;

/** Re-run the read-only Composio exporter (one at a time). It only rewrites .data/connector-logins.json. */
export function runConnectorLoginsExport(): Promise<void> {
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      await run('python3', ['-B', path.join(foundationRoot(), 'tools', 'composio_logins_export.py')], { timeout: 120_000 });
    } catch (error) {
      // The exporter prints {ok:false,error} on stdout with a short, key-free message; stderr is never surfaced.
      const stdout = String((error as { stdout?: string }).stdout ?? '');
      let message = 'export failed';
      try {
        message = String(JSON.parse(stdout.trim().split('\n').pop() ?? '{}').error ?? message);
      } catch {
        /* keep the generic message */
      }
      throw new Error(screenServiceText(message).slice(0, 300));
    }
  })().finally(() => {
    inflight = null;
  });
  return inflight;
}

export async function readConnectorLogins(): Promise<unknown | null> {
  try {
    return screenParsedValue(JSON.parse(await readFile(connectorLoginsFile(), 'utf8')));
  } catch {
    return null;
  }
}

export async function connectorLoginsAgeMs(): Promise<number> {
  try {
    return Date.now() - (await stat(connectorLoginsFile())).mtimeMs;
  } catch {
    return Number.POSITIVE_INFINITY;
  }
}
