"""Tests for the feature-distribution survey (Issue #59 Part A, section 9).

Unit tests run on synthetic dicts; the integration test builds a throwaway git
repository under ``tmp_path`` and walks it at a real ref, and skips when ``git``
is unavailable the way ``tests/test_file_snapshots.py`` does. Anything against
the real archive is marked ``slow`` and skips when the ref is unreachable -- the
committed TSV is the durable record, not the test.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scripts.feature_distribution import (
    SnapshotFeatureRow,
    _compute_stats,
    iter_snapshot_rows,
    snapshot_row,
    summarize,
    write_tsv,
)

from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.types import CalibrationSnapshot

_HAS_GIT = shutil.which("git") is not None
_ARCHIVE_REF = "superconducted-noise-engine/calibration-data"


def _qubit(t1: float | None, t2: float | None, readout: float | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if t1 is not None:
        entries.append({"name": "T1", "value": t1})
    if t2 is not None:
        entries.append({"name": "T2", "value": t2})
    if readout is not None:
        entries.append({"name": "readout_error", "value": readout})
    return entries


def _doc(qubits: list[list[dict[str, Any]]], **overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "backend": "ibm_fez",
        "timestamp": "2026-05-13T12:13:22Z",
        "schema_version": "1.0.0",
        "properties": {"qubits": qubits, "last_update_date": "2026-05-13T12:13:22Z"},
    }
    doc.update(overrides)
    return doc


# --------------------------------------------------------------------------
# _compute_stats
# --------------------------------------------------------------------------


def test_compute_stats_empty() -> None:
    assert _compute_stats([]) == (0, None, None, None, None)


def test_compute_stats_normal() -> None:
    """Percentiles and the ddof=1 sample standard deviation."""
    n, std, p10, p50, p90 = _compute_stats([10.0, 20.0, 30.0, 40.0, 50.0])

    assert n == 5
    assert std == pytest.approx(15.811, rel=1e-3)
    assert p10 == pytest.approx(14.0)
    assert p50 == pytest.approx(30.0)
    assert p90 == pytest.approx(46.0)


def test_compute_stats_single_value_has_no_spread() -> None:
    """A spread over one value is not a measurement: empty, never NaN."""
    n, std, p10, p50, p90 = _compute_stats([42.0])

    assert (n, std) == (1, None)
    assert (p10, p50, p90) == (42.0, 42.0, 42.0)


def test_compute_stats_uses_ddof_one_not_ddof_zero() -> None:
    """The ddof choice is not free: #64's ``per_qubit_spread`` ships ddof=1."""
    values = [1.0, 2.0, 3.0, 4.0]
    _, std, _, _, _ = _compute_stats(values)

    assert std == pytest.approx(float(np.std(values, ddof=1)))
    assert std != pytest.approx(float(np.std(values, ddof=0)))


# --------------------------------------------------------------------------
# snapshot_row (section 9.1)
# --------------------------------------------------------------------------


def test_snapshot_row_means_equal_the_vectorizer() -> None:
    """The survey's ``mean_*`` are the vectorizer's output, not a second definition."""
    doc = _doc([_qubit(100.0, 70.0, 0.01), _qubit(200.0, 90.0, 0.03)])

    row = snapshot_row("snapshots/2026-05/ibm_fez/x.json", doc)

    expected = BasicCalibrationVectorizer().extract(
        CalibrationSnapshot(
            backend="ibm_fez",
            timestamp=datetime.fromisoformat(row.timestamp),
            schema_version="1.0.0",
            properties=doc["properties"],
            target=None,
            configuration=None,
        )
    )
    assert (row.mean_T1, row.mean_T2, row.mean_readout_error) == pytest.approx(tuple(expected))
    assert row.rejection_reason is None
    assert row.n_qubits == 2
    assert row.stem == "x"
    assert row.path == "snapshots/2026-05/ibm_fez/x.json"
    assert row.last_update_date == "2026-05-13T12:13:22Z"


def test_snapshot_row_per_qubit_stats_cover_exactly_the_averaged_values() -> None:
    doc = _doc([_qubit(100.0, 70.0, 0.01), _qubit(200.0, 90.0, 0.03)])

    row = snapshot_row("a/b.json", doc)

    assert row.T1_n_usable == 2
    assert row.T1_qubit_std == pytest.approx(float(np.std([100.0, 200.0], ddof=1)))
    assert row.T1_qubit_p50 == pytest.approx(150.0)
    assert row.readout_error_n_usable == 2


def test_qubit_72_style_row_reduces_only_the_t2_count() -> None:
    """The committed fixture's shape: one qubit has no T2 (n_usable is one less)."""
    doc = _doc([_qubit(100.0, 70.0, 0.01), _qubit(200.0, None, 0.03)])

    row = snapshot_row("a/b.json", doc)

    assert row.n_qubits == 2
    assert row.T1_n_usable == 2
    assert row.T2_n_usable == 1
    assert row.readout_error_n_usable == 2
    assert row.T2_qubit_std is None
    assert row.mean_T2 == pytest.approx(70.0)


def test_non_finite_and_non_numeric_values_are_dropped_like_extract_drops_them() -> None:
    doc = _doc(
        [
            _qubit(100.0, 70.0, 0.01),
            _qubit(float("nan"), 90.0, 0.03),
            _qubit("not-a-number", 110.0, 0.05),  # type: ignore[arg-type]
        ]
    )

    row = snapshot_row("a/b.json", doc)

    assert row.T1_n_usable == 1
    assert row.T2_n_usable == 3
    assert row.mean_T1 == pytest.approx(100.0)


def test_rejected_snapshot_keeps_its_reason_and_is_not_dropped() -> None:
    """A snapshot ``extract`` rejects is recorded with empty means, never skipped."""
    doc = _doc([_qubit(100.0, None, 0.01)])
    doc["properties"]["qubits"] = [[{"name": "T1", "value": 100.0}]]

    row = snapshot_row("a/b.json", doc)

    assert row.mean_T1 is None
    assert row.mean_T2 is None
    assert row.mean_readout_error is None
    assert row.rejection_reason is not None
    assert "requires at least one finite value" in row.rejection_reason
    assert row.T1_n_usable == 1


def test_timestamp_falls_back_to_the_filename_stem() -> None:
    doc = _doc([_qubit(100.0, 70.0, 0.01)])
    del doc["timestamp"]

    row = snapshot_row("snapshots/2026-05/ibm_fez/20260513T121322000000Z.json", doc)

    assert row.timestamp.startswith("2026-05-13T12:13:22")
    assert row.rejection_reason is None


def test_an_unparseable_timestamp_becomes_a_rejection_rather_than_an_exception() -> None:
    """§6.4's invariant: ``snapshot_row`` never raises."""
    doc = _doc([_qubit(100.0, 70.0, 0.01)])
    del doc["timestamp"]

    row = snapshot_row("snapshots/2026-05/ibm_fez/not-a-timestamp.json", doc)

    assert row.rejection_reason is not None
    assert "unparseable timestamp" in row.rejection_reason
    assert row.mean_T1 is None


def test_fr_2_column_order_is_a_strict_prefix_of_the_row() -> None:
    """#63 reads these columns positionally; the reason column is appended last."""
    names = [f.name for f in fields(SnapshotFeatureRow)]

    assert names[:6] == ["path", "stem", "backend", "timestamp", "last_update_date", "n_qubits"]
    assert names[6:9] == ["mean_T1", "mean_T2", "mean_readout_error"]
    assert names[-1] == "rejection_reason"


# --------------------------------------------------------------------------
# summarize (section 9.1)
# --------------------------------------------------------------------------


def _row(**overrides: Any) -> SnapshotFeatureRow:
    base: dict[str, Any] = {
        "path": "p",
        "stem": "s",
        "backend": "ibm_fez",
        "timestamp": "2026-05-13T12:13:22+00:00",
        "last_update_date": "",
        "n_qubits": 1,
        "mean_T1": 100.0,
        "mean_T2": 70.0,
        "mean_readout_error": 0.01,
        "T1_n_usable": 2,
        "T1_qubit_std": 5.0,
        "T1_qubit_p10": 1.0,
        "T1_qubit_p50": 2.0,
        "T1_qubit_p90": 3.0,
        "T2_n_usable": 2,
        "T2_qubit_std": 6.0,
        "T2_qubit_p10": 1.0,
        "T2_qubit_p50": 2.0,
        "T2_qubit_p90": 3.0,
        "readout_error_n_usable": 2,
        "readout_error_qubit_std": 0.001,
        "readout_error_qubit_p10": 0.0,
        "readout_error_qubit_p50": 0.0,
        "readout_error_qubit_p90": 0.0,
        "rejection_reason": None,
    }
    base.update(overrides)
    return SnapshotFeatureRow(**base)


def test_summarize_matches_a_hand_computed_sample() -> None:
    rows = [_row(mean_T1=float(v)) for v in (10.0, 20.0, 30.0, 40.0, 50.0)]

    summary = summarize(rows)

    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert summary["file_count"] == 5
    assert summary["T1_present_rows"] == 5
    assert summary["T1_p1"] == pytest.approx(float(np.percentile(values, 1)))
    assert summary["T1_p50"] == pytest.approx(30.0)
    assert summary["T1_p99"] == pytest.approx(float(np.percentile(values, 99)))


def test_summarize_counts_rejected_rows_but_excludes_them_from_the_quantiles() -> None:
    rows = [_row(mean_T1=10.0), _row(mean_T1=None, rejection_reason="unusable"), _row(mean_T1=30.0)]

    summary = summarize(rows)

    assert summary["file_count"] == 3
    assert summary["T1_present_rows"] == 2
    assert summary["T1_p50"] == pytest.approx(20.0)
    assert summary["rejected_rows"] == 1


def test_summarize_median_spread_skips_rows_without_a_spread() -> None:
    rows = [_row(T1_qubit_std=4.0), _row(T1_qubit_std=None), _row(T1_qubit_std=8.0)]

    assert summarize(rows)["T1_median_qubit_std"] == pytest.approx(6.0)


def test_summarize_is_all_none_when_no_row_has_a_mean() -> None:
    summary = summarize([_row(mean_T1=None, T1_qubit_std=None, rejection_reason="unusable")])

    assert summary["T1_p1"] is None
    assert summary["T1_p50"] is None
    assert summary["T1_p99"] is None
    assert summary["T1_median_qubit_std"] is None


# --------------------------------------------------------------------------
# write_tsv (FR-10)
# --------------------------------------------------------------------------


def test_tsv_uses_lf_line_endings(tmp_path: Path) -> None:
    """The repo stores every text file as LF, so a CRLF writer could never
    produce output byte-identical to its own committed artifact."""
    out = tmp_path / "survey.tsv"

    write_tsv([_row()], out)

    assert b"\r\n" not in out.read_bytes()
    assert out.read_bytes().endswith(b"\n")


def test_tsv_writes_none_as_an_empty_cell(tmp_path: Path) -> None:
    out = tmp_path / "survey.tsv"

    write_tsv([_row(mean_T1=None, T1_qubit_std=None)], out)

    with out.open(newline="", encoding="utf-8") as handle:
        row = next(iter(csv.DictReader(handle, delimiter="\t")))
    assert row["mean_T1"] == ""
    assert row["T1_qubit_std"] == ""


# --------------------------------------------------------------------------
# Integration: a throwaway git repository (section 9.2)
# --------------------------------------------------------------------------


def _init_fake_archive(root: Path, stems: list[str]) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }

    def run(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, env={**env}
        )

    root.mkdir(parents=True, exist_ok=True)
    run("init", "-q")
    for i, stem in enumerate(stems):
        path = root / "snapshots" / "2026-09" / "ibm_fez" / f"{stem}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                _doc(
                    [_qubit(100.0 + i, 70.0 + i, 0.01 + i / 1000.0), _qubit(200.0, 90.0, 0.03)],
                    timestamp=f"2026-09-0{i + 1}T01:02:03Z",
                )
            ),
            encoding="utf-8",
        )
    other = root / "snapshots" / "2026-09" / "ibm_other" / "20260901T000000000000Z.json"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text(json.dumps(_doc([_qubit(1.0, 1.0, 0.5)])), encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "fixture")
    return run("rev-parse", "HEAD").stdout.decode().strip()


@pytest.mark.skipif(not _HAS_GIT, reason="git is not available")
def test_iter_snapshot_rows_walks_the_archive_at_a_ref(tmp_path: Path) -> None:
    ref = _init_fake_archive(
        tmp_path / "repo", ["20260901T010203000000Z", "20260902T010203000000Z"]
    )

    rows = list(iter_snapshot_rows(tmp_path / "repo", ref))

    # `list_snapshots` sorts by full path, so ibm_fez precedes ibm_other.
    assert [r.path for r in rows] == [
        "snapshots/2026-09/ibm_fez/20260901T010203000000Z.json",
        "snapshots/2026-09/ibm_fez/20260902T010203000000Z.json",
        "snapshots/2026-09/ibm_other/20260901T000000000000Z.json",
    ]
    assert all(r.rejection_reason is None for r in rows)
    assert rows[0].mean_T1 == pytest.approx(150.0)


@pytest.mark.skipif(not _HAS_GIT, reason="git is not available")
def test_backend_filter_applies_before_any_document_is_read(tmp_path: Path) -> None:
    ref = _init_fake_archive(tmp_path / "repo", ["20260901T010203000000Z"])

    rows = list(iter_snapshot_rows(tmp_path / "repo", ref, backend="ibm_fez"))

    assert [r.path for r in rows] == ["snapshots/2026-09/ibm_fez/20260901T010203000000Z.json"]


@pytest.mark.skipif(not _HAS_GIT, reason="git is not available")
def test_the_walk_is_byte_identical_across_two_runs(tmp_path: Path) -> None:
    """FR-10: same inputs, byte-identical TSV."""
    ref = _init_fake_archive(
        tmp_path / "repo", ["20260901T010203000000Z", "20260902T010203000000Z"]
    )

    first, second = tmp_path / "a.tsv", tmp_path / "b.tsv"
    write_tsv(list(iter_snapshot_rows(tmp_path / "repo", ref)), first)
    write_tsv(list(iter_snapshot_rows(tmp_path / "repo", ref)), second)

    assert first.read_bytes() == second.read_bytes()


@pytest.mark.skipif(not _HAS_GIT, reason="git is not available")
def test_the_written_tsv_round_trips_through_summarize(tmp_path: Path) -> None:
    ref = _init_fake_archive(
        tmp_path / "repo", ["20260901T010203000000Z", "20260902T010203000000Z"]
    )
    rows = list(iter_snapshot_rows(tmp_path / "repo", ref))
    out = tmp_path / "survey.tsv"
    write_tsv(rows, out)

    with out.open(newline="", encoding="utf-8") as handle:
        written = list(csv.DictReader(handle, delimiter="\t"))

    summary = summarize(rows)
    assert len(written) == summary["file_count"] == 3
    assert [w["path"] for w in written] == [r.path for r in rows]


# --------------------------------------------------------------------------
# The real archive (section 9.2: slow, and skipped when unreachable)
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_the_committed_survey_reproduces_from_the_archive() -> None:
    """Re-walk the pinned ref recorded in the evidence README and compare rows.

    Skipped unless the ``calibration-data`` ref is fetched, which is why the
    committed TSV -- not this test -- is the durable record.
    """
    if not _HAS_GIT:
        pytest.skip("git is not available")

    repo = Path(__file__).resolve().parents[1]
    survey_dir = repo / "docs" / "evidence" / "feature-distribution"
    matches = sorted(survey_dir.glob("*.tsv"))
    if not matches:
        pytest.skip("no committed survey")

    ref = matches[-1].stem.split("-")[-1]
    probe = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-t", ref], capture_output=True, check=False
    )
    if probe.returncode != 0:
        pytest.skip(f"calibration-data ref {ref} is unreachable; fetch {_ARCHIVE_REF} first")

    with matches[-1].open(newline="", encoding="utf-8") as handle:
        committed = list(csv.DictReader(handle, delimiter="\t"))

    walked = list(iter_snapshot_rows(repo, ref))
    assert len(walked) == len(committed)
    assert walked[0].path == committed[0]["path"]
    assert walked[0].mean_T1 == pytest.approx(float(committed[0]["mean_T1"]))
