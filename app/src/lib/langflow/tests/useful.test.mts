import assert from 'node:assert/strict';
import { test } from 'node:test';

import { mostUseful, usageCounts } from '../useful';

const c = (type: string, runs: boolean, displayName = type) => ({ type, runs, displayName });

test('starter flows count: ChatInput and ChatOutput are the most used', () => {
  const counts = usageCounts();
  assert.ok((counts.get('ChatOutput') ?? 0) >= 4);
  assert.ok((counts.get('ChatInput') ?? 0) >= 4);
});

test('used components come first, most used first, then the rest that run here; show-only unused ones stay out', () => {
  const list = [c('URLComponent', false), c('Calculator', true), c('ChatOutput', true), c('SplitText', true), c('ChatInput', true)];
  const top = mostUseful(list).map((x) => x.type);
  assert.deepEqual(top.slice(0, 2).sort(), ['ChatInput', 'ChatOutput']);
  assert.ok(top.indexOf('SplitText') < top.indexOf('Calculator'), 'a starter component ranks above an unused one');
  assert.ok(!top.includes('URLComponent'), 'an unused show-only component is not promoted');
});

test('components in the open flow are promoted even when they only show', () => {
  const list = [c('MemoryBase', false), c('Calculator', true)];
  assert.deepEqual(mostUseful(list, ['MemoryBase', 'MemoryBase']).map((x) => x.type), ['MemoryBase', 'Calculator']);
});
