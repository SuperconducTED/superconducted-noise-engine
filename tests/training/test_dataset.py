"""Archive builder selection, physics, accounting, and evidence conformance."""

import copy
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from scripts.build_training_set import main
from scripts.canonical_snapshot_digest import qubit_digest

from superconducted.calibration.features import ArchiveUnitFeatureExtractor
from superconducted.calibration.loader import load_snapshot, parse_snapshot
from superconducted.training.dataset import (
    ArchiveRefError,
    ArchiveTimestampError,
    BuildReport,
    build_training_set,
    dedup_by_qubit_block,
    hour_of_day_weights,
    iter_archive,
    qubit_block_digest,
)
from superconducted.training.targets import gate_lengths, qubit_targets, snapshot_target

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "calibration"
    / "ibm_fez_20260513T121322Z_with_gates.json"
)
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")


def document(day=1, value=100):
    return {
        "backend": "ibm_fez",
        "schema_version": "1.0.0",
        "timestamp": "1999-01-01T00:00:00Z",
        "properties": {
            "last_update_date": f"2026-09-{day:02}T12:00:00+00:00",
            "qubits": [
                [
                    {"name": "T1", "value": value, "unit": "us"},
                    {"name": "T2", "value": 80, "unit": "us"},
                    {"name": "readout_error", "value": 0.02, "unit": ""},
                ]
            ],
            "gates": [
                {
                    "gate": "sx",
                    "qubits": [0],
                    "parameters": [{"name": "gate_length", "unit": "ns", "value": 24}],
                }
            ],
        },
    }


def archive(tmp_path, docs):
    repo = tmp_path / "repo"
    repo.mkdir()
    for path, doc in docs:
        destination = repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(doc) if isinstance(doc, dict) else doc)
    for args in (
        ("init",),
        ("add", "."),
        ("-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "-m", "archive"),
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return repo


def path(day, month="09"):
    return f"snapshots/2026-{month}/ibm_fez/202609{day:02}T120000000000Z.json"


def test_digest_and_earliest_full_path_selection():
    doc = document()
    expected = hashlib.sha256(
        json.dumps(doc["properties"]["qubits"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert qubit_block_digest(doc) == expected
    later = document(2)
    docs = [(path(2, "01"), later), (path(1, "10"), doc), (path(1, "09"), doc)]
    assert dedup_by_qubit_block(docs) == [(path(1), doc)]
    changed = copy.deepcopy(doc)
    changed["properties"]["qubits"][0][0]["date"] = "2026-09-01T00:00:00Z"
    assert qubit_block_digest(changed) == qubit_digest(changed) == expected
    changed["properties"]["qubits"][0].reverse()
    assert qubit_block_digest(changed) != expected
    with pytest.raises(ValueError):
        qubit_block_digest({})


@pytest.mark.parametrize("field,new_value", [("value", 101), ("name", "T3"), ("unit", "ns")])
def test_dashboard_digest_conformance_preserves_measurements(field, new_value):
    doc = document()
    doc["properties"]["qubits"][0][0]["date"] = "2026-09-01T00:00:00Z"
    original = copy.deepcopy(doc)
    assert qubit_block_digest(doc) == qubit_digest(doc)
    changed = copy.deepcopy(doc)
    changed["properties"]["qubits"][0][0][field] = new_value
    assert qubit_block_digest(changed) == qubit_digest(changed)
    assert qubit_block_digest(changed) != qubit_block_digest(doc)
    assert doc == original


def test_date_only_republication_collapses_in_archive(tmp_path):
    first, later = document(), document(2)
    first["properties"]["qubits"][0][0]["date"] = "2026-09-01T00:00:00Z"
    later["properties"]["qubits"][0][0]["date"] = "2026-09-02T00:00:00Z"
    repo = archive(tmp_path, [(path(1), first), (path(2), later)])
    report = BuildReport()
    result = build_training_set(repo, "HEAD", report=report)
    assert result.n_rows == 1
    assert report.documents == 2 and report.duplicates == 1
    assert result.provenance == (qubit_digest(first),)
    assert report.rows[0]["path"] == path(1)
    assert report.rows[0]["qubit_date_min"] == "2026-09-01T00:00:00+00:00"


def test_pipeline_selects_before_usability_and_accounts_every_document(tmp_path):
    bad_target = document(3, 110)
    bad_target["properties"]["gates"] = []
    bad_features = document(4, 120)
    bad_features["properties"]["qubits"][0][2]["value"] = None
    bad_parse = document(5, 130)
    bad_parse["properties"]["qubits"][0][0]["unit"] = "ns"
    repo = archive(
        tmp_path,
        [
            (path(2, "01"), document(2)),
            (path(1), document()),
            (path(3), bad_target),
            (path(4), bad_features),
            (path(5), bad_parse),
            (path(6), "{broken"),
            (path(7), document(7, 140)),
            (path(8), document(8, 110)),  # Usable later copy of rejected first state.
        ],
    )
    report = BuildReport()
    result = build_training_set(repo, "HEAD", report=report)
    assert result.n_rows == 2
    assert report.documents == 8 and report.duplicates == 2
    assert report.skipped == {"parse_error": 2, "features_unusable": 1, "target_unusable": 1}
    assert result.timestamps == (
        datetime(2026, 9, 1, 12, tzinfo=UTC),
        datetime(2026, 9, 7, 12, tzinfo=UTC),
    )
    assert report.rows[0]["path"] == path(1)
    np.testing.assert_allclose(result.features[0], [100, 80, 0.02], rtol=1e-14)
    assert report.rows[0]["T1_qubit_p50"] == 100
    assert report.rows[0]["T2_qubit_p50"] == 80
    assert report.rows[0]["T1_qubit_std"] is None
    assert report.target_skips["gate_length_missing"] == 1
    assert report.missingness["init_error_absent"] == 2
    train, validation = result.time_split(datetime(2026, 9, 2, tzinfo=UTC))
    assert set(train.provenance).isdisjoint(validation.provenance)
    assert train.n_rows + validation.n_rows == result.n_rows
    cut = datetime(2026, 9, 2, tzinfo=UTC)
    assert all(timestamp < cut for timestamp in train.timestamps)
    assert all(timestamp >= cut for timestamp in validation.timestamps)
    assert np.all(result.weights == 1)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert result.archive_ref == head
    assert len(head) == 40
    assert len(list(iter_archive(repo, "HEAD"))) == 8


def test_hour_weights_balance_populated_utc_hours():
    stamps = [datetime(2026, 9, 1, hour, tzinfo=UTC) for hour in (0, 0, 1)]
    weights = hour_of_day_weights(stamps)
    np.testing.assert_allclose(weights, [0.75, 0.75, 1.5])
    assert weights.mean() == 1
    assert hour_of_day_weights([]).size == 0
    with pytest.raises(ValueError, match="timezone-aware"):
        hour_of_day_weights([datetime(2026, 9, 1)])


def test_same_timestamp_distinct_states_rejected(tmp_path):
    repo = archive(tmp_path, [(path(1), document()), (path(2), document(1, 101))])
    with pytest.raises(ArchiveTimestampError, match="Distinct states share"):
        build_training_set(repo, "HEAD")


def test_fixture_target_and_mapping_loader_equivalence(tmp_path):
    doc = json.loads(FIXTURE.read_text())
    assert parse_snapshot(doc, source=FIXTURE) == load_snapshot(FIXTURE)
    expected = snapshot_target(qubit_targets(parse_snapshot(doc), gate_lengths(doc["properties"])))
    repo = archive(tmp_path, [(path(1), doc)])
    report = BuildReport()
    result = build_training_set(repo, "HEAD", report=report, weighting="hour_of_day")
    np.testing.assert_allclose(result.targets[0], expected.mean)
    assert report.rows[0]["n_usable_qubits_target"] == expected.n_usable
    assert result.features[0, 0] > 1
    assert report.rows[0]["T1_qubit_std"] > 0


def test_cli_determinism_and_exit_codes(tmp_path):
    repo = archive(tmp_path, [(path(1), document()), (path(2), document(2, 101))])
    out = tmp_path / "evidence"
    args = ["--repo", str(repo), "--ref", "HEAD", "--out", str(out)]
    assert main(args) == 0
    tsv = next(out.glob("*.tsv"))
    first = tsv.read_bytes()
    assert main([*args, "--weighting", "hour_of_day"]) == 0
    assert tsv.read_bytes() == first
    assert list(out.glob("*.tsv")) == [tsv]
    assert (out / "README.md").read_text().count(f"## {tsv.name}") == 1
    assert "NC-012's unit is distinct device states" in (out / "README.md").read_text()
    assert main([*args, "--ref", "unreachable"]) == 2
    assert main([*args, "--backend", "absent"]) == 1
    with pytest.raises(ArchiveRefError):
        build_training_set(repo, "missing")


def test_builder_and_dedup_helper_select_the_same_paths(tmp_path):
    docs = [
        (path(2, "01"), document(2)),
        (path(1, "10"), document()),
        (path(1), document()),
        (path(3), document(3, 120)),
    ]
    repo = archive(tmp_path, docs)
    report = BuildReport()
    build_training_set(repo, "HEAD", report=report)
    assert [row["path"] for row in report.rows] == [p for p, _ in dedup_by_qubit_block(docs)]


def test_init_error_is_not_a_feature_or_a_mean_input(tmp_path):
    with_init = document(2)
    with_init["properties"]["qubits"][0].append({"name": "init_error", "unit": "", "value": 0.7})
    repo = archive(tmp_path, [(path(1), document()), (path(2), with_init)])
    result = build_training_set(repo, "HEAD")
    np.testing.assert_array_equal(result.features[0], result.features[1])
    assert all("init_error" not in name for name in result.feature_names)

    class InitExtractor(ArchiveUnitFeatureExtractor):
        @property
        def feature_names(self):
            return ("mean_init_error",)

    with pytest.raises(ValueError, match="init_error is excluded"):
        build_training_set(repo, "HEAD", extractor=InitExtractor())


def test_physically_invalid_t2_is_counted_as_target_unusable(tmp_path):
    invalid = document(2, 110)
    invalid["properties"]["qubits"][0][1]["value"] = 250
    repo = archive(tmp_path, [(path(1), document()), (path(2), invalid)])
    report = BuildReport()
    result = build_training_set(repo, "HEAD", report=report)
    assert result.n_rows == 1
    assert report.skipped["target_unusable"] == 1
    assert report.target_skips["t2_exceeds_2t1"] == 1


@pytest.mark.parametrize("operation", ["ls-tree", "show"])
def test_cli_reports_git_read_failures_without_traceback(tmp_path, monkeypatch, capsys, operation):
    repo = archive(tmp_path, [(path(1), document())])
    from superconducted.training import dataset

    original = dataset._git

    def fail_read(repo, *args):
        if args[0] == operation:
            raise subprocess.CalledProcessError(128, ["git", *args])
        return original(repo, *args)

    monkeypatch.setattr(dataset, "_git", fail_read)
    out = tmp_path / "evidence"
    assert main(["--repo", str(repo), "--ref", "HEAD", "--out", str(out)]) == 2
    assert "Traceback" not in capsys.readouterr().err
    assert not out.exists()


def test_cli_timestamp_tie_is_not_reported_as_no_usable_rows(tmp_path, capsys):
    repo = archive(tmp_path, [(path(1), document()), (path(2), document(1, 110))])
    out = tmp_path / "evidence"
    assert main(["--repo", str(repo), "--ref", "HEAD", "--out", str(out)]) == 2
    assert "Distinct states share last_update_date" in capsys.readouterr().err
    assert not out.exists()
