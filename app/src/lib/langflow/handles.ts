// Langflow stores each edge's sourceHandle and targetHandle as a JSON string in which every
// double quote is replaced by the character "œ". Decode before parsing; keep the raw string
// untouched on save so Langflow sees exactly what it wrote.

export type HandleObject = Record<string, unknown>;

export class HandleDecodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'HandleDecodeError';
  }
}

export function decodeHandle(raw: unknown): HandleObject {
  if (typeof raw !== 'string') {
    throw new HandleDecodeError('handle is not a string');
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw.replaceAll('œ', '"'));
  } catch {
    throw new HandleDecodeError('handle is not valid JSON after decoding');
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new HandleDecodeError('handle is not an object');
  }
  return parsed as HandleObject;
}

/** Same encoding Langflow uses (default JSON separators, quotes swapped for "œ"). */
export function encodeHandle(handle: HandleObject): string {
  return JSON.stringify(handle).replaceAll('"', 'œ');
}
