import { NextResponse } from 'next/server';

import { mutationAuthError } from '@/lib/server/local-auth';
import { runLocalService } from '@/lib/server/python';

export async function POST(request: Request) {
  const denied = await mutationAuthError(request);
  if (denied) return denied;
  const body = await request.json();
  const relative = String(body.path ?? '');
  const expectedSha256 = String(body.expected_sha256 ?? '');
  const document = body.document;
  const operationId = body.operation_id ? String(body.operation_id) : undefined;
  const recordId = body.record_id ? String(body.record_id) : undefined;
  const nextRevision =
    body.next_revision !== undefined && body.next_revision !== null
      ? String(body.next_revision)
      : undefined;
  if (!relative || !expectedSha256 || !document) {
    return NextResponse.json({ error: 'path, expected_sha256, and document required' }, { status: 400 });
  }
  const previewArgs = [
    'catalog-edit-preview',
    relative,
    expectedSha256,
    JSON.stringify(document),
    ...(recordId ? ['--record-id', recordId] : []),
    ...(nextRevision ? ['--next-revision', nextRevision] : []),
  ];
  if (body.preview_only) {
    const preview = await runLocalService(previewArgs);
    return NextResponse.json(preview);
  }
  const applyArgs = [
    'catalog-edit-apply',
    relative,
    expectedSha256,
    JSON.stringify(document),
    ...(operationId ? ['--operation-id', operationId] : []),
    ...(recordId ? ['--record-id', recordId] : []),
    ...(nextRevision ? ['--next-revision', nextRevision] : []),
  ];
  const applied = await runLocalService(applyArgs);
  return NextResponse.json(applied);
}
