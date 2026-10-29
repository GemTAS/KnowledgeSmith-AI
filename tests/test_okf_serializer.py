"""Tests for OKF v0.2 serialization conformance."""

import pytest
from pathlib import Path

from backend.app.extraction.models import (
    Claim,
    Concept,
    ExtractionMethod,
    Relationship,
    SourceReference,
    VerificationStatus,
)
from backend.app.knowledge.okf_serializer import (
    generate_index,
    serialize_concept,
    write_concept_file,
)


def test_serialize_concept_frontmatter():
    concept = Concept(
        concept_id="auth/token_manager",
        title="TokenManager",
        concept_type="Class",
        description="Handles authentication token issuance.",
        tags=["auth", "security"],
        claims=[
            Claim(
                claim_id="c1",
                statement="Issues signed JWT tokens for authenticated sessions.",
                source_refs=[
                    SourceReference(
                        source_id="src1",
                        relative_path="auth.py",
                        content_hash="abc",
                        start_line=10,
                    )
                ],
            )
        ],
    )
    rels = [
        Relationship(
            source_concept_id="auth/token_manager",
            target_concept_id="db/pool",
            relationship_type="depends_on",
            evidence="Imports db connection",
        )
    ]

    serialized = serialize_concept(concept, rels)
    # OKF Spec validation
    assert serialized.startswith("---")
    assert "type: Class" in serialized or "type: class" in serialized.lower()
    assert "title: TokenManager" in serialized
    assert "sources:" in serialized
    assert "generated:" in serialized
    assert "status:" in serialized
    # Markdown body
    assert "# TokenManager" in serialized
    assert "## Claims" in serialized or "## Factual Claims" in serialized
    assert "## Relationships" in serialized
    assert "depends_on" in serialized


def test_write_and_index(tmp_path: Path):
    concept1 = Concept(
        concept_id="module_a",
        title="Module A",
        concept_type="Module",
        description="Description A",
    )
    concept2 = Concept(
        concept_id="sub/module_b",
        title="Module B",
        concept_type="Class",
        description="Description B",
    )

    path1 = write_concept_file(concept1, [], tmp_path, overwrite=True)
    path2 = write_concept_file(concept2, [], tmp_path, overwrite=True)
    assert path1.exists()
    assert path2.exists()

    index_path = generate_index(tmp_path, [concept1, concept2])
    assert index_path.exists()
    index_content = index_path.read_text(encoding="utf-8")
    assert "Module A" in index_content
    assert "Module B" in index_content
