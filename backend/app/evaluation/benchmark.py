"""Benchmarking suite for knowledge bundles."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.evaluation.metrics import EvaluationMetrics, compute_metrics
from backend.app.extraction.models import Concept, Relationship
from backend.app.ingestion.loader import SourceFile
from backend.app.knowledge.graph import KnowledgeGraph
from backend.app.knowledge.validator import ValidationResult, validate_concepts

logger = logging.getLogger("knowledgesmith.evaluation.benchmark")


@dataclass
class BenchmarkCheck:
    """Individual quality check result."""

    name: str
    target: str
    actual: Any
    passed: bool
    description: str


@dataclass
class BenchmarkResult:
    """Consolidated outcome of the benchmark suite."""

    passed: bool
    overall_score: float
    letter_grade: str
    metrics: EvaluationMetrics
    checks: List[BenchmarkCheck] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "overall_score": round(self.overall_score, 1),
            "letter_grade": self.letter_grade,
            "summary": self.summary,
            "metrics": self.metrics.to_dict(),
            "checks": [
                {
                    "name": c.name,
                    "target": c.target,
                    "actual": c.actual,
                    "passed": c.passed,
                    "description": c.description,
                }
                for c in self.checks
            ],
        }


class KnowledgeBenchmark:
    """Benchmark suite asserting knowledge bundle quality thresholds."""

    def __init__(
        self,
        min_health_score: float = 70.0,
        max_validation_errors: int = 0,
        min_provenance_integrity: float = 0.80,
        max_broken_link_rate: float = 0.15,
        min_claim_density: float = 1.0,
    ) -> None:
        self.min_health_score = min_health_score
        self.max_validation_errors = max_validation_errors
        self.min_provenance_integrity = min_provenance_integrity
        self.max_broken_link_rate = max_broken_link_rate
        self.min_claim_density = min_claim_density

    def evaluate(
        self,
        concepts: List[Concept],
        relationships: List[Relationship],
        source_files: Optional[List[SourceFile]] = None,
        validation: Optional[ValidationResult] = None,
    ) -> BenchmarkResult:
        """Run benchmark checks against the extracted bundle."""
        if validation is None:
            validation = validate_concepts(concepts, relationships)

        metrics = compute_metrics(
            concepts=concepts,
            relationships=relationships,
            source_files=source_files,
            validation=validation,
        )

        checks: List[BenchmarkCheck] = []

        # 1. Validation Zero-Error Check
        err_passed = metrics.validation_errors <= self.max_validation_errors
        checks.append(
            BenchmarkCheck(
                name="Validation Errors",
                target=f"<= {self.max_validation_errors}",
                actual=metrics.validation_errors,
                passed=err_passed,
                description="Zero schema and critical OKF validation errors.",
            )
        )

        # 2. Provenance Integrity Check
        prov_passed = metrics.provenance_integrity >= self.min_provenance_integrity
        checks.append(
            BenchmarkCheck(
                name="Provenance Integrity",
                target=f">= {int(self.min_provenance_integrity * 100)}%",
                actual=f"{round(metrics.provenance_integrity * 100, 1)}%",
                passed=prov_passed,
                description="Claims with traceable source file hashes and IDs.",
            )
        )

        # 3. Graph Linkage Check
        link_passed = metrics.broken_link_rate <= self.max_broken_link_rate
        checks.append(
            BenchmarkCheck(
                name="Broken Link Rate",
                target=f"<= {int(self.max_broken_link_rate * 100)}%",
                actual=f"{round(metrics.broken_link_rate * 100, 1)}%",
                passed=link_passed,
                description="Proportion of relationship targets missing from graph.",
            )
        )

        # 4. Claim Density Check
        density_passed = metrics.claim_density >= self.min_claim_density
        checks.append(
            BenchmarkCheck(
                name="Claim Density",
                target=f">= {self.min_claim_density}",
                actual=round(metrics.claim_density, 2),
                passed=density_passed,
                description="Average number of claims extracted per concept.",
            )
        )

        # 5. Composite Health Check
        score = metrics.composite_health_score
        score_passed = score >= self.min_health_score
        checks.append(
            BenchmarkCheck(
                name="Composite Health Score",
                target=f">= {self.min_health_score}",
                actual=round(score, 1),
                passed=score_passed,
                description="Aggregate quality score reflecting all dimensions.",
            )
        )

        all_passed = all(c.passed for c in checks)

        # Letter grade assignment
        if score >= 90:
            letter = "A"
        elif score >= 80:
            letter = "B"
        elif score >= 70:
            letter = "C"
        elif score >= 60:
            letter = "D"
        else:
            letter = "F"

        passed_count = sum(1 for c in checks if c.passed)
        summary = (
            f"Benchmark {'PASSED' if all_passed else 'FAILED'}: "
            f"{passed_count}/{len(checks)} checks satisfied. "
            f"Overall Score: {round(score, 1)}/100 (Grade: {letter})."
        )

        return BenchmarkResult(
            passed=all_passed,
            overall_score=score,
            letter_grade=letter,
            metrics=metrics,
            checks=checks,
            summary=summary,
        )
