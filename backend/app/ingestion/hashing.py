"""Stable hashing and source-identifier generation."""

from __future__ import annotations

import hashlib


def compute_file_hash(content: str) -> str:
    """Return the SHA-256 hex digest of *content* (UTF-8 encoded)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def stable_source_id(relative_path: str) -> str:
    """Derive a stable, URL-safe identifier from a relative file path.

    The identifier is a truncated SHA-256 of the normalised path so that
    renames are detectable while the same path always maps to the same ID.
    """
    normalised = relative_path.replace("\\", "/").lower()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]
