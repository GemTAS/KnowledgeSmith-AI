"""Validated data models for extraction results."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Trust level of an extracted claim."""

    UNVERIFIED = "unverified"
    MACHINE_CONFIRMED = "machine_confirmed"
    HUMAN_REVIEWED = "human_reviewed"


class ExtractionMethod(str, Enum):
    """How a concept or claim was extracted."""

    DETERMINISTIC = "deterministic"
    LLM = "llm"
    MANUAL = "manual"


class SourceReference(BaseModel):
    """A provenance reference back to the original source."""

    source_id: str = Field(description="Stable identifier for the source file")
    relative_path: str = Field(description="Relative path within ingestion root")
    content_hash: str = Field(description="SHA-256 of the source content at extraction time")
    start_line: Optional[int] = Field(default=None, description="Starting line (1-indexed)")
    end_line: Optional[int] = Field(default=None, description="Ending line (1-indexed)")
    snippet: Optional[str] = Field(default=None, description="Relevant source excerpt")


class Claim(BaseModel):
    """A single factual assertion extracted from source material."""

    claim_id: str = Field(description="Unique claim identifier")
    statement: str = Field(description="The claim text")
    source_refs: List[SourceReference] = Field(default_factory=list)
    extraction_method: ExtractionMethod = ExtractionMethod.DETERMINISTIC
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Extraction confidence (only meaningful for LLM extraction)",
    )
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Relationship(BaseModel):
    """A directed relationship between two concepts."""

    source_concept_id: str
    target_concept_id: str
    relationship_type: str = Field(description="e.g. 'imports', 'depends_on', 'related_to'")
    evidence: Optional[str] = Field(default=None, description="Source evidence for this link")
    extraction_method: ExtractionMethod = ExtractionMethod.DETERMINISTIC


class Concept(BaseModel):
    """A knowledge concept extracted from source material."""

    concept_id: str = Field(description="Stable, unique concept identifier")
    title: str = Field(description="Human-readable concept name")
    concept_type: str = Field(
        default="Reference",
        description="OKF type field, e.g. 'Module', 'Class', 'Function', 'Reference'",
    )
    description: str = Field(default="", description="One-line summary")
    claims: List[Claim] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    source_refs: List[SourceReference] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    extraction_method: ExtractionMethod = ExtractionMethod.DETERMINISTIC
    metadata: Dict[str, str] = Field(default_factory=dict)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExtractionResult(BaseModel):
    """Aggregate result of extracting concepts from one or more sources."""

    concepts: List[Concept] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    source_file_count: int = 0
    extraction_method: ExtractionMethod = ExtractionMethod.DETERMINISTIC


class ChangeType(str, Enum):
    """Type of detected source modification."""

    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"


class ChangeRecord(BaseModel):
    """Records a detected change in the source material."""

    source_id: str
    relative_path: str
    change_type: str = Field(description="'added', 'modified', or 'removed'")
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def file_path(self) -> str:
        return self.relative_path

    @property
    def previous_hash(self) -> Optional[str]:
        return self.old_hash

    @property
    def current_hash(self) -> Optional[str]:
        return self.new_hash
