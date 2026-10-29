"""Tests for knowledge graph operations, neighbor traversal, and exports."""

from backend.app.extraction.models import Concept, Relationship
from backend.app.knowledge.graph import KnowledgeGraph


def test_graph_construction_and_traversal():
    c1 = Concept(concept_id="auth", title="Auth", concept_type="Module")
    c2 = Concept(concept_id="user", title="User", concept_type="Class")
    c3 = Concept(concept_id="db", title="Database", concept_type="Module")

    r1 = Relationship(source_concept_id="auth", target_concept_id="user", relationship_type="creates")
    r2 = Relationship(source_concept_id="user", target_concept_id="db", relationship_type="persists_to")

    graph = KnowledgeGraph()
    graph.build_from([c1, c2, c3], [r1, r2])

    assert graph.node_count == 3
    assert graph.edge_count == 2

    # Neighbors
    neighbors = graph.get_neighbors("auth")
    assert len(neighbors) == 1
    assert neighbors[0].concept_id == "user"

    # Reverse lookup
    reverse = graph.get_reverse_neighbors("db")
    assert len(reverse) == 1
    assert reverse[0].concept_id == "user"

    # 2-hop BFS related
    related = graph.get_related("auth", max_depth=2)
    assert "user" in related
    assert "db" in related


def test_missing_targets_detection():
    c1 = Concept(concept_id="node_a", title="Node A", concept_type="Class")
    r1 = Relationship(source_concept_id="node_a", target_concept_id="ghost_node", relationship_type="depends_on")

    graph = KnowledgeGraph()
    graph.build_from([c1], [r1])

    missing = graph.find_missing_targets()
    assert "ghost_node" in missing
