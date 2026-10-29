"""Conflict detection for knowledge artifacts."""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from backend.app.extraction.models import Concept, Claim

logger = logging.getLogger("knowledgesmith.knowledge.conflict_detector")


def detect_claim_conflicts(concepts: List[Concept]) -> List[Dict]:
    """Detect potentially conflicting claims across concepts.

    A conflict is detected when two claims make assertions about the same
    subject but with different statements (heuristic: same concept title
    referenced in different claim texts).
    """
    conflicts: List[Dict] = []

    # Group claims by the concept they belong to.
    all_claims: List[Tuple[str, Claim]] = []
    for concept in concepts:
        for claim in concept.claims:
            all_claims.append((concept.concept_id, claim))

    # Simple heuristic: look for claims with contradictory keywords.
    # This is a surface-level check, not semantic understanding.
    for i, (cid1, claim1) in enumerate(all_claims):
        for j, (cid2, claim2) in enumerate(all_claims):
            if j <= i:
                continue
            if cid1 == cid2:
                continue
            # Check for overlapping subjects with different assertions.
            s1_words = set(claim1.statement.lower().split())
            s2_words = set(claim2.statement.lower().split())
            overlap = s1_words & s2_words
            # Significant overlap with different statements suggests potential conflict.
            if len(overlap) > 5 and claim1.statement != claim2.statement:
                conflicts.append({
                    "concept_1": cid1,
                    "claim_1": claim1.statement[:100],
                    "concept_2": cid2,
                    "claim_2": claim2.statement[:100],
                    "shared_terms": len(overlap),
                })

    if conflicts:
        logger.info("Detected %d potential claim conflicts.", len(conflicts))
    return conflicts
