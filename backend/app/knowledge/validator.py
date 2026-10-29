"""OKF artifact validation — checks schema, links, and consistency."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from backend.app.extraction.models import Concept, Relationship

logger = logging.getLogger("knowledgesmith.knowledge.validator")


@dataclass
class ValidationIssue:
    """A single validation finding."""

    severity: str  # "error", "warning", "info"
    code: str
    message: str
    concept_id: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class ValidationResult:
    """Aggregate validation outcome."""

    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "severity": i.severity,
                    "code": i.code,
                    "message": i.message,
                    "concept_id": i.concept_id,
                }
                for i in self.issues
            ],
        }


def validate_concepts(
    concepts: List[Concept],
    relationships: List[Relationship],
) -> ValidationResult:
    """Validate concepts and relationships for OKF conformance.

    Checks:
    - Required fields (type).
    - Duplicate concept IDs.
    - Broken relationship targets.
    - Missing titles.
    - Empty descriptions.
    - Source reference integrity.
    """
    result = ValidationResult()
    seen_ids: Dict[str, str] = {}  # concept_id -> title

    for concept in concepts:
        # OKF requires `type`.
        if not concept.concept_type:
            result.issues.append(
                ValidationIssue(
                    severity="error",
                    code="MISSING_TYPE",
                    message=f"Concept '{concept.title}' has no type (required by OKF).",
                    concept_id=concept.concept_id,
                )
            )

        # Duplicate detection.
        if concept.concept_id in seen_ids:
            result.issues.append(
                ValidationIssue(
                    severity="warning",
                    code="DUPLICATE_ID",
                    message=(
                        f"Duplicate concept ID '{concept.concept_id}': "
                        f"'{concept.title}' conflicts with '{seen_ids[concept.concept_id]}'."
                    ),
                    concept_id=concept.concept_id,
                )
            )
        seen_ids[concept.concept_id] = concept.title

        # Recommend title.
        if not concept.title:
            result.issues.append(
                ValidationIssue(
                    severity="warning",
                    code="MISSING_TITLE",
                    message=f"Concept '{concept.concept_id}' has no title (recommended by OKF).",
                    concept_id=concept.concept_id,
                )
            )

        # Recommend description.
        if not concept.description:
            result.issues.append(
                ValidationIssue(
                    severity="info",
                    code="MISSING_DESCRIPTION",
                    message=f"Concept '{concept.title}' has no description.",
                    concept_id=concept.concept_id,
                )
            )

        # Source references.
        if not concept.source_refs:
            result.issues.append(
                ValidationIssue(
                    severity="info",
                    code="NO_SOURCE_REFS",
                    message=f"Concept '{concept.title}' has no source references.",
                    concept_id=concept.concept_id,
                )
            )

    # Validate relationship targets.
    for rel in relationships:
        if rel.target_concept_id not in seen_ids:
            result.issues.append(
                ValidationIssue(
                    severity="warning",
                    code="BROKEN_LINK",
                    message=(
                        f"Relationship '{rel.relationship_type}' from "
                        f"'{rel.source_concept_id}' targets unknown "
                        f"concept '{rel.target_concept_id}'."
                    ),
                    concept_id=rel.source_concept_id,
                )
            )
        if rel.source_concept_id not in seen_ids:
            result.issues.append(
                ValidationIssue(
                    severity="warning",
                    code="BROKEN_LINK_SOURCE",
                    message=(
                        f"Relationship '{rel.relationship_type}' originates from "
                        f"unknown concept '{rel.source_concept_id}'."
                    ),
                    concept_id=rel.source_concept_id,
                )
            )

    logger.info(
        "Validation: %d errors, %d warnings across %d concepts",
        result.error_count,
        result.warning_count,
        len(concepts),
    )
    return result


def validate_bundle_directory(bundle_dir: Path) -> ValidationResult:
    """Validate an on-disk OKF bundle directory.

    Checks:
    - All .md files have frontmatter with `type`.
    - index.md exists at root.
    - Internal markdown links resolve.
    """
    result = ValidationResult()

    if not bundle_dir.exists():
        result.issues.append(
            ValidationIssue(
                severity="error",
                code="BUNDLE_NOT_FOUND",
                message=f"Bundle directory does not exist: {bundle_dir}",
            )
        )
        return result

    # Check index.md
    index = bundle_dir / "index.md"
    if not index.exists():
        result.issues.append(
            ValidationIssue(
                severity="warning",
                code="MISSING_INDEX",
                message="Bundle root is missing index.md (recommended by OKF §8).",
            )
        )

    # Check each markdown file.
    md_files = list(bundle_dir.rglob("*.md"))
    known_paths: Set[str] = set()
    for f in md_files:
        rel = str(f.relative_to(bundle_dir)).replace("\\", "/")
        known_paths.add(rel)

    for f in md_files:
        rel = str(f.relative_to(bundle_dir)).replace("\\", "/")
        content = f.read_text(encoding="utf-8", errors="replace")

        # Check frontmatter existence.
        if content.startswith("---"):
            end = content.find("---", 3)
            if end == -1:
                result.issues.append(
                    ValidationIssue(
                        severity="error",
                        code="MALFORMED_FRONTMATTER",
                        message=f"Unclosed frontmatter in {rel}.",
                        file_path=rel,
                    )
                )
            else:
                fm = content[3:end].strip()
                if "type:" not in fm and "type :" not in fm:
                    # index.md and log.md are exempt from type requirement.
                    basename = f.name
                    if basename not in {"index.md", "log.md"}:
                        result.issues.append(
                            ValidationIssue(
                                severity="error",
                                code="MISSING_TYPE_FIELD",
                                message=f"File {rel} missing required 'type' in frontmatter.",
                                file_path=rel,
                            )
                        )
        else:
            basename = f.name
            if basename not in {"index.md", "log.md"}:
                result.issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="NO_FRONTMATTER",
                        message=f"File {rel} has no YAML frontmatter.",
                        file_path=rel,
                    )
                )

        # Check internal links.
        link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
        for match in link_pattern.finditer(content):
            target = match.group(2)
            if target.startswith("http") or target.startswith("#"):
                continue
            # Resolve relative to file's directory.
            resolved = (f.parent / target).resolve()
            try:
                resolved_rel = str(resolved.relative_to(bundle_dir)).replace("\\", "/")
            except ValueError:
                continue
            if resolved_rel not in known_paths and not resolved.exists():
                result.issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="BROKEN_INTERNAL_LINK",
                        message=f"In {rel}: link to '{target}' cannot be resolved.",
                        file_path=rel,
                    )
                )

    return result
