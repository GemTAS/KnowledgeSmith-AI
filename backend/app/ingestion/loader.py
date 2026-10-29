"""Source file loader — recursive directory scanning with safety checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Set

from backend.app.core.exceptions import IngestionError, SecurityError
from backend.app.ingestion.hashing import compute_file_hash, stable_source_id

logger = logging.getLogger("knowledgesmith.ingestion")

# Directories that must always be excluded.
_EXCLUDED_DIRS: Set[str] = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".eggs",
    "dist",
    "build",
    "output",
    ".next",
    ".nuxt",
}


@dataclass
class SourceFile:
    """Represents a single ingested source file."""

    path: Path
    relative_path: str
    content: str
    content_hash: str
    source_id: str
    size_bytes: int
    extension: str

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "relative_path": self.relative_path,
            "content_hash": self.content_hash,
            "source_id": self.source_id,
            "size_bytes": self.size_bytes,
            "extension": self.extension,
        }


@dataclass
class IngestionResult:
    """Result of scanning a source directory."""

    files: List[SourceFile] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.files)


def _is_excluded_dir(name: str) -> bool:
    return name in _EXCLUDED_DIRS or name.startswith(".")


def _resolve_and_check_root(root: Path) -> Path:
    """Resolve the ingestion root and ensure it exists."""
    resolved = root.resolve()
    if not resolved.exists():
        raise IngestionError(f"Ingestion root does not exist: {resolved}")
    if not resolved.is_dir():
        raise IngestionError(f"Ingestion root is not a directory: {resolved}")
    return resolved


def load_sources(
    root: Path,
    allowed_extensions: Optional[List[str]] = None,
    max_file_size: int = 1_048_576,
) -> IngestionResult:
    """Recursively scan *root* and load source files.

    Parameters
    ----------
    root:
        Directory to scan.  Must already exist.
    allowed_extensions:
        File suffixes to accept, e.g. ``[".md", ".py"]``.
        ``None`` means accept everything.
    max_file_size:
        Files larger than this (bytes) are skipped.

    Returns
    -------
    IngestionResult
        Loaded files, errors, and skipped paths.

    Security
    --------
    - Symlinks that escape *root* are rejected.
    - Source code is never executed.
    """
    resolved_root = _resolve_and_check_root(root)
    result = IngestionResult()

    if allowed_extensions is not None:
        exts = {e if e.startswith(".") else f".{e}" for e in allowed_extensions}
    else:
        exts = None

    for path in sorted(resolved_root.rglob("*")):
        # Skip directories themselves — we only care about files.
        if path.is_dir():
            continue

        # Exclude hidden / unwanted directories anywhere in ancestry.
        parts = path.relative_to(resolved_root).parts
        if any(_is_excluded_dir(p) for p in parts[:-1]):
            continue

        # Symlink escape check.
        try:
            real = path.resolve()
            real.relative_to(resolved_root)
        except (ValueError, OSError):
            result.skipped.append(f"symlink-escape:{path}")
            logger.warning("Skipping symlink that escapes root: %s", path)
            continue

        # Extension filter.
        if exts is not None and path.suffix.lower() not in exts:
            continue

        # Size filter.
        try:
            size = path.stat().st_size
        except OSError as exc:
            result.errors.append(f"stat-error:{path}: {exc}")
            continue

        if size > max_file_size:
            result.skipped.append(f"too-large:{path} ({size} bytes)")
            logger.info("Skipping oversized file: %s (%d bytes)", path, size)
            continue

        # Read content.
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            result.errors.append(f"read-error:{path}: {exc}")
            continue

        rel = path.relative_to(resolved_root)
        content_hash = compute_file_hash(content)
        sid = stable_source_id(str(rel))

        result.files.append(
            SourceFile(
                path=path,
                relative_path=str(rel).replace("\\", "/"),
                content=content,
                content_hash=content_hash,
                source_id=sid,
                size_bytes=size,
                extension=path.suffix.lower(),
            )
        )

    logger.info(
        "Ingested %d files (%d errors, %d skipped) from %s",
        result.total,
        len(result.errors),
        len(result.skipped),
        resolved_root,
    )
    return result


def scan_directory(
    root: Path,
    max_file_size: int = 1_048_576,
    allowed_extensions: Optional[Any] = None,
) -> IngestionResult:
    """Convenience alias for load_sources with flexible parameter options."""
    if allowed_extensions is not None and not isinstance(allowed_extensions, list):
        allowed_extensions = list(allowed_extensions)
    return load_sources(root=root, allowed_extensions=allowed_extensions, max_file_size=max_file_size)

