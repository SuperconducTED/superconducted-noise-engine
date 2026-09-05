"""Integration tests for the one-time calibration state-index backfill."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.backfill_state_index import backfill
from scripts.pipeline_health import read_index


def _snapshot(t1: float) -> dict[str, object]:
    """Create the minimum document needed to exercise a qubit digest."""
    return {"properties": {"qubits": [[{"name": "T1", "value": t1}]]}}


def _write_snapshot(root: Path, name: str, t1: float) -> None:
    path = root / "snapshots/2026-09/ibm_fez" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_snapshot(t1)), encoding="utf-8")


def test_backfill_orders_rows_marks_duplicate_state_and_is_idempotent(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, "20260902T000000000000Z.json", 1.0)
    _write_snapshot(tmp_path, "20260901T000000000000Z.json", 1.0)
    _write_snapshot(tmp_path, "20260903T000000000000Z.json", 2.0)

    assert backfill(tmp_path) == 3
    rows = read_index(tmp_path / "health/state-index.tsv")
    assert [row.filename for row in rows] == [
        "20260901T000000000000Z.json",
        "20260902T000000000000Z.json",
        "20260903T000000000000Z.json",
    ]
    assert [row.is_new for row in rows] == [True, False, True]
    assert backfill(tmp_path) == 0
    assert read_index(tmp_path / "health/state-index.tsv") == rows
