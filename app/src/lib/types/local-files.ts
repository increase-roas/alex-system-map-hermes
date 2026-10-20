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
