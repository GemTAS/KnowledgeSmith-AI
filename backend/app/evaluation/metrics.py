"""Evaluation metrics for knowledge engineering bundles."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.extraction.models import Concept, Relationship, VerificationStatus
from backend.app.ingestion.loader import SourceFile
from backend.app.knowledge.graph import KnowledgeGraph
from backend.app.knowledge.validator import ValidationResult

logger = logging.getLogger("knowledgesmith.evaluation.metrics")


@dataclass
class EvaluationMetrics:
    """Quantitative metrics describing the quality and completeness of extracted knowledge."""

    total_concepts: int = 0
    total_claims: int = 0
    total_relationships: int = 0
    total_source_files: int = 0

    # Yield & Density
    concept_coverage: float = 0.0  # concepts per file
    claim_density: float = 0.0  # claims per concept

    # Graph Topology
    orphan_concepts: int = 0  # isolated nodes
    orphan_rate: float = 0.0  # orphans / total_concepts
    missing_targets: int = 0  # dangling edge targets
    broken_link_rate: float = 0.0

    # Provenance & Trust
    provenance_integrity: float = 0.0  # claims with valid source references (%)
    line_level_evidence_rate: float = 0.0  # claims with line-level evidence (%)
    trust_distribution: Dict[str, int] = field(default_factory=dict)

    # Validation & Health
    validation_errors: int = 0
    validation_warnings: int = 0
    validation_pass_rate: float = 1.0  # 0.0 to 1.0
    composite_health_score: float = 100.0  # 0 to 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_concepts": self.total_concepts,
            "total_claims": self.total_claims,
            "total_relationships": self.total_relationships,
            "total_source_files": self.total_source_files,
            "concept_coverage": round(self.concept_coverage, 2),
            "claim_density": round(self.claim_density, 2),
            "orphan_concepts": self.orphan_concepts,
            "orphan_rate": round(self.orphan_rate, 4),
            "missing_targets": self.missing_targets,
            "broken_link_rate": round(self.broken_link_rate, 4),
            "provenance_integrity": round(self.provenance_integrity, 4),
            "line_level_evidence_rate": round(self.line_level_evidence_rate, 4),
            "trust_distribution": self.trust_distribution,
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
            "validation_pass_rate": round(self.validation_pass_rate, 4),
            "composite_health_score": round(self.composite_health_score, 1),
        }


def compute_metrics(
    concepts: List[Concept],
    relationships: List[Relationship],
    source_files: Optional[List[SourceFile]] = None,
    graph: Optional[KnowledgeGraph] = None,
    validation: Optional[ValidationResult] = None,
) -> EvaluationMetrics:
    """Compute comprehensive evaluation metrics for an extracted knowledge bundle."""
    num_concepts = len(concepts)
    all_claims = [claim for c in concepts for claim in c.claims]
    num_claims = len(all_claims)
    num_rels = len(relationships)
    num_files = len(source_files) if source_files is not None else 1

    # If graph is not supplied, build temporary one
    if graph is None:
        graph = KnowledgeGraph()
        graph.build_from(concepts, relationships)

    graph_stats = graph.statistics()
    missing_targets = graph_stats.get("missing_targets", [])
    num_missing = len(missing_targets)
    orphan_count = graph_stats.get("orphan_count", 0)

    # Coverage & density
    coverage = (num_concepts / num_files) if num_files > 0 else 0.0
    density = (num_claims / num_concepts) if num_concepts > 0 else 0.0
    orphan_rate = (orphan_count / num_concepts) if num_concepts > 0 else 0.0
    broken_link_rate = (num_missing / num_rels) if num_rels > 0 else 0.0

    # Provenance integrity
    claims_with_prov = 0
    claims_with_line = 0
    trust_counts: Dict[str, int] = {
        VerificationStatus.UNVERIFIED.value: 0,
        VerificationStatus.MACHINE_CONFIRMED.value: 0,
        VerificationStatus.HUMAN_REVIEWED.value: 0,
    }

    for claim in all_claims:
        trust_counts[claim.verification_status.value] = (
            trust_counts.get(claim.verification_status.value, 0) + 1
        )
        if claim.source_refs:
            # Check ref validity
            has_valid_ref = any(r.source_id and r.content_hash for r in claim.source_refs)
            if has_valid_ref:
                claims_with_prov += 1
            if any(r.start_line is not None for r in claim.source_refs):
                claims_with_line += 1

    prov_integrity = (claims_with_prov / num_claims) if num_claims > 0 else 1.0
    line_evidence_rate = (claims_with_line / num_claims) if num_claims > 0 else 0.0

    # Validation pass rate
    val_errors = validation.error_count if validation else 0
    val_warnings = validation.warning_count if validation else 0
    val_pass_rate = (
        max(0.0, (num_concepts - val_errors) / num_concepts) if num_concepts > 0 else 1.0
    )

    # Composite health score (0 - 100)
    # Weights: Validation 30%, Provenance 30%, Graph Connectivity 20%, Line Evidence 20%
    connectivity_factor = max(0.0, 1.0 - orphan_rate - broken_link_rate)
    composite = (
        (val_pass_rate * 30.0)
        + (prov_integrity * 30.0)
        + (connectivity_factor * 20.0)
        + (line_evidence_rate * 20.0)
    )
    composite = max(0.0, min(100.0, composite))

    return EvaluationMetrics(
        total_concepts=num_concepts,
        total_claims=num_claims,
        total_relationships=num_rels,
        total_source_files=num_files,
        concept_coverage=coverage,
        claim_density=density,
        orphan_concepts=orphan_count,
        orphan_rate=orphan_rate,
        missing_targets=num_missing,
        broken_link_rate=broken_link_rate,
        provenance_integrity=prov_integrity,
        line_level_evidence_rate=line_evidence_rate,
        trust_distribution=trust_counts,
        validation_errors=val_errors,
        validation_warnings=val_warnings,
        validation_pass_rate=val_pass_rate,
        composite_health_score=composite,
    )
