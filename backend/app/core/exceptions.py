"""Core exceptions for KnowledgeSmith AI."""

from __future__ import annotations


class KnowledgeSmithError(Exception):
    """Base exception for all KnowledgeSmith errors."""


class IngestionError(KnowledgeSmithError):
    """Raised when source ingestion fails."""


class ExtractionError(KnowledgeSmithError):
    """Raised when concept extraction fails."""


class ValidationError(KnowledgeSmithError):
    """Raised when knowledge validation fails."""


class SerializationError(KnowledgeSmithError):
    """Raised when OKF serialization fails."""


class RepositoryError(KnowledgeSmithError):
    """Raised when knowledge repository operations fail."""


class LLMError(KnowledgeSmithError):
    """Raised when LLM integration fails."""


class SecurityError(KnowledgeSmithError):
    """Raised when a security constraint is violated."""
