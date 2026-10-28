"""Tests for the archive side of the #125 hardware test (scripts/hardware_test_predictors.py).

Synthetic archive documents in the real schema; no git, no network, no filesystem beyond
``tmp_path`` for the CLI writer and the CLI run (whose archive reader is monkeypatched).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scripts.hardware_test_predictors import (
    MIN_WINDOW_DISTINCT,
    MIN_WINDOW_STATES,
    Collected,
    LiveDocumentError,
    PredictorRow,
    collect,
    execution_rows,
    freeze_controls,
    main,
    normalise_live,
    predictor_rows,
    propose_controls,
    select_balanced,
    select_discriminating,
    write_outputs,
)

from superconducted.training.dataset import qubit_block_digest

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


def _t1(rows: list[Any], q: int = 0) -> Any:
    return next(r for r in rows if r.qubit == q and r.quantity == "T1")


def test_level_and_band_match_their_definitions() -> None:
    docs = _archive(8)  # qubit 0: T1 = 100..107 us, one state per day
    col = collect(docs, backend="ibm_fez", until=T0)
    rows = predictor_rows(col, at=T0, live=None)
    row = next(r for r in rows if r.qubit == 0 and r.quantity == "T1")
    logs = np.log(np.arange(100, 108) * 1e-6)
    expected = math.exp(np.mean(logs))
    lo, hi = np.quantile(logs, (0.10, 0.90))
    assert row.n_window == 8
    assert row.level == pytest.approx(expected, rel=1e-12)
    assert row.band_lo == pytest.approx(math.exp(lo), rel=1e-12)
    assert row.band_hi == pytest.approx(math.exp(hi), rel=1e-12)
    assert row.reading == pytest.approx(107e-6, rel=1e-12)
    assert row.log_disagreement == pytest.approx(math.log(107e-6) - math.log(expected), rel=1e-9)


def test_level_may_lie_outside_the_band_and_neither_is_adjusted() -> None:
    """Bengisu's counterexample (PR #126 review, 2026-10-26): no bracketing is enforced.

    91 distinct values evenly spaced over 100 to 100.9 us and 9 over 1000 to 1008 us: the
    geometric mean is about 123.57 us, above the 90th log-space percentile (about 100.89 us).
    """
    t1 = np.concatenate([np.linspace(100.0, 100.9, 91), np.linspace(1000.0, 1008.0, 9)])
    docs = [_doc(T0 - timedelta(hours=len(t1) - 1 - i), {0: float(v)}) for i, v in enumerate(t1)]
    col = collect(docs, backend="ibm_fez", until=T0)
    row = _t1(predictor_rows(col, at=T0, live=None))
    logs = np.log(t1 * 1e-6)
    lo, hi = np.quantile(logs, (0.10, 0.90))
    assert row.n_window == 100
    assert row.level == pytest.approx(math.exp(np.mean(logs)), rel=1e-12)
    assert row.band_lo == pytest.approx(math.exp(lo), rel=1e-12)
    assert row.band_hi == pytest.approx(math.exp(hi), rel=1e-12)
    assert row.level > row.band_hi


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


def _raw_properties(stamp: datetime, t1_us: dict[int, float | None], **kw: Any) -> dict[str, Any]:
    """The raw ``BackendProperties.to_dict()`` body: no envelope, fields at the top level."""
    _, envelope = _doc(stamp, t1_us, **kw)
    raw: dict[str, Any] = copy.deepcopy(envelope["properties"])
    return raw


@pytest.mark.parametrize("mode", ["submission", "execution"])
def test_raw_to_dict_live_document_is_accepted_in_both_modes(mode: str) -> None:
    col = collect(_archive(8), backend="ibm_fez", until=T0)
    raw = _raw_properties(T0, {0: 150.0})
    before = copy.deepcopy(raw)
    if mode == "submission":
        row = _t1(predictor_rows(col, at=T0, live=raw))
        assert row.n_window == 9
    else:
        row = _t1(execution_rows(col, at=T0, live=raw))
    assert row.reading == pytest.approx(150e-6, rel=1e-12)
    assert raw == before  # normalisation never mutates the caller's document


def test_raw_to_dict_with_space_separated_timestamp_is_accepted() -> None:
    """``json.dump(props.to_dict(), default=str)`` writes datetimes with a space separator."""
    col = collect(_archive(8), backend="ibm_fez", until=T0)
    raw = _raw_properties(T0, {0: 150.0})
    raw["last_update_date"] = str(T0)  # '2026-10-01 12:00:00+00:00'
    assert _t1(execution_rows(col, at=T0, live=raw)).reading == pytest.approx(150e-6)


def test_raw_and_envelope_live_documents_digest_identically() -> None:
    _, envelope = _doc(T0, {0: 150.0})
    raw = copy.deepcopy(envelope["properties"])
    wrapped = normalise_live(raw, backend="ibm_fez")
    assert wrapped["properties"] is raw
    assert qubit_block_digest(wrapped) == qubit_block_digest(envelope)


@pytest.mark.parametrize("mode", ["submission", "execution"])
@pytest.mark.parametrize(
    "variant", ["envelope_other", "raw_other", "envelope_inconsistent", "no_identity", "shape"]
)
def test_live_document_from_another_backend_is_rejected(mode: str, variant: str) -> None:
    col = collect(_archive(8), backend="ibm_fez", until=T0)
    live: dict[str, Any]
    if variant == "envelope_other":
        live = _doc(T0, {0: 999.0}, backend="ibm_other")[1]
    elif variant == "raw_other":
        live = _raw_properties(T0, {0: 999.0}, backend="ibm_other")
    elif variant == "envelope_inconsistent":
        live = _doc(T0, {0: 999.0})[1]
        live["properties"]["backend_name"] = "ibm_other"
    elif variant == "no_identity":
        live = _doc(T0, {0: 999.0})[1]
        del live["backend"]
        del live["properties"]["backend_name"]
    else:
        live = {"backend": "ibm_fez", "qubits": []}  # neither shape
    with pytest.raises(LiveDocumentError):
        if mode == "submission":
            predictor_rows(col, at=T0, live=live)
        else:
            execution_rows(col, at=T0, live=live)


def test_live_document_that_does_not_parse_raises_live_document_error() -> None:
    col = collect(_archive(8), backend="ibm_fez", until=T0)
    live = _doc(T0, {0: 150.0})[1]
    live["properties"]["qubits"][0].append(None)
    with pytest.raises(LiveDocumentError):
        predictor_rows(col, at=T0, live=live)


def test_live_state_first_seen_before_the_window_adds_no_state() -> None:
    """Bengisu's reproduction (PR #126 review): an old state republished as the latest file.

    Archive-only extraction gives four window states and no level; supplying that same latest
    snapshot as live must give the same, with the live document overriding only the reading.
    """
    docs = [_doc(T0 - timedelta(days=40), {0: 50.0})]
    docs += [_doc(T0 - timedelta(days=4 - d), {0: 100.0 + d}) for d in range(4)]
    docs.append(_doc(T0 - timedelta(hours=1), {0: 50.0}))  # same qubit block as day -40
    col = collect(docs, backend="ibm_fez", until=T0)
    archive_only = _t1(predictor_rows(col, at=T0, live=None))
    assert archive_only.n_window == 4 and math.isnan(archive_only.level)

    live = copy.deepcopy(docs[-1][1])
    with_live = _t1(predictor_rows(col, at=T0, live=live))
    assert with_live.n_window == 4
    assert math.isnan(with_live.level)
    assert with_live.n_distinct == archive_only.n_distinct
    assert with_live.reading == pytest.approx(50e-6, rel=1e-12)
    assert with_live.reading_time == T0.isoformat()


def test_live_state_seen_inside_the_window_keeps_its_original_time() -> None:
    col = collect(_archive(8), backend="ibm_fez", until=T0)
    live = copy.deepcopy(_archive(8)[-1][1])  # same block as the state at T0
    row = _t1(predictor_rows(col, at=T0, live=live))
    assert row.n_window == 8


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


@pytest.mark.parametrize("bad", [None, 3, "T1", ["nested"]])
def test_malformed_nduv_entry_is_counted_and_collection_continues(bad: Any) -> None:
    docs = _archive(8)
    path, doc = docs[3]
    broken = copy.deepcopy(doc)
    broken["properties"]["qubits"][0].append(bad)
    docs[3] = (path, broken)
    col = collect(docs, backend="ibm_fez", until=T0)
    assert col.skipped["parse_error"] == 1
    assert len(col.files) == 7 and len(col.states) == 7


def test_non_list_qubit_entry_is_counted_and_collection_continues() -> None:
    docs = _archive(8)
    path, doc = docs[2]
    broken = copy.deepcopy(doc)
    broken["properties"]["qubits"][1] = None
    docs[2] = (path, broken)
    col = collect(docs, backend="ibm_fez", until=T0)
    assert col.skipped["parse_error"] == 1
    assert len(col.states) == 7


def test_collect_records_the_backend_it_filtered_on() -> None:
    assert collect(_archive(2), backend="ibm_fez", until=T0).backend == "ibm_fez"
    assert Collected().backend == ""


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


def _run_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, live_bytes: bytes, mode: str
) -> tuple[int, Path, Path]:
    """Run ``main`` against a synthetic archive, with the git reader monkeypatched out."""
    monkeypatch.setattr(
        "scripts.hardware_test_predictors.resolve_archive_ref", lambda repo, ref: "f" * 40
    )
    monkeypatch.setattr(
        "scripts.hardware_test_predictors.iter_archive", lambda repo, sha: iter(_archive(8))
    )
    live_path = tmp_path / "live.json"
    live_path.write_bytes(live_bytes)
    out = tmp_path / f"out-{mode}"
    # Submission now needs the frozen controls; these tests are about the live document, so
    # they run as an archive dry run.
    dry_run = ["--no-frozen-controls"] if mode == "submission" else []
    code = main(
        [
            "--ref",
            "pinned",
            "--at",
            T0.isoformat(),
            "--mode",
            mode,
            "--live-properties",
            str(live_path),
            "--out",
            str(out),
            *dry_run,
        ]
    )
    return code, live_path, out


@pytest.mark.parametrize("mode", ["submission", "execution"])
def test_cli_accepts_raw_to_dict_and_keeps_the_original_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str
) -> None:
    raw = _raw_properties(T0, {0: 150.0})
    live_bytes = json.dumps(raw, indent=1).encode("utf-8")  # any byte layout must survive
    code, live_path, out = _run_cli(monkeypatch, tmp_path, live_bytes, mode)
    assert code == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["live_properties_sha256"] == hashlib.sha256(live_bytes).hexdigest()
    copies = list(out.glob("live-properties-*.json"))
    assert len(copies) == 1 and copies[0].read_bytes() == live_path.read_bytes() == live_bytes
    tsv = (out / "predictors.tsv").read_text(encoding="utf-8").splitlines()
    header = tsv[0].split("\t")
    first = dict(zip(header, tsv[1].split("\t"), strict=True))
    assert (first["qubit"], first["quantity"]) == ("0", "T1")
    assert float(first["reading"]) == pytest.approx(150e-6, rel=1e-12)


@pytest.mark.parametrize("mode", ["submission", "execution"])
def test_cli_rejects_a_live_document_from_another_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str
) -> None:
    raw = _raw_properties(T0, {0: 999.0}, backend="ibm_other")
    code, _, out = _run_cli(monkeypatch, tmp_path, json.dumps(raw).encode("utf-8"), mode)
    assert code == 2
    assert not (out / "predictors.tsv").exists()


# Selection rules of the #125 pre-registration, proposals A, B and D
# (docs/implementations/2026-10-28-hardware-test-selection-rules.md).


def _window_archive() -> list[Any]:
    """40 daily states; the window at ``T0`` holds days 10 to 39 (day 9 sits on its open edge).

    Qubit 0 changes daily (40 distinct, 30 in the window). Qubit 1 changes daily to day 14 and
    then holds one value: 16 distinct over the archive, 6 in the window (proposal A's case of a
    level that is mostly one carried value). Qubit 2 never changes. Qubit 3 is missing on odd
    days: 20 distinct, 15 in the window, exactly the floor.
    """
    t1: dict[int, dict[int, float | None]] = {}
    for d in range(40):
        t1[d] = {
            0: 100.0 + d,
            1: 100.0 + d if d <= 14 else 300.0,
            2: 80.0,
            3: 50.0 + d if d % 2 == 0 else None,
        }
    return _archive(40, t1)


def test_window_distinct_counts_finite_values_inside_the_window_only() -> None:
    col = collect(_window_archive(), backend="ibm_fez", until=T0)
    rows = predictor_rows(col, at=T0, live=None)
    counts = {q: (_t1(rows, q).n_distinct, _t1(rows, q).n_window_distinct) for q in range(4)}
    assert counts == {0: (40, 30), 1: (16, 6), 2: (1, 1), 3: (20, 15)}
    assert MIN_WINDOW_DISTINCT == 15


def test_tsv_carries_the_window_distinct_count_as_the_last_column(tmp_path: Path) -> None:
    col = collect(_window_archive(), backend="ibm_fez", until=T0)
    write_outputs(tmp_path, rows=predictor_rows(col, at=T0, live=None), selection=None, manifest={})
    lines = (tmp_path / "predictors.tsv").read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    assert header[-1] == "n_window_distinct"
    first = dict(zip(header, lines[1].split("\t"), strict=True))
    assert (first["qubit"], first["quantity"], first["n_window_distinct"]) == ("0", "T1", "30")


def test_window_floor_excludes_what_the_whole_archive_floor_admits() -> None:
    col = collect(_window_archive(), backend="ibm_fez", until=T0)
    rows = predictor_rows(col, at=T0, live=None)
    # qubit 1 jumped to 300 us and holds it: the largest disagreement on the chip
    assert _t1(rows, 1).log_disagreement > _t1(rows, 0).log_disagreement > 0.0
    old = select_discriminating(rows, k=1, min_distinct=15)
    assert [p["qubit"] for p in old] == [1]
    new = select_balanced(rows, k=2, controls=set())
    assert 1 not in [p["qubit"] for p in new["discriminating"]]
    assert 1 in new["below_window_floor"] and 2 in new["below_window_floor"]


def _row(qubit: int, d: float, *, window: int = 30) -> PredictorRow:
    return PredictorRow(qubit, "T1", 1e-4 * math.exp(d), 1e-4, 8e-5, 1.2e-4, 30, 100, d, "", window)


def _picked(selection: dict[str, Any]) -> list[tuple[int, str, bool]]:
    return [(p["qubit"], p["side"], p["filled"]) for p in selection["discriminating"]]


def test_balanced_takes_four_below_and_four_above() -> None:
    rows = [_row(q, d) for q, d in enumerate([-1.0, -0.9, -0.8, -0.7, -0.6])]
    rows += [_row(5 + q, d) for q, d in enumerate([0.5, 0.4, 0.3, 0.2, 0.1])]
    sel = select_balanced(rows, k=8, controls=set())
    assert _picked(sel) == [
        (0, "below", False),
        (1, "below", False),
        (2, "below", False),
        (3, "below", False),
        (5, "above", False),
        (6, "above", False),
        (7, "above", False),
        (8, "above", False),
    ]
    assert sel["short_side"] is None and sel["n_filled"] == 0 and sel["n_selected"] == 8
    assert sel["admitted"] == {"below": 5, "above": 5, "zero": 0}
    # the design's rule on the same rows: all five dips and only three rises
    old = select_discriminating(rows, k=8, min_distinct=20)
    assert [p["qubit"] for p in old] == [0, 1, 2, 3, 4, 5, 6, 7]


def test_short_side_is_filled_from_the_other_side_and_logged() -> None:
    rows = [_row(q, -1.0 + 0.1 * q) for q in range(6)]  # six dips, |d| from 1.0 down to 0.5
    rows += [_row(10, 0.3), _row(11, 0.2)]  # two rises
    sel = select_balanced(rows, k=8, controls=set())
    assert _picked(sel) == [
        (0, "below", False),
        (1, "below", False),
        (2, "below", False),
        (3, "below", False),
        (4, "below", True),
        (5, "below", True),
        (10, "above", False),
        (11, "above", False),
    ]
    assert (sel["short_side"], sel["filled_from"], sel["n_filled"]) == ("above", "below", 2)
    assert sel["n_selected"] == 8


def test_short_lower_side_is_filled_from_the_upper_side() -> None:
    rows = [_row(0, -0.2)]  # one dip
    rows += [_row(10 + q, 0.9 - 0.1 * q) for q in range(5)]  # five rises, |d| 0.9 down to 0.5
    sel = select_balanced(rows, k=4, controls=set())
    assert _picked(sel) == [
        (0, "below", False),
        (10, "above", False),
        (11, "above", False),
        (12, "above", True),
    ]
    assert (sel["short_side"], sel["filled_from"], sel["n_filled"]) == ("below", "above", 1)


def test_fewer_than_k_admitted_selects_fewer_and_says_so() -> None:
    rows = [_row(0, -0.5), _row(1, -0.4), _row(2, 0.3), _row(3, 0.2), _row(4, 0.1)]
    sel = select_balanced(rows, k=8, controls=set())
    assert sel["n_selected"] == 5
    assert (sel["short_side"], sel["filled_from"], sel["n_filled"]) == ("both", None, 0)


def test_zero_disagreement_is_never_selected_even_to_fill() -> None:
    rows = [_row(0, -0.5), _row(1, 0.0), _row(2, 0.4)]
    sel = select_balanced(rows, k=4, controls=set())
    assert [p["qubit"] for p in sel["discriminating"]] == [0, 2]
    assert sel["zero_disagreement"] == [1]
    assert sel["admitted"] == {"below": 1, "above": 1, "zero": 1}


def test_ties_in_disagreement_break_by_qubit_index() -> None:
    rows = [_row(7, -0.5), _row(3, -0.5), _row(9, 0.5), _row(4, 0.5)]
    sel = select_balanced(rows, k=2, controls=set())
    assert [p["qubit"] for p in sel["discriminating"]] == [3, 4]


def test_frozen_controls_are_never_discriminating() -> None:
    rows = [_row(0, -2.0), _row(1, -0.5), _row(2, 2.0), _row(3, 0.5)]
    sel = select_balanced(rows, k=2, controls={0, 2})
    assert [p["qubit"] for p in sel["discriminating"]] == [1, 3]
    assert sel["excluded_controls"] == [0, 2]


def test_window_floor_boundary_admits_fifteen_and_excludes_fourteen() -> None:
    rows = [_row(0, -0.9, window=14), _row(1, -0.5, window=15), _row(2, 0.5)]
    sel = select_balanced(rows, k=2, controls=set())
    assert [p["qubit"] for p in sel["discriminating"]] == [1, 2]
    assert sel["below_window_floor"] == [0]


@pytest.mark.parametrize("k", [0, -2, 7])
def test_balanced_selection_needs_a_positive_even_k(k: int) -> None:
    with pytest.raises(ValueError, match="positive even"):
        select_balanced([_row(0, -0.5)], k=k, controls=set())


def test_freeze_controls_excludes_only_qubits_below_the_window_floor() -> None:
    # qubit 1: 23 distinct values over the archive (passes the whole-archive 20) but 13 in the
    # window (fails proposal A's 15); qubits 2 and 3 never change and fail both floors
    t1: dict[int, dict[int, float | None]] = {}
    for d in range(40):
        t1[d] = {
            0: 100.0 * math.exp(0.1 * math.sin(d)),
            1: 100.0 * math.exp(0.1 * math.cos(d)) if d <= 21 else 90.0,
            2: 80.0,
            3: 70.0,
        }
    col = collect(_archive(40, t1), backend="ibm_fez", until=T0)
    rows = predictor_rows(col, at=T0, live=None)
    assert (_t1(rows, 1).n_distinct, _t1(rows, 1).n_window_distinct) == (23, 13)
    assert {c["qubit"] for c in propose_controls(col, k=4, exclude=set())} == {0, 1}
    frozen = freeze_controls(col, rows, k=4)
    assert [c["qubit"] for c in frozen["controls"]] == [0]
    assert frozen["below_window_floor"] == [1, 2, 3]


def _cli_archive() -> list[Any]:
    """40 days, every qubit in the window 30 times: qubits 0 and 2 rise, 1 and 3 fall."""
    t1: dict[int, dict[int, float | None]] = {
        d: {0: 100.0 + d, 1: 200.0 - d, 2: 50.0 + 2 * d, 3: 300.0 - 3 * d} for d in range(40)
    }
    return _archive(40, t1)


def _cli(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> int:
    monkeypatch.setattr(
        "scripts.hardware_test_predictors.resolve_archive_ref", lambda repo, ref: "f" * 40
    )
    monkeypatch.setattr(
        "scripts.hardware_test_predictors.iter_archive", lambda repo, sha: iter(_cli_archive())
    )
    return main(["--ref", "pinned", "--at", T0.isoformat(), *args])


def test_submission_without_frozen_controls_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "job"
    assert _cli(monkeypatch, ["--out", str(out)]) == 2
    assert "frozen controls" in capsys.readouterr().err
    assert not out.exists()
    both = ["--controls", str(tmp_path / "c.json"), "--no-frozen-controls", "--out", str(out)]
    assert _cli(monkeypatch, both) == 2
    assert not out.exists()


def test_controls_mode_refuses_a_live_document(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    live = tmp_path / "live.json"
    live.write_text(json.dumps(_raw_properties(T0, {0: 150.0})), encoding="utf-8")
    out = tmp_path / "freeze"
    args = ["--mode", "controls", "--live-properties", str(live), "--out", str(out)]
    assert _cli(monkeypatch, args) == 2
    assert not out.exists()


def test_controls_then_submission_round_trip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    freeze = tmp_path / "freeze"
    args = ["--mode", "controls", "--propose-controls", "1", "--out", str(freeze)]
    assert _cli(monkeypatch, args) == 0
    frozen = json.loads((freeze / "controls.json").read_text(encoding="utf-8"))
    assert frozen["backend"] == "ibm_fez" and frozen["ref_sha"] == "f" * 40
    assert frozen["min_window_distinct"] == 15 and frozen["below_window_floor"] == []
    (control,) = [c["qubit"] for c in frozen["controls"]]

    job = tmp_path / "job"
    controls_path = freeze / "controls.json"
    args = ["--controls", str(controls_path), "--select-discriminating", "2", "--out", str(job)]
    assert _cli(monkeypatch, args) == 0
    selection = json.loads((job / "selection.json").read_text(encoding="utf-8"))
    picked = [p["qubit"] for p in selection["discriminating"]]
    assert control not in picked and len(picked) == 2
    assert {p["side"] for p in selection["discriminating"]} == {"below", "above"}
    assert selection["controls"] == [control] and "proposed_controls" not in selection
    manifest = json.loads((job / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["controls"] == [control]
    digest = hashlib.sha256(controls_path.read_bytes()).hexdigest()
    assert manifest["controls_file_sha256"] == digest
    assert manifest["controls_ref_sha"] == "f" * 40 and manifest["min_window_distinct"] == 15


def test_dry_run_without_controls_records_null(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    job = tmp_path / "dry"
    assert _cli(monkeypatch, ["--no-frozen-controls", "--out", str(job)]) == 0
    selection = json.loads((job / "selection.json").read_text(encoding="utf-8"))
    manifest = json.loads((job / "manifest.json").read_text(encoding="utf-8"))
    assert selection["controls"] is None and manifest["controls"] is None
    assert manifest["controls_file_sha256"] is None
    assert selection["n_selected"] == 4  # all four qubits: two below, two above


@pytest.mark.parametrize(
    "payload",
    [
        {"backend": "ibm_other", "controls": [{"qubit": 1}]},
        {"backend": "ibm_fez", "controls": []},
        {"backend": "ibm_fez", "controls": [{"qubit": "1"}]},
        {"backend": "ibm_fez"},
    ],
)
def test_unusable_controls_file_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, payload: dict[str, Any]
) -> None:
    path = tmp_path / "controls.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    job = tmp_path / "job"
    assert _cli(monkeypatch, ["--controls", str(path), "--out", str(job)]) == 2
    assert not job.exists()


def test_odd_discriminating_count_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    job = tmp_path / "job"
    args = ["--no-frozen-controls", "--select-discriminating", "7", "--out", str(job)]
    assert _cli(monkeypatch, args) == 2
    assert not job.exists()


def test_json_outputs_are_written_with_lf_on_every_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A recorded file hash must be the hash every checkout sees; the repository stores LF, so a
    # CRLF write on Windows would record a hash no clone reproduces.
    freeze = tmp_path / "freeze"
    assert (
        _cli(monkeypatch, ["--mode", "controls", "--propose-controls", "1", "--out", str(freeze)])
        == 0
    )
    job = tmp_path / "job"
    controls = freeze / "controls.json"
    args = ["--controls", str(controls), "--select-discriminating", "2", "--out", str(job)]
    assert _cli(monkeypatch, args) == 0
    written = [controls, freeze / "manifest.json", job / "selection.json", job / "manifest.json"]
    for path in written:
        data = path.read_bytes()
        assert b"\n" in data and b"\r" not in data, path.name
