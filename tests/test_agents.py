"""Tests for autonomous agents and knowledge orchestrator."""

from pathlib import Path

from backend.app.agents.orchestrator import KnowledgeOrchestrator, WorkflowStage


def test_orchestrator_end_to_end(tmp_path: Path):
    # Setup test workspace
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "calc.py").write_text(
        "class Calculator:\n    def add(self, a, b):\n        return a + b\n",
        encoding="utf-8",
    )
    (src_dir / "guide.md").write_text(
        "# Calculator Guide\nUse calculator to add numbers.\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "output"

    orchestrator = KnowledgeOrchestrator()
    status = orchestrator.run(
        input_dir=src_dir,
        output_dir=out_dir,
        use_llm=False,
    )

    assert status.stage == WorkflowStage.COMPLETED
    assert status.files_ingested == 2
    assert status.concepts_extracted >= 2
    assert status.artifacts_written >= 2
    assert (out_dir / "index.md").exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "provenance.json").exists()
