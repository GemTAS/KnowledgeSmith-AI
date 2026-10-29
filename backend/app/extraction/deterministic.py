"""Deterministic concept extractor — works offline without any API key.

Uses transparent heuristics: headings, Python declarations (classes,
functions, imports), filenames, and identifiers.  This is explicitly
*not* equivalent to language-model understanding — it finds surface-level
candidates only.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import List

from backend.app.extraction.models import (
    Claim,
    Concept,
    ExtractionMethod,
    ExtractionResult,
    Relationship,
    SourceReference,
    VerificationStatus,
)
from backend.app.ingestion.loader import SourceFile

logger = logging.getLogger("knowledgesmith.extraction.deterministic")

# ── Regular expressions for Python source ────────────────────────────

_RE_CLASS = re.compile(r"^class\s+(\w+)\s*[:\(]", re.MULTILINE)
_RE_FUNCTION = re.compile(r"^def\s+(\w+)\s*\(", re.MULTILINE)
_RE_IMPORT = re.compile(
    r"^(?:from\s+([\w.]+)\s+)?import\s+([\w., ]+)", re.MULTILINE
)
_RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _make_concept_id(relative_path: str, name: str) -> str:
    """Deterministic concept ID from path + name."""
    raw = f"{relative_path}::{name}".lower().replace("\\", "/")
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _make_claim_id(concept_id: str, idx: int) -> str:
    return f"{concept_id}-c{idx}"


def _source_ref(sf: SourceFile, start: int | None = None, end: int | None = None, snippet: str = "") -> SourceReference:
    return SourceReference(
        source_id=sf.source_id,
        relative_path=sf.relative_path,
        content_hash=sf.content_hash,
        start_line=start,
        end_line=end,
        snippet=snippet[:200] if snippet else None,
    )


# ── File-level concept ───────────────────────────────────────────────

def _extract_file_concept(sf: SourceFile) -> Concept:
    """Every source file becomes at least one concept — the file itself."""
    name = sf.relative_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    title = name.replace("_", " ").replace("-", " ").title()
    cid = _make_concept_id(sf.relative_path, "__file__")

    description_lines = []
    for line in sf.content.split("\n")[:10]:
        stripped = line.strip().strip("#").strip()
        if stripped and not stripped.startswith("```"):
            description_lines.append(stripped)
            break

    desc_text = " ".join(description_lines) or f"Source file: {sf.relative_path}"
    claims: List[Claim] = [
        Claim(
            claim_id=_make_claim_id(cid, 1),
            statement=f"{title}: {desc_text}",
            source_refs=[_source_ref(sf, start=1, end=min(5, len(sf.content.splitlines())), snippet=desc_text)],
            extraction_method=ExtractionMethod.DETERMINISTIC,
            verification_status=VerificationStatus.UNVERIFIED,
        )
    ]

    return Concept(
        concept_id=cid,
        title=title,
        concept_type="Source File",
        description=desc_text,
        claims=claims,
        source_refs=[_source_ref(sf)],
        tags=_infer_tags(sf),
        extraction_method=ExtractionMethod.DETERMINISTIC,
        metadata={"relative_path": sf.relative_path, "extension": sf.extension},
    )


def _infer_tags(sf: SourceFile) -> List[str]:
    """Infer tags from the file extension and path components."""
    tags: List[str] = []
    ext_map = {
        ".py": "python",
        ".md": "documentation",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".txt": "text",
    }
    if sf.extension in ext_map:
        tags.append(ext_map[sf.extension])

    parts = sf.relative_path.replace("\\", "/").split("/")
    for part in parts[:-1]:
        clean = part.lower().strip()
        if clean and clean not in {"src", "lib", "app"}:
            tags.append(clean)

    return tags


# ── Markdown heading extraction ──────────────────────────────────────

def _extract_headings(sf: SourceFile) -> List[Concept]:
    """Extract concepts from markdown headings."""
    if sf.extension not in {".md", ".txt"}:
        return []

    concepts: List[Concept] = []
    lines = sf.content.split("\n")

    for match in _RE_HEADING.finditer(sf.content):
        heading_text = match.group(2).strip()
        if len(heading_text) < 2:
            continue

        level = len(match.group(1))
        line_no = sf.content[: match.start()].count("\n") + 1

        cid = _make_concept_id(sf.relative_path, heading_text)
        ctype = "Section" if level > 1 else "Document"

        # Gather content under this heading for the description.
        end_line = line_no
        for j in range(line_no, min(line_no + 5, len(lines))):
            l = lines[j].strip() if j < len(lines) else ""
            if l and not l.startswith("#"):
                desc = l[:150]
                end_line = j + 1
                break
        else:
            desc = heading_text

        claims: List[Claim] = []
        if desc and desc != heading_text:
            claims.append(
                Claim(
                    claim_id=_make_claim_id(cid, 1),
                    statement=desc,
                    source_refs=[_source_ref(sf, start=line_no, end=end_line, snippet=desc)],
                    extraction_method=ExtractionMethod.DETERMINISTIC,
                    verification_status=VerificationStatus.UNVERIFIED,
                )
            )

        concepts.append(
            Concept(
                concept_id=cid,
                title=heading_text,
                concept_type=ctype,
                description=desc,
                claims=claims,
                source_refs=[_source_ref(sf, start=line_no, end=end_line, snippet=heading_text)],
                tags=_infer_tags(sf),
                extraction_method=ExtractionMethod.DETERMINISTIC,
            )
        )

    return concepts


# ── Python declaration extraction ────────────────────────────────────

def _extract_python_declarations(sf: SourceFile) -> tuple[List[Concept], List[Relationship]]:
    """Extract class and function concepts from Python source."""
    if sf.extension != ".py":
        return [], []

    concepts: List[Concept] = []
    relationships: List[Relationship] = []
    file_cid = _make_concept_id(sf.relative_path, "__file__")
    lines = sf.content.split("\n")

    # Classes
    for match in _RE_CLASS.finditer(sf.content):
        name = match.group(1)
        line_no = sf.content[: match.start()].count("\n") + 1
        cid = _make_concept_id(sf.relative_path, f"class:{name}")

        # Try to extract the docstring.
        desc = f"Class {name}"
        for j in range(line_no, min(line_no + 5, len(lines))):
            l = lines[j].strip() if j < len(lines) else ""
            if l.startswith('"""') or l.startswith("'''"):
                desc = l.strip("\"'").strip()[:150] or desc
                break

        claims: List[Claim] = []
        if desc:
            claims.append(
                Claim(
                    claim_id=_make_claim_id(cid, 1),
                    statement=f"{name}: {desc}",
                    source_refs=[_source_ref(sf, start=line_no, end=line_no + 1, snippet=desc)],
                    extraction_method=ExtractionMethod.DETERMINISTIC,
                    verification_status=VerificationStatus.UNVERIFIED,
                )
            )

        concepts.append(
            Concept(
                concept_id=cid,
                title=name,
                concept_type="Class",
                description=desc,
                claims=claims,
                source_refs=[_source_ref(sf, start=line_no, end=line_no, snippet=match.group(0))],
                tags=["python", "class"],
                extraction_method=ExtractionMethod.DETERMINISTIC,
            )
        )
        relationships.append(
            Relationship(
                source_concept_id=file_cid,
                target_concept_id=cid,
                relationship_type="defines",
            )
        )

    # Functions
    for match in _RE_FUNCTION.finditer(sf.content):
        name = match.group(1)
        if name.startswith("_"):
            continue  # Skip private helpers.
        line_no = sf.content[: match.start()].count("\n") + 1
        cid = _make_concept_id(sf.relative_path, f"func:{name}")

        desc = f"Function {name}"
        for j in range(line_no, min(line_no + 5, len(lines))):
            l = lines[j].strip() if j < len(lines) else ""
            if l.startswith('"""') or l.startswith("'''"):
                desc = l.strip("\"'").strip()[:150] or desc
                break

        claims = []
        if desc:
            claims.append(
                Claim(
                    claim_id=_make_claim_id(cid, 1),
                    statement=f"{name}: {desc}",
                    source_refs=[_source_ref(sf, start=line_no, end=line_no + 1, snippet=desc)],
                    extraction_method=ExtractionMethod.DETERMINISTIC,
                    verification_status=VerificationStatus.UNVERIFIED,
                )
            )

        concepts.append(
            Concept(
                concept_id=cid,
                title=name,
                concept_type="Function",
                description=desc,
                claims=claims,
                source_refs=[_source_ref(sf, start=line_no, end=line_no, snippet=match.group(0))],
                tags=["python", "function"],
                extraction_method=ExtractionMethod.DETERMINISTIC,
            )
        )
        relationships.append(
            Relationship(
                source_concept_id=file_cid,
                target_concept_id=cid,
                relationship_type="defines",
            )
        )

    # Imports → relationships
    seen_modules = set()
    for match in _RE_IMPORT.finditer(sf.content):
        module = (match.group(1) or match.group(2).split(",")[0]).strip()
        if not module or module in seen_modules:
            continue
        seen_modules.add(module)
        mod_cid = _make_concept_id("__external__", f"module:{module}")
        claims = [
            Claim(
                claim_id=_make_claim_id(mod_cid, 1),
                statement=f"Module '{module}' is imported as a dependency.",
                source_refs=[_source_ref(sf, snippet=match.group(0).strip())],
                extraction_method=ExtractionMethod.DETERMINISTIC,
                verification_status=VerificationStatus.UNVERIFIED,
            )
        ]
        concepts.append(
            Concept(
                concept_id=mod_cid,
                title=module,
                concept_type="Module",
                description=f"Imported module '{module}'",
                claims=claims,
                tags=["python", "module", "dependency"],
                extraction_method=ExtractionMethod.DETERMINISTIC,
            )
        )
        relationships.append(
            Relationship(
                source_concept_id=file_cid,
                target_concept_id=mod_cid,
                relationship_type="imports",
                evidence=match.group(0).strip(),
            )
        )

    return concepts, relationships



# ── JSON / YAML key extraction ───────────────────────────────────────

def _extract_json_keys(sf: SourceFile) -> List[Claim]:
    """Extract top-level keys from JSON files as claims."""
    if sf.extension != ".json":
        return []

    import json

    try:
        data = json.loads(sf.content)
    except (json.JSONDecodeError, ValueError):
        return []

    claims: List[Claim] = []
    if isinstance(data, dict):
        file_cid = _make_concept_id(sf.relative_path, "__file__")
        for i, key in enumerate(list(data.keys())[:20]):
            val = data[key]
            val_summary = str(val)[:100] if not isinstance(val, (dict, list)) else f"({type(val).__name__})"
            claims.append(
                Claim(
                    claim_id=_make_claim_id(file_cid, i),
                    statement=f"Key '{key}': {val_summary}",
                    source_refs=[_source_ref(sf, snippet=f'"{key}": ...')],
                    extraction_method=ExtractionMethod.DETERMINISTIC,
                    verification_status=VerificationStatus.UNVERIFIED,
                )
            )

    return claims


# ── Public entry point ───────────────────────────────────────────────

def extract_deterministic(files: List[SourceFile]) -> ExtractionResult:
    """Run the deterministic extraction pipeline over a list of source files.

    This extractor uses surface-level heuristics and does not claim to
    understand semantics.  It is designed to work fully offline without
    any API key.
    """
    result = ExtractionResult(
        source_file_count=len(files),
        extraction_method=ExtractionMethod.DETERMINISTIC,
    )

    for sf in files:
        try:
            # File-level concept.
            file_concept = _extract_file_concept(sf)
            # JSON claims go onto the file concept.
            file_concept.claims.extend(_extract_json_keys(sf))
            result.concepts.append(file_concept)

            # Heading concepts (markdown).
            heading_concepts = _extract_headings(sf)
            result.concepts.extend(heading_concepts)
            # Link heading concepts to file concept.
            for hc in heading_concepts:
                result.relationships.append(
                    Relationship(
                        source_concept_id=file_concept.concept_id,
                        target_concept_id=hc.concept_id,
                        relationship_type="contains",
                    )
                )

            # Python declarations.
            py_concepts, py_rels = _extract_python_declarations(sf)
            result.concepts.extend(py_concepts)
            result.relationships.extend(py_rels)

        except Exception as exc:
            logger.warning("Extraction error for %s: %s", sf.relative_path, exc)
            result.errors.append(f"{sf.relative_path}: {exc}")

    logger.info(
        "Deterministic extraction: %d concepts, %d relationships from %d files",
        len(result.concepts),
        len(result.relationships),
        len(files),
    )
    return result
