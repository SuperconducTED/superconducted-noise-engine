"""Public provenance, completeness, temporal replay, and source isolation."""

import copy
import hashlib
from datetime import timedelta

import numpy as np
import pytest

from superconducted.training import public_archive as public
from superconducted.training.dataset import BuildReport, build_training_set


def write_parquet(tmp_path, monkeypatch, rows):
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = tmp_path / "public.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    monkeypatch.setattr(public, "PUBLIC_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    return path


def event(q, prop, value, hour=0.5, observed=None):
    stamp = public.PUBLIC_START + timedelta(hours=hour)
    return dict(
        backend="ibm_fez",
        scope="gate1q" if prop == "sx_gate_length" else "qubit",
        property=prop,
        qubit_a=q,
        qubit_b=None,
        calibrated_time=stamp,
        observed_time=stamp if observed is None else observed,
        value=float(value),
        unit="ns" if prop == "sx_gate_length" else public.EXPECTED_UNITS[prop],
        SN=999.0,
    )


def complete_events():
    return [
        event(q, prop, 0.0001 if prop in ("T1", "T2") else 0.02)
        for q in range(156)
        for prop in public.COMPLETE
    ] + [event(q, "sx_gate_length", 24) for q in range(156)]


def test_hash_mismatch_fails_before_reader_import(tmp_path):
    path = tmp_path / "bad.parquet"
    path.write_bytes(b"not the pinned bytes")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        list(public.iter_public_archive(path, public.PublicReplayReport()))


def test_replay_completeness_rescaling_first_value_and_no_lookahead(tmp_path, monkeypatch):
    rows = complete_events()
    # Same calibration stamp, later observation: the first value must win,
    # even when the parquet presents the later observation first.
    rows.insert(0, event(0, "T1", 900, observed=public.PUBLIC_START + timedelta(days=1)))
    rows += [event(0, "T1", 200, hour=1.5), event(0, "readout_length", 1600, hour=2.5)]
    path = write_parquet(tmp_path, monkeypatch, rows)
    report = public.PublicReplayReport()
    result = list(
        public.iter_public_archive(path, report, end=public.PUBLIC_START + timedelta(hours=4))
    )
    assert report.marks == 4 and report.incomplete_marks == 1
    assert report.distinct_states == 3
    assert "SN" not in public.COLUMNS
    first = result[0][1]
    assert first["properties"]["last_update_date"].endswith("01:00:00+00:00")
    q0 = {e["name"]: e["value"] for e in first["properties"]["qubits"][0]}
    assert q0["T1"] == 100 and q0["T2"] == 100
    assert not {e["name"] for e in first["properties"]["qubits"][72]} & {"T1", "T2"}
    assert first["properties"]["gates"][0]["parameters"][0]["value"] == 24
    assert report.rescaled_events == {"T1": 155, "T2": 155}
    assert report.excluded_rescale_events == {"T1": 1, "T2": 1}
    assert all(k not in first for k in ("target", "configuration"))


def test_missing_one_readout_quantity_excludes_every_mark(tmp_path, monkeypatch):
    rows = [
        r
        for r in complete_events()
        if not (r["qubit_a"] == 72 and r["property"] == "prob_meas0_prep1")
    ]
    path = write_parquet(tmp_path, monkeypatch, rows)
    report = public.PublicReplayReport()
    assert (
        list(public.iter_public_archive(path, report, end=public.PUBLIC_START + timedelta(hours=3)))
        == []
    )
    assert report.incomplete_marks == 3


def test_scope_window_and_unit_validation(tmp_path, monkeypatch):
    rows = complete_events()
    ignored = event(0, "T1", 999, hour=2)
    ignored["backend"] = "ibm_torino"
    rows += [ignored, event(0, "T1", 999, hour=4000)]
    path = write_parquet(tmp_path, monkeypatch, rows)
    assert len(public._events(path, public.PublicReplayReport())) == 934
    rows[0]["unit"] = "s"
    path = write_parquet(tmp_path, monkeypatch, rows)
    with pytest.raises(ValueError, match="expected unit"):
        public._events(path, public.PublicReplayReport())


def test_builder_keeps_ibm_authoritative_and_tags_public_rows(tmp_path, monkeypatch):
    from scripts.build_training_set import main

    from superconducted.training import dataset

    rows = [*complete_events(), event(0, "T1", 200, hour=1.5)]
    path = write_parquet(tmp_path, monkeypatch, rows)
    replay = list(
        public.iter_public_archive(
            path, public.PublicReplayReport(), end=public.PUBLIC_START + timedelta(hours=3)
        )
    )
    own = copy.deepcopy(replay[0][1])
    own["properties"]["last_update_date"] = "2026-05-13T12:13:22+00:00"
    monkeypatch.setattr(dataset, "resolve_archive_ref", lambda *args: "a" * 40)
    monkeypatch.setattr(
        dataset,
        "iter_archive",
        lambda *args: iter([("snapshots/2026-05/ibm_fez/20260513T121322000000Z.json", own)]),
    )
    report = BuildReport()
    result = build_training_set(
        tmp_path, "HEAD", backend="ibm_fez", public_parquet=path, report=report
    )
    assert result.n_rows == 2
    assert report.public.distinct_states == 2 and report.public.overlap_states == 1
    assert [r["source"] for r in report.rows] == [public.PUBLIC_SOURCE, "calibration-data"]
    assert report.rows[0]["source_revision"] == public.PUBLIC_REVISION
    assert result.provenance[0].startswith(public.PUBLIC_SOURCE + "@")
    assert result.provenance[1] == dataset.qubit_block_digest(own)
    assert result.timestamps[0] < result.timestamps[1]
    assert len(report.rows) + sum(report.skipped.values()) + report.duplicates == report.documents
    np.testing.assert_allclose(result.features[1], [100, 100, 0.02])
    with pytest.raises(ValueError, match="backend='ibm_fez'"):
        build_training_set(tmp_path, "HEAD", public_parquet=path)
    out = tmp_path / "evidence"
    args = ["--repo", str(tmp_path), "--ref", "HEAD", "--backend", "ibm_fez", "--out", str(out)]
    assert main(args) == 0
    assert main([*args, "--public-parquet", str(path)]) == 0
    assert len(list(out.glob("*.tsv"))) == 2  # public evidence cannot overwrite IBM-only evidence
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert '"distinct_states": 2' in readme
    assert '"rescaled_events": {"T1": 155, "T2": 155}' in readme
    assert "Public replay audit" in readme


@pytest.mark.parametrize("usable_qubits", [0, 1, 99, 100])
def test_sparse_public_targets_are_skipped_after_state_counting(
    tmp_path, monkeypatch, usable_qubits
):
    from superconducted.training import dataset

    full = write_parquet(tmp_path, monkeypatch, complete_events())
    own = next(
        public.iter_public_archive(
            full, public.PublicReplayReport(), end=public.PUBLIC_START + timedelta(hours=2)
        )
    )[1]
    own["properties"]["last_update_date"] = "2026-05-13T12:13:22+00:00"
    for entry in own["properties"]["qubits"][0]:
        if entry["name"] == "T1":
            entry["value"] = 300.0  # distinct IBM state, never suppresses the public state
    selected = set([q for q in range(156) if q != 72][:usable_qubits])
    rows = [
        r
        for r in complete_events()
        if r["property"] != "sx_gate_length" or r["qubit_a"] in selected
    ]
    path = write_parquet(tmp_path, monkeypatch, rows)
    monkeypatch.setattr(dataset, "resolve_archive_ref", lambda *args: "a" * 40)
    monkeypatch.setattr(
        dataset,
        "iter_archive",
        lambda *args: iter([("snapshots/2026-05/ibm_fez/20260513T121322000000Z.json", own)]),
    )
    report = BuildReport()
    result = build_training_set(
        tmp_path, "HEAD", backend="ibm_fez", public_parquet=path, report=report
    )
    rejected = int(usable_qubits < public.PUBLIC_MIN_TARGET_QUBITS)
    assert result.n_rows == 2 - rejected
    assert report.public.distinct_states == 1 and report.public.incomplete_marks == 1
    assert report.public.minimum_target_qubits == 100
    assert report.public.target_coverage_skips == rejected
    assert report.skipped["target_coverage_insufficient"] == rejected
    assert len(report.rows) + sum(report.skipped.values()) + report.duplicates == report.documents
