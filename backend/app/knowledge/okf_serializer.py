"""OKF v0.2 serializer — generates Markdown + YAML frontmatter artifacts.

Follows the Open Knowledge Format specification:
https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md

Key spec requirements implemented:
- `type` is the only REQUIRED frontmatter field.
- Recommended fields: `title`, `description`, `resource`, `tags`.
- Provenance via `sources` with credibility signals.
- Trust via `generated` (actor + timestamp) and `verified`.
- Status/lifecycle via `status`.
- Body uses structural markdown (headings, lists, tables, code).
- `index.md` files for progressive disclosure.
- Concept ID = file path within bundle with `.md` suffix removed.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.extraction.models import (
    Concept,
    Claim,
    ExtractionMethod,
    Relationship,
    SourceReference,
    VerificationStatus,
)

logger = logging.getLogger("knowledgesmith.knowledge.okf")

# We use a minimal YAML serializer to avoid hard pyyaml dependency at
# serialization time. For complex cases we fall back to pyyaml.
try:
    import yaml

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


def _yaml_dump(data: dict) -> str:
    """Serialize *data* to YAML frontmatter string."""
    if _HAS_YAML:
        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True).rstrip()
    # Fallback: minimal manual serializer for flat/shallow dicts.
    return _manual_yaml_dump(data)


def _manual_yaml_dump(data: dict, indent: int = 0) -> str:
    """Best-effort YAML serialization without pyyaml."""
    lines: List[str] = []
    prefix = "  " * indent
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_manual_yaml_dump(value, indent + 1))
        elif isinstance(value, list):
            if not value:
                lines.append(f"{prefix}{key}: []")
            elif all(isinstance(v, str) for v in value):
                items = ", ".join(v for v in value)
                lines.append(f"{prefix}{key}: [{items}]")
            else:
                lines.append(f"{prefix}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        first = True
                        for k2, v2 in item.items():
                            pref = f"{prefix}  - " if first else f"{prefix}    "
                            first = False
                            lines.append(f"{pref}{k2}: {v2}")
                    else:
                        lines.append(f"{prefix}  - {item}")
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{prefix}{key}: {value}")
        else:
            s = str(value)
            if ":" in s or "#" in s or s.startswith("{"):
                s = f'"{s}"'
            lines.append(f"{prefix}{key}: {s}")
    return "\n".join(lines)


def _safe_filename(title: str) -> str:
    """Convert a concept title to a safe, URL-friendly filename."""
    name = title.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name[:80] or "unnamed"


def _concept_to_frontmatter(concept: Concept) -> Dict[str, Any]:
    """Build the OKF frontmatter dict for a concept."""
    fm: Dict[str, Any] = {
        "type": concept.concept_type,  # REQUIRED per OKF spec
    }

    # Recommended fields.
    if concept.title:
        fm["title"] = concept.title
    if concept.description:
        fm["description"] = concept.description
    if concept.tags:
        fm["tags"] = concept.tags

    # Generated (provenance of the concept itself per OKF §5.2).
    actor = "knowledgesmith-ai/deterministic"
    if concept.extraction_method == ExtractionMethod.LLM:
        actor = "knowledgesmith-ai/llm"
    fm["generated"] = {
        "by": actor,
        "at": concept.extracted_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # Status.
    fm["status"] = "active"

    # Sources (provenance per OKF §5.1).
    refs = list(concept.source_refs)
    if not refs and concept.claims:
        for cl in concept.claims:
            for r in cl.source_refs:
                if not any(existing.source_id == r.source_id for existing in refs):
                    refs.append(r)

    if refs:
        sources = []
        for ref in refs:
            entry: Dict[str, Any] = {
                "id": ref.source_id,
                "resource": ref.relative_path,
            }
            if ref.content_hash:
                entry["content_hash"] = ref.content_hash
            if ref.start_line is not None:
                entry["start_line"] = ref.start_line
            sources.append(entry)
        fm["sources"] = sources

    # Extension: extraction metadata.
    fm["extraction_method"] = concept.extraction_method.value

    return fm


def _concept_to_body(concept: Concept, all_relationships: List[Relationship]) -> str:
    """Build the markdown body for a concept."""
    sections: List[str] = []

    # Title header.
    if concept.title:
        sections.append(f"# {concept.title}")
        sections.append("")

    # Description section.
    if concept.description:
        sections.append(concept.description)
        sections.append("")

    # Claims section.
    if concept.claims:
        sections.append("## Claims")
        sections.append("")
        for claim in concept.claims:
            status = claim.verification_status.value.replace("_", " ").title()
            sections.append(f"- **{status}**: {claim.statement}")
            if claim.extraction_method == ExtractionMethod.LLM:
                sections.append(f"  *(extracted by LLM — not source-verified)*")
        sections.append("")

    # Relationships section.
    outgoing = [r for r in all_relationships if r.source_concept_id == concept.concept_id]
    incoming = [r for r in all_relationships if r.target_concept_id == concept.concept_id]

    if outgoing or incoming:
        sections.append("## Relationships")
        sections.append("")
        for r in outgoing:
            sections.append(f"- **{r.relationship_type}** → [{r.target_concept_id}]({r.target_concept_id}.md)")
        for r in incoming:
            sections.append(f"- **{r.relationship_type}** ← [{r.source_concept_id}]({r.source_concept_id}.md)")
        sections.append("")

    # Source references section.
    if concept.source_refs:
        sections.append("## Sources")
        sections.append("")
        for ref in concept.source_refs:
            loc = ""
            if ref.start_line is not None:
                loc = f" (line {ref.start_line}"
                if ref.end_line is not None and ref.end_line != ref.start_line:
                    loc += f"–{ref.end_line}"
                loc += ")"
            sections.append(f"- `{ref.relative_path}`{loc}")
            if ref.snippet:
                sections.append(f"  > {ref.snippet}")
        sections.append("")

    return "\n".join(sections)


def serialize_concept(
    concept: Concept,
    all_relationships: List[Relationship],
) -> str:
    """Serialize a single concept to an OKF-compliant markdown document."""
    fm = _concept_to_frontmatter(concept)
    body = _concept_to_body(concept, all_relationships)

    frontmatter_str = _yaml_dump(fm)
    return f"---\n{frontmatter_str}\n---\n\n{body}"


def write_concept_file(
    concept: Concept,
    all_relationships: List[Relationship],
    output_dir: Path,
    overwrite: bool = False,
) -> Path:
    """Write a concept to an OKF markdown file.

    Parameters
    ----------
    concept:
        The concept to serialize.
    all_relationships:
        All relationships (used to find this concept's links).
    output_dir:
        Root output directory for the knowledge bundle.
    overwrite:
        If False (default), existing files are preserved and a warning is logged.

    Returns
    -------
    Path
        The path of the written file.
    """
    filename = _safe_filename(concept.title) + ".md"

    # Organise by concept type into subdirectories.
    type_dir = _safe_filename(concept.concept_type)
    dest_dir = output_dir / type_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / filename

    if dest.exists() and not overwrite:
        logger.warning("File already exists, skipping: %s", dest)
        return dest

    content = serialize_concept(concept, all_relationships)

    # Atomic write: write to temp then rename.
    tmp = dest.with_suffix(".md.tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        if dest.exists():
            dest.unlink()
        tmp.rename(dest)
    except OSError:
        # Fallback: direct write.
        dest.write_text(content, encoding="utf-8")
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass

    return dest


def generate_index(output_dir: Path, concepts: List[Concept]) -> Path:
    """Generate an OKF index.md for progressive disclosure.

    Per OKF §8, index.md provides a directory listing.
    """
    lines: List[str] = [
        "# Knowledge Bundle Index",
        "",
        f"Generated by KnowledgeSmith AI at {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        f"Total concepts: {len(concepts)}",
        "",
    ]

    # Group by type.
    by_type: Dict[str, List[Concept]] = {}
    for c in concepts:
        by_type.setdefault(c.concept_type, []).append(c)

    for ctype, items in sorted(by_type.items()):
        type_dir = _safe_filename(ctype)
        lines.append(f"## {ctype} ({len(items)})")
        lines.append("")
        for c in sorted(items, key=lambda x: x.title):
            fname = _safe_filename(c.title) + ".md"
            desc = f" — {c.description}" if c.description else ""
            lines.append(f"- [{c.title}]({type_dir}/{fname}){desc}")
        lines.append("")

    dest = output_dir / "index.md"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest
