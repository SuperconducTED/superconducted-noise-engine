"""Tests for the archive side of the #125 hardware test (scripts/hardware_test_predictors.py).

Synthetic archive documents in the real schema; no git, no network, no filesystem beyond
``tmp_path`` for the CLI writer.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scripts.hardware_test_predictors import (
    MIN_WINDOW_STATES,
    collect,
    execution_rows,
    predictor_rows,
    propose_controls,
    select_discriminating,
    write_outputs,
)

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
N_QUBITS = 4


def _nduv(name: str, unit: str, value: float | None, stamp: datetime) -> dict[str, Any]:
    return {"date": stamp.isoformat(), "name": name, "unit": unit, "value": value}


def _doc(
    stamp: datetime,
    t1_us: dict[int, float | None],
    *,
    readout: float = 0.01,
    backend: str = "ibm_fez",
) -> tuple[str, dict[str, Any]]:
    """One archive document; T1 in microseconds as IBM publishes it, T2 = T1."""
    qubits = []
    for q in range(N_QUBITS):
        t1 = t1_us.get(q, 100.0)
        entries = []
        if t1 is not None:
            entries.append(_nduv("T1", "us", t1, stamp))
            entries.append(_nduv("T2", "us", t1, stamp))
        entries.append(_nduv("readout_error", "", readout, stamp))
        entries.append(_nduv("prob_meas0_prep1", "", readout * 1.5, stamp))
        entries.append(_nduv("prob_meas1_prep0", "", readout * 0.5, stamp))
        qubits.append(entries)
    path = f"snapshots/{stamp:%Y-%m}/{backend}/{stamp:%Y%m%dT%H%M%S}000000Z.json"
    doc = {
        "backend": backend,
        "timestamp": stamp.isoformat(),
        "schema_version": 1,
        "properties": {
            "backend_name": backend,
            "backend_version": "1.0",
            "last_update_date": stamp.isoformat(),
            "qubits": qubits,
            "gates": [],
            "general": [],
        },
    }
    return path, doc


def _archive(days: int, t1_by_day: dict[int, dict[int, float | None]] | None = None) -> list[Any]:
    docs = []
    for d in range(days):
        stamp = T0 - timedelta(days=days - 1 - d)
        docs.append(_doc(stamp, (t1_by_day or {}).get(d, {0: 100.0 + d})))
    return docs


def test_level_is_the_geometric_mean_and_band_brackets_it() -> None:
    docs = _archive(8)  # qubit 0: T1 = 100..107 us, one state per day
    col = collect(docs, backend="ibm_fez", until=T0)
    rows = predictor_rows(col, at=T0, live=None)
    row = next(r for r in rows if r.qubit == 0 and r.quantity == "T1")
    expected = math.exp(np.mean(np.log(np.arange(100, 108) * 1e-6)))
    assert row.n_window == 8
    assert row.level == pytest.approx(expected, rel=1e-12)
    assert row.band_lo <= row.level <= row.band_hi
    assert row.reading == pytest.approx(107e-6, rel=1e-12)
    assert row.log_disagreement == pytest.approx(math.log(107e-6) - math.log(expected), rel=1e-9)


def test_window_excludes_older_states_and_includes_the_state_at_t_s() -> None:
    docs = _archive(40)  # 40 daily states; the window keeps 30 days, (T0 - 30 d, T0]
    col = collect(docs, backend="ibm_fez", until=T0)
    row = next(
        r for r in predictor_rows(col, at=T0, live=None) if r.qubit == 0 and r.quantity == "T1"
    )
    assert row.n_window == 30
    # the state exactly 30 days old is excluded, the one at T0 included
    at_edge = next(
        r
        for r in predictor_rows(col, at=T0 - timedelta(days=9), live=None)
        if r.qubit == 0 and r.quantity == "T1"
    )
    assert at_edge.n_window == 30
    assert at_edge.reading == pytest.approx((100 + 30) * 1e-6, rel=1e-12)


def test_reading_is_the_latest_file_not_the_first_file_of_the_state() -> None:
    # two files with identical qubit blocks are one state; the later file's time is not the state's
    base = _archive(6)
    path, doc = base[-1]
    later = (path.replace("Z.json", "1Z.json"), json.loads(json.dumps(doc)))
    later[1]["properties"]["last_update_date"] = (T0 + timedelta(hours=1)).isoformat()
    col = collect([*base, later], backend="ibm_fez", until=T0 + timedelta(hours=2))
    assert len(col.states) == 6
    assert len(col.files) == 7
    row = next(
        r
        for r in predictor_rows(col, at=T0 + timedelta(hours=2), live=None)
        if r.qubit == 0 and r.quantity == "T1"
    )
    assert row.reading_time == (T0 + timedelta(hours=1)).isoformat()


def test_fewer_than_min_states_gives_nan_not_a_number() -> None:
    docs = _archive(MIN_WINDOW_STATES - 1)
    col = collect(docs, backend="ibm_fez", until=T0)
    row = next(
        r for r in predictor_rows(col, at=T0, live=None) if r.qubit == 0 and r.quantity == "T1"
    )
    assert row.n_window == MIN_WINDOW_STATES - 1
    assert math.isnan(row.level) and math.isnan(row.band_lo) and math.isnan(row.log_disagreement)
    assert row.reading == pytest.approx((100 + MIN_WINDOW_STATES - 2) * 1e-6)


def test_missing_t1_gives_nan_reading_and_nan_disagreement() -> None:
    docs = _archive(8, {d: {0: 100.0 + d, 3: None} for d in range(8)})
    col = collect(docs, backend="ibm_fez", until=T0)
    row = next(
        r for r in predictor_rows(col, at=T0, live=None) if r.qubit == 3 and r.quantity == "T1"
    )
    assert math.isnan(row.reading) and math.isnan(row.level) and math.isnan(row.log_disagreement)
    assert row.n_window == 0


def test_live_document_overrides_the_reading_and_joins_the_window() -> None:
    docs = _archive(8)
    col = collect(docs, backend="ibm_fez", until=T0)
    _, live = _doc(T0 + timedelta(minutes=5), {0: 150.0})
    rows = predictor_rows(col, at=T0 + timedelta(minutes=5), live=live)
    row = next(r for r in rows if r.qubit == 0 and r.quantity == "T1")
    assert row.reading == pytest.approx(150e-6, rel=1e-12)
    assert row.n_window == 9
    assert row.reading_time == (T0 + timedelta(minutes=5)).isoformat()


def test_execution_mode_emits_only_the_reading() -> None:
    docs = _archive(8)
    col = collect(docs, backend="ibm_fez", until=T0)
    rows = execution_rows(col, at=T0 - timedelta(days=2, hours=1), live=None)
    row = next(r for r in rows if r.qubit == 0 and r.quantity == "T1")
    assert row.reading == pytest.approx((100 + 7 - 3) * 1e-6, rel=1e-12)
    assert math.isnan(row.level) and row.n_window == 0


def test_other_backends_and_future_documents_are_dropped_and_counted() -> None:
    docs = _archive(8)
    docs.append(_doc(T0 - timedelta(days=1), {0: 1.0}, backend="ibm_other"))
    docs.append(_doc(T0 + timedelta(days=1), {0: 1.0}))
    col = collect(docs, backend="ibm_fez", until=T0)
    assert len(col.states) == 8
    assert col.skipped["other_backend"] == 1
    assert col.skipped["after_until"] == 1


def test_malformed_document_is_counted_and_skipped() -> None:
    docs = _archive(8)
    docs.append(
        (
            "snapshots/2026-10/ibm_fez/bad.json",
            {"backend": "ibm_fez", "properties": {"last_update_date": T0.isoformat()}},
        )
    )
    col = collect(docs, backend="ibm_fez", until=T0)
    assert len(col.states) == 8
    assert col.skipped["parse_error"] == 1


def test_selection_respects_the_distinct_value_floor_and_orders_by_disagreement() -> None:
    # 25 daily states; qubit 1 varies daily and jumps at the end (large disagreement),
    # qubit 2 is constant (one distinct value, below the floor), qubit 3 drifts mildly
    t1 = {d: {0: 100.0 + d, 1: 100.0 + d, 2: 80.0, 3: 100.0 + 0.5 * d} for d in range(25)}
    t1[24][1] = 180.0
    docs = _archive(25, t1)
    col = collect(docs, backend="ibm_fez", until=T0)
    rows = predictor_rows(col, at=T0, live=None)
    picked = select_discriminating(rows, k=2, min_distinct=20)
    assert [p["qubit"] for p in picked] == [1, 0]
    assert all(p["n_distinct"] >= 20 for p in picked)
    assert picked[0]["abs_log_disagreement"] > picked[1]["abs_log_disagreement"]
    controls = propose_controls(col, k=1, exclude={1, 0}, min_distinct=20)
    assert controls[0]["qubit"] == 3  # qubit 2 has one distinct value and is excluded by the floor


def test_cli_writer_emits_tsv_selection_and_manifest(tmp_path: Path) -> None:
    docs = _archive(25)
    col = collect(docs, backend="ibm_fez", until=T0)
    rows = predictor_rows(col, at=T0, live=None)
    write_outputs(
        tmp_path,
        rows=rows,
        selection={
            "discriminating": select_discriminating(rows, k=1, min_distinct=20),
            "controls": [],
        },
        manifest={"ref_sha": "deadbeef", "at": T0.isoformat()},
    )
    tsv = (tmp_path / "predictors.tsv").read_text(encoding="utf-8").splitlines()
    assert tsv[0].split("\t")[:4] == ["qubit", "quantity", "reading", "level"]
    assert len(tsv) == 1 + N_QUBITS * 5
    assert (
        json.loads((tmp_path / "selection.json").read_text(encoding="utf-8"))["discriminating"][0][
            "qubit"
        ]
        == 0
    )
    assert (
        json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["ref_sha"]
        == "deadbeef"
    )
