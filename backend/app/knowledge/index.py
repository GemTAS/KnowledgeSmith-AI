"""Lightweight in-memory index for the knowledge repository."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from backend.app.extraction.models import Concept

logger = logging.getLogger("knowledgesmith.knowledge.index")


class KnowledgeIndex:
    """In-memory search index over concepts.

    Maintains inverted indexes for title words, tags, and types.
    No external database required.
    """

    def __init__(self) -> None:
        self._concepts: Dict[str, Concept] = {}
        self._title_index: Dict[str, Set[str]] = defaultdict(set)
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)
        self._type_index: Dict[str, Set[str]] = defaultdict(set)

    def add(self, concept: Concept) -> None:
        """Index a concept."""
        self._concepts[concept.concept_id] = concept

        # Title word index.
        for word in concept.title.lower().split():
            clean = word.strip(".,;:!?()[]{}\"'")
            if len(clean) > 1:
                self._title_index[clean].add(concept.concept_id)

        # Description word index.
        for word in concept.description.lower().split():
            clean = word.strip(".,;:!?()[]{}\"'")
            if len(clean) > 2:
                self._title_index[clean].add(concept.concept_id)

        # Tag index.
        for tag in concept.tags:
            self._tag_index[tag.lower()].add(concept.concept_id)

        # Type index.
        self._type_index[concept.concept_type.lower()].add(concept.concept_id)

    def build(self, concepts: List[Concept]) -> None:
        """Index a list of concepts."""
        for c in concepts:
            self.add(c)
        logger.info("Indexed %d concepts", len(concepts))

    def search(self, query: str) -> List[Concept]:
        """Search by text query across titles and descriptions."""
        q = query.lower().strip()
        matching_ids: Set[str] = set()

        # Word-level search.
        for word in q.split():
            clean = word.strip(".,;:!?()[]{}\"'")
            if clean in self._title_index:
                matching_ids |= self._title_index[clean]

        # Exact substring fallback.
        if not matching_ids:
            for cid, concept in self._concepts.items():
                if q in concept.title.lower() or q in concept.description.lower():
                    matching_ids.add(cid)

        return [self._concepts[cid] for cid in matching_ids if cid in self._concepts]

    def by_tag(self, tag: str) -> List[Concept]:
        ids = self._tag_index.get(tag.lower(), set())
        return [self._concepts[cid] for cid in ids if cid in self._concepts]

    def by_type(self, concept_type: str) -> List[Concept]:
        ids = self._type_index.get(concept_type.lower(), set())
        return [self._concepts[cid] for cid in ids if cid in self._concepts]

    def all_tags(self) -> List[str]:
        return sorted(self._tag_index.keys())

    def all_types(self) -> List[str]:
        return sorted(self._type_index.keys())

    @property
    def count(self) -> int:
        return len(self._concepts)

    def save(self, path: Path) -> None:
        """Persist the index as JSON."""
        data = {
            "concept_count": len(self._concepts),
            "concepts": {
                cid: {
                    "title": c.title,
                    "type": c.concept_type,
                    "description": c.description[:200],
                    "tags": c.tags,
                }
                for cid, c in self._concepts.items()
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, path: Path) -> None:
        """Reload concepts from index file (metadata only, not full rebuild)."""
        if not path.exists():
            return
        # Index is rebuilt from concepts, not loaded from JSON.
        # This method exists for interface compatibility.
        logger.info("Index load from %s — rebuild from concepts recommended.", path)

    build_from = build


InMemoryKnowledgeIndex = KnowledgeIndex
