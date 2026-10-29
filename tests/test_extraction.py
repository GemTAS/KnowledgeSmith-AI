"""Tests for concept, claim, and relationship extraction."""

import pytest
from pathlib import Path

from backend.app.extraction.deterministic import extract_deterministic
from backend.app.extraction.models import (
    Concept,
    ExtractionMethod,
    ExtractionResult,
    VerificationStatus,
)
from backend.app.ingestion.loader import SourceFile


def test_deterministic_python_extraction():
    content = '''"""User management module."""

class UserManager:
    """Manages active user profiles."""
    def create_user(self, name: str):
        return {"name": name}

def helper_util():
    pass
'''
    sf = SourceFile(
        path=Path("user_service.py"),
        relative_path="user_service.py",
        content=content,
        content_hash="abc123hash",
        source_id="src001",
        size_bytes=len(content),
        extension=".py",
    )

    res: ExtractionResult = extract_deterministic([sf])
    assert len(res.concepts) >= 3  # Module + Class + Function

    titles = [c.title for c in res.concepts]
    assert "UserManager" in titles
    assert any("user" in t.lower() for t in titles)

    # Trust check: deterministic claims must default to unverified
    for c in res.concepts:
        assert c.extraction_method == ExtractionMethod.DETERMINISTIC
        for claim in c.claims:
            assert claim.verification_status == VerificationStatus.UNVERIFIED


def test_deterministic_markdown_extraction():
    md_content = """# Architecture Overview
This system processes raw knowledge.

## Ingestion Pipeline
Ingests source files safely.
"""
    sf = SourceFile(
        path=Path("docs/arch.md"),
        relative_path="docs/arch.md",
        content=md_content,
        content_hash="mdhash999",
        source_id="src002",
        size_bytes=len(md_content),
        extension=".md",
    )

    res = extract_deterministic([sf])
    titles = [c.title for c in res.concepts]
    assert "Architecture Overview" in titles or "Ingestion Pipeline" in titles
