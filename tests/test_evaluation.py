"""Tests for evaluation metrics and benchmark suite."""

from backend.app.evaluation.benchmark import KnowledgeBenchmark
from backend.app.evaluation.metrics import compute_metrics
from backend.app.extraction.models import (
    Claim,
    Concept,
    Relationship,
    SourceReference,
    VerificationStatus,
)


def test_metrics_and_benchmark():
    c1 = Concept(
        concept_id="c1",
        title="PaymentGateway",
        concept_type="Class",
        claims=[
            Claim(
                claim_id="cl1",
                statement="Processes credit card payments.",
                source_refs=[
                    SourceReference(
                        source_id="s1",
                        relative_path="pay.py",
                        content_hash="h1",
                        start_line=5,
                    )
                ],
            )
        ],
    )
    c2 = Concept(
        concept_id="c2",
        title="OrderSystem",
        concept_type="Class",
        claims=[],
    )
    r1 = Relationship(
        source_concept_id="c2",
        target_concept_id="c1",
        relationship_type="calls",
    )

    metrics = compute_metrics([c1, c2], [r1])
    assert metrics.total_concepts == 2
    assert metrics.total_claims == 1
    assert metrics.total_relationships == 1
    assert metrics.provenance_integrity == 1.0
    assert metrics.broken_link_rate == 0.0

    benchmark = KnowledgeBenchmark()
    res = benchmark.evaluate([c1, c2], [r1])
    assert res.overall_score > 0
    assert res.letter_grade in ["A", "B", "C", "D", "F"]
    assert len(res.checks) == 5
