"""Smoke test for the bench harness CLI."""

from __future__ import annotations

import json
from pathlib import Path

from evalforge.bench import main


def test_bench_smoke_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EVALFORGE_BENCH_DIR", str(tmp_path / "bench-results"))
    rc = main(["--callers", "5", "--calls", "2"])
    assert rc == 0
    results_dir = tmp_path / "bench-results"
    files = list(results_dir.glob("run-*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["total_calls"] == 10
    assert payload["error_count"] == 0
    assert payload["latency_ms_p99"] > 0
