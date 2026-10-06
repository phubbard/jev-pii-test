import json
from pathlib import Path

from jev_pii.cli import main


def test_end_to_end_mock(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    data = tmp_path / "data"
    main(["generate", "--records", "30", "--tables", "3", "--seed", "9", "--out", str(data)])
    out = tmp_path / "results"
    main(["run", "--data", str(data), "--out", str(out), "--cache", str(tmp_path / "c.sqlite"), "--mock", "--batch", "3"])
    runs = list(out.iterdir())
    assert len(runs) == 1 and runs[0].name.endswith("-MOCK")
    summary = json.loads((runs[0] / "summary.json").read_text())
    assert summary["usage"]["mock"] is True
    assert summary["record"]["n_records"] == 30
    assert summary["span"]["n_gold_spans"] > 0
    assert summary["column"]["n_columns"] > 0
    assert (runs[0] / "report.md").read_text().startswith("# jev-pii run")
    # second run hits the cache for every request
    main(["run", "--data", str(data), "--out", str(out), "--cache", str(tmp_path / "c.sqlite"), "--mock", "--batch", "3"])
    second = sorted(out.iterdir())[-1]
    s2 = json.loads((second / "summary.json").read_text())
    assert s2["usage"]["requests_sent"] == 0 and s2["usage"]["cache_hits"] > 0
