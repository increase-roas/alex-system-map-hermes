/**
 * Screen sensitive fields before persisting browser/network diagnostics.
 */
import crypto from 'node:crypto';

export const BENIGN = 'LOCAL-SCREENING-OK';
export const CANARY = 'FAKE-canary-token-res0722-emitted';
const REDACTED_LOCAL_TOKEN = '[REDACTED local-mutation-token]';
const LOCAL_TOKEN_VALUE = /^[a-f0-9]{48}$/i;
const PLAIN_FIXTURE_TOKEN = /\b[a-f0-9]{48}\b/gi;
const LOCAL_TOKEN_JSON = /("token"\s*:\s*")([a-f0-9]{48})(")/gi;
const FAKE_CANARY = /\bFAKE[-_]canary[-_]token[-_][A-Za-z0-9-]+\b|sk-fake-canary-rel06-do-not-use-[A-Za-z0-9]+/gi;

export function screenDiagnosticText(text) {
  const notes = [];
  let value = String(text ?? '');
  if (LOCAL_TOKEN_JSON.test(value)) {
    value = value.replace(LOCAL_TOKEN_JSON, `$1${REDACTED_LOCAL_TOKEN}$3`);
    notes.push('local-mutation-token withheld');
  }
  if (FAKE_CANARY.test(value)) {
    value = value.replace(FAKE_CANARY, '[REDACTED test-canary]');
    notes.push('test-canary tokens withheld');
  }
  if (PLAIN_FIXTURE_TOKEN.test(value)) {
    value = value.replace(PLAIN_FIXTURE_TOKEN, REDACTED_LOCAL_TOKEN);
    notes.push('local-mutation-token withheld');
  }
  return { text: value, notes };
}

function redactValue(key, value) {
  const notes = [];
  if (typeof value === 'string') {
    if ((key === 'token' || key === 'x-local-token') && LOCAL_TOKEN_VALUE.test(value)) {
      notes.push('local-mutation-token withheld');
      return { value: REDACTED_LOCAL_TOKEN, notes };
    }
    const screened = screenDiagnosticText(value);
    notes.push(...screened.notes);
    return { value: screened.text, notes };
  }
  if (Array.isArray(value)) {
    const out = [];
    for (const item of value) {
      const r = redactDeep(item);
      notes.push(...r.notes);
      out.push(r.value);
    }
    return { value: out, notes };
  }
  if (value && typeof value === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      const r =
        (k === 'token' || k === 'x-local-token') && typeof v === 'string'
          ? redactValue(k, v)
          : redactDeep(v);
      notes.push(...r.notes);
      out[k] = r.value;
    }
    return { value: out, notes };
  }
  return { value, notes: [] };
}

export function redactDeep(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return redactValue('', value);
  }
  if (Array.isArray(value)) {
    return redactValue('', value);
  }
  if (typeof value === 'string') {
    const s = screenDiagnosticText(value);
    return { value: s.text, notes: s.notes };
  }
  return { value, notes: [] };
}

export function screenNetworkLogEntry(entry) {
  const { value, notes } = redactDeep(entry);
  const out = { ...value };
  out.screening_notes = [...new Set(notes)].sort();
  out.diagnostic_marker = BENIGN;
  if (typeof out.bodyPreview === 'string') {
    out.bodyPreview = screenDiagnosticText(out.bodyPreview).text;
  }
  if (Array.isArray(out.parsedKeys) && out.parsedKeys.includes('token')) {
    out.parsedKeys = out.parsedKeys.filter((k) => k !== 'token').concat(['token_redacted']);
  }
  return out;
}

export function containsExposedLocalMutationToken(blob) {
  let text = String(blob).replaceAll(REDACTED_LOCAL_TOKEN, '');
  LOCAL_TOKEN_JSON.lastIndex = 0;
  PLAIN_FIXTURE_TOKEN.lastIndex = 0;
  return LOCAL_TOKEN_JSON.test(text) || PLAIN_FIXTURE_TOKEN.test(text);
}

export function sha256Text(text) {
  return crypto.createHash('sha256').update(text).digest('hex');
}
