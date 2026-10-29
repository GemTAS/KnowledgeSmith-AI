"""Knowledge graph — directed concept relationship graph."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.extraction.models import Concept, Relationship

logger = logging.getLogger("knowledgesmith.knowledge.graph")


@dataclass
class GraphNode:
    """A node in the knowledge graph."""

    concept_id: str
    title: str
    concept_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A directed edge in the knowledge graph."""

    source_id: str
    target_id: str
    relationship_type: str
    evidence: Optional[str] = None


class KnowledgeGraph:
    """In-memory directed knowledge graph.

    Uses plain Python dicts — no graph library dependency.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, GraphNode] = {}
        self._outgoing: Dict[str, List[GraphEdge]] = defaultdict(list)
        self._incoming: Dict[str, List[GraphEdge]] = defaultdict(list)

    # ── Construction ──────────────────────────────────────────────

    def add_node(self, concept: Concept) -> None:
        """Add a concept as a graph node."""
        self._nodes[concept.concept_id] = GraphNode(
            concept_id=concept.concept_id,
            title=concept.title,
            concept_type=concept.concept_type,
            metadata=concept.metadata,
        )

    def add_edge(self, relationship: Relationship) -> None:
        """Add a directed relationship as a graph edge."""
        edge = GraphEdge(
            source_id=relationship.source_concept_id,
            target_id=relationship.target_concept_id,
            relationship_type=relationship.relationship_type,
            evidence=relationship.evidence,
        )
        self._outgoing[edge.source_id].append(edge)
        self._incoming[edge.target_id].append(edge)

    def build_from(
        self,
        concepts: List[Concept],
        relationships: List[Relationship],
    ) -> None:
        """Populate the graph from extraction results."""
        for c in concepts:
            self.add_node(c)
        for r in relationships:
            self.add_edge(r)
        logger.info(
            "Graph built: %d nodes, %d edges",
            len(self._nodes),
            sum(len(v) for v in self._outgoing.values()),
        )

    # ── Queries ───────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(v) for v in self._outgoing.values())

    def get_node(self, concept_id: str) -> Optional[GraphNode]:
        return self._nodes.get(concept_id)

    def get_neighbors(self, concept_id: str) -> List[GraphNode]:
        """Return nodes directly connected to *concept_id* (outgoing)."""
        result: List[GraphNode] = []
        for edge in self._outgoing.get(concept_id, []):
            node = self._nodes.get(edge.target_id)
            if node:
                result.append(node)
        return result

    def get_reverse_neighbors(self, concept_id: str) -> List[GraphNode]:
        """Return nodes that point *to* concept_id (incoming)."""
        result: List[GraphNode] = []
        for edge in self._incoming.get(concept_id, []):
            node = self._nodes.get(edge.source_id)
            if node:
                result.append(node)
        return result

    def get_outgoing_edges(self, concept_id: str) -> List[GraphEdge]:
        return self._outgoing.get(concept_id, [])

    def get_incoming_edges(self, concept_id: str) -> List[GraphEdge]:
        return self._incoming.get(concept_id, [])

    def get_related(self, concept_id: str, max_depth: int = 2) -> Set[str]:
        """BFS discovery of related concept IDs up to *max_depth*."""
        visited: Set[str] = set()
        frontier = {concept_id}
        for _ in range(max_depth):
            next_frontier: Set[str] = set()
            for cid in frontier:
                if cid in visited:
                    continue
                visited.add(cid)
                for edge in self._outgoing.get(cid, []):
                    next_frontier.add(edge.target_id)
                for edge in self._incoming.get(cid, []):
                    next_frontier.add(edge.source_id)
            frontier = next_frontier - visited
        visited.update(frontier)
        visited.discard(concept_id)
        return visited

    def find_missing_targets(self) -> List[str]:
        """Return edge target IDs that have no corresponding node."""
        missing: Set[str] = set()
        for edges in self._outgoing.values():
            for edge in edges:
                if edge.target_id not in self._nodes:
                    missing.add(edge.target_id)
        return sorted(missing)

    # ── Statistics ────────────────────────────────────────────────

    def statistics(self) -> Dict[str, Any]:
        """Return summary statistics about the graph."""
        type_counts: Dict[str, int] = defaultdict(int)
        for node in self._nodes.values():
            type_counts[node.concept_type] += 1

        rel_counts: Dict[str, int] = defaultdict(int)
        for edges in self._outgoing.values():
            for edge in edges:
                rel_counts[edge.relationship_type] += 1

        orphans = [
            cid
            for cid in self._nodes
            if cid not in self._outgoing and cid not in self._incoming
        ]

        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "type_distribution": dict(type_counts),
            "relationship_distribution": dict(rel_counts),
            "orphan_count": len(orphans),
            "missing_targets": self.find_missing_targets(),
        }

    # ── Export ────────────────────────────────────────────────────

    def to_json(self) -> str:
        """Export the graph as a JSON string."""
        data = {
            "nodes": [
                {
                    "id": n.concept_id,
                    "title": n.title,
                    "type": n.concept_type,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "type": e.relationship_type,
                }
                for edges in self._outgoing.values()
                for e in edges
            ],
        }
        return json.dumps(data, indent=2)

    def all_nodes(self) -> List[GraphNode]:
        return list(self._nodes.values())

    def all_edges(self) -> List[GraphEdge]:
        return [e for edges in self._outgoing.values() for e in edges]
