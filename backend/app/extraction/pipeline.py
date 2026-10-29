"""Extraction pipeline — orchestrates deterministic and optional LLM extraction."""

from __future__ import annotations

import logging
from typing import List

from backend.app.extraction.deterministic import extract_deterministic
from backend.app.extraction.llm import extract_llm
from backend.app.extraction.models import ExtractionResult, Concept, Relationship
from backend.app.ingestion.loader import SourceFile

logger = logging.getLogger("knowledgesmith.extraction.pipeline")


def _merge_results(base: ExtractionResult, extra: ExtractionResult) -> ExtractionResult:
    """Merge *extra* into *base* without duplicating concepts by ID."""
    seen_ids = {c.concept_id for c in base.concepts}
    for c in extra.concepts:
        if c.concept_id not in seen_ids:
            base.concepts.append(c)
            seen_ids.add(c.concept_id)
    base.relationships.extend(extra.relationships)
    base.errors.extend(extra.errors)
    return base


def run_extraction(
    files: List[SourceFile],
    use_llm: bool = False,
    model_name: str = "gemini-2.5-flash",
) -> ExtractionResult:
    """Run the full extraction pipeline.

    1. Always runs deterministic extraction (offline, no API key needed).
    2. Optionally runs LLM extraction and merges results.

    Parameters
    ----------
    files:
        Source files from the ingestion phase.
    use_llm:
        Whether to also invoke the LLM extractor.
    model_name:
        Model name when using LLM extraction.
    """
    logger.info("Starting extraction pipeline for %d files (use_llm=%s)", len(files), use_llm)

    # Phase 1: Deterministic.
    result = extract_deterministic(files)

    # Phase 2: Optional LLM.
    if use_llm:
        llm_result = extract_llm(files, model_name=model_name)
        result = _merge_results(result, llm_result)

    logger.info(
        "Extraction complete: %d concepts, %d relationships, %d errors",
        len(result.concepts),
        len(result.relationships),
        len(result.errors),
    )
    return result
