"""Tests for the #125 submission script (scripts/hardware_submit.py).

Synthetic archives built on the configuration and properties bundled offline with
``qiskit_ibm_runtime``'s ``FakeFez``, plus throwaway git repositories for the freeze guard. No
network and no token: the real device class runs against a fake service.
"""

from __future__ import annotations

import copy
import json
import math
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import pytest
import scripts.hardware_submit as hs
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.primitives.containers import BitArray, DataBin, SamplerPubResult
from qiskit.transpiler import Target
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import SamplerV2
from qiskit_ibm_runtime.fake_provider import FakeFez
from scripts.hardware_reading_vs_level import (
    _write_tsv,
    archived_backend,
    arm_a_circuit,
    calendar_block_bootstrap,
    circuit_seeds,
    ghz_idle_circuit,
    transpile_layout,
)

BASE = datetime(2026, 10, 1, tzinfo=UTC)
T_S = datetime(2026, 10, 23, 3, 50, tzinfo=UTC)
T_EXECUTE = T_S + timedelta(hours=2)
AFTER = T_S + timedelta(days=1)
VARIED = tuple(range(16))
CONTROLS = (12, 13, 14, 15)
FAKE_TOKEN = "fake-token-value-that-must-never-be-written-0123456789"
DRAFT_STATUS = (
    "**Date**: 2026-10-24 · **Author**: Mert Efe Şensoy · **Status**: **DRAFT, not frozen. Nothing\n"
    'here is in force.** The commit that freezes it changes this line to "Frozen at `<commit>`" and\n'
    "is made only after all of section 6 is done\n"
)


def _plain_props() -> dict[str, Any]:
    backend = FakeFez()
    backend._set_props_dict_from_json()
    props = copy.deepcopy(backend._props_dict)
    plain: dict[str, Any] = json.loads(json.dumps(props, default=str))
    plain["backend_name"] = hs.BACKEND
    return plain


@pytest.fixture(scope="module")
def configuration() -> dict[str, Any]:
    conf: dict[str, Any] = json.loads(json.dumps(FakeFez()._get_conf_dict_from_json(), default=str))
    return conf


def _state(props: dict[str, Any], day: int, conf: dict[str, Any] | None = None) -> dict[str, Any]:
    """A document whose ``VARIED`` qubits move every day, so each is a distinct device state."""
    out = copy.deepcopy(props)
    stamp = (BASE + timedelta(days=day)).isoformat()
    out["last_update_date"] = stamp
    for q in VARIED:
        shift = math.sin(0.9 * day + q)
        for entry in out["qubits"][q]:
            if entry["name"] == "T1":
                entry["value"], entry["unit"] = 150.0 * math.exp(0.3 * shift), "us"
            elif entry["name"] == "T2":
                entry["value"], entry["unit"] = 110.0 * math.exp(0.2 * shift), "us"
    doc: dict[str, Any] = {"backend": hs.BACKEND, "timestamp": stamp, "properties": out}
    if conf is not None:
        doc["configuration"] = conf
    return doc


def _state_at(props: dict[str, Any], day: int, at: datetime) -> dict[str, Any]:
    """A new device state published at ``at``, for snapshots after the job."""
    doc = _state(props, day)
    doc["timestamp"] = at.isoformat()
    doc["properties"]["last_update_date"] = at.isoformat()
    return doc


@pytest.fixture(scope="module")
def props() -> dict[str, Any]:
    return _plain_props()


@pytest.fixture(scope="module")
def archive_docs(props: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(f"snapshots/{day:03d}.json", _state(props, day)) for day in range(23)]


@pytest.fixture(scope="module")
def live_doc(props: dict[str, Any], configuration: dict[str, Any]) -> dict[str, Any]:
    """A new device state, not in the archive: its readings differ from every archived one."""
    doc = _state(props, 40, configuration)
    doc["timestamp"] = T_S.isoformat()
    doc["properties"]["last_update_date"] = T_S.isoformat()
    return doc


@pytest.fixture
def controls_file(tmp_path: Path) -> Path:
    path = tmp_path / "controls.json"
    path.write_text(
        json.dumps(
            {
                "backend": hs.BACKEND,
                "controls": [{"qubit": q} for q in CONTROLS],
                "requested_controls": len(CONTROLS),
            }
        ),
        encoding="utf-8",
    )
    return path


class ScriptedDevice:
    """Everything a device does, instantly, with counts of the right size."""

    name = hs.BACKEND

    def __init__(
        self,
        live: Mapping[str, Any],
        *,
        status: str = "DONE",
        rep_range: Sequence[float] = (0.0, 500e-6),
        target: Target | None = None,
    ) -> None:
        self._live = live
        self._status = status
        self._rep_range = rep_range
        self._target = target if target is not None else archived_backend(live).target
        self.submitted: list[tuple[list[QuantumCircuit], list[int], dict[str, Any]]] = []
        self.captures = 0
        self.cancelled: list[str] = []

    @property
    def target(self) -> Target:
        return self._target

    def rep_delay_range(self) -> Sequence[float]:
        return self._rep_range

    def capture(self) -> dict[str, Any]:
        self.captures += 1
        return dict(self._live)

    def submit(
        self,
        circuits: Sequence[QuantumCircuit],
        shots: Sequence[int],
        options: Mapping[str, Any],
    ) -> str:
        self.submitted.append((list(circuits), list(shots), dict(options)))
        return "scripted-job"

    def status(self, job_id: str) -> str:
        del job_id
        return self._status

    def cancel(self, job_id: str) -> None:
        self.cancelled.append(job_id)

    def fetch(self, job_id: str, circuits: Sequence[QuantumCircuit]) -> hs.Fetched:
        del job_id
        counts: list[dict[str, int]] = []
        for circuit in circuits:
            shots = hs.ARM_A_SHOTS if circuit.metadata["arm"] == "A" else hs.ARM_B_SHOTS
            width = circuit.cregs[0].size
            counts.append({"0" * width: shots // 2, "1" * width: shots - shots // 2})
        return hs.Fetched(
            counts=counts,
            metrics={
                "timestamps": {"running": T_EXECUTE.isoformat()},
                "usage": {"quantum_seconds": 12.5},
            },
            inputs={"options": {"execution": {"rep_delay": hs.REP_DELAY_S}}, "version": 2},
        )

    def properties_at(self, at: datetime) -> dict[str, Any] | None:
        return {"asked_for": at.isoformat()}


def _build(
    tmp_path: Path,
    controls_file: Path,
    device: hs.Device,
    archive_docs: Iterable[tuple[str, dict[str, Any]]],
    *,
    job_number: int = 2,
    at: datetime = T_S,
    enforce_window: bool = True,
) -> Path:
    return hs.run_build(
        jobs_dir=tmp_path / "jobs",
        controls_path=controls_file,
        job_number=job_number,
        device=device,
        archive=lambda: list(archive_docs),
        now=lambda: at,
        ref_sha="a" * 40,
        code_commit="b" * 40,
        enforce_window=enforce_window,
    )


# --- the options ------------------------------------------------------------------------------


def test_pinned_options_are_the_decided_ones_and_the_sampler_accepts_them() -> None:
    options = SamplerV2(mode=FakeFez(), options=hs.pinned_options("issue-125-job-01")).options
    assert options.dynamical_decoupling.enable is False
    assert options.twirling.enable_gates is False
    assert options.twirling.enable_measure is False
    assert options.execution.init_qubits is True
    assert options.execution.rep_delay == 500e-6
    assert options.execution.meas_type == "classified"
    assert options.environment.job_tags == ["issue-125-job-01"]


@pytest.mark.parametrize("allowed", [(0.0, 250e-6), (600e-6, 700e-6)])
def test_rep_delay_outside_the_live_range_is_refused(allowed: tuple[float, float]) -> None:
    with pytest.raises(hs.RefusedError, match="rep_delay"):
        hs.check_rep_delay(hs.REP_DELAY_S, allowed)


def test_rep_delay_at_the_edge_of_the_range_is_allowed() -> None:
    hs.check_rep_delay(500e-6, (0.0, 500e-6))


# --- the freeze guard -------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _repo(tmp_path: Path, prereg_text: str) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    prereg = Path("prereg.md")
    (repo / prereg).write_text(prereg_text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "freeze")
    return repo, prereg, _git(repo, "rev-parse", "HEAD")


FROZEN = "**Status**: **Frozen**\n**Controls SHA-256**: `" + "c" * 64 + "`\n"


def test_guard_passes_only_on_the_frozen_commit(tmp_path: Path) -> None:
    repo, prereg, head = _repo(tmp_path, FROZEN)
    hs.check_frozen(repo, head, prereg, "c" * 64)


def test_guard_refuses_another_commit(tmp_path: Path) -> None:
    repo, prereg, _head = _repo(tmp_path, FROZEN)
    with pytest.raises(hs.RefusedError, match="not the frozen commit"):
        hs.check_frozen(repo, "0" * 40, prereg, "c" * 64)


@pytest.mark.parametrize(("frozen_at", "prereg"), [(None, Path("p.md")), ("x", None)])
def test_guard_needs_both_arguments(
    tmp_path: Path, frozen_at: str | None, prereg: Path | None
) -> None:
    with pytest.raises(hs.RefusedError, match="needs --frozen-at"):
        hs.check_frozen(tmp_path, frozen_at, prereg, "c" * 64)


@pytest.mark.parametrize("dirt", ["tracked", "untracked"])
def test_guard_refuses_a_dirty_tree(tmp_path: Path, dirt: str) -> None:
    repo, prereg, head = _repo(tmp_path, FROZEN)
    if dirt == "tracked":
        (repo / prereg).write_text(FROZEN + "edited\n", encoding="utf-8")
    else:
        (repo / "stray.txt").write_text("x", encoding="utf-8")
    with pytest.raises(hs.RefusedError, match="not clean"):
        hs.check_frozen(repo, head, prereg, "c" * 64)


def test_guard_refuses_the_real_drafts_status_line(tmp_path: Path) -> None:
    """The draft's own text contains the words 'Frozen at', so the check must read the field."""
    repo, prereg, head = _repo(
        tmp_path, DRAFT_STATUS + "**Controls SHA-256**: `" + "c" * 64 + "`\n"
    )
    with pytest.raises(hs.RefusedError, match="does not read Frozen"):
        hs.check_frozen(repo, head, prereg, "c" * 64)


def test_guard_refuses_a_pre_registration_without_the_hash(tmp_path: Path) -> None:
    repo, prereg, head = _repo(tmp_path, "**Status**: **Frozen**\n")
    with pytest.raises(hs.RefusedError, match="does not name"):
        hs.check_frozen(repo, head, prereg, "c" * 64)


def test_guard_refuses_other_controls(tmp_path: Path) -> None:
    repo, prereg, head = _repo(tmp_path, FROZEN)
    with pytest.raises(hs.RefusedError, match="not the frozen"):
        hs.check_frozen(repo, head, prereg, "d" * 64)


def test_a_refused_guard_stops_main_before_the_network_or_the_token(
    tmp_path: Path, controls_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, prereg, _head = _repo(tmp_path, FROZEN)

    def must_not_run(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("reached the network or the token")

    monkeypatch.setattr(hs, "ibm_device", must_not_run)
    monkeypatch.setattr(hs, "_fetch_archive", must_not_run)
    code = hs.main(
        [
            "build",
            "--repo",
            str(repo),
            "--jobs-dir",
            str(tmp_path / "jobs"),
            "--controls",
            str(controls_file),
            "--job-number",
            "1",
            "--frozen-at",
            "0" * 40,
            "--prereg",
            str(prereg),
        ]
    )
    assert code == hs.EXIT_REFUSED
    assert not (tmp_path / "jobs").exists()


def test_a_real_run_cannot_set_its_own_clock(tmp_path: Path, controls_file: Path) -> None:
    with pytest.raises(SystemExit):
        hs.main(
            [
                "build",
                "--jobs-dir",
                str(tmp_path),
                "--controls",
                str(controls_file),
                "--job-number",
                "1",
                "--at",
                T_S.isoformat(),
            ]
        )


# --- build ------------------------------------------------------------------------------------


def test_job_one_is_arm_a_only_and_later_jobs_send_both_arms(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    first = ScriptedDevice(live_doc)
    _build(tmp_path / "a", controls_file, first, archive_docs, job_number=1)
    circuits, shots, options = first.submitted[0]
    assert {c.metadata["arm"] for c in circuits} == {"A"}
    assert shots == [hs.ARM_A_SHOTS] * 7
    assert options == hs.pinned_options("issue-125-job-01")

    later = ScriptedDevice(live_doc)
    _build(tmp_path / "b", controls_file, later, archive_docs, job_number=2)
    circuits, shots, options = later.submitted[0]
    arms = [c.metadata["arm"] for c in circuits]
    assert arms.count("A") == 7 and arms.count("B") > 0
    assert shots == [hs.ARM_A_SHOTS] * 7 + [hs.ARM_B_SHOTS] * arms.count("B")
    assert options["environment"]["job_tags"] == ["issue-125-job-02"]


def test_job_number_must_be_positive() -> None:
    with pytest.raises(hs.RefusedError, match="not positive"):
        hs.arms_for(0)


def test_everything_is_written_before_submission_and_the_id_right_after(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    seen: list[str] = []
    jobs = tmp_path / "jobs" / f"{T_S:%Y-%m-%d}"

    class Spy(ScriptedDevice):
        def submit(
            self,
            circuits: Sequence[QuantumCircuit],
            shots: Sequence[int],
            options: Mapping[str, Any],
        ) -> str:
            seen.extend(sorted(p.name for p in jobs.iterdir()))
            return super().submit(circuits, shots, options)

    job_dir = _build(tmp_path, controls_file, Spy(live_doc), archive_docs)
    for name in (
        "live-properties.json",
        "predictors.tsv",
        "selection.json",
        "sealed.json",
        "circuits.qpy",
        "submission.json",
    ):
        assert name in seen
    assert "job_id.txt" not in seen
    assert (job_dir / "job_id.txt").read_text(encoding="utf-8").strip() == "scripted-job"
    submission = json.loads((job_dir / "submission.json").read_text(encoding="utf-8"))
    assert submission["t_s"] == T_S.isoformat()
    assert submission["t_submit"] == T_S.isoformat()
    assert submission["rep_delay_range"] == [0.0, 500e-6]
    assert submission["options"]["execution"]["rep_delay"] == 500e-6


def test_reading_comes_from_the_live_document_and_its_hash_is_recorded(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    """Criterion 4: a live state not in the archive, one the dry run's path has never seen."""
    job_dir = _build(tmp_path, controls_file, ScriptedDevice(live_doc), archive_docs)
    state = json.loads((job_dir / "sealed.json").read_text(encoding="utf-8"))
    entry = next(e for e in live_doc["properties"]["qubits"][3] if e["name"] == "T1")
    assert state["sources"]["reading"]["3"][0] == pytest.approx(entry["value"] * 1e-6)
    archived = [
        next(e for e in doc["properties"]["qubits"][3] if e["name"] == "T1")["value"]
        for _path, doc in archive_docs
    ]
    assert entry["value"] not in archived
    submission = json.loads((job_dir / "submission.json").read_text(encoding="utf-8"))
    assert submission["live_properties_sha256"] == hs._sha256(job_dir / "live-properties.json")


def test_a_second_job_for_one_day_is_refused(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    device = ScriptedDevice(live_doc)
    _build(tmp_path, controls_file, device, archive_docs)
    with pytest.raises(hs.RefusedError, match="already submitted"):
        _build(tmp_path, controls_file, device, archive_docs)
    assert len(device.submitted) == 1


def test_before_the_window_nothing_happens(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    device = ScriptedDevice(live_doc)
    with pytest.raises(hs.RefusedError, match="opens at 03:45"):
        _build(tmp_path, controls_file, device, archive_docs, at=T_S.replace(hour=3, minute=44))
    assert device.captures == 0 and not device.submitted


def test_after_the_window_the_day_is_recorded_as_missed(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    device = ScriptedDevice(live_doc)
    late = T_S.replace(hour=4, minute=45)
    with pytest.raises(hs.RefusedError, match="stays empty"):
        _build(tmp_path, controls_file, device, archive_docs, at=late)
    assert device.captures == 0 and not device.submitted
    missed = json.loads(
        (tmp_path / "jobs" / f"{late:%Y-%m-%d}" / "missed.json").read_text(encoding="utf-8")
    )
    assert "window" in missed["reason"]


def test_the_last_minute_of_the_window_still_submits(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    device = ScriptedDevice(live_doc)
    _build(tmp_path, controls_file, device, archive_docs, at=T_S.replace(hour=4, minute=44))
    assert len(device.submitted) == 1


def test_a_rep_delay_the_device_refuses_stops_before_the_capture(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    device = ScriptedDevice(live_doc, rep_range=(0.0, 250e-6))
    with pytest.raises(hs.RefusedError, match="rep_delay"):
        _build(tmp_path, controls_file, device, archive_docs)
    assert device.captures == 0 and not device.submitted


def test_a_selected_qubit_missing_from_the_live_target_refuses_the_job(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    target = copy.deepcopy(archived_backend(live_doc).target)
    target["x"].pop((CONTROLS[0],))
    device = ScriptedDevice(live_doc, target=target)
    with pytest.raises(hs.RefusedError, match="not operational"):
        _build(tmp_path, controls_file, device, archive_docs)
    assert not device.submitted


def test_arm_b_leaves_out_a_coupler_gone_from_the_live_target(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    full = ScriptedDevice(live_doc)
    job_dir = _build(tmp_path / "full", controls_file, full, archive_docs)
    layouts = json.loads((job_dir / "sealed.json").read_text(encoding="utf-8"))["layouts"]
    b, a = layouts[0][0], layouts[0][1]

    target = copy.deepcopy(archived_backend(live_doc).target)
    removed = [key for key in target["cz"] if set(key) == {a, b}]
    assert removed, "the fixture's first layout has no such coupler"
    for key in removed:
        target["cz"].pop(key)
    device = ScriptedDevice(live_doc, target=target)
    job_dir = _build(tmp_path / "less", controls_file, device, archive_docs)
    layouts = json.loads((job_dir / "sealed.json").read_text(encoding="utf-8"))["layouts"]
    assert all(not ({a, b} <= {t[0], t[1]} or {a, b} <= {t[0], t[2]}) for t in layouts)


# --- the sealed job ---------------------------------------------------------------------------


def test_a_sealed_job_reads_back_exactly(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    job_dir = _build(tmp_path, controls_file, ScriptedDevice(live_doc), archive_docs)
    state = json.loads((job_dir / "sealed.json").read_text(encoding="utf-8"))
    circuits = hs.read_circuits(job_dir / "circuits.qpy")
    job = hs.job_from_state(state, circuits)
    assert hs.job_to_state(job) == state
    assert len(job.arm_a) == 7
    assert [c.cregs[0].name for c in job.arm_a[:1] + job.arm_b[:1]] == ["c", "meas"]
    assert job.arm_a[0].metadata["arm"] == "A"
    assert job.arm_b[0].metadata["arm"] == "B"
    assert "reading_at_execution" not in job.arm_b_predicted
    assert job.sources["reading_at_execution"] == {}


# --- score ------------------------------------------------------------------------------------


def _score(job_dir: Path, device: hs.Device, docs: Iterable[tuple[str, dict[str, Any]]]) -> int:
    return hs.run_score(
        job_dir=job_dir, device=device, archive=lambda: list(docs), now=lambda: AFTER
    )


def test_score_adds_the_control_from_the_archive_and_scores_both_arms(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
    props: dict[str, Any],
) -> None:
    device = ScriptedDevice(live_doc)
    job_dir = _build(tmp_path, controls_file, device, archive_docs)
    before = _state_at(props, 41, T_EXECUTE - timedelta(minutes=5))
    after = _state_at(props, 42, T_EXECUTE + timedelta(minutes=5))
    later = [*archive_docs, ("snapshots/before.json", before), ("snapshots/after.json", after)]
    assert _score(job_dir, device, later) == 0

    rows = (job_dir / "arm-a.tsv").read_text(encoding="utf-8").splitlines()
    header = rows[0].split("\t")
    assert "abs_err_reading_at_execution" in header
    first = dict(zip(header, rows[1].split("\t"), strict=True))
    assert first["abs_err_reading_at_execution"] != "nan"
    assert first["shots"] == str(hs.ARM_A_SHOTS)

    arm_b = json.loads((job_dir / "arm-b.json").read_text(encoding="utf-8"))
    assert arm_b["reading_at_execution"]["n_predicted"] > 0
    summary = json.loads((job_dir / "daily-summary.json").read_text(encoding="utf-8"))
    assert summary["quantum_seconds"] == 12.5
    assert summary["t_execute"] == T_EXECUTE.isoformat()
    assert summary["arm_a"]["control"]["rows"] > 0
    assert summary["arm_a"]["discriminating"]["mae_level"] is not None
    back = json.loads((job_dir / "inputs-read-back.json").read_text(encoding="utf-8"))
    assert back["options"]["execution"]["rep_delay"] == hs.REP_DELAY_S
    assert (job_dir / "properties-at-execution.json").exists()


def test_job_one_scores_arm_a_only(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
    props: dict[str, Any],
) -> None:
    device = ScriptedDevice(live_doc)
    job_dir = _build(tmp_path, controls_file, device, archive_docs, job_number=1)
    newest = ("snapshots/newest.json", _state_at(props, 42, T_EXECUTE + timedelta(minutes=5)))
    assert _score(job_dir, device, [*archive_docs, newest]) == 0
    assert (job_dir / "arm-a.tsv").exists()
    assert not (job_dir / "arm-b.json").exists()
    assert "arm_b" not in json.loads((job_dir / "daily-summary.json").read_text(encoding="utf-8"))


def test_score_waits_for_the_archive_to_pass_the_execution_time(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    device = ScriptedDevice(live_doc)
    job_dir = _build(tmp_path, controls_file, device, archive_docs)
    assert _score(job_dir, device, archive_docs) == hs.EXIT_NOT_YET
    assert not (job_dir / "arm-a.tsv").exists()


def test_a_queued_job_is_left_alone_until_the_next_submission(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    device = ScriptedDevice(live_doc, status="QUEUED")
    job_dir = _build(tmp_path, controls_file, device, archive_docs)
    code = hs.run_score(
        job_dir=job_dir,
        device=device,
        archive=lambda: list(archive_docs),
        now=lambda: T_S + timedelta(hours=20),
    )
    assert code == hs.EXIT_NOT_YET
    assert not device.cancelled and not (job_dir / "failed.json").exists()


def test_a_job_still_queued_at_the_next_submission_is_cancelled_and_the_day_is_empty(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    device = ScriptedDevice(live_doc, status="QUEUED")
    job_dir = _build(tmp_path, controls_file, device, archive_docs)
    code = hs.run_score(
        job_dir=job_dir,
        device=device,
        archive=lambda: list(archive_docs),
        now=lambda: hs.next_submission(T_S),
    )
    assert code == 0
    assert device.cancelled == ["scripted-job"]
    assert (
        "still queued"
        in json.loads((job_dir / "failed.json").read_text(encoding="utf-8"))["reason"]
    )


def test_a_running_job_is_never_cancelled(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    device = ScriptedDevice(live_doc, status="RUNNING")
    job_dir = _build(tmp_path, controls_file, device, archive_docs)
    code = hs.run_score(
        job_dir=job_dir,
        device=device,
        archive=lambda: list(archive_docs),
        now=lambda: hs.next_submission(T_S) + timedelta(hours=1),
    )
    assert code == hs.EXIT_NOT_YET
    assert not device.cancelled


@pytest.mark.parametrize("status", ["ERROR", "CANCELLED"])
def test_a_failed_job_is_an_empty_day_with_no_re_run(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
    status: str,
) -> None:
    device = ScriptedDevice(live_doc, status=status)
    job_dir = _build(tmp_path, controls_file, device, archive_docs)
    assert _score(job_dir, device, archive_docs) == 0
    assert json.loads((job_dir / "failed.json").read_text(encoding="utf-8"))["status"] == status
    assert len(device.submitted) == 1
    assert not (job_dir / "arm-a.tsv").exists()


@pytest.mark.parametrize("name", ["sealed.json", "circuits.qpy"])
def test_score_refuses_a_sealed_file_changed_after_submission(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
    name: str,
) -> None:
    device = ScriptedDevice(live_doc)
    job_dir = _build(tmp_path, controls_file, device, archive_docs)
    with (job_dir / name).open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(hs.RefusedError, match="no longer matches"):
        _score(job_dir, device, archive_docs)


def test_score_refuses_a_folder_with_no_job(tmp_path: Path, live_doc: dict[str, Any]) -> None:
    with pytest.raises(hs.RefusedError, match="no submitted job"):
        _score(tmp_path, ScriptedDevice(live_doc), [])


def test_score_refuses_counts_of_the_wrong_size(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    class Short(ScriptedDevice):
        def fetch(self, job_id: str, circuits: Sequence[QuantumCircuit]) -> hs.Fetched:
            fetched = super().fetch(job_id, circuits)
            fetched.counts[0]["0" * circuits[0].cregs[0].size] -= 1
            return fetched

    device = Short(live_doc)
    job_dir = _build(tmp_path, controls_file, device, archive_docs)
    with pytest.raises(ValueError, match="not 2048"):
        _score(job_dir, device, archive_docs)


def test_an_unscored_cross_check_failing_does_not_cost_the_scores(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
    props: dict[str, Any],
) -> None:
    class Flaky(ScriptedDevice):
        def properties_at(self, at: datetime) -> dict[str, Any] | None:
            raise RuntimeError("historical read failed")

    device = Flaky(live_doc)
    job_dir = _build(tmp_path, controls_file, device, archive_docs)
    newest = ("snapshots/newest.json", _state_at(props, 42, T_EXECUTE + timedelta(minutes=5)))
    assert _score(job_dir, device, [*archive_docs, newest]) == 0
    assert (job_dir / "arm-a.tsv").exists()
    cross_check = json.loads((job_dir / "properties-at-execution.json").read_text(encoding="utf-8"))
    assert "historical read failed" in cross_check["error"]


# --- the real device class, against a fake service --------------------------------------------


class _Properties:
    def __init__(self, doc: Mapping[str, Any]) -> None:
        self._doc = doc
        self.last_update_date = doc["last_update_date"]

    def to_dict(self) -> dict[str, Any]:
        return dict(self._doc)


class _Configuration:
    rep_delay_range = (0.0, 500e-6)

    def __init__(self, doc: Mapping[str, Any]) -> None:
        self._doc = doc

    def to_dict(self) -> dict[str, Any]:
        return dict(self._doc)


class _Backend:
    def __init__(self, live: Mapping[str, Any]) -> None:
        self._live = live
        self.target = archived_backend(live).target

    def properties(self, refresh: bool = False, datetime: Any = None) -> _Properties:
        del refresh, datetime
        return _Properties(self._live["properties"])

    def configuration(self) -> _Configuration:
        return _Configuration(self._live["configuration"])


class _RemoteJob:
    inputs: ClassVar[dict[str, Any]] = {
        "options": {"execution": {"rep_delay": 500e-6}},
        "version": 2,
    }

    def job_id(self) -> str:
        return "remote-job"


class _Service:
    def __init__(self, live: Mapping[str, Any], **kwargs: Any) -> None:
        self.kwargs = kwargs
        self._backend = _Backend(live)

    def backend(self, name: str) -> _Backend:
        assert name == hs.BACKEND
        return self._backend


def test_the_token_reaches_the_service_and_no_file_a_job_writes(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"IBM_QUANTUM_TOKEN={FAKE_TOKEN}\nIBM_QUANTUM_INSTANCE=crn:fake\n", encoding="utf-8"
    )
    services: list[_Service] = []
    runs: list[tuple[Any, dict[str, Any], list[Any]]] = []

    def factory(**kwargs: Any) -> _Service:
        service = _Service(live_doc, **kwargs)
        services.append(service)
        return service

    class Sampler:
        def __init__(self, mode: Any, options: dict[str, Any]) -> None:
            self.mode, self.options = mode, options

        def run(self, pubs: list[Any]) -> _RemoteJob:
            runs.append((self.mode, self.options, pubs))
            return _RemoteJob()

    device = hs.ibm_device(env_file, service_factory=factory, sampler=Sampler)
    job_dir = _build(tmp_path, controls_file, device, archive_docs, job_number=1)

    assert services[0].kwargs["token"] == FAKE_TOKEN
    assert services[0].kwargs["instance"] == "crn:fake"
    _mode, options, pubs = runs[0]
    assert options == hs.pinned_options("issue-125-job-01")
    assert [p[2] for p in pubs] == [hs.ARM_A_SHOTS] * 7
    assert (job_dir / "job_id.txt").read_text(encoding="utf-8").strip() == "remote-job"
    written = [p for p in (tmp_path / "jobs").rglob("*") if p.is_file()]
    assert len(written) >= 6
    for path in written:
        assert FAKE_TOKEN.encode() not in path.read_bytes(), path
    captured = capsys.readouterr()
    assert FAKE_TOKEN not in captured.out + captured.err


def test_an_env_file_without_a_token_is_refused(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("IBM_QUANTUM_CHANNEL=x\n", encoding="utf-8")

    def factory(**kwargs: Any) -> Any:
        raise AssertionError("connected without a token")

    with pytest.raises(hs.RefusedError, match="no IBM_QUANTUM_TOKEN"):
        hs.ibm_device(env_file, service_factory=factory)


# --- the rehearsal device ---------------------------------------------------------------------


def _pub(**registers: dict[str, int]) -> SamplerPubResult:
    bits = {
        name: BitArray.from_counts(counts, num_bits=len(next(iter(counts))))
        for name, counts in registers.items()
    }
    return SamplerPubResult(DataBin(**bits))


def test_counts_come_from_each_circuits_own_register() -> None:
    arm_a = QuantumCircuit(QuantumRegister(2), ClassicalRegister(2, "c"))
    arm_b = QuantumCircuit(QuantumRegister(2), ClassicalRegister(2, "meas"))
    result = [_pub(c={"01": 3}), _pub(meas={"10": 5})]
    assert hs._counts_from_pubs(result, [arm_a, arm_b]) == [{"01": 3}, {"10": 5}]


def test_counts_join_a_circuits_registers_with_the_lowest_bit_on_the_right() -> None:
    """The ``T1`` analysis reads bit ``i`` as qubit ``i``: a swap would trade two qubits' fits."""
    circuit = QuantumCircuit(
        QuantumRegister(2), ClassicalRegister(1, "c0"), ClassicalRegister(1, "c8")
    )
    result = [_pub(c0={"1": 4}, c8={"0": 4})]
    assert hs._counts_from_pubs(result, [circuit]) == [{"01": 4}]


def test_a_circuit_with_no_register_is_refused() -> None:
    with pytest.raises(ValueError, match="no classical register"):
        hs._counts_from_pubs([_pub(c={"0": 1})], [QuantumCircuit(1, name="bare")])


def test_a_build_that_ends_after_the_window_closed_is_missed_not_submitted(
    tmp_path: Path,
    controls_file: Path,
    live_doc: dict[str, Any],
    archive_docs: list[tuple[str, dict[str, Any]]],
) -> None:
    device = ScriptedDevice(live_doc)
    closes = hs.window_for(T_S)[1]
    clock = iter([T_S, closes])
    with pytest.raises(hs.RefusedError, match="the window closed"):
        hs.run_build(
            jobs_dir=tmp_path / "jobs",
            controls_path=controls_file,
            job_number=2,
            device=device,
            archive=lambda: list(archive_docs),
            now=lambda: next(clock),
            ref_sha="a" * 40,
            code_commit="b" * 40,
            enforce_window=True,
        )
    assert device.submitted == []
    job_dir = tmp_path / "jobs" / f"{T_S:%Y-%m-%d}"
    assert (job_dir / "missed.json").exists()
    assert not (job_dir / "job_id.txt").exists()


def test_a_rehearsal_job_keeps_its_own_execution_time(
    tmp_path: Path, live_doc: dict[str, Any]
) -> None:
    """Scored days later with another clock, the job still ran when it ran."""
    store = tmp_path / "local"
    circuit = QuantumCircuit(1, 1, name="one")
    circuit.measure(0, 0)
    device = hs.LocalDevice(live_doc, execute_at=T_EXECUTE, store=store, seed=7)
    job_id = device.submit([circuit], [8], {})
    later = hs.LocalDevice(live_doc, execute_at=T_EXECUTE + timedelta(days=2), store=store, seed=7)
    fetched = later.fetch(job_id, [circuit])
    assert fetched.metrics["timestamps"]["running"] == T_EXECUTE.isoformat()


def test_every_local_run_gets_exactly_one_circuit(
    tmp_path: Path, live_doc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fast guard: the Aer defect needs two circuits in one run, so there must never be two."""
    runs: list[int] = []

    class Spy:
        def __init__(self, mode: Any, options: dict[str, Any]) -> None:
            self.seed = options["simulator"]["seed_simulator"]

        def run(self, pubs: list[Any]) -> list[Any]:
            runs.append(len(pubs))

            class Data:
                def __getattr__(self, name: str) -> Any:
                    class Bits:
                        def get_counts(self) -> dict[str, int]:
                            return {"0": 1}

                    return Bits()

            class Pub:
                data = Data()

            class Result(list[Any]):
                def result(self) -> list[Any]:
                    return [Pub() for _ in pubs]

            return Result()

    monkeypatch.setattr(hs, "SamplerV2", Spy)
    monkeypatch.setattr(hs.AerSimulator, "from_backend", staticmethod(lambda backend: object()))
    device = hs.LocalDevice(live_doc, execute_at=T_EXECUTE, store=tmp_path, seed=7)
    circuits = [QuantumCircuit(1, 1, name=f"c{i}") for i in range(5)]
    device.submit(circuits, [1] * 5, {})
    assert runs == [1, 1, 1, 1, 1]


@pytest.mark.slow
def test_the_rehearsal_runs_each_circuit_alone_so_the_aer_defect_cannot_reach_it(
    tmp_path: Path, live_doc: dict[str, Any]
) -> None:
    """Arm B after Arm A in one job must equal the same circuit run alone, seed for seed.

    Seven active qubits at 64 shots make Aer pick statevector for the first circuit and density
    matrix for the second, the order that comes out wrong if the two ever share one run.
    """
    target = archived_backend(live_doc).target
    active = tuple(range(7))
    x_len = {q: round(float(target["x"][(q,)].duration) / float(target.dt)) for q in active}
    first = arm_a_circuit(2, dict.fromkeys(active, 1000), x_len, int(target.num_qubits))
    second = transpile_layout(ghz_idle_circuit(1000), (1, 0, 2), target, seed=125)
    pick = [first, second]

    device = hs.LocalDevice(live_doc, execute_at=T_EXECUTE, store=tmp_path / "local", seed=125)
    job_id = device.submit(pick, [64, 64], {})
    assert device.status(job_id) == "DONE"
    together = device.fetch(job_id, pick).counts

    alone = AerSimulator.from_backend(archived_backend(live_doc))
    seeds, _ = circuit_seeds(125, 2, 0)
    sampler = SamplerV2(mode=alone, options={"simulator": {"seed_simulator": seeds[1]}})
    expected = sampler.run([(second, None, 64)]).result()[0].data.meas.get_counts()
    assert together[1] == expected
    assert sum(together[0].values()) == 64


def test_the_rehearsal_reports_its_metrics_in_the_real_shape(
    tmp_path: Path, live_doc: dict[str, Any]
) -> None:
    device = hs.LocalDevice(live_doc, execute_at=T_EXECUTE, store=tmp_path, seed=1)
    (tmp_path / "x.json").write_text(
        json.dumps({"counts": [], "running": T_EXECUTE.isoformat()}), encoding="utf-8"
    )
    fetched = device.fetch("x", [])
    assert fetched.metrics["timestamps"]["running"] == T_EXECUTE.isoformat()
    assert fetched.metrics["usage"]["quantum_seconds"] == 0
    assert device.properties_at(T_EXECUTE) is None
    assert device.rep_delay_range()[1] >= hs.REP_DELAY_S


# --- report: the decision rule ----------------------------------------------------------------


def _row(
    stratum: str, reading: float, level: float, execution: float, band: int = 1
) -> dict[str, Any]:
    return {
        "stratum": stratum,
        "abs_err_reading": reading,
        "abs_err_level": level,
        "abs_err_reading_at_execution": execution,
        "band_covered": band,
        "band_covered_widened": band,
    }


def _scored_day(
    jobs: Path,
    day: datetime,
    rows: Sequence[Mapping[str, Any]],
    arm_b: Mapping[str, Any] | None = None,
) -> None:
    folder = jobs / f"{day:%Y-%m-%d}"
    folder.mkdir(parents=True)
    _write_tsv(folder / "arm-a.tsv", rows)
    if arm_b is not None:
        (folder / "arm-b.json").write_text(json.dumps(arm_b), encoding="utf-8")


def _arm_b(measured: list[float], **predicted: list[float | None]) -> dict[str, Any]:
    return {"measured": measured, **{k: {"predicted": v} for k, v in predicted.items()}}


FIRST = datetime(2026, 11, 10, tzinfo=UTC)


def _day(i: int) -> datetime:
    return FIRST + timedelta(days=i)


def _report(jobs: Path, today: int) -> dict[str, Any]:
    return hs.run_report(jobs, first_day=FIRST.date(), today=_day(today).date())


def _strong_day(i: int, jitter: float = 0.0) -> list[dict[str, Any]]:
    disc = _row("discriminating", 0.20 + jitter, 0.05, 0.19 + jitter)
    ctrl = _row("control", 0.10 + jitter, 0.05, 0.09 + jitter)
    return [dict(disc) for _ in range(8)] + [dict(ctrl) for _ in range(4)]


def test_report_passes_when_level_is_clearly_closer_on_every_day(tmp_path: Path) -> None:
    for i in range(14):
        _scored_day(tmp_path, _day(i), _strong_day(i, 0.01 * (i % 3)))
    out = _report(tmp_path, 14)
    assert out["complete"] is True and out["interim_note"] is None
    assert out["arm_a"]["A1_level_beats_reading"]["passes"] is True
    assert out["arm_a"]["A2_level_beats_reading_at_execution"]["passes"] is True
    assert out["arm_a"]["A3_sign_holds_on_controls"] is True
    assert out["arm_a"]["A4_band_covers_nominal_within_widening"]["passes"] is True
    assert out["reading"] == "S1 passes"
    assert out["arm_a"]["rows"] == {"discriminating": 112, "control": 56}


def test_report_keeps_missed_failed_and_absent_days_on_the_calendar(tmp_path: Path) -> None:
    _scored_day(tmp_path, _day(0), _strong_day(0))
    (tmp_path / f"{_day(1):%Y-%m-%d}").mkdir()
    (tmp_path / f"{_day(1):%Y-%m-%d}" / "missed.json").write_text("{}", encoding="utf-8")
    (tmp_path / f"{_day(2):%Y-%m-%d}").mkdir()
    (tmp_path / f"{_day(2):%Y-%m-%d}" / "failed.json").write_text("{}", encoding="utf-8")
    _scored_day(tmp_path, _day(4), _strong_day(4))
    out = _report(tmp_path, 4)
    statuses = {d["date"]: d["status"] for d in out["days"]}
    assert statuses == {
        f"{_day(0):%Y-%m-%d}": "scored",
        f"{_day(1):%Y-%m-%d}": "missed",
        f"{_day(2):%Y-%m-%d}": "failed",
        f"{_day(3):%Y-%m-%d}": "empty",
        f"{_day(4):%Y-%m-%d}": "scored",
    }
    assert out["complete"] is False
    assert "must not stop or extend" in out["interim_note"]
    assert out["arm_a"]["rows"]["discriminating"] == 16


def test_report_axis_reaches_the_runs_last_day_when_it_was_missed(tmp_path: Path) -> None:
    _scored_day(tmp_path, _day(0), _strong_day(0))
    out = _report(tmp_path, 30)
    assert out["complete"] is True
    assert out["last_day"] == f"{_day(13):%Y-%m-%d}"
    assert len(out["days"]) == 14
    assert [d["status"] for d in out["days"][1:]] == ["empty"] * 13


def test_a_span_reaching_empty_days_changes_the_block_draws() -> None:
    dates = [_day(0).date()] * 4 + [_day(1).date()] * 4 + [_day(2).date()] * 4
    diffs = [1.0] * 4 + [0.0] * 4 + [-1.0] * 4
    plain = calendar_block_bootstrap(diffs, dates, block_days=1, n_boot=400, seed=3)
    longer = calendar_block_bootstrap(
        diffs, dates, block_days=1, n_boot=400, seed=3, span=(_day(0).date(), _day(13).date())
    )
    assert plain != longer


def test_a_span_inside_the_rows_leaves_the_axis_alone() -> None:
    dates = [_day(0).date()] * 4 + [_day(1).date()] * 4 + [_day(2).date()] * 4
    diffs = [1.0] * 4 + [0.0] * 4 + [-1.0] * 4
    plain = calendar_block_bootstrap(diffs, dates, block_days=1, n_boot=400, seed=3)
    same = calendar_block_bootstrap(
        diffs, dates, block_days=1, n_boot=400, seed=3, span=(_day(1).date(), _day(1).date())
    )
    assert plain == same


def test_report_fails_s1_when_the_execution_reading_is_as_good_as_level(tmp_path: Path) -> None:
    for i in range(14):
        rows = [_row("discriminating", 0.20, 0.05, 0.05) for _ in range(8)]
        rows += [_row("control", 0.10, 0.05, 0.05) for _ in range(4)]
        _scored_day(tmp_path, _day(i), rows)
    out = _report(tmp_path, 14)
    assert out["arm_a"]["A2_level_beats_reading_at_execution"]["passes"] is False
    assert out["reading"].startswith("S1 fails")


def test_report_names_the_staleness_finding(tmp_path: Path) -> None:
    for i in range(14):
        jitter = 0.03 if i % 2 else -0.03
        rows = [_row("discriminating", 0.20, 0.05, 0.05 + jitter + 0.001) for _ in range(8)]
        rows += [_row("control", 0.10, 0.05, 0.09) for _ in range(4)]
        _scored_day(tmp_path, _day(i), rows)
    out = _report(tmp_path, 14)
    assert out["arm_a"]["A1_level_beats_reading"]["passes"] is True
    assert out["arm_a"]["A2_level_beats_reading_at_execution"]["passes"] is False
    assert "staleness" in out["reading"]


@pytest.mark.parametrize(
    ("control", "expected"),
    [
        (_row("control", 0.10, 0.05, 0.09), True),
        (_row("control", 0.05, 0.10, 0.20), False),
        (_row("control", 0.20, 0.10, 0.05), False),
    ],
)
def test_a3_needs_level_ahead_of_both_readings_on_the_controls(
    tmp_path: Path, control: dict[str, Any], expected: bool
) -> None:
    rows = [_row("discriminating", 0.20, 0.05, 0.19) for _ in range(8)] + [control]
    _scored_day(tmp_path, _day(0), rows)
    assert _report(tmp_path, 0)["arm_a"]["A3_sign_holds_on_controls"] is expected


@pytest.mark.parametrize(("hits", "passes"), [(8, True), (7, False)])
def test_a4_reads_the_widened_coverage_against_the_nominal(
    tmp_path: Path, hits: int, passes: bool
) -> None:
    rows = [_row("discriminating", 0.2, 0.05, 0.19, 1) for _ in range(hits)]
    rows += [_row("discriminating", 0.2, 0.05, 0.19, 0) for _ in range(10 - hits)]
    _scored_day(tmp_path, _day(0), rows)
    a4 = _report(tmp_path, 0)["arm_a"]["A4_band_covers_nominal_within_widening"]
    assert a4["passes"] is passes
    assert a4["coverage_widened"] == hits / 10


def test_a4_passes_on_the_widening_when_the_nominal_alone_falls_short(tmp_path: Path) -> None:
    rows = [_row("discriminating", 0.2, 0.05, 0.19, 1) for _ in range(7)]
    rows.append({**_row("discriminating", 0.2, 0.05, 0.19, 0), "band_covered_widened": 1})
    rows += [_row("discriminating", 0.2, 0.05, 0.19, 0) for _ in range(2)]
    _scored_day(tmp_path, _day(0), rows)
    a4 = _report(tmp_path, 0)["arm_a"]["A4_band_covers_nominal_within_widening"]
    assert a4["coverage"] == 0.7
    assert a4["coverage_widened"] == 0.8
    assert a4["passes"] is True


def test_a4_ignores_rows_with_no_band_and_reports_nominal_beside_widened(tmp_path: Path) -> None:
    rows = [_row("discriminating", 0.2, 0.05, 0.19, 1) for _ in range(4)]
    rows.append(_row("discriminating", 0.2, 0.05, 0.19, -1))
    rows.append({**_row("discriminating", 0.2, 0.05, 0.19, 0), "band_covered_widened": 1})
    _scored_day(tmp_path, _day(0), rows)
    a4 = _report(tmp_path, 0)["arm_a"]["A4_band_covers_nominal_within_widening"]
    assert a4["coverage"] == 4 / 5
    assert a4["coverage_widened"] == 1.0


def test_unusable_predictors_are_left_out_of_the_comparison(tmp_path: Path) -> None:
    rows = [_row("discriminating", math.nan, 0.05, 0.19) for _ in range(4)]
    rows += [_row("discriminating", 0.20, 0.05, 0.19) for _ in range(4)]
    _scored_day(tmp_path, _day(0), rows)
    a1 = _report(tmp_path, 0)["arm_a"]["A1_level_beats_reading"]
    assert a1["rows"] == 4


def test_a3_compares_the_two_predictors_on_the_same_rows(tmp_path: Path) -> None:
    """A row only ``level`` predicted must not count for or against it."""
    rows = [_row("discriminating", 0.20, 0.05, 0.19) for _ in range(8)]
    rows += [_row("control", 0.10, 0.08, 0.09) for _ in range(4)]
    rows += [_row("control", math.nan, 0.50, 0.60) for _ in range(4)]
    _scored_day(tmp_path, _day(0), rows)
    assert _report(tmp_path, 0)["arm_a"]["A3_sign_holds_on_controls"] is True


def test_the_report_hands_the_bootstrap_the_whole_calendar_in_three_day_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, Any]] = []
    real = hs.calendar_block_bootstrap

    def spy(diffs: Any, dates: Any, **kwargs: Any) -> Any:
        seen.append(kwargs)
        return real(diffs, dates, **kwargs)

    monkeypatch.setattr(hs, "calendar_block_bootstrap", spy)
    _scored_day(tmp_path, _day(1), _strong_day(1))
    _report(tmp_path, 4)
    assert len(seen) == 2
    assert {k["block_days"] for k in seen} == {3}
    assert {k["span"] for k in seen} == {(_day(0).date(), _day(4).date())}
    assert seen[0]["seed"] != seen[1]["seed"]


def test_the_block_length_is_amendment_8s_three_days_and_the_run_is_fourteen() -> None:
    assert hs.BLOCK_DAYS == 3
    assert hs.N_JOBS == 14
    assert hs.BAND_NOMINAL == 0.80


def test_arm_b_ranks_the_band_by_its_midpoint_and_reports_both_readings() -> None:
    measured = [0.9, 0.7, 0.5, 0.3]
    job = _arm_b(
        measured,
        reading=[0.1, 0.9, 0.5, 0.3],
        level=[0.1, 0.2, 0.3, 0.9],
        band_lo=[0.85, 0.1, 0.45, 0.25],
        band_hi=[0.95, 1.3, 0.55, 0.35],
    )
    out = hs._arm_b_report([job])
    assert out["mean_spearman"]["band"] == pytest.approx(1.0)
    assert out["best_pick_hits"] == {"reading": 0, "level": 0, "band": 1}
    assert out["one_predictor_meets_both"] is True
    assert out["each_condition_by_either"] is True


def test_arm_b_two_readings_of_level_or_band_can_differ() -> None:
    """Level ranks better but misses the pick; the band picks but ranks worse than reading."""
    jobs = [
        _arm_b(
            [0.9, 0.7, 0.5, 0.3],
            reading=[0.9, 0.3, 0.7, 0.5],
            level=[0.8, 0.9, 0.5, 0.3],
            band_lo=[0.9, 0.1, 0.2, 0.8],
            band_hi=[0.9, 0.1, 0.2, 0.8],
        )
    ]
    out = hs._arm_b_report(jobs)
    assert out["best_pick_hits"] == {"reading": 1, "level": 0, "band": 1}
    assert out["mean_spearman"]["level"] == pytest.approx(0.8)
    assert out["mean_spearman"]["reading"] == pytest.approx(0.4)
    assert out["mean_spearman"]["band"] == pytest.approx(0.2)
    assert out["one_predictor_meets_both"] is False
    assert out["each_condition_by_either"] is True


def test_arm_b_fails_both_readings_when_neither_predictor_keeps_up() -> None:
    jobs = [
        _arm_b(
            [0.9, 0.7, 0.5, 0.3],
            reading=[0.9, 0.7, 0.5, 0.3],
            level=[0.3, 0.5, 0.7, 0.9],
            band_lo=[0.3, 0.5, 0.7, 0.9],
            band_hi=[0.3, 0.5, 0.7, 0.9],
        )
    ]
    out = hs._arm_b_report(jobs)
    assert out["one_predictor_meets_both"] is False
    assert out["each_condition_by_either"] is False


def test_arm_b_treats_a_missing_band_end_as_no_prediction() -> None:
    job = _arm_b(
        [0.9, 0.7, 0.5],
        reading=[0.9, 0.7, 0.5],
        level=[0.9, 0.7, 0.5],
        band_lo=[None, 0.6, 0.4],
        band_hi=[0.8, 0.7, 0.6],
    )
    out = hs._arm_b_report([job])
    assert out["best_pick_hits"]["band"] == 0
    assert out["mean_spearman"]["band"] == pytest.approx(1.0)


def test_report_refuses_a_jobs_dir_that_is_not_there(tmp_path: Path) -> None:
    with pytest.raises(hs.RefusedError, match="not a folder"):
        _report(tmp_path / "absent", 0)


def test_report_refuses_a_day_before_the_run_starts(tmp_path: Path) -> None:
    with pytest.raises(hs.RefusedError, match="the run starts on"):
        hs.run_report(tmp_path, first_day=FIRST.date(), today=_day(-1).date())


@pytest.mark.parametrize("offset", [-1, 14])
def test_report_refuses_a_job_folder_outside_the_runs_days(tmp_path: Path, offset: int) -> None:
    """Day 15 would be an extension, and a folder before day 1 another run's."""
    (tmp_path / f"{_day(offset):%Y-%m-%d}").mkdir()
    with pytest.raises(hs.RefusedError, match="outside"):
        _report(tmp_path, 20)


def test_report_refuses_a_job_folder_dated_after_today(tmp_path: Path) -> None:
    (tmp_path / f"{_day(3):%Y-%m-%d}").mkdir()
    with pytest.raises(hs.RefusedError, match="outside"):
        _report(tmp_path, 2)


def test_a_missed_first_day_does_not_move_the_calendar(tmp_path: Path) -> None:
    _scored_day(tmp_path, _day(1), _strong_day(1))
    out = _report(tmp_path, 14)
    assert out["first_day"] == f"{_day(0):%Y-%m-%d}"
    assert out["last_day"] == f"{_day(13):%Y-%m-%d}"
    assert out["days"][0]["status"] == "empty"


def test_day_fourteen_is_still_interim_and_the_next_is_not(tmp_path: Path) -> None:
    assert _report(tmp_path, 13)["complete"] is False
    assert _report(tmp_path, 14)["complete"] is True


def test_report_with_no_rows_says_so(tmp_path: Path) -> None:
    (tmp_path / f"{FIRST:%Y-%m-%d}").mkdir()
    out = _report(tmp_path, 0)
    assert out["reading"] == "no scored rows"
    assert out["arm_a"]["A1_level_beats_reading"]["passes"] is False
    assert out["arm_a"]["A3_sign_holds_on_controls"] is False
    assert out["arm_a"]["A4_band_covers_nominal_within_widening"]["passes"] is False


def test_a_scored_day_reads_scored_even_with_an_older_status_file(tmp_path: Path) -> None:
    _scored_day(tmp_path, _day(0), _strong_day(0))
    (tmp_path / f"{_day(0):%Y-%m-%d}" / "job_id.txt").write_text("x", encoding="utf-8")
    assert _report(tmp_path, 0)["days"][0]["status"] == "scored"


def test_a_submitted_day_with_no_scores_is_named(tmp_path: Path) -> None:
    (tmp_path / f"{_day(0):%Y-%m-%d}").mkdir()
    (tmp_path / f"{_day(0):%Y-%m-%d}" / "job_id.txt").write_text("x", encoding="utf-8")
    assert _report(tmp_path, 0)["days"][0]["status"] == "submitted, not scored"


def test_the_arm_b_scores_of_a_job_folder_reach_the_report(tmp_path: Path) -> None:
    job = _arm_b(
        [0.9, 0.7, 0.5],
        reading=[0.9, 0.7, 0.5],
        level=[0.9, 0.7, 0.5],
        band_lo=[0.9, 0.7, 0.5],
        band_hi=[0.9, 0.7, 0.5],
    )
    _scored_day(tmp_path, _day(1), _strong_day(1), job)
    assert _report(tmp_path, 1)["arm_b"]["jobs"] == 1


def test_report_command_writes_the_file_and_marks_it_interim(tmp_path: Path) -> None:
    _scored_day(tmp_path, _day(0), _strong_day(0))
    code = hs.main(
        [
            "report",
            "--jobs-dir",
            str(tmp_path),
            "--first-day",
            f"{_day(0):%Y-%m-%d}",
            "--today",
            f"{_day(1):%Y-%m-%d}",
        ]
    )
    assert code == 0
    written = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert written["complete"] is False
    assert written["interim_note"]
    assert b"\r\n" not in (tmp_path / "report.json").read_bytes()


def test_report_command_exits_refused_without_a_traceback(tmp_path: Path) -> None:
    code = hs.main(["report", "--jobs-dir", str(tmp_path / "absent"), "--first-day", "2026-11-10"])
    assert code == hs.EXIT_REFUSED
