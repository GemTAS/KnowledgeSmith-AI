"""Provenance tracking for extracted claims and concepts."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.extraction.models import (
    Claim,
    Concept,
    ExtractionMethod,
    SourceReference,
    VerificationStatus,
)

logger = logging.getLogger("knowledgesmith.knowledge.provenance")


class ProvenanceRecord:
    """Tracks the provenance of a single concept or claim."""

    def __init__(
        self,
        entity_id: str,
        entity_type: str,  # "concept" or "claim"
        source_refs: List[SourceReference],
        extraction_method: ExtractionMethod,
        verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
        generated_at: Optional[datetime] = None,
    ) -> None:
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.source_refs = source_refs
        self.extraction_method = extraction_method
        self.verification_status = verification_status
        self.generated_at = generated_at or datetime.now(timezone.utc)

    @property
    def is_source_derived(self) -> bool:
        """True if this entity was extracted from a specific source location."""
        return bool(self.source_refs)

    @property
    def is_llm_generated(self) -> bool:
        """True if a language model contributed to this entity."""
        return self.extraction_method == ExtractionMethod.LLM

    @property
    def trust_tier(self) -> str:
        """Derive OKF trust tier per §5.3."""
        if self.verification_status == VerificationStatus.HUMAN_REVIEWED:
            return "human-reviewed"
        elif self.verification_status == VerificationStatus.MACHINE_CONFIRMED:
            return "machine-confirmed"
        return "unverified"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "source_refs": [
                {
                    "source_id": r.source_id,
                    "relative_path": r.relative_path,
                    "content_hash": r.content_hash,
                    "start_line": r.start_line,
                    "end_line": r.end_line,
                }
                for r in self.source_refs
            ],
            "extraction_method": self.extraction_method.value,
            "verification_status": self.verification_status.value,
            "trust_tier": self.trust_tier,
            "generated_at": self.generated_at.isoformat(),
            "is_source_derived": self.is_source_derived,
            "is_llm_generated": self.is_llm_generated,
        }


class ProvenanceTracker:
    """Collects and persists provenance records for all entities."""

    def __init__(self) -> None:
        self._records: Dict[str, ProvenanceRecord] = {}

    def track_concept(self, concept: Concept) -> None:
        """Record provenance for a concept."""
        self._records[concept.concept_id] = ProvenanceRecord(
            entity_id=concept.concept_id,
            entity_type="concept",
            source_refs=concept.source_refs,
            extraction_method=concept.extraction_method,
            generated_at=concept.extracted_at,
        )
        # Track claims within the concept.
        for claim in concept.claims:
            self._records[claim.claim_id] = ProvenanceRecord(
                entity_id=claim.claim_id,
                entity_type="claim",
                source_refs=claim.source_refs,
                extraction_method=claim.extraction_method,
                verification_status=claim.verification_status,
                generated_at=claim.extracted_at,
            )

    def get_record(self, entity_id: str) -> Optional[ProvenanceRecord]:
        return self._records.get(entity_id)

    def get_all(self) -> List[ProvenanceRecord]:
        return list(self._records.values())

    def get_unverified(self) -> List[ProvenanceRecord]:
        return [
            r for r in self._records.values()
            if r.verification_status == VerificationStatus.UNVERIFIED
        ]

    def get_llm_generated(self) -> List[ProvenanceRecord]:
        return [r for r in self._records.values() if r.is_llm_generated]

    def save(self, path: Path) -> None:
        """Persist provenance records as JSON."""
        data = [r.to_dict() for r in self._records.values()]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Saved %d provenance records to %s", len(data), path)

    def load(self, path: Path) -> None:
        """Load provenance records from a JSON file."""
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data:
            refs = [
                SourceReference(
                    source_id=r["source_id"],
                    relative_path=r["relative_path"],
                    content_hash=r["content_hash"],
                    start_line=r.get("start_line"),
                    end_line=r.get("end_line"),
                )
                for r in entry.get("source_refs", [])
            ]
            self._records[entry["entity_id"]] = ProvenanceRecord(
                entity_id=entry["entity_id"],
                entity_type=entry["entity_type"],
                source_refs=refs,
                extraction_method=ExtractionMethod(entry["extraction_method"]),
                verification_status=VerificationStatus(entry["verification_status"]),
                generated_at=datetime.fromisoformat(entry["generated_at"]),
            )
        logger.info("Loaded %d provenance records from %s", len(self._records), path)

    @property
    def count(self) -> int:
        return len(self._records)
