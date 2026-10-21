import { mutationAuthError } from '@/lib/server/local-auth';
import { invalidRepairRequest, repairBody, repairResponse } from '@/lib/server/universal-repairs';
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const denied = await mutationAuthError(request);
  if (denied) return denied;
  const query = new URL(request.url).searchParams;
  if (!query.size) return repairResponse({ action: 'discover' });
  if (query.size !== 1) return invalidRepairRequest();
  if (query.has('target_id') && query.get('target_id')) return repairResponse({ action: 'source', target_id: query.get('target_id') });
  if (query.has('plan_id') && /^[a-f0-9]{32}$/.test(query.get('plan_id') || '')) return repairResponse({ action: 'plan', plan_id: query.get('plan_id') });
  return invalidRepairRequest();
}

export async function POST(request: Request) {
  const denied = await mutationAuthError(request);
  if (denied) return denied;
  const value = await repairBody(request);
  if (!value) return invalidRepairRequest();
  if (value.action === 'propose' && Object.keys(value).length === 3 && Array.isArray(value.target_ids) && value.target_ids.length > 0 && value.target_ids.every((id) => typeof id === 'string' && id.length > 0) && typeof value.intent === 'string' && value.intent.trim()) return repairResponse(value);
  if (value.action === 'apply' && Object.keys(value).length === 3 && typeof value.plan_id === 'string' && /^[a-f0-9]{32}$/.test(value.plan_id) && typeof value.digest === 'string' && /^[a-f0-9]{64}$/.test(value.digest)) return repairResponse(value);
  return invalidRepairRequest();
}
