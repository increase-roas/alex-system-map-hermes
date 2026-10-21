import { mutationAuthError } from '@/lib/server/local-auth';
import { invalidRepairRequest, repairBody, repairResponse } from '@/lib/server/universal-repairs';
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
type Context = { params: Promise<{ jobId: string }> };

export async function GET(request: Request, context: Context) {
  const denied = await mutationAuthError(request);
  if (denied) return denied;
  const { jobId } = await context.params;
  if (!/^[a-f0-9]{32}$/.test(jobId) || new URL(request.url).searchParams.size) return invalidRepairRequest();
  return repairResponse({ action: 'job', job_id: jobId });
}

export async function POST(request: Request, context: Context) {
  const denied = await mutationAuthError(request);
  if (denied) return denied;
  const { jobId } = await context.params;
  const value = await repairBody(request);
  if (!/^[a-f0-9]{32}$/.test(jobId) || !value || Object.keys(value).length !== 1 || !['resume', 'reconcile', 'undo'].includes(String(value.action))) return invalidRepairRequest();
  return repairResponse({ action: value.action, job_id: jobId });
}
