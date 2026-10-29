"""Tests for OKF artifact validator."""

from backend.app.extraction.models import Concept, Relationship
from backend.app.knowledge.validator import validate_concepts


def test_validator_detects_missing_type():
    concept = Concept(
        concept_id="c1",
        title="Test Concept",
        concept_type="",  # Missing required type
        description="A concept without type",
    )
    result = validate_concepts([concept], [])
    assert not result.is_valid
    assert result.error_count == 1
    assert any(i.code == "MISSING_TYPE" for i in result.issues)


def test_validator_detects_duplicate_ids():
    c1 = Concept(concept_id="dup_id", title="Title 1", concept_type="Class")
    c2 = Concept(concept_id="dup_id", title="Title 2", concept_type="Class")
    result = validate_concepts([c1, c2], [])
    assert any(i.code == "DUPLICATE_ID" for i in result.issues)


def test_validator_detects_broken_link():
    c1 = Concept(concept_id="valid_node", title="Valid", concept_type="Class")
    rel = Relationship(
        source_concept_id="valid_node",
        target_concept_id="non_existent_node",
        relationship_type="references",
    )
    result = validate_concepts([c1], [rel])
    assert any(i.code == "BROKEN_LINK" for i in result.issues)
