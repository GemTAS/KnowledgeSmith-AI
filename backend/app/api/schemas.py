"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check endpoint response."""

    status: str = "ok"
    version: str = "0.1.0"
    platform: str = "KnowledgeSmith AI"


class PipelineRunRequest(BaseModel):
    """Request payload to trigger an autonomous pipeline execution."""

    input_dir: Optional[str] = Field(
        default=None,
        description="Path to directory containing source files. Defaults to ingestion_root.",
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="Path to directory to output OKF artifacts. Defaults to output_dir.",
    )
    use_llm: bool = Field(
        default=False,
        description="Whether to run the LLM-based extractor in addition to deterministic.",
    )
    model_name: str = Field(
        default="gemini-2.5-flash",
        description="Model to use if LLM extraction is enabled.",
    )
    overwrite: bool = Field(
        default=True,
        description="Whether to overwrite existing artifacts in the output directory.",
    )


class IngestRequest(BaseModel):
    """Request payload to scan and ingest source files directly."""

    root_dir: str = Field(description="Root directory path to scan.")
    max_file_size: Optional[int] = Field(
        default=1_048_576,
        description="Maximum file size in bytes.",
    )
    allowed_extensions: Optional[List[str]] = Field(
        default=None,
        description="List of file extensions to include.",
    )


class IngestFileSummary(BaseModel):
    """Summary of an ingested file."""

    relative_path: str
    source_id: str
    size_bytes: int
    extension: str
    content_hash: str


class IngestResponse(BaseModel):
    """Response containing scan and ingestion results."""

    total_files: int
    files: List[IngestFileSummary]
    skipped_count: int
    errors: List[str]


class ClaimSummary(BaseModel):
    """Claim representation in API responses."""

    claim_id: str
    statement: str
    extraction_method: str
    verification_status: str
    confidence: Optional[float] = None
    source_count: int = 0


class ConceptSummary(BaseModel):
    """Compact concept representation for list views."""

    concept_id: str
    title: str
    concept_type: str
    description: str
    tags: List[str] = Field(default_factory=list)
    claims_count: int = 0


class ConceptDetail(BaseModel):
    """Detailed concept representation."""

    concept_id: str
    title: str
    concept_type: str
    description: str
    tags: List[str] = Field(default_factory=list)
    claims: List[ClaimSummary] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConceptListResponse(BaseModel):
    """Response containing a list of concepts."""

    total: int
    concepts: List[ConceptSummary]


class GraphNodeItem(BaseModel):
    """Graph node item."""

    id: str
    title: str
    type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdgeItem(BaseModel):
    """Graph edge item."""

    source: str
    target: str
    type: str
    evidence: Optional[str] = None


class GraphResponse(BaseModel):
    """Full knowledge graph representation."""

    node_count: int
    edge_count: int
    nodes: List[GraphNodeItem]
    edges: List[GraphEdgeItem]
    statistics: Dict[str, Any]


class ValidationIssueItem(BaseModel):
    """Issue detail in validation response."""

    severity: str
    code: str
    message: str
    concept_id: Optional[str] = None


class ValidationResponse(BaseModel):
    """Validation report response."""

    is_valid: bool
    error_count: int
    warning_count: int
    issues: List[ValidationIssueItem]


class EvaluationResponse(BaseModel):
    """Evaluation metrics and benchmark assessment response."""

    metrics: Dict[str, Any]
    benchmark: Dict[str, Any]


class ChangeRecordItem(BaseModel):
    """Change record item in incremental update response."""

    file_path: str
    change_type: str
    previous_hash: Optional[str] = None
    current_hash: Optional[str] = None


class ChangesResponse(BaseModel):
    """Change detection summary response."""

    total_changes: int
    changes: List[ChangeRecordItem]
