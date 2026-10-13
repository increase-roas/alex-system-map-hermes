// Last line of defence for text that leaves the server: run output, errors, logs and exports.
// Patterns match credential-shaped strings; they do not prove that nothing else is sensitive.

const PATTERNS: Array<[RegExp, string]> = [
  [/-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----/g, '[redacted private key]'],
  [/\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}/g, '[redacted token]'],
  [/\bsk-[A-Za-z0-9_-]{16,}/g, '[redacted key]'],
  [/\bAKIA[0-9A-Z]{16}\b/g, '[redacted key]'],
  [/\bBearer\s+[A-Za-z0-9._~+/=-]{8,}/g, 'Bearer [redacted]'],
  [/(x-api-key|api[_-]?key|secret|token|password)(\s*[:=]\s*)["']?[^\s"',}]{6,}/gi, '$1$2[redacted]'],
];

export function screenText(value: string): string {
  let out = value;
  for (const [pattern, replacement] of PATTERNS) {
    out = out.replace(pattern, replacement);
  }
  return out;
}

export function clip(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max)}… (${value.length - max} more characters)` : value;
}

/** Replaces this Mac's home folder with "~" so engine errors do not reveal local paths (user name, venv). */
export function stripLocalPaths(value: string, home = process.env.HOME ?? ''): string {
  if (!home || home === '/') return value;
  return value.split(home).join('~');
}
