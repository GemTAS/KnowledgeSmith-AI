"""Evaluation package — metrics, benchmarking, and quality assessment."""

from backend.app.evaluation.metrics import EvaluationMetrics, compute_metrics
from backend.app.evaluation.benchmark import KnowledgeBenchmark, BenchmarkResult

__all__ = [
    "EvaluationMetrics",
    "compute_metrics",
    "KnowledgeBenchmark",
    "BenchmarkResult",
]
