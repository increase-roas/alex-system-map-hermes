import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { test } from 'node:test';

import { startLfxRun, type RunnerConfig } from '../runner';

const dir = fs.mkdtempSync(path.join(process.env.TMPDIR ?? os.tmpdir(), 'lf-runner-'));

// A stand-in for `lfx`: a shell script that prints whatever body we give it.
function fakeLfx(body: string): string {
  const file = path.join(dir, `fake-lfx-${randomUUID()}.sh`);
  fs.writeFileSync(file, `#!/bin/sh\n${body}\n`, { mode: 0o755 });
  return file;
}

const cfg = (lfxBin: string | null, timeoutMs = 10_000): RunnerConfig => ({ lfxBin, configDir: null, timeoutMs });
const flowFile = path.join(dir, 'flow.json');
fs.writeFileSync(flowFile, '{}');

test('runner: no engine configured is a clear failure, not a crash', async () => {
  const run = startLfxRun({ flowFile, input: 'hi' }, cfg(null));
  const out = await run.done;
  assert.equal(out.status, 'failed');
  assert.equal((out as { code: string }).code, 'not_configured');
});

test('runner: a missing engine binary is reported by path-free message', async () => {
  const out = await startLfxRun({ flowFile, input: 'hi' }, cfg('/definitely/not/here/lfx')).done;
  assert.equal((out as { code: string }).code, 'missing_binary');
});

test('runner: a successful engine result is returned as the output', async () => {
  const bin = fakeLfx('echo \'{"result": "hello back", "type": "message", "component": "Chat Output", "success": true}\'');
  const out = await startLfxRun({ flowFile, input: 'hi' }, cfg(bin)).done;
  assert.deepEqual(out, { status: 'succeeded', output: 'hello back', component: 'Chat Output' });
});

test('runner: an engine error is reported with its message', async () => {
  const bin = fakeLfx('echo \'{"success": false, "exception_message": "component blew up"}\'');
  const out = await startLfxRun({ flowFile, input: 'hi' }, cfg(bin)).done;
  assert.equal((out as { code: string }).code, 'engine_error');
  assert.equal((out as { message: string }).message, 'component blew up');
});

test('runner: output with no readable result is bad_output', async () => {
  const bin = fakeLfx('echo "garbage with no json"');
  const out = await startLfxRun({ flowFile, input: 'hi' }, cfg(bin)).done;
  assert.equal((out as { code: string }).code, 'bad_output');
});

test('runner: the input is passed as an argument, never through a shell', async () => {
  const bin = fakeLfx('echo "{\\"success\\": true, \\"result\\": \\"$*\\"}"');
  const out = await startLfxRun({ flowFile, input: 'hello $(whoami) ; rm -rf x' }, cfg(bin)).done;
  assert.equal(out.status, 'succeeded');
  const text = (out as { output: string }).output;
  assert.ok(text.includes('--input-value'));
  assert.ok(text.includes('hello $(whoami) ; rm -rf x'), 'the input arrives verbatim');
});

test('runner: provider keys in the dashboard environment do not reach the engine', async () => {
  process.env.OPENAI_API_KEY = 'FAKE-canary-openai-key-for-env-test';
  try {
    const bin = fakeLfx('echo "{\\"success\\": true, \\"result\\": \\"env:${OPENAI_API_KEY:-none}\\"}"');
    const out = await startLfxRun({ flowFile, input: 'hi' }, cfg(bin)).done;
    assert.equal((out as { output: string }).output, 'env:none');
  } finally {
    delete process.env.OPENAI_API_KEY;
  }
});

test('runner: a run that exceeds its time limit is killed and reported as a timeout', async () => {
  const bin = fakeLfx('sleep 30');
  const started = Date.now();
  const out = await startLfxRun({ flowFile, input: 'hi' }, cfg(bin, 300)).done;
  assert.equal((out as { code: string }).code, 'timeout');
  assert.ok(Date.now() - started < 10_000, 'the child was killed, not waited for');
});

test('runner: stop kills the engine process and reports stopped', async () => {
  const bin = fakeLfx('sleep 30');
  const run = startLfxRun({ flowFile, input: 'hi' }, cfg(bin, 60_000));
  await new Promise((r) => setTimeout(r, 200));
  assert.equal(run.stop(), true);
  const out = await run.done;
  assert.equal((out as { code: string }).code, 'stopped');
  assert.equal(run.stop(), false, 'a second stop does nothing');
});
