// Run with: node --import ./src/lib/langflow/tests/register.mjs --test src/lib/langflow/tests/*.test.mts
import { registerHooks } from 'node:module';

import { resolve } from './resolve-hook.mjs';

registerHooks({ resolve });
