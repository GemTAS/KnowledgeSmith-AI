"""CLI script to run the KnowledgeSmith knowledge engineering pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.agents.orchestrator import KnowledgeOrchestrator
from backend.app.core.logging_config import setup_logging


def main() -> int:
    parser = argparse.ArgumentParser(
        description="KnowledgeSmith AI — Autonomous Knowledge Engineering Platform",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="./examples/sample_project",
        help="Input source directory to scan (default: ./examples/sample_project)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="./output",
        help="Output directory for OKF artifacts (default: ./output)",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable Gemini LLM extraction (requires GOOGLE_API_KEY)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini model name (default: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    print("=" * 64)
    print(" KnowledgeSmith AI — Knowledge Engineering Pipeline")
    print(f" Input Directory : {input_path}")
    print(f" Output Directory: {output_path}")
    print(f" LLM Extraction  : {args.use_llm}")
    print("=" * 64)

    orchestrator = KnowledgeOrchestrator()
    status = orchestrator.run(
        input_dir=input_path,
        output_dir=output_path,
        use_llm=args.use_llm,
        model_name=args.model,
    )

    print("\n" + "=" * 64)
    print(" Execution Summary")
    print("=" * 64)
    print(f" Status        : {status.stage.value.upper()}")
    print(f" Elapsed Time  : {round(status.elapsed_seconds, 2)}s")
    print(f" Files Ingested: {status.files_ingested}")
    print(f" Concepts      : {status.concepts_extracted}")
    print(f" Claims        : {status.claims_extracted}")
    print(f" Relationships : {status.relationships_extracted}")
    print(f" Conflicts     : {status.conflicts_detected}")
    print(f" OKF Errors    : {status.validation_errors}")
    print(f" OKF Warnings  : {status.validation_warnings}")
    print(f" Artifacts     : {status.artifacts_written}")
    print("=" * 64)

    if status.stage.value == "failed":
        print(f"\n[ERROR] Pipeline failed: {status.error_message}", file=sys.stderr)
        return 1

    print("\n[SUCCESS] Knowledge artifacts generated successfully!")
    print(f"Explore the bundle at: {output_path / 'index.md'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
