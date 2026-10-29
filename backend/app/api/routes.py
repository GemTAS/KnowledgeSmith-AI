"""FastAPI route handlers for KnowledgeSmith AI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.app.agents.orchestrator import KnowledgeOrchestrator
from backend.app.api.schemas import (
    ChangeRecordItem,
    ChangesResponse,
    ClaimSummary,
    ConceptDetail,
    ConceptListResponse,
    ConceptSummary,
    EvaluationResponse,
    GraphEdgeItem,
    GraphNodeItem,
    GraphResponse,
    HealthResponse,
    IngestFileSummary,
    IngestRequest,
    IngestResponse,
    PipelineRunRequest,
    ValidationIssueItem,
    ValidationResponse,
)
from backend.app.config import settings
from backend.app.evaluation.benchmark import KnowledgeBenchmark
from backend.app.evaluation.metrics import compute_metrics
from backend.app.knowledge.index import InMemoryKnowledgeIndex

logger = logging.getLogger("knowledgesmith.api.routes")

router = APIRouter(prefix="/api", tags=["KnowledgeSmith"])

# Shared orchestrator instance
orchestrator = KnowledgeOrchestrator()
search_index = InMemoryKnowledgeIndex()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return system health status."""
    return HealthResponse()


@router.post("/pipeline/run")
def run_pipeline(payload: Optional[PipelineRunRequest] = None) -> Dict[str, Any]:
    """Execute the full autonomous knowledge engineering pipeline."""
    req = payload or PipelineRunRequest()
    in_dir = Path(req.input_dir) if req.input_dir else Path(settings.ingestion_root)
    out_dir = Path(req.output_dir) if req.output_dir else Path(settings.output_dir)

    status = orchestrator.run(
        input_dir=in_dir,
        output_dir=out_dir,
        use_llm=req.use_llm,
        model_name=req.model_name,
        overwrite=req.overwrite,
    )

    # Refresh search index
    search_index.build_from(orchestrator.current_concepts)

    return status.to_dict()


@router.get("/pipeline/status")
def get_pipeline_status() -> Dict[str, Any]:
    """Retrieve current/latest pipeline execution status."""
    return orchestrator.status.to_dict()


@router.post("/ingest", response_model=IngestResponse)
def ingest_sources(payload: IngestRequest) -> IngestResponse:
    """Scan and ingest source files from a directory."""
    root_path = Path(payload.root_dir)
    res = orchestrator.ingest_tool.execute(
        root_dir=root_path,
        max_file_size=payload.max_file_size or settings.max_file_size,
        allowed_extensions=payload.allowed_extensions,
    )
    return IngestResponse(
        total_files=len(res.files),
        files=[
            IngestFileSummary(
                relative_path=sf.relative_path,
                source_id=sf.source_id,
                size_bytes=sf.size_bytes,
                extension=sf.extension,
                content_hash=sf.content_hash,
            )
            for sf in res.files
        ],
        skipped_count=len(res.skipped),
        errors=res.errors,
    )


@router.get("/concepts", response_model=ConceptListResponse)
def list_concepts(
    q: Optional[str] = Query(default=None, description="Search query across titles and tags"),
    concept_type: Optional[str] = Query(default=None, alias="type", description="Filter by concept type"),
    tag: Optional[str] = Query(default=None, description="Filter by tag"),
) -> ConceptListResponse:
    """List extracted concepts with optional search and filters."""
    concepts = orchestrator.current_concepts

    # Apply search query if index is populated
    if q:
        matched = search_index.search(q)
        matched_ids = {c.concept_id if hasattr(c, "concept_id") else str(c) for c in matched}
        concepts = [c for c in concepts if c.concept_id in matched_ids]

    if concept_type:
        concepts = [c for c in concepts if c.concept_type.lower() == concept_type.lower()]

    if tag:
        concepts = [c for c in concepts if any(t.lower() == tag.lower() for t in c.tags)]

    summaries = [
        ConceptSummary(
            concept_id=c.concept_id,
            title=c.title,
            concept_type=c.concept_type,
            description=c.description,
            tags=c.tags,
            claims_count=len(c.claims),
        )
        for c in concepts
    ]
    return ConceptListResponse(total=len(summaries), concepts=summaries)


@router.get("/concepts/{concept_id}", response_model=ConceptDetail)
def get_concept(concept_id: str) -> ConceptDetail:
    """Get complete details for a specific concept."""
    concept = next((c for c in orchestrator.current_concepts if c.concept_id == concept_id), None)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")

    # Find relevant relationships
    rels = [
        {
            "source_id": r.source_concept_id,
            "target_id": r.target_concept_id,
            "relationship_type": r.relationship_type,
            "evidence": r.evidence,
        }
        for r in orchestrator.current_relationships
        if r.source_concept_id == concept_id or r.target_concept_id == concept_id
    ]

    claims = [
        ClaimSummary(
            claim_id=cl.claim_id,
            statement=cl.statement,
            extraction_method=cl.extraction_method.value,
            verification_status=cl.verification_status.value,
            confidence=cl.confidence,
            source_count=len(cl.source_refs),
        )
        for cl in concept.claims
    ]

    return ConceptDetail(
        concept_id=concept.concept_id,
        title=concept.title,
        concept_type=concept.concept_type,
        description=concept.description,
        tags=concept.tags,
        claims=claims,
        relationships=rels,
        metadata=concept.metadata,
    )


@router.get("/graph", response_model=GraphResponse)
def get_knowledge_graph() -> GraphResponse:
    """Retrieve graph topology, nodes, edges, and statistics."""
    graph = orchestrator.current_graph
    if not graph:
        # Build on the fly if not initialized
        graph = orchestrator.graph_tool.execute(
            orchestrator.current_concepts,
            orchestrator.current_relationships,
        )
        orchestrator.current_graph = graph

    nodes = [
        GraphNodeItem(
            id=n.concept_id,
            title=n.title,
            type=n.concept_type,
            metadata=n.metadata,
        )
        for n in graph._nodes.values()
    ]

    edges: List[GraphEdgeItem] = []
    for edge_list in graph._outgoing.values():
        for e in edge_list:
            edges.append(
                GraphEdgeItem(
                    source=e.source_id,
                    target=e.target_id,
                    type=e.relationship_type,
                    evidence=e.evidence,
                )
            )

    return GraphResponse(
        node_count=graph.node_count,
        edge_count=graph.edge_count,
        nodes=nodes,
        edges=edges,
        statistics=graph.statistics(),
    )


@router.get("/graph/neighbors/{concept_id}")
def get_concept_neighbors(concept_id: str) -> Dict[str, Any]:
    """Retrieve direct neighbors and 2-hop connected concepts."""
    graph = orchestrator.current_graph
    if not graph:
        graph = orchestrator.graph_tool.execute(
            orchestrator.current_concepts,
            orchestrator.current_relationships,
        )
        orchestrator.current_graph = graph

    node = graph.get_node(concept_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{concept_id}' not in graph")

    outgoing = [n.concept_id for n in graph.get_neighbors(concept_id)]
    incoming = [n.concept_id for n in graph.get_reverse_neighbors(concept_id)]
    related = list(graph.get_related(concept_id, max_depth=2))

    return {
        "concept_id": concept_id,
        "outgoing_neighbors": outgoing,
        "incoming_neighbors": incoming,
        "two_hop_related": related,
    }


@router.get("/validation", response_model=ValidationResponse)
def get_validation() -> ValidationResponse:
    """Return validation results and OKF compliance findings."""
    val = orchestrator.current_validation
    if not val:
        val = orchestrator.validation_tool.execute(
            orchestrator.current_concepts,
            orchestrator.current_relationships,
        )
        orchestrator.current_validation = val

    return ValidationResponse(
        is_valid=val.is_valid,
        error_count=val.error_count,
        warning_count=val.warning_count,
        issues=[
            ValidationIssueItem(
                severity=i.severity,
                code=i.code,
                message=i.message,
                concept_id=i.concept_id,
            )
            for i in val.issues
        ],
    )


@router.get("/changes", response_model=ChangesResponse)
def get_changes() -> ChangesResponse:
    """Return records of detected source modifications and deltas."""
    changes = orchestrator.status.changes
    return ChangesResponse(
        total_changes=len(changes),
        changes=[
            ChangeRecordItem(
                file_path=c.file_path,
                change_type=c.change_type.value if hasattr(c.change_type, "value") else str(c.change_type),
                previous_hash=c.previous_hash,
                current_hash=c.current_hash,
            )
            for c in changes
        ],
    )


@router.get("/evaluation", response_model=EvaluationResponse)
def get_evaluation() -> EvaluationResponse:
    """Compute and return quality metrics and benchmark scorecard."""
    benchmark = KnowledgeBenchmark()
    res = benchmark.evaluate(
        concepts=orchestrator.current_concepts,
        relationships=orchestrator.current_relationships,
        source_files=orchestrator.current_files,
        validation=orchestrator.current_validation,
    )
    return EvaluationResponse(
        metrics=res.metrics.to_dict(),
        benchmark=res.to_dict(),
    )


@router.get("/provenance")
def get_provenance() -> List[Dict[str, Any]]:
    """Return all recorded provenance records."""
    return [r.to_dict() for r in orchestrator.provenance_tracker.get_all()]
