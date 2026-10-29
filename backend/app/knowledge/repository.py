"""Knowledge repository — manage artifacts on the filesystem."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.extraction.models import Concept, Relationship
from backend.app.knowledge.okf_serializer import (
    generate_index,
    serialize_concept,
    write_concept_file,
    _safe_filename,
)

logger = logging.getLogger("knowledgesmith.knowledge.repository")


class KnowledgeRepository:
    """Manages a filesystem-based knowledge bundle."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._concepts: Dict[str, Concept] = {}
        self._relationships: List[Relationship] = []
        self._written_files: Dict[str, Path] = {}

    def add_concepts(
        self,
        concepts: List[Concept],
        relationships: List[Relationship],
    ) -> None:
        """Add concepts and relationships to the repository."""
        for c in concepts:
            self._concepts[c.concept_id] = c
        self._relationships.extend(relationships)

    def write_all(self, overwrite: bool = False) -> List[Path]:
        """Serialize all concepts to OKF files and return written paths."""
        written: List[Path] = []
        for concept in self._concepts.values():
            path = write_concept_file(
                concept,
                self._relationships,
                self.output_dir,
                overwrite=overwrite,
            )
            self._written_files[concept.concept_id] = path
            written.append(path)

        # Generate index.
        idx = generate_index(self.output_dir, list(self._concepts.values()))
        written.append(idx)

        logger.info("Wrote %d files to %s", len(written), self.output_dir)
        return written

    def get_concept(self, concept_id: str) -> Optional[Concept]:
        return self._concepts.get(concept_id)

    def list_concepts(
        self,
        concept_type: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Concept]:
        """List concepts with optional filtering."""
        result = list(self._concepts.values())
        if concept_type:
            result = [c for c in result if c.concept_type == concept_type]
        if tag:
            result = [c for c in result if tag in c.tags]
        return result

    def search(self, query: str) -> List[Concept]:
        """Simple text search across titles, descriptions, and claims."""
        q = query.lower()
        results: List[Concept] = []
        for c in self._concepts.values():
            if q in c.title.lower() or q in c.description.lower():
                results.append(c)
                continue
            for claim in c.claims:
                if q in claim.statement.lower():
                    results.append(c)
                    break
        return results

    def find_duplicates(self) -> List[tuple[str, str]]:
        """Find concepts with identical titles (potential duplicates)."""
        by_title: Dict[str, List[str]] = {}
        for c in self._concepts.values():
            key = c.title.lower().strip()
            by_title.setdefault(key, []).append(c.concept_id)
        return [(title, ids) for title, ids in by_title.items() if len(ids) > 1]

    def validate_source_refs(self, source_ids: set[str]) -> List[str]:
        """Check that all source references point to known source IDs."""
        broken: List[str] = []
        for c in self._concepts.values():
            for ref in c.source_refs:
                if ref.source_id not in source_ids:
                    broken.append(
                        f"Concept '{c.title}' references unknown source '{ref.source_id}'"
                    )
        return broken

    @property
    def concept_count(self) -> int:
        return len(self._concepts)

    def save_manifest(self) -> Path:
        """Save a manifest of written files."""
        manifest = {
            "concept_count": len(self._concepts),
            "relationship_count": len(self._relationships),
            "files": {
                cid: str(path) for cid, path in self._written_files.items()
            },
        }
        path = self.output_dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return path
