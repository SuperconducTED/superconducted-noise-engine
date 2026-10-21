"""Integration tests for the one-time calibration state-index backfill."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.backfill_state_index import archived_snapshots, backfill
from scripts.canonical_snapshot_digest import qubit_digest
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


def test_backfill_refuses_to_append_history_after_partial_poll_index(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, "20260901T000000000000Z.json", 1.0)
    assert backfill(tmp_path) == 1
    _write_snapshot(tmp_path, "20260902T000000000000Z.json", 2.0)
    with pytest.raises(ValueError, match="incomplete"):
        backfill(tmp_path)


def _poll_indexed(root: Path, name: str, digest_of: float) -> None:
    """Write the index the poll workflow leaves behind when it runs before the backfill.

    The poller only ever sees the document in front of it, so it marks every new
    filename as a new state. That is correct going forward and wrong for history.
    """
    index = root / "health/state-index.tsv"
    index.parent.mkdir(parents=True, exist_ok=True)
    digest = qubit_digest(_snapshot(digest_of))
    index.write_text(
        "snapshot_filename\tlast_update_date\tqubit_digest\tis_new_state\n"
        f"{name}\t2026-09-02T00:00:00.000000Z\t{digest}\t1\n",
        encoding="utf-8",
    )


class TestRebuild:
    """The escape hatch for an index the hourly poller has already started writing."""

    def test_rebuild_restores_chronology_the_append_path_refuses_to_touch(
        self, tmp_path: Path
    ) -> None:
        """Once a poll row exists, only a rebuild can put is_new_state back in order."""
        _write_snapshot(tmp_path, "20260901T000000000000Z.json", 1.0)
        _write_snapshot(tmp_path, "20260902T000000000000Z.json", 1.0)
        _poll_indexed(tmp_path, "20260902T000000000000Z.json", 1.0)

        with pytest.raises(ValueError, match="--rebuild"):
            backfill(tmp_path)

        assert backfill(tmp_path, rebuild=True) == 2
        rows = read_index(tmp_path / "health/state-index.tsv")
        assert [row.filename for row in rows] == [
            "20260901T000000000000Z.json",
            "20260902T000000000000Z.json",
        ]
        assert [row.is_new for row in rows] == [True, False], (
            "the earlier document is the new state"
        )

    def test_rebuild_is_idempotent_and_byte_stable(self, tmp_path: Path) -> None:
        _write_snapshot(tmp_path, "20260901T000000000000Z.json", 1.0)
        _write_snapshot(tmp_path, "20260903T000000000000Z.json", 2.0)
        index = tmp_path / "health/state-index.tsv"
        assert backfill(tmp_path, rebuild=True) == 2
        first = index.read_bytes()
        assert backfill(tmp_path, rebuild=True) == 2
        assert index.read_bytes() == first

    def test_rebuild_repairs_an_index_the_append_path_cannot_read(self, tmp_path: Path) -> None:
        """Rebuild regenerates from the archive, so a corrupt header is not a dead end."""
        _write_snapshot(tmp_path, "20260901T000000000000Z.json", 1.0)
        index = tmp_path / "health/state-index.tsv"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text("wrong\theader\n", encoding="utf-8")
        with pytest.raises(ValueError, match="unexpected header"):
            backfill(tmp_path)
        assert backfill(tmp_path, rebuild=True) == 1
        assert [row.is_new for row in read_index(index)] == [True]


def test_a_fractional_stamp_sorts_after_the_bare_second_it_shares(tmp_path: Path) -> None:
    """`.` precedes `Z` in ASCII, so the ISO string sorts the later instant first.

    Latent while every archived name carries the six-digit fraction, but STAMP
    admits both shapes, and getting it wrong swaps which of two documents in the
    same second is recorded as a state's first sighting.
    """
    _write_snapshot(tmp_path, "20260901T000000Z.json", 1.0)
    _write_snapshot(tmp_path, "20260901T000000123456Z.json", 2.0)
    _write_snapshot(tmp_path, "20260901T000001Z.json", 3.0)
    assert [path.name for path in archived_snapshots(tmp_path)] == [
        "20260901T000000Z.json",
        "20260901T000000123456Z.json",
        "20260901T000001Z.json",
    ]


class TestTolerance:
    """One bad file must not throw away a nine-hundred-file dispatch."""

    def test_an_undigestable_document_is_skipped_not_fatal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Matches `file_snapshots.sh`: preserved on the branch, absent from the index."""
        _write_snapshot(tmp_path, "20260901T000000000000Z.json", 1.0)
        broken = tmp_path / "snapshots/2026-09/ibm_fez/20260902T000000000000Z.json"
        broken.write_text(json.dumps({"properties": {}}), encoding="utf-8")
        _write_snapshot(tmp_path, "20260903T000000000000Z.json", 2.0)

        assert backfill(tmp_path, rebuild=True) == 2
        assert "preserved but not indexed" in capsys.readouterr().out
        rows = read_index(tmp_path / "health/state-index.tsv")
        assert [row.filename for row in rows] == [
            "20260901T000000000000Z.json",
            "20260903T000000000000Z.json",
        ]
        assert broken.exists(), "the payload stays archived; only the measurement is missing"

    def test_a_non_timestamp_filename_is_skipped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_snapshot(tmp_path, "20260901T000000000000Z.json", 1.0)
        stray = tmp_path / "snapshots/2026-09/ibm_fez/notes.json"
        stray.write_text(json.dumps({"properties": {"qubits": []}}), encoding="utf-8")
        assert backfill(tmp_path, rebuild=True) == 1
        assert "not a UTC-timestamp snapshot name" in capsys.readouterr().out

    def test_a_skipped_document_does_not_break_idempotency(self, tmp_path: Path) -> None:
        """The count reports rows written, so a second run still appends zero."""
        _write_snapshot(tmp_path, "20260901T000000000000Z.json", 1.0)
        broken = tmp_path / "snapshots/2026-09/ibm_fez/20260902T000000000000Z.json"
        broken.write_text(json.dumps({"properties": {}}), encoding="utf-8")
        assert backfill(tmp_path) == 1
        assert backfill(tmp_path) == 0


def test_archived_snapshots_order_is_reproducible_across_backends(tmp_path: Path) -> None:
    """Two backends can publish one last_update_date, which gives their files one name."""
    for backend in ("ibm_fez", "ibm_torino"):
        path = tmp_path / "snapshots/2026-09" / backend / "20260901T000000000000Z.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_snapshot(1.0)), encoding="utf-8")
    ordered = archived_snapshots(tmp_path)
    assert [path.parent.name for path in ordered] == ["ibm_fez", "ibm_torino"]


class TestOneNameUnderTwoPartitions:
    """The archive already holds one document filed under two month partitions.

    At `f0930b9`, `snapshots/2026-06/ibm_fez/20260630T214008000000Z.json` and
    `snapshots/2026-07/ibm_fez/20260630T214008000000Z.json` are different blobs
    under one instant, one backend and one filename: 894 paths, 893 distinct
    names. The 2026-07 copy is misfiled against ADR-020, since its stem names
    June, but the pipeline has to be correct over the archive as it is.
    """

    @staticmethod
    def _both(root: Path, first: float = 1.0, second: float = 1.0) -> None:
        for partition, t1 in (("2026-06", first), ("2026-07", second)):
            path = root / "snapshots" / partition / "ibm_fez" / "20260630T214008000000Z.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_snapshot(t1)), encoding="utf-8")

    def test_the_order_is_decided_rather_than_left_to_the_filesystem(self, tmp_path: Path) -> None:
        """Without the partition key these tie and `sorted` falls back to glob order."""
        self._both(tmp_path)
        ordered = archived_snapshots(tmp_path)
        assert [path.parent.parent.name for path in ordered] == ["2026-06", "2026-07"]

    def test_both_documents_are_indexed(self, tmp_path: Path) -> None:
        """Two paths, two rows. Keying `existing` on the name alone loses one."""
        self._both(tmp_path, 1.0, 2.0)
        assert backfill(tmp_path) == 2
        rows = read_index(tmp_path / "health/state-index.tsv")
        assert [row.filename for row in rows] == ["20260630T214008000000Z.json"] * 2
        assert len({row.digest for row in rows}) == 2, "different blobs, different states"

    def test_a_second_run_still_appends_nothing(self, tmp_path: Path) -> None:
        """FR-3 idempotency has to survive the duplicate name, in both directions.

        Counting rows rather than testing set membership is what makes the
        second run see the archive as fully indexed instead of one short.
        """
        self._both(tmp_path, 1.0, 2.0)
        assert backfill(tmp_path) == 2
        assert backfill(tmp_path) == 0
        assert backfill(tmp_path, rebuild=True) == 2
        assert backfill(tmp_path) == 0

    def test_a_half_indexed_pair_is_still_incomplete(self, tmp_path: Path) -> None:
        """The row that set membership silently dropped now reaches the refusal.

        One row present and two paths on disk is a partially indexed archive,
        which the append path must refuse rather than append behind, exactly as
        it would for any other unindexed document.
        """
        self._both(tmp_path, 1.0, 2.0)
        index = tmp_path / "health/state-index.tsv"
        assert backfill(tmp_path) == 2
        kept = index.read_text(encoding="utf-8").splitlines()[:2]
        index.write_text("\n".join(kept) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="state index is incomplete"):
            backfill(tmp_path)
