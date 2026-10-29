"""Change detection — compare source manifests to identify deltas."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.extraction.models import ChangeRecord, ChangeType
from backend.app.ingestion.loader import SourceFile

logger = logging.getLogger("knowledgesmith.knowledge.change_detector")


class SourceManifest:
    """Persisted record of source file hashes and metadata."""

    def __init__(self) -> None:
        self.entries: Dict[str, Dict[str, Any]] = {}
        self.generated_at: Optional[str] = None

    def record(self, sf: SourceFile) -> None:
        """Record a source file in the manifest."""
        self.entries[sf.source_id] = {
            "relative_path": sf.relative_path,
            "content_hash": sf.content_hash,
            "size_bytes": sf.size_bytes,
            "extension": sf.extension,
        }

    def save(self, path: Path) -> None:
        """Persist the manifest to a JSON file."""
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(self.entries),
            "entries": self.entries,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Saved source manifest with %d entries to %s", len(self.entries), path)

    @classmethod
    def load(cls, path: Path) -> "SourceManifest":
        """Load a manifest from a JSON file."""
        manifest = cls()
        if not path.exists():
            return manifest
        data = json.loads(path.read_text(encoding="utf-8"))
        manifest.entries = data.get("entries", {})
        manifest.generated_at = data.get("generated_at")
        logger.info("Loaded source manifest with %d entries from %s", len(manifest.entries), path)
        return manifest


def detect_changes(
    current_files: List[SourceFile],
    previous_manifest: SourceManifest,
) -> List[ChangeRecord]:
    """Compare current source files against the previous manifest.

    Returns a list of change records for added, modified, and removed sources.
    Artifacts referencing removed sources are NOT automatically deleted —
    they should be marked stale instead.
    """
    changes: List[ChangeRecord] = []

    current_ids = {sf.source_id: sf for sf in current_files}
    previous_ids = set(previous_manifest.entries.keys())

    # Added files.
    for sid, sf in current_ids.items():
        if sid not in previous_ids:
            changes.append(
                ChangeRecord(
                    source_id=sid,
                    relative_path=sf.relative_path,
                    change_type=ChangeType.ADDED,
                    new_hash=sf.content_hash,
                )
            )

    # Modified files.
    for sid, sf in current_ids.items():
        if sid in previous_ids:
            old_hash = previous_manifest.entries[sid].get("content_hash", "")
            if old_hash != sf.content_hash:
                changes.append(
                    ChangeRecord(
                        source_id=sid,
                        relative_path=sf.relative_path,
                        change_type=ChangeType.MODIFIED,
                        old_hash=old_hash,
                        new_hash=sf.content_hash,
                    )
                )

    # Removed files.
    for sid in previous_ids:
        if sid not in current_ids:
            entry = previous_manifest.entries[sid]
            changes.append(
                ChangeRecord(
                    source_id=sid,
                    relative_path=entry.get("relative_path", "unknown"),
                    change_type=ChangeType.REMOVED,
                    old_hash=entry.get("content_hash"),
                )
            )

    logger.info(
        "Change detection: %d added, %d modified, %d removed",
        sum(1 for c in changes if c.change_type == ChangeType.ADDED),
        sum(1 for c in changes if c.change_type == ChangeType.MODIFIED),
        sum(1 for c in changes if c.change_type == ChangeType.REMOVED),
    )
    return changes


def find_stale_concepts(
    changes: List[ChangeRecord],
    concepts: List[Any],
) -> List[str]:
    """Find concept IDs whose source references are affected by changes.

    Returns concept IDs that may need re-extraction or staleness marking.
    """
    changed_source_ids = {c.source_id for c in changes if c.change_type in ("modified", "removed")}

    stale_ids: List[str] = []
    for concept in concepts:
        for ref in getattr(concept, "source_refs", []):
            if ref.source_id in changed_source_ids:
                stale_ids.append(concept.concept_id)
                break

    return stale_ids
