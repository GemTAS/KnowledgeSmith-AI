export interface ConceptSummary {
  concept_id: string;
  title: string;
  concept_type: string;
  description: string;
  tags: string[];
  claims_count: number;
}

export interface ClaimSummary {
  claim_id: string;
  statement: string;
  extraction_method: string;
  verification_status: string;
  confidence?: number;
  source_count: number;
}

export interface ConceptDetail {
  concept_id: string;
  title: string;
  concept_type: string;
  description: string;
  tags: string[];
  claims: ClaimSummary[];
  relationships: {
    source_id: string;
    target_id: string;
    relationship_type: string;
    evidence?: string;
  }[];
  metadata: Record<string, unknown>;
}

export interface GraphNode {
  id: string;
  title: string;
  type: string;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  evidence?: string;
}

export interface GraphResponse {
  node_count: number;
  edge_count: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  statistics: Record<string, unknown>;
}

export interface BenchmarkCheck {
  name: string;
  target: string;
  actual: string | number;
  passed: boolean;
  description: string;
}

export interface EvaluationData {
  metrics: {
    total_concepts: number;
    total_claims: number;
    total_relationships: number;
    total_source_files: number;
    concept_coverage: number;
    claim_density: number;
    orphan_concepts: number;
    orphan_rate: number;
    missing_targets: number;
    broken_link_rate: number;
    provenance_integrity: number;
    line_level_evidence_rate: number;
    trust_distribution: Record<string, number>;
    validation_errors: number;
    validation_warnings: number;
    validation_pass_rate: number;
    composite_health_score: number;
  };
  benchmark: {
    passed: boolean;
    overall_score: number;
    letter_grade: string;
    summary: string;
    checks: BenchmarkCheck[];
  };
}

export interface ValidationIssue {
  severity: string;
  code: string;
  message: string;
  concept_id?: string;
}

export interface ValidationData {
  is_valid: boolean;
  error_count: number;
  warning_count: number;
  issues: ValidationIssue[];
}
