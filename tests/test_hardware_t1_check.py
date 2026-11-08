"""Tests for the T1 check (scripts/hardware_t1_check.py).

The guards and the bookkeeping run on the project's pins with the library stubbed. The tests that
need Qiskit Experiments itself skip without it, so a green CI run says nothing about them: they run
from the check's own environment, which the runbook names.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import scripts.hardware_submit as hs
import scripts.hardware_t1_check as t1
from qiskit import QuantumCircuit
from qiskit.transpiler import Target
from qiskit_ibm_runtime.fake_provider import FakeFez
from scripts.hardware_reading_vs_level import archived_backend, write_json_lf

from tests.test_hardware_submit import FAKE_TOKEN, _plain_props, _state

QUBITS = (0, 1, 2)
T_EXECUTE = datetime(2026, 10, 23, 5, 50, tzinfo=UTC)


@pytest.fixture(scope="module")
def live_doc() -> dict[str, Any]:
    conf: dict[str, Any] = json.loads(json.dumps(FakeFez()._get_conf_dict_from_json(), default=str))
    return _state(_plain_props(), 40, conf)


def _t1_circuit(n_qubits: int, qubit: int, index: int) -> QuantumCircuit:
    circuit = QuantumCircuit(n_qubits, 1, name=f"t1-{qubit}-{index}")
    circuit.x(qubit)
    circuit.delay(100, qubit, "dt")
    circuit.measure(qubit, 0)
    circuit.metadata = {"index": index}
    return circuit


class StubExperiment:
    def __init__(self, n_qubits: int) -> None:
        self._n_qubits = n_qubits

    def _transpiled_circuits(self) -> list[QuantumCircuit]:
        return [_t1_circuit(self._n_qubits, 0, i) for i in range(t1.N_DELAYS)]


class StubDevice:
    name = hs.BACKEND

    def __init__(
        self,
        live: Mapping[str, Any],
        *,
        status: str = "DONE",
        rep_range: Sequence[float] = (0.0, 500e-6),
    ) -> None:
        self.backend = archived_backend(live)
        self._status = status
        self._rep_range = rep_range
        self.submitted: list[tuple[list[QuantumCircuit], list[int], dict[str, Any]]] = []
        self.shots_returned = t1.T1_SHOTS

    @property
    def target(self) -> Target:
        target: Target = self.backend.target
        return target

    def rep_delay_range(self) -> Sequence[float]:
        return self._rep_range

    def capture(self) -> dict[str, Any]:
        raise AssertionError("the check does not capture")

    def submit(
        self, circuits: Sequence[QuantumCircuit], shots: Sequence[int], options: Mapping[str, Any]
    ) -> str:
        self.submitted.append((list(circuits), list(shots), dict(options)))
        return "scripted-t1-job"

    def status(self, job_id: str) -> str:
        del job_id
        return self._status

    def cancel(self, job_id: str) -> None:
        raise AssertionError(f"the check never cancels {job_id}")

    def fetch(self, job_id: str, circuits: Sequence[QuantumCircuit]) -> hs.Fetched:
        del job_id
        return hs.Fetched(
            counts=[{"0": self.shots_returned} for _ in circuits],
            metrics={
                "timestamps": {"running": T_EXECUTE.isoformat()},
                "usage": {"quantum_seconds": 6.5},
            },
            inputs={},
        )

    def properties_at(self, at: datetime) -> dict[str, Any] | None:
        del at
        return None


def _job_folder(
    tmp_path: Path,
    *,
    number: int = 1,
    main_id: str | None = "main-job",
    t1_us: Mapping[int, float] | None = None,
) -> Path:
    expected = {0: 20.0, 1: 200.0, 2: 60.0} if t1_us is None else t1_us
    job_dir = tmp_path / "2026-10-23"
    job_dir.mkdir()
    write_json_lf(
        job_dir / "submission.json", {"job_number": number, "controls_file_sha256": "c" * 64}
    )
    write_json_lf(
        job_dir / "sealed.json",
        {
            "discriminating": list(expected),
            "sources": {
                "level": {str(q): [v * 1e-6, 1e-4, 0.01, 0.01] for q, v in expected.items()},
                "reading": {str(q): [v * 2e-6, 1e-4, 0.01, 0.01] for q, v in expected.items()},
            },
        },
    )
    if main_id is not None:
        (job_dir / "job_id.txt").write_text(main_id + "\n", encoding="utf-8", newline="\n")
    return job_dir


@pytest.fixture
def stub_library(monkeypatch: pytest.MonkeyPatch) -> list[Mapping[int, Sequence[float]]]:
    """No Qiskit Experiments: stubbed circuits and a stubbed fit, recording what they were given."""
    seen: list[Mapping[int, Sequence[float]]] = []

    def experiment(backend: Any, delays: Mapping[int, Sequence[float]]) -> StubExperiment:
        seen.append(delays)
        return StubExperiment(int(backend.target.num_qubits))

    def fit(
        backend: Any,
        delays: Mapping[int, Sequence[float]],
        circuits: Sequence[QuantumCircuit],
        counts: Sequence[Mapping[str, int]],
    ) -> dict[int, dict[str, Any]]:
        del backend, circuits, counts
        return {
            q: {
                "t1_s": 1e-4 * (q + 1),
                "stderr_s": 4e-6 * (q + 1),
                "relative_se": 0.01 * (q + 1),
                "reduced_chi_squared": 1.0,
                "quality": "good",
            }
            for q in delays
        }

    monkeypatch.setattr(t1, "_experiment", experiment)
    monkeypatch.setattr(t1, "fit_t1", fit)
    monkeypatch.setattr(t1, "_library_version", lambda: "stub")
    return seen


def _submit(job_dir: Path, device: StubDevice, *, local: bool = False) -> None:
    t1.run_submit(job_dir=job_dir, device=device, local=local)


# --- the delays ---------------------------------------------------------------------------------


@pytest.mark.parametrize("expected", [7e-6, 54e-6, 220e-6])
def test_delays_cover_three_of_the_qubits_own_t1(expected: float) -> None:
    delays = t1.t1_delays(expected)
    assert len(delays) == 8
    assert delays[0] == pytest.approx(1e-6)
    assert delays[-1] == pytest.approx(3.0 * expected)
    assert np.allclose(np.diff(delays), np.diff(delays)[0])


@pytest.mark.parametrize("expected", [math.nan, math.inf, 0.0, -1e-6, 3e-7])
def test_delays_refuse_an_expectation_with_no_usable_span(expected: float) -> None:
    with pytest.raises(hs.RefusedError, match="cannot space delays"):
        t1.t1_delays(expected)


def test_shots_and_delays_are_the_designs() -> None:
    assert (t1.T1_SHOTS, t1.N_DELAYS) == (1024, 8)


# --- submit -------------------------------------------------------------------------------------


@pytest.mark.parametrize("number", [1, 14])
def test_the_first_and_last_jobs_submit_the_check(
    tmp_path: Path,
    live_doc: dict[str, Any],
    stub_library: list[Mapping[int, Sequence[float]]],
    number: int,
) -> None:
    device = StubDevice(live_doc)
    job_dir = _job_folder(tmp_path, number=number)
    _submit(job_dir, device)
    circuits, shots, options = device.submitted[0]
    assert len(circuits) == 8
    assert shots == [1024] * 8
    assert options == hs.pinned_options(f"issue-125-t1-{number:02d}")
    assert (job_dir / "t1-job_id.txt").read_text(encoding="utf-8") == "scripted-t1-job\n"
    assert list(stub_library[0]) == list(QUBITS)
    assert stub_library[0][1][-1] == pytest.approx(3 * 200e-6)
    sealed = json.loads((job_dir / "t1-sealed.json").read_text(encoding="utf-8"))
    assert sealed["qiskit_experiments"] == "stub"
    assert sealed["circuits_sha256"] == hs._sha256(job_dir / "t1-circuits.qpy")


@pytest.mark.parametrize("number", [2, 7, 13, 15])
def test_no_other_job_has_a_check(
    tmp_path: Path,
    live_doc: dict[str, Any],
    stub_library: list[Mapping[int, Sequence[float]]],
    number: int,
) -> None:
    device = StubDevice(live_doc)
    with pytest.raises(hs.RefusedError, match="has no check"):
        _submit(_job_folder(tmp_path, number=number), device)
    assert device.submitted == []


def test_a_day_whose_main_job_never_left_has_no_check(
    tmp_path: Path, live_doc: dict[str, Any], stub_library: list[Mapping[int, Sequence[float]]]
) -> None:
    device = StubDevice(live_doc)
    with pytest.raises(hs.RefusedError, match="no submitted main job"):
        _submit(_job_folder(tmp_path, main_id=None), device)
    assert device.submitted == []


def test_a_real_check_refuses_a_rehearsals_folder(
    tmp_path: Path, live_doc: dict[str, Any], stub_library: list[Mapping[int, Sequence[float]]]
) -> None:
    device = StubDevice(live_doc)
    job_dir = _job_folder(tmp_path, main_id="local-abc")
    with pytest.raises(hs.RefusedError, match="rehearsal"):
        _submit(job_dir, device)
    _submit(job_dir, device, local=True)
    assert len(device.submitted) == 1


def test_the_check_is_submitted_once(
    tmp_path: Path, live_doc: dict[str, Any], stub_library: list[Mapping[int, Sequence[float]]]
) -> None:
    device = StubDevice(live_doc)
    job_dir = _job_folder(tmp_path)
    _submit(job_dir, device)
    with pytest.raises(hs.RefusedError, match="already submitted"):
        _submit(job_dir, device)
    assert len(device.submitted) == 1


def test_a_rep_delay_outside_the_live_range_refuses_the_check(
    tmp_path: Path, live_doc: dict[str, Any], stub_library: list[Mapping[int, Sequence[float]]]
) -> None:
    device = StubDevice(live_doc, rep_range=(0.0, 250e-6))
    with pytest.raises(hs.RefusedError, match="rep_delay"):
        _submit(_job_folder(tmp_path), device)
    assert device.submitted == []


def test_circuits_are_validated_and_sealed_before_anything_leaves(
    tmp_path: Path,
    live_doc: dict[str, Any],
    stub_library: list[Mapping[int, Sequence[float]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid(circuits: Any, target: Any) -> None:
        del circuits, target
        raise ValueError("not ISA")

    monkeypatch.setattr(t1, "validate_isa_circuits", invalid)
    device = StubDevice(live_doc)
    with pytest.raises(ValueError, match="not ISA"):
        _submit(_job_folder(tmp_path), device)
    assert device.submitted == []


def test_the_seal_is_on_disk_when_the_job_is_submitted(
    tmp_path: Path, live_doc: dict[str, Any], stub_library: list[Mapping[int, Sequence[float]]]
) -> None:
    job_dir = _job_folder(tmp_path)
    present: list[bool] = []

    class Watching(StubDevice):
        def submit(
            self,
            circuits: Sequence[QuantumCircuit],
            shots: Sequence[int],
            options: Mapping[str, Any],
        ) -> str:
            present.extend(
                [(job_dir / "t1-sealed.json").exists(), (job_dir / "t1-circuits.qpy").exists()]
            )
            return super().submit(circuits, shots, options)

    _submit(job_dir, Watching(live_doc))
    assert present == [True, True]


# --- score --------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["QUEUED", "VALIDATING", "RUNNING"])
def test_a_check_still_on_its_way_is_left_alone(
    tmp_path: Path,
    live_doc: dict[str, Any],
    stub_library: list[Mapping[int, Sequence[float]]],
    status: str,
) -> None:
    job_dir = _job_folder(tmp_path)
    _submit(job_dir, StubDevice(live_doc))
    assert t1.run_score(job_dir=job_dir, device=StubDevice(live_doc, status=status)) == 3
    assert not (job_dir / "t1-check.json").exists()
    assert not (job_dir / "t1-failed.json").exists()


@pytest.mark.parametrize("status", ["ERROR", "CANCELLED"])
def test_a_failed_check_is_recorded_and_costs_nothing_else(
    tmp_path: Path,
    live_doc: dict[str, Any],
    stub_library: list[Mapping[int, Sequence[float]]],
    status: str,
) -> None:
    job_dir = _job_folder(tmp_path)
    _submit(job_dir, StubDevice(live_doc))
    assert t1.run_score(job_dir=job_dir, device=StubDevice(live_doc, status=status)) == 0
    written = json.loads((job_dir / "t1-failed.json").read_text(encoding="utf-8"))
    assert written["status"] == status
    assert not (job_dir / "failed.json").exists()


def test_a_finished_check_writes_each_qubits_fit_beside_its_readings(
    tmp_path: Path, live_doc: dict[str, Any], stub_library: list[Mapping[int, Sequence[float]]]
) -> None:
    job_dir = _job_folder(tmp_path)
    device = StubDevice(live_doc)
    _submit(job_dir, device)
    assert t1.run_score(job_dir=job_dir, device=device) == 0
    out = json.loads((job_dir / "t1-check.json").read_text(encoding="utf-8"))
    assert [row["qubit"] for row in out["qubits"]] == list(QUBITS)
    first = out["qubits"][0]
    assert first["level_t1_s"] == pytest.approx(20e-6)
    assert first["reading_t1_s"] == pytest.approx(40e-6)
    assert first["t1_s"] == pytest.approx(1e-4)
    assert len(first["delays_s"]) == 8
    assert out["median_relative_se"] == pytest.approx(0.02)
    assert out["t_execute"] == T_EXECUTE.isoformat()
    assert out["quantum_seconds"] == 6.5
    assert out["rep_delay_s"] == hs.REP_DELAY_S
    raw = json.loads((job_dir / "t1-results.json").read_text(encoding="utf-8"))
    assert raw["job_id"] == "scripted-t1-job"
    assert len(raw["counts"]) == 8


def test_raw_counts_survive_a_fit_that_fails(
    tmp_path: Path,
    live_doc: dict[str, Any],
    stub_library: list[Mapping[int, Sequence[float]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_dir = _job_folder(tmp_path)
    device = StubDevice(live_doc)
    _submit(job_dir, device)

    def fails(*args: Any) -> Any:
        del args
        raise ValueError("no fit")

    monkeypatch.setattr(t1, "fit_t1", fails)
    with pytest.raises(ValueError, match="no fit"):
        t1.run_score(job_dir=job_dir, device=device)
    assert (job_dir / "t1-results.json").exists()
    assert not (job_dir / "t1-check.json").exists()


def test_a_result_with_the_wrong_shot_count_is_refused(
    tmp_path: Path, live_doc: dict[str, Any], stub_library: list[Mapping[int, Sequence[float]]]
) -> None:
    job_dir = _job_folder(tmp_path)
    device = StubDevice(live_doc)
    _submit(job_dir, device)
    device.shots_returned = 1000
    with pytest.raises(ValueError, match="1000 shots"):
        t1.run_score(job_dir=job_dir, device=device)
    assert not (job_dir / "t1-results.json").exists()


def test_circuits_changed_after_the_seal_are_refused(
    tmp_path: Path, live_doc: dict[str, Any], stub_library: list[Mapping[int, Sequence[float]]]
) -> None:
    job_dir = _job_folder(tmp_path)
    device = StubDevice(live_doc)
    _submit(job_dir, device)
    with (job_dir / "t1-circuits.qpy").open("ab") as handle:
        handle.write(b"x")
    with pytest.raises(hs.RefusedError, match="no longer matches"):
        t1.run_score(job_dir=job_dir, device=device)


def test_score_refuses_a_folder_with_no_check(tmp_path: Path, live_doc: dict[str, Any]) -> None:
    with pytest.raises(hs.RefusedError, match="no submitted check"):
        t1.run_score(job_dir=_job_folder(tmp_path), device=StubDevice(live_doc))


# --- the command line ---------------------------------------------------------------------------


def test_the_guard_runs_before_the_token_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_dir = _job_folder(tmp_path)
    calls: list[str] = []

    def guard(repo: Path, frozen: Any, prereg: Any, sha: str) -> None:
        del repo, frozen, prereg
        calls.append(sha)
        raise hs.RefusedError("not frozen")

    def connect(env_file: Path) -> Any:
        del env_file
        raise AssertionError("the token must not be read")

    monkeypatch.setattr(t1, "check_frozen", guard)
    monkeypatch.setattr(t1, "ibm_device", connect)
    code = t1.main(["submit", "--job-dir", str(job_dir), "--frozen-at", "a" * 40])
    assert code == hs.EXIT_REFUSED
    assert calls == ["c" * 64]


def test_a_rehearsal_needs_an_execution_time(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        t1.main(
            ["score", "--job-dir", str(tmp_path), "--sealed-dir", "s", "--local-live", "x.json"]
        )


def test_the_token_reaches_no_file_the_check_writes(
    tmp_path: Path,
    live_doc: dict[str, Any],
    stub_library: list[Mapping[int, Sequence[float]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = tmp_path / "secret.env"
    env.write_text(f"IBM_QUANTUM_TOKEN={FAKE_TOKEN}\n", encoding="utf-8")
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    job_dir = _job_folder(jobs)
    seen: list[str] = []

    def device_from(env_file: Path) -> StubDevice:
        seen.append(hs.dotenv_values(env_file)["IBM_QUANTUM_TOKEN"] or "")
        return StubDevice(live_doc)

    monkeypatch.setattr(t1, "check_frozen", lambda *args: None)
    monkeypatch.setattr(t1, "ibm_device", device_from)
    assert t1.main(["submit", "--job-dir", str(job_dir), "--env-file", str(env)]) == 0
    sealed = tmp_path / "sealed"
    score = ["score", "--job-dir", str(job_dir), "--sealed-dir", str(sealed)]
    assert t1.main([*score, "--env-file", str(env)]) == 0
    assert seen == [FAKE_TOKEN, FAKE_TOKEN]
    written = [p for p in job_dir.iterdir() if p.is_file()]
    written += [p for p in (sealed / job_dir.name).iterdir() if p.is_file()]
    assert len(written) >= 7
    assert not [p.name for p in written if FAKE_TOKEN.encode() in p.read_bytes()]


# --- the fit, with the library's objects stubbed ---------------------------------------------------


class _Value:
    nominal_value = 1e-4
    std_dev = 4e-6


class _Results:
    def __init__(self, qubits: Sequence[int]) -> None:
        self._qubits = qubits

    def iterrows(self) -> Any:
        for q in self._qubits:
            yield q, {"components": [f"Q{q}"], "value": _Value(), "chisq": 1.2, "quality": "good"}


def _stub_fit_library(monkeypatch: pytest.MonkeyPatch, fitted: Sequence[int]) -> None:
    class Done:
        def analysis_results(self, name: str, dataframe: bool) -> _Results:
            assert (name, dataframe) == ("T1", True)
            return _Results(fitted)

    class Run:
        def block_for_results(self, timeout: float) -> Done:
            assert timeout == t1.ANALYSIS_TIMEOUT_S
            return Done()

    class Analysis:
        def run(self, data: Any) -> Run:
            del data
            return Run()

    class Experiment:
        analysis = Analysis()

    class Data:
        def __init__(self, experiment: Any) -> None:
            del experiment

        def add_data(self, rows: Any) -> None:
            del rows

    class Framework:
        ExperimentData = Data

    monkeypatch.setattr(t1.importlib, "import_module", lambda name: Framework())
    monkeypatch.setattr(t1, "_experiment", lambda backend, delays: Experiment())


def test_a_fit_for_every_qubit_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_fit_library(monkeypatch, [3, 5])
    out = t1.fit_t1(None, {3: [1e-6], 5: [1e-6]}, [], [])
    assert set(out) == {3, 5}
    assert out[3]["t1_s"] == pytest.approx(1e-4)
    assert out[3]["stderr_s"] == pytest.approx(4e-6)
    assert out[3]["relative_se"] == pytest.approx(0.04)
    assert out[3]["reduced_chi_squared"] == pytest.approx(1.2)
    assert out[3]["quality"] == "good"


def test_a_fit_that_lost_a_qubit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_fit_library(monkeypatch, [3])
    with pytest.raises(ValueError, match="fitted"):
        t1.fit_t1(None, {3: [1e-6], 5: [1e-6]}, [], [])


# --- with the library itself --------------------------------------------------------------------


@pytest.fixture
def library() -> None:
    pytest.importorskip("qiskit_experiments")


def _doc_with_t1(live_doc: Mapping[str, Any], t1_us: Mapping[int, float]) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(json.dumps(live_doc))
    for qubit, value in t1_us.items():
        for entry in doc["properties"]["qubits"][qubit]:
            if entry["name"] == "T1" or entry["name"] == "T2":
                entry["value"], entry["unit"] = value, "us"
    return doc


def test_the_librarys_circuits_are_valid_for_the_device_and_keep_a_register_per_qubit(
    library: None, live_doc: dict[str, Any]
) -> None:
    backend = archived_backend(live_doc)
    delays = {q: t1.t1_delays(100e-6) for q in QUBITS}
    circuits = t1._experiment(backend, delays)._transpiled_circuits()
    t1.validate_isa_circuits(circuits, backend.target)
    assert len(circuits) == 8
    assert [r.size for r in circuits[0].cregs] == [1, 1, 1]
    assert [circuits[0].metadata["composite_qubits"][i] for i in range(3)] == [[0], [1], [2]]


@pytest.mark.slow
def test_each_fit_recovers_its_own_qubits_t1_through_the_whole_path(
    library: None, tmp_path: Path, live_doc: dict[str, Any]
) -> None:
    """Three qubits a factor of ten apart: a register read in the wrong order would swap them."""
    t1_us = {0: 20.0, 1: 200.0, 2: 60.0}
    doc = _doc_with_t1(live_doc, t1_us)
    job_dir = _job_folder(tmp_path, t1_us=t1_us)
    device = hs.LocalDevice(
        doc,
        execute_at=datetime(2026, 10, 23, 5, 50, tzinfo=UTC) + timedelta(0),
        store=tmp_path / "local-jobs",
        seed=125,
    )
    _submit(job_dir, device, local=True)
    assert t1.run_score(job_dir=job_dir, device=device) == 0
    out = json.loads((job_dir / "t1-check.json").read_text(encoding="utf-8"))
    for row in out["qubits"]:
        built = t1_us[row["qubit"]] * 1e-6
        assert abs(row["t1_s"] - built) <= 4.0 * row["stderr_s"], row
        assert row["relative_se"] < 0.15, row
    assert out["qiskit_experiments"] == "0.14.2"


# --- sealing (amendment 27, criterion 23) -----------------------------------------------------

PLANTED_ONES = 677
PLANTED_T1 = {0: 0.000123456789, 1: 0.000246913578, 2: 0.000370370367}


class PlantedCounts(StubDevice):
    def fetch(self, job_id: str, circuits: Sequence[QuantumCircuit]) -> hs.Fetched:
        fetched = super().fetch(job_id, circuits)
        counts = [{"0": self.shots_returned - PLANTED_ONES, "1": PLANTED_ONES} for _ in circuits]
        return hs.Fetched(counts=counts, metrics=fetched.metrics, inputs=fetched.inputs)


def test_a_fitted_check_leaves_no_count_or_fit_in_the_jobs_folder(
    tmp_path: Path,
    live_doc: dict[str, Any],
    stub_library: list[Mapping[int, Sequence[float]]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Criterion 23 for the check: counts and every fitted number go to the sealed folder only."""

    def fit(*args: Any) -> dict[int, dict[str, Any]]:
        del args
        return {
            q: {
                "t1_s": t,
                "stderr_s": t / 37.0,
                "relative_se": 1.0 / 37.0 + q * 1e-9,
                "reduced_chi_squared": 1.0 + 0.0123456 * (q + 1),
                "quality": "good",
            }
            for q, t in PLANTED_T1.items()
        }

    monkeypatch.setattr(t1, "fit_t1", fit)
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    job_dir = _job_folder(jobs)
    device = PlantedCounts(live_doc)
    _submit(job_dir, device)
    sealed = tmp_path / "sealed"
    capsys.readouterr()
    assert t1.run_score(job_dir=job_dir, device=device, sealed_dir=sealed) == 0
    printed = capsys.readouterr().out.encode()

    day = sealed / job_dir.name
    assert sorted(p.name for p in day.iterdir()) == ["t1-check.json", "t1-results.json"]
    values = [v for fitted in fit().values() for k, v in fitted.items() if k != "quality"]
    needles = {repr(v).encode() for v in values} | {str(PLANTED_ONES).encode()}
    check = json.loads((day / "t1-check.json").read_text(encoding="utf-8"))
    needles.add(repr(check["median_relative_se"]).encode())
    in_sealed = b"".join(p.read_bytes() for p in day.iterdir())

    def holds(data: bytes, needle: bytes) -> bool:
        return re.search(rb"(?<![\w.])" + re.escape(needle) + rb"(?![\w])", data) is not None

    assert all(holds(in_sealed, n) for n in needles), "a needle the sealed day does not hold"
    files = [p for p in jobs.rglob("*") if p.is_file()]
    assert len(files) >= 5
    assert [(p.name, n) for p in files for n in needles if holds(p.read_bytes(), n)] == []
    assert [n for n in needles if holds(printed, n)] == []
    operations = json.loads((job_dir / "t1-operations.json").read_text(encoding="utf-8"))
    assert operations == {
        "status": "fitted",
        "job_id": operations["job_id"],
        "qubits": 3,
        "fit_quality": {"good": 3},
        "quantum_seconds": 6.5,
    }


def test_the_check_refuses_a_sealed_folder_inside_the_jobs_folder_before_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    jobs = tmp_path / "jobs"
    job_dir = jobs / "2026-11-10"
    job_dir.mkdir(parents=True)

    def no_network(*args: Any) -> Any:
        raise AssertionError("the network was reached")

    monkeypatch.setattr(t1, "ibm_device", no_network)
    for inside in (jobs, jobs / "sealed", job_dir / "sealed"):
        argv = ["score", "--job-dir", str(job_dir), "--sealed-dir", str(inside)]
        assert t1.main(argv) == hs.EXIT_REFUSED
        assert "refused" in capsys.readouterr().err
    assert not (jobs / "sealed").exists()
