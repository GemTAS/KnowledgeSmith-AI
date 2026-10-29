"""Tests for the ingestion package (loader, hashing, chunker)."""

import pytest
from pathlib import Path

from backend.app.ingestion.chunker import chunk_by_headings, chunk_by_size
from backend.app.ingestion.hashing import compute_file_hash, stable_source_id
from backend.app.ingestion.loader import scan_directory


def test_hashing_consistency():
    content = "def hello():\n    return 'world'\n"
    h1 = compute_file_hash(content)
    h2 = compute_file_hash(content)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256


def test_stable_source_id():
    id1 = stable_source_id("backend/app/main.py")
    id2 = stable_source_id("backend\\app\\main.py")  # Windows style
    assert id1 == id2
    assert len(id1) == 16


def test_chunk_by_headings():
    doc = "# Section 1\nLine 1\nLine 2\n# Section 2\nLine 3\n"
    chunks = chunk_by_headings(doc, source_id="src1")
    assert len(chunks) == 2
    assert chunks[0].heading == "Section 1"
    assert chunks[1].heading == "Section 2"
    assert chunks[0].start_line == 1
    assert chunks[1].start_line == 4


def test_scan_directory(tmp_path: Path):
    # Create test directory structure
    (tmp_path / "valid.py").write_text("print('test')", encoding="utf-8")
    (tmp_path / "valid.md").write_text("# Test", encoding="utf-8")
    (tmp_path / "ignored.bin").write_bytes(b"\x00\x01\x02")

    # Hidden folder should be excluded
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "config").write_text("git config", encoding="utf-8")

    result = scan_directory(tmp_path, allowed_extensions={".py", ".md"})
    assert len(result.files) == 2
    assert any(f.extension == ".py" for f in result.files)
    assert any(f.extension == ".md" for f in result.files)
    assert not any(".git" in f.relative_path for f in result.files)
