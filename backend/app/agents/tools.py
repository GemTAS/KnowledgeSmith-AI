"""Autonomous knowledge engineering tools.

Each tool encapsulates a single capability in the knowledge extraction,
graph synthesis, validation, and serialization workflow.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.core.exceptions import (
    IngestionError,
    ExtractionError,
    ValidationError,
    SerializationError,
)
from backend.app.extraction.models import (
    ChangeRecord,
    Concept,
    ExtractionResult,
    Relationship,
)
from backend.app.extraction.pipeline import run_extraction
from backend.app.ingestion.loader import IngestionResult, SourceFile, scan_directory
from backend.app.knowledge.change_detector import SourceManifest, detect_changes
from backend.app.knowledge.conflict_detector import detect_claim_conflicts
from backend.app.knowledge.graph import KnowledgeGraph
from backend.app.knowledge.provenance import ProvenanceTracker
from backend.app.knowledge.repository import KnowledgeRepository
from backend.app.knowledge.validator import ValidationResult, validate_concepts

logger = logging.getLogger("knowledgesmith.agents.tools")


class IngestTool:
    """Tool for scanning and loading raw source files from disk."""

    def __init__(self, name: str = "ingest_sources") -> None:
        self.name = name

    def execute(
        self,
        root_dir: Path,
        max_file_size: int = 1_048_576,
        allowed_extensions: Optional[List[str]] = None,
    ) -> IngestionResult:
        """Scan *root_dir* and load valid source files."""
        logger.info("IngestTool: scanning directory %s", root_dir)
        try:
            allowed_set = set(allowed_extensions) if allowed_extensions else None
            result = scan_directory(
                root=root_dir,
                max_file_size=max_file_size,
                allowed_extensions=allowed_set,
            )
            logger.info("IngestTool: ingested %d files (skipped %d)", len(result.files), len(result.skipped))
            return result
        except Exception as e:
            logger.error("IngestTool failed: %s", e)
            raise IngestionError(f"Failed to ingest from {root_dir}: {e}") from e


class ChangeDetectionTool:
    """Tool for computing incremental differences against a prior manifest."""

    def __init__(self, name: str = "detect_changes") -> None:
        self.name = name

    def execute(
        self,
        current_files: List[SourceFile],
        manifest_path: Path,
    ) -> Tuple[List[ChangeRecord], SourceManifest]:
        """Compare current files with previous manifest, return changes and new manifest."""
        logger.info("ChangeDetectionTool: checking changes against %s", manifest_path)
        previous_manifest = SourceManifest.load(manifest_path)
        changes = detect_changes(current_files, previous_manifest)

        new_manifest = SourceManifest()
        for sf in current_files:
            new_manifest.record(sf)

        logger.info("ChangeDetectionTool: found %d changed records", len(changes))
        return changes, new_manifest


class ExtractionTool:
    """Tool for extracting concepts, claims, and relationships from source files."""

    def __init__(self, name: str = "extract_knowledge") -> None:
        self.name = name

    def execute(
        self,
        files: List[SourceFile],
        use_llm: bool = False,
        model_name: str = "gemini-2.5-flash",
    ) -> ExtractionResult:
        """Execute deterministic and optional LLM concept extraction."""
        logger.info("ExtractionTool: extracting from %d files (use_llm=%s)", len(files), use_llm)
        try:
            result = run_extraction(files, use_llm=use_llm, model_name=model_name)
            logger.info(
                "ExtractionTool: extracted %d concepts, %d relationships, %d errors",
                len(result.concepts),
                len(result.relationships),
                len(result.errors),
            )
            return result
        except Exception as e:
            logger.error("ExtractionTool failed: %s", e)
            raise ExtractionError(f"Extraction failed: {e}") from e


class ConflictResolutionTool:
    """Tool for identifying and reporting conflicts across claims and concepts."""

    def __init__(self, name: str = "resolve_conflicts") -> None:
        self.name = name

    def execute(self, concepts: List[Concept]) -> List[Dict[str, Any]]:
        """Identify potential claim conflicts across extracted concepts."""
        logger.info("ConflictResolutionTool: analyzing %d concepts", len(concepts))
        conflicts = detect_claim_conflicts(concepts)
        logger.info("ConflictResolutionTool: found %d conflict notices", len(conflicts))
        return conflicts


class GraphTool:
    """Tool for building the knowledge graph and extracting structural topology."""

    def __init__(self, name: str = "build_graph") -> None:
        self.name = name

    def execute(
        self,
        concepts: List[Concept],
        relationships: List[Relationship],
    ) -> KnowledgeGraph:
        """Construct a knowledge graph from concepts and relationships."""
        logger.info("GraphTool: constructing graph from %d concepts, %d relations", len(concepts), len(relationships))
        graph = KnowledgeGraph()
        graph.build_from(concepts, relationships)
        logger.info("GraphTool: graph has %d nodes", graph.node_count)
        return graph


class ValidationTool:
    """Tool for validating extracted artifacts against the OKF specification."""

    def __init__(self, name: str = "validate_artifacts") -> None:
        self.name = name

    def execute(
        self,
        concepts: List[Concept],
        relationships: List[Relationship],
    ) -> ValidationResult:
        """Validate concept schemas, types, links, and source reference integrity."""
        logger.info("ValidationTool: validating %d concepts, %d relationships", len(concepts), len(relationships))
        result = validate_concepts(concepts, relationships)
        logger.info(
            "ValidationTool: valid=%s (%d errors, %d warnings)",
            result.is_valid,
            result.error_count,
            result.warning_count,
        )
        return result


class SerializationTool:
    """Tool for generating OKF v0.2 Markdown files, index.md, and manifests."""

    def __init__(self, name: str = "serialize_okf") -> None:
        self.name = name

    def execute(
        self,
        concepts: List[Concept],
        relationships: List[Relationship],
        output_dir: Path,
        overwrite: bool = True,
        manifest: Optional[SourceManifest] = None,
        tracker: Optional[ProvenanceTracker] = None,
    ) -> List[Path]:
        """Serialize repository artifacts to disk."""
        logger.info("SerializationTool: writing to %s", output_dir)
        try:
            repo = KnowledgeRepository(output_dir=output_dir)
            repo.add_concepts(concepts, relationships)
            written = repo.write_all(overwrite=overwrite)

            # Persist manifest
            if manifest:
                manifest_path = output_dir / "manifest.json"
                manifest.save(manifest_path)
                written.append(manifest_path)

            # Persist provenance
            if tracker:
                prov_path = output_dir / "provenance.json"
                tracker.save(prov_path)
                written.append(prov_path)

            logger.info("SerializationTool: wrote %d artifacts", len(written))
            return written
        except Exception as e:
            logger.error("SerializationTool failed: %s", e)
            raise SerializationError(f"Serialization failed: {e}") from e
