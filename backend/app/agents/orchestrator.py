"""Autonomous Knowledge Engineering Orchestrator.

Manages the lifecycle of an autonomous extraction run:
1. Ingestion of raw sources.
2. Incremental change detection against previous manifest.
3. Concept and claim extraction (deterministic + optional LLM).
4. Provenance tracking with trust tier resolution.
5. Conflict detection and deduplication.
6. Knowledge graph topology construction.
7. OKF v0.2 validation.
8. Output serialization and index generation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.agents.tools import (
    ChangeDetectionTool,
    ConflictResolutionTool,
    ExtractionTool,
    GraphTool,
    IngestTool,
    SerializationTool,
    ValidationTool,
)
from backend.app.extraction.models import (
    ChangeRecord,
    Concept,
    Relationship,
)
from backend.app.ingestion.loader import SourceFile
from backend.app.knowledge.change_detector import SourceManifest
from backend.app.knowledge.graph import KnowledgeGraph
from backend.app.knowledge.provenance import ProvenanceTracker
from backend.app.knowledge.validator import ValidationResult

logger = logging.getLogger("knowledgesmith.agents.orchestrator")


class WorkflowStage(str, Enum):
    """Execution stages of the knowledge engineering pipeline."""

    IDLE = "idle"
    INGESTION = "ingestion"
    CHANGE_DETECTION = "change_detection"
    EXTRACTION = "extraction"
    PROVENANCE = "provenance"
    CONFLICT_RESOLUTION = "conflict_resolution"
    GRAPH_BUILD = "graph_build"
    VALIDATION = "validation"
    SERIALIZATION = "serialization"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowStatus:
    """Real-time and summary status of an orchestration run."""

    stage: WorkflowStage = WorkflowStage.IDLE
    progress_percent: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    elapsed_seconds: float = 0.0

    # Counts and metrics
    files_ingested: int = 0
    files_changed: int = 0
    concepts_extracted: int = 0
    claims_extracted: int = 0
    relationships_extracted: int = 0
    conflicts_detected: int = 0
    validation_errors: int = 0
    validation_warnings: int = 0
    artifacts_written: int = 0

    # Detail collections
    changes: List[ChangeRecord] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    def log(self, message: str) -> None:
        """Append a timestamped log entry."""
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = f"[{now}] [{self.stage.value.upper()}] {message}"
        self.logs.append(entry)
        logger.info(entry)

    def to_dict(self) -> Dict[str, Any]:
        """Convert status to a JSON-serializable dictionary."""
        return {
            "stage": self.stage.value,
            "progress_percent": self.progress_percent,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "files_ingested": self.files_ingested,
            "files_changed": self.files_changed,
            "concepts_extracted": self.concepts_extracted,
            "claims_extracted": self.claims_extracted,
            "relationships_extracted": self.relationships_extracted,
            "conflicts_detected": self.conflicts_detected,
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
            "artifacts_written": self.artifacts_written,
            "conflicts": self.conflicts,
            "error_message": self.error_message,
            "recent_logs": self.logs[-50:],
        }


class KnowledgeOrchestrator:
    """Autonomous Knowledge Engineering Pipeline Orchestrator."""

    def __init__(
        self,
        ingest_tool: Optional[IngestTool] = None,
        change_tool: Optional[ChangeDetectionTool] = None,
        extraction_tool: Optional[ExtractionTool] = None,
        conflict_tool: Optional[ConflictResolutionTool] = None,
        graph_tool: Optional[GraphTool] = None,
        validation_tool: Optional[ValidationTool] = None,
        serialization_tool: Optional[SerializationTool] = None,
    ) -> None:
        self.ingest_tool = ingest_tool or IngestTool()
        self.change_tool = change_tool or ChangeDetectionTool()
        self.extraction_tool = extraction_tool or ExtractionTool()
        self.conflict_tool = conflict_tool or ConflictResolutionTool()
        self.graph_tool = graph_tool or GraphTool()
        self.validation_tool = validation_tool or ValidationTool()
        self.serialization_tool = serialization_tool or SerializationTool()

        # In-memory execution state
        self.status = WorkflowStatus()
        self.current_files: List[SourceFile] = []
        self.current_concepts: List[Concept] = []
        self.current_relationships: List[Relationship] = []
        self.current_graph: Optional[KnowledgeGraph] = None
        self.current_validation: Optional[ValidationResult] = None
        self.provenance_tracker = ProvenanceTracker()
        self.current_manifest: Optional[SourceManifest] = None

    def run(
        self,
        input_dir: Path,
        output_dir: Path,
        use_llm: bool = False,
        model_name: str = "gemini-2.5-flash",
        max_file_size: int = 1_048_576,
        allowed_extensions: Optional[List[str]] = None,
        overwrite: bool = True,
    ) -> WorkflowStatus:
        """Run the end-to-end knowledge engineering lifecycle."""
        self.status = WorkflowStatus(
            stage=WorkflowStage.IDLE,
            start_time=datetime.now(timezone.utc),
            progress_percent=0,
        )
        start_ts = time.time()
        self.status.log("Starting KnowledgeSmith AI Autonomous Knowledge Pipeline")

        try:
            # 1. Ingestion
            self.status.stage = WorkflowStage.INGESTION
            self.status.progress_percent = 10
            self.status.log(f"Scanning source directory: {input_dir}")
            ingest_res = self.ingest_tool.execute(
                root_dir=input_dir,
                max_file_size=max_file_size,
                allowed_extensions=allowed_extensions,
            )
            self.current_files = ingest_res.files
            self.status.files_ingested = len(self.current_files)
            self.status.log(f"Successfully ingested {self.status.files_ingested} files.")

            if not self.current_files:
                self.status.log("Warning: No eligible files found to process.")
                self.status.stage = WorkflowStage.COMPLETED
                self.status.progress_percent = 100
                self.status.end_time = datetime.now(timezone.utc)
                self.status.elapsed_seconds = time.time() - start_ts
                return self.status

            # 2. Change Detection
            self.status.stage = WorkflowStage.CHANGE_DETECTION
            self.status.progress_percent = 25
            manifest_path = output_dir / "manifest.json"
            changes, new_manifest = self.change_tool.execute(
                current_files=self.current_files,
                manifest_path=manifest_path,
            )
            self.status.changes = changes
            self.status.files_changed = len(changes)
            self.current_manifest = new_manifest
            self.status.log(f"Change detection completed: {self.status.files_changed} changes identified.")

            # 3. Extraction
            self.status.stage = WorkflowStage.EXTRACTION
            self.status.progress_percent = 45
            self.status.log(f"Extracting knowledge (use_llm={use_llm}, model={model_name})")
            extraction_res = self.extraction_tool.execute(
                files=self.current_files,
                use_llm=use_llm,
                model_name=model_name,
            )
            self.current_concepts = extraction_res.concepts
            self.current_relationships = extraction_res.relationships
            self.status.concepts_extracted = len(self.current_concepts)
            self.status.relationships_extracted = len(self.current_relationships)
            self.status.claims_extracted = sum(len(c.claims) for c in self.current_concepts)
            self.status.log(
                f"Extracted {self.status.concepts_extracted} concepts, "
                f"{self.status.claims_extracted} claims, and "
                f"{self.status.relationships_extracted} relationships."
            )

            # 4. Provenance Tracking
            self.status.stage = WorkflowStage.PROVENANCE
            self.status.progress_percent = 60
            self.status.log("Recording provenance and resolving trust tiers.")
            self.provenance_tracker = ProvenanceTracker()
            for c in self.current_concepts:
                self.provenance_tracker.track_concept(c)
            self.status.log(f"Tracked provenance for {self.provenance_tracker.count} entities.")

            # 5. Conflict Resolution
            self.status.stage = WorkflowStage.CONFLICT_RESOLUTION
            self.status.progress_percent = 70
            self.status.log("Analyzing potential claim and concept conflicts.")
            conflicts = self.conflict_tool.execute(self.current_concepts)
            self.status.conflicts = conflicts
            self.status.conflicts_detected = len(conflicts)
            self.status.log(f"Conflict detection found {self.status.conflicts_detected} potential conflicts.")

            # 6. Knowledge Graph Construction
            self.status.stage = WorkflowStage.GRAPH_BUILD
            self.status.progress_percent = 80
            self.status.log("Synthesizing in-memory knowledge graph.")
            self.current_graph = self.graph_tool.execute(
                concepts=self.current_concepts,
                relationships=self.current_relationships,
            )
            stats = self.current_graph.statistics()
            self.status.log(
                f"Knowledge graph constructed: {stats.get('node_count')} nodes, "
                f"{stats.get('edge_count')} edges."
            )

            # 7. OKF Validation
            self.status.stage = WorkflowStage.VALIDATION
            self.status.progress_percent = 90
            self.status.log("Validating extracted artifacts against OKF specification.")
            self.current_validation = self.validation_tool.execute(
                concepts=self.current_concepts,
                relationships=self.current_relationships,
            )
            self.status.validation_errors = self.current_validation.error_count
            self.status.validation_warnings = self.current_validation.warning_count
            self.status.log(
                f"Validation finished: {self.status.validation_errors} errors, "
                f"{self.status.validation_warnings} warnings."
            )

            # 8. OKF Serialization
            self.status.stage = WorkflowStage.SERIALIZATION
            self.status.progress_percent = 95
            self.status.log(f"Serializing OKF v0.2 artifacts to: {output_dir}")
            written_paths = self.serialization_tool.execute(
                concepts=self.current_concepts,
                relationships=self.current_relationships,
                output_dir=output_dir,
                overwrite=overwrite,
                manifest=self.current_manifest,
                tracker=self.provenance_tracker,
            )
            self.status.artifacts_written = len(written_paths)
            self.status.log(f"Successfully serialized {self.status.artifacts_written} artifacts.")

            # Complete
            self.status.stage = WorkflowStage.COMPLETED
            self.status.progress_percent = 100
            self.status.end_time = datetime.now(timezone.utc)
            self.status.elapsed_seconds = time.time() - start_ts
            self.status.log(
                f"Knowledge engineering run finished cleanly in {round(self.status.elapsed_seconds, 2)}s."
            )
            return self.status

        except Exception as e:
            self.status.stage = WorkflowStage.FAILED
            self.status.error_message = str(e)
            self.status.end_time = datetime.now(timezone.utc)
            self.status.elapsed_seconds = time.time() - start_ts
            self.status.log(f"Pipeline failed with error: {e}")
            logger.exception("KnowledgeOrchestrator run failed.")
            return self.status
