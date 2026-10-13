// Shared helpers for the Langflow API routes. Route files stay thin; the rules live in the lib modules.

import { NextResponse } from 'next/server';

import { screenText } from './redact';

export const MAX_BODY_BYTES = 2_000_000;

export function fail(status: number, message: string, extra: Record<string, unknown> = {}): NextResponse {
  return NextResponse.json({ error: message, ...extra }, { status, headers: { 'Cache-Control': 'no-store' } });
}

export function ok(body: unknown, status = 200): NextResponse {
  return NextResponse.json(body, { status, headers: { 'Cache-Control': 'no-store' } });
}

/** 413 when the body is too large; 422 when it is not JSON. Callers pass both straight to fail(). */
export async function readJson(
  request: Request,
): Promise<{ ok: true; value: unknown } | { ok: false; status: 413 | 422; message: string }> {
  const tooLarge = { ok: false as const, status: 413 as const, message: `The request is larger than ${MAX_BODY_BYTES / 1_000_000} MB.` };
  const declared = Number(request.headers.get('content-length') ?? '0');
  if (declared > MAX_BODY_BYTES) return tooLarge;
  const text = await request.text();
  if (text.length > MAX_BODY_BYTES) return tooLarge;
  try {
    return { ok: true, value: JSON.parse(text) as unknown };
  } catch {
    return { ok: false, status: 422, message: 'The request body is not valid JSON.' };
  }
}

/** Screens every string in a JSON value, so nothing credential-shaped leaves the server. */
export function screenDeep<T>(value: T): T {
  if (typeof value === 'string') return screenText(value) as unknown as T;
  if (Array.isArray(value)) return value.map((v) => screenDeep(v)) as unknown as T;
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) out[k] = screenDeep(v);
    return out as unknown as T;
  }
  return value;
}
