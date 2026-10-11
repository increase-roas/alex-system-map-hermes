export type CatalogComponent = {
  id: string;
  name: string;
  layer_id: string;
  kind: string;
  aliases: string[];
  purpose: string;
  boundary: string;
  category: string;
  evidence_level: string;
  observed_condition: string;
  evidence_ids: string[];
  source_record_ids: string[];
};

export type CatalogRelationship = {
  id: string;
  source_id: string;
  target_id: string;
  type: string;
  label: string;
  category: string;
  evidence_level: string;
  observed_condition: string;
  evidence_ids: string[];
};

export type CatalogIssue = {
  id: string;
  subject_id: string;
  severity: string;
  status: string;
  category: string;
  summary: string;
  evidence_ids: string[];
};

export type CatalogSource = {
  id: string;
  kind: string;
  group?: string;
  relative_path?: string;
  original_path?: string;
  archive?: string;
  archive_member?: string;
  sha256?: string;
  bytes?: number;
};

export type CatalogBundle = {
  loaded_at: string;
  foundation_root: string;
  data: {
    components: CatalogComponent[];
    relationships: CatalogRelationship[];
    sources: CatalogSource[];
    evidence: Record<string, unknown>[];
    issues: CatalogIssue[];
    coverage: Record<string, unknown>[];
    'source-records': Record<string, unknown>[];
    layers: { id: string; name: string; order: number }[];
    'table-index': Record<string, unknown>[];
  };
  overview_memberships: {
    component_id: string;
    layer_id: string;
    parent_id: string | null;
    order: number;
    collapsed?: boolean;
    synthetic?: boolean;
  }[];
  membership_is_runtime_relationship: boolean;
  dangling_relationship_ids: string[];
  load_gaps: { file: string; error: string; expected_sha256?: string }[];
  completeness?: {
    components: number;
    relationships: number;
    coverage: number;
    overview_memberships: number;
    load_gaps: number;
    dangling_relationships: number;
    complete: boolean;
  };
};
