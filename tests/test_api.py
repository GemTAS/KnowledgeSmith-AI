"""Tests for FastAPI endpoints."""

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_endpoints():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res_api = client.get("/api/health")
    assert res_api.status_code == 200
    assert res_api.json()["status"] == "ok"


def test_empty_state_queries():
    # Before pipeline runs, endpoints should return valid empty schemas without crashing
    res = client.get("/api/concepts")
    assert res.status_code == 200
    assert "concepts" in res.json()

    res_g = client.get("/api/graph")
    assert res_g.status_code == 200
    assert "nodes" in res_g.json()

    res_v = client.get("/api/validation")
    assert res_v.status_code == 200
    assert "is_valid" in res_v.json()

    res_e = client.get("/api/evaluation")
    assert res_e.status_code == 200
    assert "metrics" in res_e.json()


def test_pipeline_trigger(tmp_path):
    # Trigger pipeline on sample project
    sample_dir = tmp_path / "sample"
    sample_dir.mkdir()
    (sample_dir / "mod.py").write_text("class TestMod:\n    pass\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    res = client.post(
        "/api/pipeline/run",
        json={"input_dir": str(sample_dir), "output_dir": str(out_dir), "use_llm": False},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["stage"] == "completed"
    assert data["concepts_extracted"] >= 1

    # Verify concept now appears in concepts endpoint
    c_res = client.get("/api/concepts")
    assert c_res.status_code == 200
    assert c_res.json()["total"] >= 1
