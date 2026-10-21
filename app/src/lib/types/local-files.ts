export type LocalFile = {
  id: string; path: string; real_path: string | null; root: string; relative_path: string;
  kind: 'rule' | 'skill' | 'hook' | 'config' | 'handoff' | 'document' | 'script';
  state: 'readable' | 'missing' | 'unreadable' | 'too_large' | 'changed_during_scan';
  bytes: number | null; mtime: string | null; sha256: string | null; line_count: number | null;
  is_symlink: boolean; link_target: string | null; generated: boolean; generated_sources: string[];
};
export type LocalEvidence = { file_id: string; line: number; text: string };
export type LocalFinding = {
  id: string; kind: 'conflict_candidate' | 'repeated_rule'; topic: string;
  reason: string; confidence: 'candidate' | 'exact'; evidence: LocalEvidence[];
};
export type LocalDuplicate = { id: string; kind: 'same_file' | 'identical_copy'; file_ids: string[]; reason: string };
export type LocalReference = { source_id: string; target_id: string; kind: 'symlink' | 'generated_from' | 'references'; line: number | null };
export type LocalFileIndex = {
  schema_version: 1; scanned_at: string; home: string; files: LocalFile[];
  duplicates: LocalDuplicate[]; findings: LocalFinding[]; references: LocalReference[];
  coverage: {
    roots: { path: string; label: string; state: string; files: number }[];
    exclusions: string[]; limits: { max_files: number; max_depth: number; max_bytes: number };
    truncated: boolean; skipped: { reason: string; count: number }[]; errors: string[];
  };
};
export type LocalFileContent = {
  file_id: string; path: string; scanned_sha256: string | null; current_sha256: string | null;
  changed_since_scan: boolean; read_at: string; content: string; redacted: boolean; truncated: boolean;
  error?: string;
};

export type LocalRepairSource = {
  file_id: string; path: string; sha256: string | null; content: string;
  editable: boolean; reason: string; source_file_ids: string[];
};
export type LocalRepairApplicability = { role: string; scope: string; activation: string; limitations: string[] };
export type LocalRepairCase = {
  id: string; scenario: string; purpose: 'fix' | 'preserve'; choices: { A: string; B: string; C: string };
  expected: 'A' | 'B' | 'C'; before: 'A' | 'B' | 'C' | 'unknown'; after: 'A' | 'B' | 'C' | 'unknown';
  status: 'passed' | 'failed' | 'unknown'; rationale: string; evidence: LocalRepairCitation[];
};
export type LocalRepairChecks = {
  status: 'passed' | 'failed' | 'unavailable'; checked_at: string; model: string;
  cases: LocalRepairCase[]; limitations: string[];
};
export type LocalRepairDistributionPlan = {
  status: 'ready' | 'not_needed' | 'blocked';
  targets: { path: string; before_sha256: string | null; after_sha256: string; diff: string; kind: 'generated' | 'import'; requires_new_session: boolean }[];
  limitations: string[];
};
export type LocalRepairPreview = {
  repair_id: string; file_id: string; path: string; before_sha256: string;
  after_sha256: string; proposal_sha256: string; diff: string;
  created_at: string; expires_at: string; generated_follow_up: boolean;
  checks?: LocalRepairChecks | null; distribution?: LocalRepairDistributionPlan;
};
export type LocalRepairResult = {
  repair_id: string; file_id: string; path: string;
  state: 'applied' | 'applied_publish_pending' | 'undone' | 'undone_publish_pending';
  current_sha256: string; backup_path: string; commit: string | null;
  source_verified?: boolean; pushed: boolean; generated_follow_up: boolean; message: string;
  distribution?: { status: 'verified' | 'pending' | 'not_needed'; targets: { path: string; status: 'verified' | 'pending'; sha256: string | null; reason: string }[]; message: string };
};

export type LocalRepairCitation = { file_id: string; line: number; quote: string };
export type LocalRepairSuggestion = {
  status: 'proposed' | 'no_change' | 'needs_decision';
  summary: string; rationale: string;
  conflicts: { explanation: string; evidence: LocalRepairCitation[] }[];
  limitations: string[];
  context_files: { file_id: string; path: string; sha256: string; applicability?: LocalRepairApplicability }[];
  checks: LocalRepairChecks | null;
  model: string; generated_at: string;
  proposed_content: string | null; preview: LocalRepairPreview | null;
};
