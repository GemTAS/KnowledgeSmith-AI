"""CLI script to benchmark and evaluate knowledge quality."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.agents.orchestrator import KnowledgeOrchestrator
from backend.app.evaluation.benchmark import KnowledgeBenchmark


def main() -> int:
    parser = argparse.ArgumentParser(
        description="KnowledgeSmith AI — Benchmark and Quality Evaluation",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="./examples/sample_project",
        help="Input source directory to evaluate against (default: ./examples/sample_project)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as raw JSON instead of table",
    )

    args = parser.parse_args()
    input_path = Path(args.input).resolve()

    orchestrator = KnowledgeOrchestrator()
    # Ingest and extract in memory
    ingest_res = orchestrator.ingest_tool.execute(input_path)
    extraction_res = orchestrator.extraction_tool.execute(ingest_res.files)

    benchmark = KnowledgeBenchmark()
    res = benchmark.evaluate(
        concepts=extraction_res.concepts,
        relationships=extraction_res.relationships,
        source_files=ingest_res.files,
    )

    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
        return 0 if res.passed else 1

    print("=" * 72)
    print(" KnowledgeSmith AI - Quality Benchmark Report")
    print(f" Analyzed Directory: {input_path}")
    print(f" Overall Score     : {round(res.overall_score, 1)} / 100  (Grade: {res.letter_grade})")
    print(f" Final Verdict     : {'PASSED' if res.passed else 'FAILED'}")
    print("=" * 72)

    print("\n Rubric Evaluation Checks:")
    print("-" * 72)
    for c in res.checks:
        status_sym = "[PASS]" if c.passed else "[FAIL]"
        print(f" {status_sym}  {c.name:<25} Actual: {str(c.actual):<12} Target: {c.target}")
        print(f"        +- {c.description}")
    print("-" * 72)

    m = res.metrics
    print("\n Quantitative Metrics Breakdown:")
    print(f" * Concepts Extracted    : {m.total_concepts}")
    print(f" * Extracted Claims      : {m.total_claims} (Density: {m.claim_density:.2f}/concept)")
    print(f" * Graph Relationships   : {m.total_relationships} (Broken Link Rate: {m.broken_link_rate * 100:.1f}%)")
    print(f" * Provenance Integrity  : {m.provenance_integrity * 100:.1f}%")
    print(f" * Validation Pass Rate  : {m.validation_pass_rate * 100:.1f}%\n")

    return 0 if res.passed else 1


if __name__ == "__main__":
    sys.exit(main())
