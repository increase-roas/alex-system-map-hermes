/** Public wire schema v1. Browser submits IDs and intent only. */
export type RepairCheck = {
  kind: 'guidance_support' | 'simulated_behavior' | 'native_behavior' | 'syntax' | 'owner_lifecycle' | 'native_dry_run' | 'readback' | 'runtime';
  status: 'passed' | 'failed' | 'unavailable'; runner_id: string;
  input_digest?: string; output_digest?: string; evidence: string[];
  checked_at?: string; limitations: string[];
};
export type RepairTarget = {
  id: string; adapter_id: string; category: string; owner: string;
  scope: 'local' | 'remote'; identity: Record<string, unknown>;
  capabilities: string[]; observed_at: string; evidence: string[];
  limitations: string[]; missing_capability?: string;
  allowed_patch_paths?: string[]; content_format?: 'text' | 'json'; source_language?: string;
  related_target_ids?: string[]; hook_behavior_profile?: string;
  hook_hosts?: { runtime: string; config_target_id: string; registration_digest: string }[];
};
export type RepairOperation = {
  step_id: string; target_id: string; adapter_id: string; adapter_version: string;
  action: string; public_diff: string; checks: RepairCheck[];
  expected_fingerprint?: string; expected_version?: string;
};
export type RepairGuidance = {
  schema_version: 1; retrieved_at: string; expires_at: string; route: string;
  sources: { id: string; url: string; title: string; publisher: string; content_sha256: string;
    version: string | null; publication_date: string | null; crawl_status: 'crawled' | 'cached' | 'unknown';
    retrieved_at: string; passages: { id: string; text: string }[]; target_ids: string[] }[];
  coverage: { target_id: string; source_ids: string[]; status: 'available' | 'unavailable'; limitations: string[] }[];
  limitations: string[];
};
export type RepairRationale = {
  target_id: string; diagnosis: string; recommendation: string;
  practice_kind: 'native_contract' | 'vendor_recommendation' | 'alex_policy' | 'inference';
  applicability: string; guidance_evidence: { source_id: string; passage_id: string; quote: string }[];
  alternatives: { option: string; why_rejected: string }[]; limitations: string[];
};
export type RepairGuidanceAssessment = {
  status: 'passed' | 'failed' | 'unavailable';
  findings: { target_id: string; status: 'supported' | 'unsupported' | 'uncertain'; reason: string }[];
  limitations: string[];
};
export type RepairResearch = { guidance?: RepairGuidance; rationales?: RepairRationale[]; guidance_assessment?: RepairGuidanceAssessment };
export type RepairPlan = RepairResearch & {
  schema_version: 1; plan_id: string; digest: string; created_at: string;
  proposal_target_ids?: string[];
  expires_at: string; intent: string; targets: RepairTarget[];
  operations: RepairOperation[]; checks: RepairCheck[]; limitations: string[];
};
export type RepairReceipt = {
  ok: boolean; state: 'written' | 'byte_verified' | 'effective' | 'reloaded' | 'pending' | 'blocked' | 'unknown' | 'undone';
  fingerprint?: string; evidence: string[]; checks: RepairCheck[]; limitations: string[];
};
export type RepairStep = { step_id: string; target_id: string; phase: string; outcome?: string; receipt?: RepairReceipt };
export type RepairJob = {
  schema_version: 1; job_id: string; plan_id: string; digest: string;
  status: 'queued' | 'preflight' | 'applying' | 'unknown' | 'blocked' | 'completed' | 'undoing' | 'undone';
  next_step: number; steps: RepairStep[]; events: { at: string; phase: string; step_id?: string }[];
  unknown_effect: string | null; error?: string; created_at: string; updated_at: string;
};
export type RepairRequest =
  | { action: 'propose'; target_ids: string[]; intent: string }
  | { action: 'apply'; plan_id: string; digest: string };
export type RepairJobRequest = { action: 'resume' | 'reconcile' | 'undo' };
export type RepairInventory = { schema_version: 1; targets: RepairTarget[]; limitations: string[] };
