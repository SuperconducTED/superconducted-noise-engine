"""Submission and scoring for the #125 hardware test (step 1d).

Forecasts are sealed before a job runs and opened after it. ``build`` runs at ``t_s``: it captures
the device's live calibration, computes the predictors, builds circuits against the live target,
writes everything to the job's folder and only then submits. ``score`` runs the next morning: it
fetches the results, adds the ``reading_at_execution`` control from the archive and scores both
arms.

Plan and acceptance criteria: ``docs/implementations/2026-11-05-hardware-test-submission.md``.
Pre-registration: ``docs/roadmap/2026-10-24-issue-125-preregistration.md``.

Nothing reaches the QPU unless ``HEAD`` is the commit passed as ``--frozen-at``, the tree is clean,
the pre-registration at that commit reads Frozen, and it names the controls file's hash. The token
is read from ``--env-file`` and is never logged or written anywhere. Usage::

    python -m scripts.hardware_submit build --repo . --jobs-dir <dir> --controls controls.json \\
        --job-number 1 --frozen-at <sha> --prereg <path> --env-file .env
    python -m scripts.hardware_submit score --repo . --job-dir <dir>/<date> --env-file .env

``--local-live <doc.json> --at <t_s> --local-execute-at <t>`` runs the same code on a local
simulator built from that document: the rehearsal, which needs no token and no guard.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, NoReturn, Protocol

import numpy as np
import qiskit
import qiskit_aer
import qiskit_ibm_runtime
from dotenv import dotenv_values
from qiskit import QuantumCircuit, qpy
from qiskit.transpiler import Target
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
from qiskit_ibm_runtime.utils.validations import validate_isa_circuits

from scripts.hardware_reading_vs_level import (
    ARM_A_SHOTS,
    ARM_B_SHOTS,
    SEED,
    SOURCES,
    GateTable,
    Job,
    QubitSource,
    UnusableSourceError,
    _write_tsv,
    archived_backend,
    binomial_se,
    build_job,
    calendar_block_bootstrap,
    circuit_seeds,
    not_operational_qubits,
    p1_closed_form,
    score_arm_a,
    score_arm_b,
    spearman,
    with_execution,
    write_json_lf,
)
from scripts.hardware_test_predictors import (
    ControlsFileError,
    collect,
    execution_rows,
    load_controls,
    predictor_rows,
    select_balanced,
    write_outputs,
)
from superconducted.calibration.poller import DEFAULT_CHANNEL, serialize_configuration
from superconducted.training.dataset import iter_archive, resolve_archive_ref

BACKEND = "ibm_fez"
REP_DELAY_S = 500e-6
SUBMISSION_TIME = time(3, 45, tzinfo=UTC)
SUBMISSION_WINDOW = timedelta(hours=1)
N_DISCRIMINATING = 8
N_JOBS = 14
BLOCK_DAYS = 3  # amendment 8: proposed; frozen after Bengisu's statistics review on PR #135
BAND_NOMINAL = 0.80
ARCHIVE_REF = "refs/remotes/origin/calibration-data"
FROZEN_STATUS = re.compile(r"\*\*Status\*\*:\s*\*\*Frozen\b")
CONTROLS_SHA = re.compile(r"\*\*Controls SHA-256\*\*:\s*`([0-9a-f]{64})`")
WAITING = frozenset({"INITIALIZING", "QUEUED", "VALIDATING"})
EXIT_REFUSED = 2
EXIT_NOT_YET = 3

Archive = Callable[[], Iterable[tuple[str, dict[str, Any]]]]


class RefusedError(RuntimeError):
    """Something a guard will not allow. The message says which, and nothing was submitted."""


def pinned_options(job_tag: str) -> dict[str, Any]:
    """Every Sampler option the test depends on, explicit, because defaults can change.

    Decoupling would put pulses inside Arm A's ``delay``, and twirling would change the circuits
    the forecasts were computed for.
    """
    return {
        "dynamical_decoupling": {"enable": False},
        "twirling": {"enable_gates": False, "enable_measure": False},
        "execution": {"init_qubits": True, "rep_delay": REP_DELAY_S, "meas_type": "classified"},
        "environment": {"job_tags": [job_tag]},
    }


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def check_frozen(repo: Path, frozen_at: str | None, prereg: Path | None, controls_sha: str) -> None:
    """Refuse unless this checkout is exactly the frozen commit the pre-registration describes."""
    if not frozen_at or prereg is None:
        raise RefusedError("a real device needs --frozen-at and --prereg")
    head = _git(repo, "rev-parse", "HEAD").strip()
    if head != frozen_at:
        raise RefusedError(f"HEAD is {head}, not the frozen commit {frozen_at}")
    if _git(repo, "status", "--porcelain").strip():
        raise RefusedError("the tree is not clean")
    try:
        text = _git(repo, "show", f"HEAD:{prereg.as_posix()}")
    except subprocess.CalledProcessError as exc:
        raise RefusedError(f"{prereg} is not in the frozen commit") from exc
    if not FROZEN_STATUS.search(text):
        raise RefusedError("the pre-registration's status line does not read Frozen")
    named = CONTROLS_SHA.search(text)
    if named is None:
        raise RefusedError("the pre-registration does not name the controls file's hash")
    if named.group(1) != controls_sha:
        raise RefusedError(f"controls hash {controls_sha} is not the frozen {named.group(1)}")


def check_rep_delay(rep_delay: float, allowed: Sequence[float]) -> None:
    low, high = float(allowed[0]), float(allowed[1])
    if not low <= rep_delay <= high:
        raise RefusedError(f"rep_delay {rep_delay} is outside the live range [{low}, {high}]")


def window_for(at: datetime) -> tuple[datetime, datetime]:
    """The day's submission window: 03:45 UTC, and one hour after it (the missed-job rule)."""
    opens = datetime.combine(at.astimezone(UTC).date(), SUBMISSION_TIME)
    return opens, opens + SUBMISSION_WINDOW


def next_submission(t_s: datetime) -> datetime:
    return window_for(t_s)[0] + timedelta(days=1)


def arms_for(job_number: int) -> str:
    """Job 1 is Arm A only, the first contact between the pipeline and the hardware."""
    if job_number < 1:
        raise RefusedError(f"job number {job_number} is not positive")
    return "A" if job_number == 1 else "AB"


def pubs_for(job: Job, arms: str) -> tuple[list[QuantumCircuit], list[int]]:
    circuits = list(job.arm_a)
    shots = [ARM_A_SHOTS] * len(job.arm_a)
    if "B" in arms:
        circuits += list(job.arm_b)
        shots += [ARM_B_SHOTS] * len(job.arm_b)
    return circuits, shots


# ---------------------------------------------------------------------------------------------
# The sealed job: everything score needs, written before anything is submitted


def job_to_state(job: Job) -> dict[str, Any]:
    return {
        "t_s": job.t_s.isoformat(),
        "n_qubits": job.n_qubits,
        "dt": job.dt,
        "discriminating": job.discriminating,
        "controls": job.controls,
        "sources": {
            name: {str(q): [s.t1, s.t2, s.e10, s.e01] for q, s in per_qubit.items()}
            for name, per_qubit in job.sources.items()
        },
        "slots": {str(q): slots for q, slots in job.slots.items()},
        "layouts": [list(t) for t in job.layouts],
        "arm_b_predicted": job.arm_b_predicted,
        "layout_log": job.layout_log,
        "n_arm_a": len(job.arm_a),
        "gate_lengths": [[g, q, v] for (g, q), v in sorted(job.gates.lengths.items())],
        "cz_errors": sorted([*sorted(pair), v] for pair, v in job.gates.cz_error.items()),
    }


def job_from_state(state: Mapping[str, Any], circuits: Sequence[QuantumCircuit]) -> Job:
    n_arm_a = int(state["n_arm_a"])
    return Job(
        t_s=datetime.fromisoformat(state["t_s"]),
        n_qubits=int(state["n_qubits"]),
        dt=float(state["dt"]),
        discriminating=[int(q) for q in state["discriminating"]],
        controls=[int(q) for q in state["controls"]],
        sources={
            name: {int(q): QubitSource(*values) for q, values in per_qubit.items()}
            for name, per_qubit in state["sources"].items()
        },
        slots={int(q): list(slots) for q, slots in state["slots"].items()},
        arm_a=list(circuits[:n_arm_a]),
        layouts=[(int(a), int(b), int(c)) for a, b, c in state["layouts"]],
        arm_b=list(circuits[n_arm_a:]),
        arm_b_predicted={k: list(v) for k, v in state["arm_b_predicted"].items()},
        layout_log=dict(state["layout_log"]),
        gates=GateTable(
            {(str(g), int(q)): float(v) for g, q, v in state["gate_lengths"]},
            {frozenset((int(a), int(b))): float(v) for a, b, v in state["cz_errors"]},
        ),
    )


def write_circuits(path: Path, circuits: Sequence[QuantumCircuit]) -> None:
    with path.open("wb") as handle:
        qpy.dump(list(circuits), handle)


def read_circuits(path: Path) -> list[QuantumCircuit]:
    with path.open("rb") as handle:
        return list(qpy.load(handle))


def _read_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} does not hold one JSON object")
    return loaded


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------------------------
# Devices: the real one and the rehearsal's, behind one interface


@dataclass(frozen=True)
class Fetched:
    counts: list[dict[str, int]]
    metrics: dict[str, Any]
    inputs: dict[str, Any]


class Device(Protocol):
    name: str

    @property
    def target(self) -> Target: ...

    def rep_delay_range(self) -> Sequence[float]: ...

    def capture(self) -> dict[str, Any]: ...

    def submit(
        self,
        circuits: Sequence[QuantumCircuit],
        shots: Sequence[int],
        options: Mapping[str, Any],
    ) -> str: ...

    def status(self, job_id: str) -> str: ...

    def cancel(self, job_id: str) -> None: ...

    def fetch(self, job_id: str, circuits: Sequence[QuantumCircuit]) -> Fetched: ...

    def properties_at(self, at: datetime) -> dict[str, Any] | None: ...


def _plain(value: Any) -> Any:
    """JSON's own types only, through the same ``default=str`` the raw shape documents."""
    return json.loads(json.dumps(value, default=str))


def _counts_from_pubs(result: Any, circuits: Sequence[QuantumCircuit]) -> list[dict[str, int]]:
    """Each circuit's own registers: Arm A's is ``c``, a transpiled Arm B's ``meas``, and a ``T1``
    circuit has one per qubit, joined with its lowest classical bit on the right of the key."""
    out: list[dict[str, int]] = []
    for pub, circuit in zip(result, circuits, strict=True):
        names = [register.name for register in circuit.cregs]
        if not names:
            raise ValueError(f"{circuit.name} has no classical register")
        bits = getattr(pub.data, names[0]) if len(names) == 1 else pub.join_data(names)
        out.append({k: int(v) for k, v in bits.get_counts().items()})
    return out


class IbmDevice:
    """The QPU. Holds the token only inside the service object it is given."""

    def __init__(self, service: Any, name: str, sampler: Callable[..., Any] = SamplerV2) -> None:
        self._service = service
        self._sampler = sampler
        self._backend = service.backend(name)
        self.name = name

    @property
    def backend(self) -> Any:
        return self._backend

    @property
    def target(self) -> Target:
        target: Target = self._backend.target
        return target

    def rep_delay_range(self) -> Sequence[float]:
        allowed: Sequence[float] = self._backend.configuration().rep_delay_range
        return allowed

    def capture(self) -> dict[str, Any]:
        properties = self._backend.properties(refresh=True)
        if properties is None:
            raise RefusedError("the device returned no properties")
        document = {
            "backend": self.name,
            "timestamp": properties.last_update_date,
            "properties": properties.to_dict(),
            "configuration": serialize_configuration(self._backend.configuration()),
        }
        plain: dict[str, Any] = _plain(document)
        return plain

    def submit(
        self,
        circuits: Sequence[QuantumCircuit],
        shots: Sequence[int],
        options: Mapping[str, Any],
    ) -> str:
        sampler = self._sampler(mode=self._backend, options=dict(options))
        job = sampler.run([(c, None, s) for c, s in zip(circuits, shots, strict=True)])
        return str(job.job_id())

    def status(self, job_id: str) -> str:
        return str(self._service.job(job_id).status())

    def cancel(self, job_id: str) -> None:
        self._service.job(job_id).cancel()

    def fetch(self, job_id: str, circuits: Sequence[QuantumCircuit]) -> Fetched:
        job = self._service.job(job_id)
        return Fetched(
            counts=_counts_from_pubs(job.result(), circuits),
            metrics=_plain(job.metrics()),
            inputs=_plain(
                {"options": job.inputs.get("options"), "version": job.inputs.get("version")}
            ),
        )

    def properties_at(self, at: datetime) -> dict[str, Any] | None:
        properties = self._backend.properties(datetime=at)
        if properties is None:
            return None
        plain: dict[str, Any] = _plain(properties.to_dict())
        return plain


class LocalDevice:
    """The rehearsal: ``doc`` plays the live calibration and a simulator built from it the device.

    Each circuit is its own local job, the rule the dry run follows. In one noisy Aer run a density-
    matrix circuit after a statevector circuit comes out wrong (Aer 0.17.2), so a batched rehearsal
    could pass with Arm B silently corrupted. Local mode also ignores the Sampler options, so a
    rehearsal shows nothing about them; a test pins what is sent and job 1 reads it back.
    """

    def __init__(
        self,
        doc: Mapping[str, Any],
        *,
        execute_at: datetime,
        store: Path,
        seed: int = SEED,
        name: str = BACKEND,
    ) -> None:
        self._doc = dict(doc)
        self._execute_at = execute_at
        self._store = store
        self._seed = seed
        self.name = name
        self._archived = archived_backend(doc, f"local_{name}")

    @property
    def backend(self) -> Any:
        return self._archived

    @property
    def target(self) -> Target:
        target: Target = self._archived.target
        return target

    def rep_delay_range(self) -> Sequence[float]:
        return tuple(self._doc["configuration"].get("rep_delay_range", (0.0, REP_DELAY_S)))

    def capture(self) -> dict[str, Any]:
        plain: dict[str, Any] = _plain(self._doc)
        return plain

    def submit(
        self,
        circuits: Sequence[QuantumCircuit],
        shots: Sequence[int],
        options: Mapping[str, Any],
    ) -> str:
        del options  # local mode ignores them; see the class docstring
        simulator = AerSimulator.from_backend(self._archived)
        seeds, more = circuit_seeds(self._seed, len(circuits), 0)
        assert not more
        counts: list[dict[str, int]] = []
        for circuit, n_shots, seed in zip(circuits, shots, seeds, strict=True):
            sampler = SamplerV2(mode=simulator, options={"simulator": {"seed_simulator": seed}})
            result = sampler.run([(circuit, None, n_shots)]).result()
            counts.extend(_counts_from_pubs(result, [circuit]))
        job_id = f"local-{uuid.uuid4()}"
        self._store.mkdir(parents=True, exist_ok=True)
        write_json_lf(
            self._store / f"{job_id}.json",
            {"counts": counts, "running": self._execute_at.isoformat()},
        )
        return job_id

    def status(self, job_id: str) -> str:
        return "DONE" if (self._store / f"{job_id}.json").exists() else "QUEUED"

    def cancel(self, job_id: str) -> None:
        (self._store / f"{job_id}.json").unlink(missing_ok=True)

    def fetch(self, job_id: str, circuits: Sequence[QuantumCircuit]) -> Fetched:
        del circuits
        stored = _read_json(self._store / f"{job_id}.json")
        running = stored["running"]
        return Fetched(
            counts=stored["counts"],
            metrics={
                "timestamps": {"running": running, "finished": running},
                "usage": {"quantum_seconds": 0},
            },
            inputs={"options": None, "version": None},
        )

    def properties_at(self, at: datetime) -> dict[str, Any] | None:
        del at
        return None


def ibm_device(
    env_file: Path,
    *,
    name: str = BACKEND,
    service_factory: Callable[..., Any] = QiskitRuntimeService,
    sampler: Callable[..., Any] = SamplerV2,
) -> IbmDevice:
    """Connect with the token in ``env_file``. The token goes to the service and nowhere else."""
    values = dotenv_values(env_file)
    token = values.get("IBM_QUANTUM_TOKEN")
    if not token:
        raise RefusedError(f"{env_file} has no IBM_QUANTUM_TOKEN")
    kwargs: dict[str, str] = {
        "token": token,
        "channel": values.get("IBM_QUANTUM_CHANNEL") or DEFAULT_CHANNEL,
    }
    instance = values.get("IBM_QUANTUM_INSTANCE")
    if instance:
        kwargs["instance"] = instance
    return IbmDevice(service_factory(**kwargs), name, sampler)


# ---------------------------------------------------------------------------------------------
# build


def _record_missed(job_dir: Path, at: datetime, closes: datetime) -> NoReturn:
    job_dir.mkdir(parents=True, exist_ok=True)
    write_json_lf(
        job_dir / "missed.json",
        {"reason": "not submitted by the window's close", "at": at.isoformat()},
    )
    raise RefusedError(f"the window closed at {closes:%H:%M} UTC: this day stays empty")


def run_build(
    *,
    jobs_dir: Path,
    controls_path: Path,
    job_number: int,
    device: Device,
    archive: Archive,
    now: Callable[[], datetime],
    ref_sha: str,
    code_commit: str,
    enforce_window: bool,
) -> Path:
    """Capture, seal, validate, write, submit; returns the job's folder.

    Refuses a second job for one UTC day, and with ``enforce_window`` anything outside the day's
    window, recording ``missed.json`` once the window has closed. The job id reaches the disk before
    anything else happens after submission.
    """
    arms = arms_for(job_number)
    t_s = now()
    job_dir = jobs_dir / f"{t_s:%Y-%m-%d}"
    if (job_dir / "job_id.txt").exists():
        raise RefusedError(f"a job was already submitted for {t_s:%Y-%m-%d}")
    opens, closes = window_for(t_s)
    if enforce_window:
        if t_s >= closes:
            _record_missed(job_dir, t_s, closes)
        if t_s < opens:
            raise RefusedError(f"the window opens at {opens:%H:%M} UTC")
    try:
        controls_doc, controls_sha = load_controls(controls_path, backend=device.name)
    except ControlsFileError as exc:
        raise RefusedError(str(exc)) from exc
    controls = [int(c["qubit"]) for c in controls_doc["controls"]]
    check_rep_delay(REP_DELAY_S, device.rep_delay_range())

    job_dir.mkdir(parents=True, exist_ok=True)
    live = device.capture()
    live_path = job_dir / "live-properties.json"
    write_json_lf(live_path, live)
    collected = collect(archive(), backend=device.name, until=t_s)
    rows = predictor_rows(collected, at=t_s, live=live)
    # Amendment 20: a qubit that is not operational at t_s gives no rows today. The frozen ranking
    # runs over the rest, and the whole frozen set stays out of the discriminating stratum.
    dead = not_operational_qubits(live["properties"], device.target)
    selection = select_balanced(
        [r for r in rows if r.qubit not in dead], k=N_DISCRIMINATING, controls=set(controls)
    )
    running_controls = [q for q in controls if q not in dead]
    selection["controls"] = running_controls
    selection["controls_left_out"] = [q for q in controls if q in dead]
    selection["not_operational"] = dead
    try:
        job = build_job(
            rows=rows,
            execution=None,
            selection=selection,
            controls=running_controls,
            snapshot=live,
            t_s=t_s,
            target=device.target,
        )
    except ValueError as exc:
        raise RefusedError(str(exc)) from exc
    circuits, shots = pubs_for(job, arms)
    validate_isa_circuits(circuits, device.target)

    options = pinned_options(f"issue-125-job-{job_number:02d}")
    write_outputs(
        job_dir,
        rows=rows,
        selection=selection,
        manifest={
            "ref_sha": ref_sha,
            "at": t_s.isoformat(),
            "files_used": len(collected.files),
            "states_used": len(collected.states),
            "skipped": dict(collected.skipped),
        },
    )
    write_json_lf(job_dir / "sealed.json", job_to_state(job))
    write_circuits(job_dir / "circuits.qpy", job.arm_a + job.arm_b)
    submission: dict[str, Any] = {
        "job_number": job_number,
        "arms": arms,
        "backend": device.name,
        "t_s": t_s.isoformat(),
        "ref_sha": ref_sha,
        "code_commit": code_commit,
        "live_properties_sha256": _sha256(live_path),
        "sealed_sha256": _sha256(job_dir / "sealed.json"),
        "circuits_sha256": _sha256(job_dir / "circuits.qpy"),
        "controls_file_sha256": controls_sha,
        "options": options,
        "rep_delay_range": [float(v) for v in device.rep_delay_range()],
        "shots": shots,
        "versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "qiskit": qiskit.__version__,
            "qiskit_aer": qiskit_aer.__version__,
            "qiskit_ibm_runtime": qiskit_ibm_runtime.__version__,
        },
    }
    write_json_lf(job_dir / "submission.json", submission)

    # A build that began in time can still finish late, and the rule is on submission.
    if enforce_window and (at_submit := now()) >= closes:
        _record_missed(job_dir, at_submit, closes)
    job_id = device.submit(circuits, shots, options)
    (job_dir / "job_id.txt").write_text(job_id + "\n", encoding="utf-8", newline="\n")
    submission["t_submit"] = now().isoformat()
    write_json_lf(job_dir / "submission.json", submission)
    return job_dir


# ---------------------------------------------------------------------------------------------
# score


def _as_utc(value: Any) -> datetime:
    stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)


def daily_summary(
    a_rows: Sequence[Mapping[str, Any]], b_score: Mapping[str, Any] | None
) -> dict[str, Any]:
    """What one job showed. Descriptive only: the decision rule is applied once, after job 14."""
    arm_a: dict[str, Any] = {}
    for stratum in ("discriminating", "control"):
        rows = [r for r in a_rows if r["stratum"] == stratum]
        entry: dict[str, Any] = {"rows": len(rows)}
        for name in ("reading", "level", "reading_at_execution"):
            errors = [float(r[f"abs_err_{name}"]) for r in rows]
            finite = [e for e in errors if math.isfinite(e)]
            entry[f"mae_{name}"] = float(np.mean(finite)) if finite else None
        covered = [int(r["band_covered"]) for r in rows if int(r["band_covered"]) >= 0]
        entry["band_coverage"] = float(np.mean(covered)) if covered else None
        arm_a[stratum] = entry
    out: dict[str, Any] = {"arm_a": arm_a}
    if b_score is not None:
        out["arm_b"] = {
            name: {
                "spearman": b_score[name]["spearman"],
                "best_pick_hit": b_score[name]["best_pick_hit"],
                "mean_abs_error": b_score[name]["mean_abs_error"],
            }
            for name in SOURCES
        }
    return out


def run_score(
    *,
    job_dir: Path,
    device: Device,
    archive: Archive,
    now: Callable[[], datetime],
) -> int:
    """Fetch, add the control, score. 0 when scored or recorded empty, ``EXIT_NOT_YET`` otherwise.

    A failed job, or one still queued at the next day's submission (then cancelled), is an empty
    day: ``failed.json`` records it and nothing is re-run.
    """
    if not (job_dir / "job_id.txt").exists():
        raise RefusedError(f"{job_dir} holds no submitted job")
    job_id = (job_dir / "job_id.txt").read_text(encoding="utf-8").strip()
    submission = _read_json(job_dir / "submission.json")
    for name, key in (
        ("sealed.json", "sealed_sha256"),
        ("circuits.qpy", "circuits_sha256"),
    ):
        if _sha256(job_dir / name) != submission[key]:
            raise RefusedError(f"{name} no longer matches the hash written at submission")
    t_s = _as_utc(submission["t_s"])

    status = device.status(job_id)
    if status in WAITING:
        if now() < next_submission(t_s):
            print(f"job {job_id} is {status}; not scored yet")
            return EXIT_NOT_YET
        device.cancel(job_id)
        write_json_lf(
            job_dir / "failed.json",
            {"reason": "still queued at the next submission; cancelled", "status": status},
        )
        return 0
    if status == "RUNNING":
        print(f"job {job_id} is running; not scored yet")
        return EXIT_NOT_YET
    if status != "DONE":
        write_json_lf(
            job_dir / "failed.json", {"reason": "the job did not finish", "status": status}
        )
        return 0

    circuits = read_circuits(job_dir / "circuits.qpy")
    state = _read_json(job_dir / "sealed.json")
    job = job_from_state(state, circuits)
    arms = str(submission["arms"])
    submitted, shots = pubs_for(job, arms)
    fetched = device.fetch(job_id, submitted)
    for circuit, circuit_counts, expected in zip(submitted, fetched.counts, shots, strict=True):
        if sum(circuit_counts.values()) != expected:
            raise ValueError(
                f"{circuit.name}: {sum(circuit_counts.values())} shots, not {expected}"
            )
    t_execute = _as_utc(fetched.metrics["timestamps"]["running"])

    collected = collect(archive(), backend=device.name, until=now())
    if not any(f.time > t_execute for f in collected.files):
        print(f"the archive has no file after t_execute {t_execute.isoformat()}; not scored yet")
        return EXIT_NOT_YET
    job = with_execution(job, execution_rows(collected, at=t_execute, live=None))

    write_json_lf(job_dir / "results.json", {"job_id": job_id, "counts": fetched.counts})
    write_json_lf(job_dir / "metrics.json", fetched.metrics)
    write_json_lf(job_dir / "inputs-read-back.json", fetched.inputs)
    try:
        historical = device.properties_at(t_execute)
    except Exception as exc:  # an unscored cross-check must not cost the day's scores
        historical = {"error": f"{type(exc).__name__}: {exc}"}
    if historical is not None:
        write_json_lf(job_dir / "properties-at-execution.json", historical)

    n_a = len(job.arm_a)
    a_rows = score_arm_a(job, fetched.counts[:n_a], shots=ARM_A_SHOTS)
    _write_tsv(job_dir / "arm-a.tsv", a_rows)
    b_score = None
    if "B" in arms:
        b_score = score_arm_b(job, fetched.counts[n_a:], shots=ARM_B_SHOTS)
        write_json_lf(job_dir / "arm-b.json", b_score)
    summary = {
        "job_id": job_id,
        "job_number": submission["job_number"],
        "t_s": t_s.isoformat(),
        "t_execute": t_execute.isoformat(),
        "queue_seconds": (
            t_execute - _as_utc(submission.get("t_submit", submission["t_s"]))
        ).total_seconds(),
        "quantum_seconds": fetched.metrics.get("usage", {}).get("quantum_seconds"),
        **daily_summary(a_rows, b_score),
    }
    write_json_lf(job_dir / "daily-summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


# ---------------------------------------------------------------------------------------------
# report: the decision rule over every day so far


def _day_status(job_dir: Path) -> str:
    if (job_dir / "arm-a.tsv").exists():
        return "scored"
    if (job_dir / "failed.json").exists():
        return "failed"
    if (job_dir / "missed.json").exists():
        return "missed"
    if (job_dir / "job_id.txt").exists():
        return "submitted, not scored"
    return "empty"


def _read_rows(path: Path, day: date) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [{**row, "date": day} for row in csv.DictReader(handle, delimiter="\t")]


def _errors(rows: Sequence[Mapping[str, Any]], name: str) -> list[float]:
    return [float(r[f"abs_err_{name}"]) for r in rows]


def _mean(values: Iterable[float]) -> float | None:
    finite = [v for v in values if math.isfinite(v)]
    return float(np.mean(finite)) if finite else None


def _gaps(rows: Sequence[Mapping[str, Any]], other: str) -> list[tuple[float, date]]:
    """Per-row error of ``other`` minus that of ``level``, on the rows where both predicted.

    Positive means ``level`` is closer. Pairing keeps each comparison on one set of rows when a
    predictor has no value for some of them.
    """
    return [
        (float(r[f"abs_err_{other}"]) - float(r["abs_err_level"]), r["date"])
        for r in rows
        if math.isfinite(float(r[f"abs_err_{other}"])) and math.isfinite(float(r["abs_err_level"]))
    ]


def _beats(
    rows: Sequence[Mapping[str, Any]],
    other: str,
    *,
    span: tuple[date, date],
    seed: int,
) -> dict[str, Any]:
    """``level`` against ``other`` on one set of rows.

    Passes when the block bootstrap's 90% interval of the mean difference lies above zero.
    """
    pairs = _gaps(rows, other)
    if not pairs:
        return {"rows": 0, "mean_difference": None, "interval": None, "passes": False}
    diffs, dates = zip(*pairs, strict=True)
    if (span[1] - span[0]).days + 1 <= BLOCK_DAYS:
        # Early in the run a block can hold the whole calendar, so every draw is the same draw and
        # the interval has no width. That says nothing about uncertainty, so it cannot pass.
        return {
            "rows": len(pairs),
            "mean_difference": float(np.mean(diffs)),
            "interval": None,
            "passes": False,
        }
    low, high = calendar_block_bootstrap(
        list(diffs), list(dates), block_days=BLOCK_DAYS, seed=seed, span=span
    )
    return {
        "rows": len(pairs),
        "mean_difference": float(np.mean(diffs)),
        "interval": [low, high],
        "passes": low > 0.0,
    }


def _arm_b_report(jobs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Arm B over its jobs. The band is ranked by the midpoint of its two ends (amendment 4).

    The rule's "``level`` or ``band``" has two readings, and the pre-registration's null values give
    both, so both are reported until the freeze settles one.
    """
    rho: dict[str, list[float]] = {"reading": [], "level": [], "band": []}
    hits: dict[str, int] = {"reading": 0, "level": 0, "band": 0}
    for job in jobs:
        measured = [float(m) for m in job["measured"]]
        best = int(np.argmax(measured))
        lows, highs = job["band_lo"]["predicted"], job["band_hi"]["predicted"]
        predicted = {
            "reading": job["reading"]["predicted"],
            "level": job["level"]["predicted"],
            "band": [
                None if a is None or b is None else (float(a) + float(b)) / 2.0
                for a, b in zip(lows, highs, strict=True)
            ],
        }
        for name, values in predicted.items():
            usable = [i for i, v in enumerate(values) if v is not None]
            if not usable:
                continue
            value = spearman([float(values[i]) for i in usable], [measured[i] for i in usable])
            if math.isfinite(value):
                rho[name].append(value)
            hits[name] += int(max(usable, key=lambda i: float(values[i])) == best)
    mean_rho = {name: _mean(values) for name, values in rho.items()}

    def ranks(name: str) -> bool:
        ours, theirs = mean_rho[name], mean_rho["reading"]
        return ours is not None and theirs is not None and ours >= theirs

    def picks(name: str) -> bool:
        return hits[name] >= hits["reading"]

    return {
        "jobs": len(jobs),
        "mean_spearman": mean_rho,
        "best_pick_hits": hits,
        "one_predictor_meets_both": any(ranks(n) and picks(n) for n in ("level", "band")),
        "each_condition_by_either": any(ranks(n) for n in ("level", "band"))
        and any(picks(n) for n in ("level", "band")),
    }


# ---------------------------------------------------------------------------------------------
# The decision rule of PR #135's section 3.12 (amendments 24 to 30)

# One-sided 95% points of Student t with 2 and 3 degrees of freedom, as the pre-registration writes
# them (amendment 25). A test checks them against SciPy; SciPy is not imported at runtime.
T95: dict[int, float] = {2: 2.9199855803537242, 3: 2.3533634348018233}
Z90 = 1.2815515655446004
ARM_A_BATCHES: tuple[tuple[int, ...], ...] = tuple(
    tuple(int(i) for i in batch) for batch in np.array_split(np.arange(N_JOBS), 4)
)
N_ARM_B_JOBS = N_JOBS - 1
ARM_B_BATCHES: tuple[tuple[int, ...], ...] = tuple(
    tuple(int(i) for i in batch) for batch in np.array_split(np.arange(N_ARM_B_JOBS), 4)
)
MIN_BATCHES = 3
MIN_ARM_A_DAYS = 10
MIN_ARM_B_JOBS = 10
FIT_GRID = np.linspace(-3.0, 3.0, 1201)


def level_minus_other(rows: Sequence[Mapping[str, Any]], other: str) -> list[tuple[float, date]]:
    """Amendment 25's ``D``: ``level``'s absolute error minus ``other``'s, negative favouring it.

    Only rows where both predicted, so each comparison stays on one set of rows.
    """
    out = []
    for r in rows:
        ours, theirs = float(r["abs_err_level"]), float(r[f"abs_err_{other}"])
        if math.isfinite(ours) and math.isfinite(theirs):
            out.append((ours - theirs, r["date"]))
    return out


def batch_means_test(
    values: Sequence[tuple[float, int]], batches: Sequence[Sequence[int]], *, side: int
) -> dict[str, Any]:
    """Batch means over fixed batches (amendment 25), rows given as ``(value, item index)``.

    A batch's value is the mean of its rows (row-pooled). Empty batches are dropped while at least
    three remain, and ``t`` then has ``q - 1`` degrees of freedom; with fewer the result is
    inconclusive; ``sd = 0`` fails. A pass needs ``t < -t95`` when ``side`` is -1 (Arm A) and
    ``t > t95`` when it is +1 (Arm B).
    """
    where = {item: b for b, items in enumerate(batches) for item in items}
    sums = [0.0] * len(batches)
    counts = [0] * len(batches)
    for value, item in values:
        if item not in where:
            raise ValueError(f"item {item} is in no batch")
        sums[where[item]] += value
        counts[where[item]] += 1
    means = [s / c if c else None for s, c in zip(sums, counts, strict=True)]
    present = [m for m in means if m is not None]
    q = len(present)
    out: dict[str, Any] = {
        "batch_means": means,
        "batch_rows": counts,
        "q": q,
        "mean_of_batches": None,
        "t": None,
        "critical": None,
        "sd_zero": False,
        "inconclusive": q < MIN_BATCHES,
        "passes": False,
    }
    if q < MIN_BATCHES:
        return out
    mean = sum(present) / q
    sd = math.sqrt(sum((m - mean) ** 2 for m in present) / (q - 1))
    out["mean_of_batches"] = mean
    if sd == 0.0:
        out["sd_zero"] = True
        return out
    t = mean / (sd / math.sqrt(q))
    critical = T95[q - 1]
    out.update({"t": t, "critical": critical, "passes": side * t > critical})
    return out


def fit_log_t1_ratio(points: Sequence[tuple[float, int, int]], level: QubitSource) -> float | None:
    """Amendment 30: grid maximum likelihood of ``log(T1 / level)`` from ``(tau_s, ones, shots)``.

    Uses ``level``'s readout, as Bengisu's ``arm_a_fit.py`` does; ``None`` without points or a
    usable ``level``.
    """
    if not points or not level.usable_for_decay():
        return None
    taus = np.array([p[0] for p in points], dtype=np.float64)
    ones = np.array([p[1] for p in points], dtype=np.float64)
    shots = np.array([p[2] for p in points], dtype=np.float64)
    t1 = level.t1 * np.exp(FIT_GRID)
    survive = np.exp(-taus[None, :] / t1[:, None])
    p = np.clip((1.0 - level.e10) * survive + level.e01 * (1.0 - survive), 1e-9, 1.0 - 1e-9)
    log_lik = (ones * np.log(p) + (shots - ones) * np.log1p(-p)).sum(axis=1)
    return float(FIT_GRID[int(np.argmax(log_lik))])


def slope_and_spread(points: Sequence[tuple[float, float]]) -> dict[str, Any]:
    """Amendment 30's ``c`` (slope through the origin) and ``s_res`` (robust residual spread)."""
    if not points:
        return {"c": None, "s_res": None, "qubit_days": 0}
    x = np.array([p[0] for p in points], dtype=np.float64)
    y = np.array([p[1] for p in points], dtype=np.float64)
    sxx = float((x * x).sum())
    if sxx == 0.0:
        return {"c": None, "s_res": None, "qubit_days": len(points)}
    c = float((x * y).sum() / sxx)
    q10, q90 = np.percentile(y - c * x, [10, 90])
    return {"c": c, "s_res": float((q90 - q10) / (2.0 * Z90)), "qubit_days": len(points)}


def _source(state: Mapping[str, Any], name: str, qubit: int) -> QubitSource | None:
    values = state.get("sources", {}).get(name, {}).get(str(qubit))
    return None if values is None else QubitSource(*(float(v) for v in values))


def no_information_coverage(
    rows: Sequence[Mapping[str, Any]], state: Mapping[str, Any]
) -> tuple[list[float], list[float]]:
    """Amendment 24's no-information coverage for one day's ``tau > 0`` discriminating rows.

    Each row's band is moved in ``log T1`` by the difference between another discriminating qubit's
    ``log level`` and its own, turned into ``p_1`` at the row's ``tau`` with the row's own
    ``level`` readout, and checked against ``p_hat``; a row's value is the share of the other
    qubits for which the moved band covers it. Returns per-row shares, nominal and widened.
    """
    levels: dict[int, QubitSource] = {}
    for q in sorted({int(r["qubit"]) for r in rows}):
        source = _source(state, "level", q)
        if source is not None and source.usable_for_decay():
            levels[q] = source
    nominal: list[float] = []
    widened: list[float] = []
    for r in rows:
        q = int(r["qubit"])
        own, lo, hi = levels.get(q), _source(state, "band_lo", q), _source(state, "band_hi", q)
        if own is None or lo is None or hi is None:
            continue
        others = [o for o in levels if o != q]
        if not others:
            continue
        p_hat, tau = float(r["p_hat"]), float(r["tau_s"])
        widen = binomial_se(p_hat, int(r["shots"]))
        hits = [0, 0]
        counted = 0
        for o in others:
            ratio = levels[o].t1 / own.t1
            try:
                ends = sorted(
                    p1_closed_form(tau, QubitSource(band.t1 * ratio, band.t2, own.e10, own.e01))
                    for band in (lo, hi)
                )
            except UnusableSourceError:
                continue
            counted += 1
            hits[0] += int(ends[0] <= p_hat <= ends[1])
            hits[1] += int(ends[0] - widen <= p_hat <= ends[1] + widen)
        if counted:
            nominal.append(hits[0] / counted)
            widened.append(hits[1] / counted)
    return nominal, widened


def s1_reading(
    *, inconclusive: bool, a1: Mapping[str, Any], a2: Mapping[str, Any], a3: bool
) -> tuple[str, str]:
    """Amendment 29's first table, read top to bottom: ``(row, reading)`` of the first that applies.

    ``a1`` and ``a2`` carry ``passes`` and ``mean_d``, the row mean of ``D`` (negative favours
    ``level``).
    """
    if inconclusive:
        return "too few completed days", "inconclusive: nothing is read"
    if a1["passes"] and a2["passes"] and a3:
        return (
            "A1, A2 and A3 pass",
            "S1 passes: level beats both readings, and most of the deviation is gone by execution",
        )
    if a1["passes"] and a2["passes"]:
        return (
            "A1 and A2 pass, A3 fails",
            "S1 not supported: the controls disagree in sign; the result is specific to the "
            "selected qubits",
        )
    if a2["mean_d"] is not None and a2["mean_d"] >= 0.0:
        return (
            "A2's mean D at or above zero",
            "S1 fails: reading_at_execution is at least as good as level",
        )
    if a1["passes"]:
        return (
            "A1 passes, A2 does not",
            "staleness: level beats the submission-time reading but not the execution-time one",
        )
    means = (a1["mean_d"], a2["mean_d"])
    if all(m is not None and m < 0.0 for m in means):
        return (
            "A1 and A2 both fail, both mean D below zero",
            "no claim: the data do not separate the predictors",
        )
    return "anything else", "reported as observed, with no S1 reading"


def arm_b_reading(*, s1_passes: bool, inconclusive: bool, passes: bool) -> tuple[str, str]:
    """Amendment 29's second table. An inconclusive Arm B adds nothing, whatever S1 says."""
    if inconclusive:
        return "Arm B inconclusive", "nothing is added"
    if s1_passes and passes:
        return "S1 and Arm B pass", "S1 passes for the engineer's purpose too"
    if s1_passes:
        return (
            "S1 passes, Arm B does not",
            "S1 holds for decay prediction, not for ranking layouts",
        )
    if passes:
        return "Arm B passes, S1 does not", "no claim from Arm B alone"
    return "neither passes", "nothing is added"


def run_report(jobs_dir: Path, *, first_day: date, today: date) -> dict[str, Any]:
    """The decision rule (design section 7) over every day so far.

    Every calendar day from ``first_day`` on is on the axis, and a day with no rows stays there as
    an empty day. ``first_day`` is declared, not read from the folders, so a first day the laptop
    slept through cannot move the calendar. A job folder outside the run's 14 days is refused: the
    run is never extended, and a stray folder must not be dropped or scored in silence. Until the
    14 days have passed the result is marked interim: it is not the decision, and it must not stop
    or extend the run.
    """
    if not jobs_dir.is_dir():
        raise RefusedError(f"{jobs_dir} is not a folder")
    if today < first_day:
        raise RefusedError(f"the run starts on {first_day}, after {today}")
    final = first_day + timedelta(days=N_JOBS - 1)
    complete = today > final
    last = min(today, final)
    named = {
        date.fromisoformat(p.name): p
        for p in jobs_dir.iterdir()
        if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)
    }
    outside = sorted(d.isoformat() for d in named if not first_day <= d <= last)
    if outside:
        raise RefusedError(f"job folders outside {first_day} to {last}: {outside}")
    calendar = [first_day + timedelta(days=i) for i in range((last - first_day).days + 1)]
    days = [
        {"date": d.isoformat(), "status": _day_status(named[d]) if d in named else "empty"}
        for d in calendar
    ]
    span = (first_day, last)

    rows: list[dict[str, Any]] = []
    arm_b_jobs: list[dict[str, Any]] = []
    for day, folder in sorted(named.items()):
        if (folder / "arm-a.tsv").exists():
            rows.extend(_read_rows(folder / "arm-a.tsv", day))
        if (folder / "arm-b.json").exists():
            arm_b_jobs.append(_read_json(folder / "arm-b.json"))
    discriminating = [r for r in rows if r["stratum"] == "discriminating"]
    control = [r for r in rows if r["stratum"] == "control"]

    state = np.random.SeedSequence(SEED).generate_state(2, dtype=np.uint32)
    a1 = _beats(discriminating, "reading", span=span, seed=int(state[0]))
    a2 = _beats(discriminating, "reading_at_execution", span=span, seed=int(state[1]))
    mae = {
        stratum: {
            name: _mean(_errors(subset, name))
            for name in ("reading", "level", "reading_at_execution")
        }
        for stratum, subset in (("discriminating", discriminating), ("control", control))
    }
    a3 = all(
        (gap := _mean(g for g, _ in _gaps(control, name))) is not None and gap > 0.0
        for name in ("reading", "reading_at_execution")
    )
    covered = [int(r["band_covered"]) for r in discriminating if int(r["band_covered"]) >= 0]
    widened = [
        int(r["band_covered_widened"])
        for r in discriminating
        if int(r["band_covered_widened"]) >= 0
    ]
    coverage = float(np.mean(covered)) if covered else None
    coverage_widened = float(np.mean(widened)) if widened else None
    a4 = coverage_widened is not None and coverage_widened >= BAND_NOMINAL

    execution_gap = a2["mean_difference"]
    if not discriminating:
        reading = "no scored rows"
    elif a1["passes"] and a2["passes"] and a3 and a4:
        reading = "S1 passes"
    elif execution_gap is not None and execution_gap <= 0.0:
        reading = "S1 fails: reading_at_execution is at least as good as level"
    elif a1["passes"] and not a2["passes"]:
        reading = "level beats reading but not reading_at_execution: a finding about staleness"
    else:
        reading = "none of the design's named outcomes"

    return {
        "complete": complete,
        "interim_note": None
        if complete
        else "interim: not the decision, and it must not stop or extend the run",
        "first_day": first_day.isoformat(),
        "last_day": last.isoformat(),
        "days": days,
        "block_days": BLOCK_DAYS,
        "arm_a": {
            "rows": {"discriminating": len(discriminating), "control": len(control)},
            "mean_abs_error": mae,
            "A1_level_beats_reading": a1,
            "A2_level_beats_reading_at_execution": a2,
            "A3_sign_holds_on_controls": a3,
            "A4_band_covers_nominal_within_widening": {
                "nominal": BAND_NOMINAL,
                "coverage": coverage,
                "coverage_widened": coverage_widened,
                "passes": a4,
            },
        },
        "arm_b": _arm_b_report(arm_b_jobs),
        "reading": reading,
    }


# ---------------------------------------------------------------------------------------------
# Command line


def _parse_at(value: str) -> datetime:
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise argparse.ArgumentTypeError("the time must carry a zone")
    return stamp.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _archive_for(repo: Path, sha: str) -> Archive:
    return lambda: iter_archive(repo, sha)


def _fetch_archive(repo: Path) -> None:
    _git(repo, "fetch", "origin", f"+refs/heads/calibration-data:{ARCHIVE_REF}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    modes = parser.add_subparsers(dest="mode", required=True)
    build = modes.add_parser("build", help="capture, seal and submit one job")
    build.add_argument("--jobs-dir", type=Path, required=True)
    build.add_argument("--controls", type=Path, required=True)
    build.add_argument("--job-number", type=int, required=True)
    build.add_argument("--frozen-at", default=None)
    build.add_argument("--prereg", type=Path, default=None)
    score = modes.add_parser("score", help="fetch one job's results and score them")
    score.add_argument("--job-dir", type=Path, required=True)
    report = modes.add_parser("report", help="the decision rule over every day so far")
    report.add_argument("--jobs-dir", type=Path, required=True)
    report.add_argument("--first-day", type=date.fromisoformat, required=True)
    report.add_argument("--today", type=date.fromisoformat, default=None, help="rehearsal only")
    for mode in (build, score):
        mode.add_argument("--repo", type=Path, default=Path("."))
        mode.add_argument(
            "--ref", default=ARCHIVE_REF, help="calibration-data ref; real runs fetch it"
        )
        mode.add_argument("--env-file", type=Path, default=Path(".env"))
        mode.add_argument(
            "--local-live", type=Path, default=None, help="rehearsal: the 'live' document"
        )
        mode.add_argument("--at", type=_parse_at, default=None, help="rehearsal: the current time")
        mode.add_argument("--local-execute-at", type=_parse_at, default=None)
    args = parser.parse_args(argv)
    if args.mode == "report":
        try:
            outcome = run_report(
                args.jobs_dir, first_day=args.first_day, today=args.today or _utc_now().date()
            )
        except RefusedError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return EXIT_REFUSED
        write_json_lf(args.jobs_dir / "report.json", outcome)
        print(json.dumps(outcome, indent=2))
        return 0
    local = args.local_live is not None
    if not local and args.at is not None:
        parser.error("--at is for rehearsals: a real run uses the clock")
    if local and (args.at is None or args.local_execute_at is None):
        parser.error("--local-live needs --at and --local-execute-at")
    at: datetime | None = args.at
    now: Callable[[], datetime] = (lambda: at) if at is not None else _utc_now

    try:
        if args.mode == "build" and not local:
            # Before any network and before the token is read.
            try:
                _, controls_sha = load_controls(args.controls, backend=BACKEND)
            except ControlsFileError as exc:
                raise RefusedError(str(exc)) from exc
            check_frozen(args.repo, args.frozen_at, args.prereg, controls_sha)
        if not local:
            _fetch_archive(args.repo)
        sha = resolve_archive_ref(args.repo, args.ref)
        device: Device
        if local:
            store = (args.jobs_dir if args.mode == "build" else args.job_dir.parent) / "local-jobs"
            device = LocalDevice(
                _read_json(args.local_live),
                execute_at=args.local_execute_at,
                store=store,
                seed=SEED + now().toordinal(),
            )
        else:
            device = ibm_device(args.env_file)
        if args.mode == "build":
            job_dir = run_build(
                jobs_dir=args.jobs_dir,
                controls_path=args.controls,
                job_number=args.job_number,
                device=device,
                archive=_archive_for(args.repo, sha),
                now=now,
                ref_sha=sha,
                code_commit=_git(args.repo, "rev-parse", "HEAD").strip(),
                enforce_window=not local,
            )
            print(f"submitted: {job_dir}")
            return 0
        return run_score(
            job_dir=args.job_dir, device=device, archive=_archive_for(args.repo, sha), now=now
        )
    except RefusedError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
