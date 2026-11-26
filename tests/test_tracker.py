from datetime import date
from pathlib import Path

from figreview.tracker import run

ROOT = Path(__file__).resolve().parents[1]


def test_demo_catches_every_planted_mistake(tmp_path):
    rows = {r["id"]: r for r in run(ROOT / "manifest.yaml", date(2026, 11, 25), tmp_path)}
    found = {k: {f["check"] for f in r["findings"]} for k, r in rows.items()}
    assert "value_mismatch" in found["benchmark_accuracy"]
    assert {"missing_row", "units"} <= found["compute_scaling"]
    assert {"claim", "caption_number"} <= found["refusal_heatmap"]
    assert found["jailbreak_mitigation"] == set()
    assert rows["jailbreak_mitigation"]["status"] == "approved"


def test_outputs_written(tmp_path):
    run(ROOT / "manifest.yaml", date(2026, 11, 25), tmp_path)
    assert (tmp_path / "tracker.html").exists()
    assert (tmp_path / "tracker.csv").exists()
    assert (tmp_path / "followups.md").read_text().count("- Figure") == 3
    assert len(list((tmp_path / "feedback").glob("*.md"))) == 4
