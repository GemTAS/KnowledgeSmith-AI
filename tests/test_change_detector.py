"""Tests for incremental change detection and manifest persistence."""

from pathlib import Path

from backend.app.extraction.models import ChangeType
from backend.app.ingestion.loader import SourceFile
from backend.app.knowledge.change_detector import SourceManifest, detect_changes


def test_change_detector(tmp_path: Path):
    f1 = SourceFile(
        path=Path("main.py"),
        relative_path="main.py",
        content="print(1)",
        content_hash="hash1",
        source_id="src1",
        size_bytes=8,
        extension=".py",
    )
    f2 = SourceFile(
        path=Path("auth.py"),
        relative_path="auth.py",
        content="print(2)",
        content_hash="hash2",
        source_id="src2",
        size_bytes=8,
        extension=".py",
    )

    manifest = SourceManifest()
    manifest.record(f1)
    manifest.record(f2)

    manifest_file = tmp_path / "manifest.json"
    manifest.save(manifest_file)
    assert manifest_file.exists()

    loaded = SourceManifest.load(manifest_file)
    assert len(loaded.entries) == 2

    # Now modify f1 and add f3
    f1_mod = SourceFile(
        path=Path("main.py"),
        relative_path="main.py",
        content="print(1_modified)",
        content_hash="hash1_new",
        source_id="src1",
        size_bytes=17,
        extension=".py",
    )
    f3_new = SourceFile(
        path=Path("extra.py"),
        relative_path="extra.py",
        content="print(3)",
        content_hash="hash3",
        source_id="src3",
        size_bytes=8,
        extension=".py",
    )

    changes = detect_changes([f1_mod, f3_new], loaded)
    change_types = {c.change_type for c in changes}
    assert ChangeType.MODIFIED in change_types
    assert ChangeType.ADDED in change_types
    assert ChangeType.REMOVED in change_types  # f2 was omitted
