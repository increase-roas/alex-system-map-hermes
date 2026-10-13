// Test-only loader: lets the test runner import the app's modules the way Next.js resolves them,
// including the "@/" alias for src/ and extensionless relative imports. Production code is not affected.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const srcRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const EXTENSIONS = ['.ts', '.mts'];

function withExtension(base) {
  if (fs.existsSync(base) && fs.statSync(base).isFile()) return base;
  for (const ext of EXTENSIONS) {
    if (fs.existsSync(base + ext)) return base + ext;
  }
  return null;
}

export function resolve(specifier, context, nextResolve) {
  // Node needs the explicit file for Next's server entry; the bundler does not.
  if (specifier === 'next/server') {
    return nextResolve('next/server.js', context);
  }
  if (specifier.startsWith('@/')) {
    const found = withExtension(path.join(srcRoot, specifier.slice(2)));
    if (found) return nextResolve(pathToFileURL(found).href, context);
  }
  const relative = specifier.startsWith('./') || specifier.startsWith('../');
  if (relative && path.extname(specifier) === '' && context.parentURL?.startsWith('file:')) {
    const base = path.resolve(path.dirname(fileURLToPath(context.parentURL)), specifier);
    const found = withExtension(base);
    if (found) return nextResolve(pathToFileURL(found).href, context);
  }
  return nextResolve(specifier, context);
}
