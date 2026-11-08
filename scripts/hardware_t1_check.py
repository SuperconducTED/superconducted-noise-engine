"""The ``T1`` check of design section 6, on the selected qubits of the run's first and last jobs.

    python scripts/hardware_t1_check.py submit --job-dir <folder> --frozen-at <sha> --prereg <path>
    python scripts/hardware_t1_check.py score --job-dir <folder>

**The question it answers.** IBM's consecutive ``T1`` readings of one qubit scatter widely. Is that
fit noise, or what the device does? A fit of our own gives a ``T1`` with its standard error, and if
that error is far smaller than the scatter the scatter is the device's. This check takes no part in
the decision rule: nothing here reaches ``report``, and a missing or failed check costs no day.

**Why a separate environment.** Qiskit Experiments is not in the project's pins, so this script runs
from an environment holding the pins plus ``qiskit-experiments==0.14.2``, with the version written
to the output. The library is imported only inside the functions that need it, so the project's own
checks can import this file without it.

**What the library does and does not do.** It builds the circuits and fits the results. The job
itself goes through the same device and the same pinned options as the main job, instead of the
library's own ``run()``. That keeps the job id on disk the moment it exists, so the fit can happen
the next morning in a new process, and it keeps the one rule the rehearsal needs: one circuit per
Aer run.
"""

from __future__ import annotations

import argparse
import importlib
import statistics
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from qiskit import QuantumCircuit
from qiskit_ibm_runtime.utils.validations import validate_isa_circuits

from scripts.hardware_reading_vs_level import SEED, write_json_lf
from scripts.hardware_submit import (
    EXIT_NOT_YET,
    EXIT_REFUSED,
    N_JOBS,
    REP_DELAY_S,
    WAITING,
    Device,
    LocalDevice,
    RefusedError,
    _read_json,
    _sha256,
    check_frozen,
    check_rep_delay,
    ibm_device,
    pinned_options,
    read_circuits,
    refuse_sealed_inside,
    write_circuits,
)

N_DELAYS = 8
T1_SHOTS = 1024
FIRST_DELAY_S = 1e-6
DELAY_SPAN_IN_T1 = 3.0
T1_JOBS = frozenset({1, N_JOBS})
ANALYSIS_TIMEOUT_S = 300.0


class T1Device(Device, Protocol):
    """A device that also hands over the backend object the library builds circuits from."""

    @property
    def backend(self) -> Any: ...


def t1_delays(expected_t1_s: float) -> list[float]:
    """Eight delays from 1 us to three times the qubit's expected ``T1``, evenly spaced.

    A qubit's own span keeps the decay on the grid whatever its ``T1``: selected qubits differ by
    more than a factor of 30. The expectation comes from ``level``, the steadiest of the predictors,
    and a fit's span only has to be right to within a factor of about two.
    """
    if not np.isfinite(expected_t1_s) or expected_t1_s * DELAY_SPAN_IN_T1 <= FIRST_DELAY_S:
        raise RefusedError(f"cannot space delays for an expected T1 of {expected_t1_s} s")
    return [
        float(d) for d in np.linspace(FIRST_DELAY_S, DELAY_SPAN_IN_T1 * expected_t1_s, N_DELAYS)
    ]


def _experiment(backend: Any, delays: Mapping[int, Sequence[float]]) -> Any:
    framework = importlib.import_module("qiskit_experiments.framework")
    library = importlib.import_module("qiskit_experiments.library")
    experiments = [
        library.T1((q,), delays=list(values), backend=backend) for q, values in delays.items()
    ]
    return framework.ParallelExperiment(experiments, backend=backend, flatten_results=True)


def _library_version() -> str:
    return str(importlib.import_module("qiskit_experiments").__version__)


def fit_t1(
    backend: Any,
    delays: Mapping[int, Sequence[float]],
    circuits: Sequence[QuantumCircuit],
    counts: Sequence[Mapping[str, int]],
) -> dict[int, dict[str, Any]]:
    """Each qubit's fitted ``T1``, standard error and fit quality, from the library's analysis."""
    framework = importlib.import_module("qiskit_experiments.framework")
    experiment = _experiment(backend, delays)
    data = framework.ExperimentData(experiment=experiment)
    data.add_data(
        [
            {
                "counts": dict(c),
                "metadata": circuit.metadata,
                "shots": sum(c.values()),
                "meas_level": 2,
            }
            for circuit, c in zip(circuits, counts, strict=True)
        ]
    )
    done = experiment.analysis.run(data).block_for_results(timeout=ANALYSIS_TIMEOUT_S)
    out: dict[int, dict[str, Any]] = {}
    for _, row in done.analysis_results("T1", dataframe=True).iterrows():
        qubit = int(str(row["components"][0]).removeprefix("Q"))
        value = row["value"]
        out[qubit] = {
            "t1_s": float(value.nominal_value),
            "stderr_s": float(value.std_dev),
            "relative_se": float(value.std_dev) / float(value.nominal_value),
            "reduced_chi_squared": float(row["chisq"]),
            "quality": str(row["quality"]),
        }
    if set(out) != set(delays):
        raise ValueError(f"the analysis fitted {sorted(out)}, not {sorted(delays)}")
    return out


def run_submit(*, job_dir: Path, device: T1Device, local: bool) -> None:
    """Build, seal and submit the check for a job folder whose main job has been submitted."""
    if not (job_dir / "job_id.txt").exists():
        raise RefusedError(f"{job_dir} holds no submitted main job")
    main_id = (job_dir / "job_id.txt").read_text(encoding="utf-8").strip()
    if not local and main_id.startswith("local-"):
        raise RefusedError("this job folder is a rehearsal's; a real check needs a real job")
    if (job_dir / "t1-job_id.txt").exists():
        raise RefusedError(f"the check was already submitted for {job_dir.name}")
    submission = _read_json(job_dir / "submission.json")
    number = int(submission["job_number"])
    if number not in T1_JOBS:
        raise RefusedError(f"job {number} has no check: only jobs {sorted(T1_JOBS)} do")
    check_rep_delay(REP_DELAY_S, device.rep_delay_range())

    state = _read_json(job_dir / "sealed.json")
    qubits = [int(q) for q in state["discriminating"]]
    level = state["sources"]["level"]
    delays = {q: t1_delays(float(level[str(q)][0])) for q in qubits}
    circuits = list(_experiment(device.backend, delays)._transpiled_circuits())
    validate_isa_circuits(circuits, device.target)

    write_circuits(job_dir / "t1-circuits.qpy", circuits)
    options = pinned_options(f"issue-125-t1-{number:02d}")
    sealed = {
        "job_number": number,
        "qubits": qubits,
        "delays_s": {str(q): values for q, values in delays.items()},
        "shots": T1_SHOTS,
        "options": options,
        "qiskit_experiments": _library_version(),
        "circuits_sha256": _sha256(job_dir / "t1-circuits.qpy"),
    }
    write_json_lf(job_dir / "t1-sealed.json", sealed)
    job_id = device.submit(circuits, [T1_SHOTS] * len(circuits), options)
    (job_dir / "t1-job_id.txt").write_text(job_id + "\n", encoding="utf-8", newline="\n")


def run_score(*, job_dir: Path, device: T1Device, sealed_dir: Path | None = None) -> int:
    """Fetch and fit. Raw counts reach the disk first, so a failed fit can be repeated.

    Sealing (amendment 27): the counts and the fit go to ``sealed_dir / <day>``; the jobs folder
    gets only ``t1-operations.json``: that the check ran and each fit's quality, no value.
    """
    if not (job_dir / "t1-job_id.txt").exists():
        raise RefusedError(f"{job_dir} holds no submitted check")
    job_id = (job_dir / "t1-job_id.txt").read_text(encoding="utf-8").strip()
    sealed = _read_json(job_dir / "t1-sealed.json")
    if _sha256(job_dir / "t1-circuits.qpy") != sealed["circuits_sha256"]:
        raise RefusedError("t1-circuits.qpy no longer matches the hash written at submission")

    status = device.status(job_id)
    if status in WAITING or status == "RUNNING":
        print(f"check {job_id} is {status}; not scored yet")
        return EXIT_NOT_YET
    if status != "DONE":
        write_json_lf(
            job_dir / "t1-failed.json", {"reason": "the check did not finish", "status": status}
        )
        return 0

    circuits = read_circuits(job_dir / "t1-circuits.qpy")
    fetched = device.fetch(job_id, circuits)
    expected = int(sealed["shots"])
    for circuit, counts in zip(circuits, fetched.counts, strict=True):
        if sum(counts.values()) != expected:
            raise ValueError(f"{circuit.name}: {sum(counts.values())} shots, not {expected}")
    out = job_dir if sealed_dir is None else sealed_dir / job_dir.name
    out.mkdir(parents=True, exist_ok=True)
    write_json_lf(out / "t1-results.json", {"job_id": job_id, "counts": fetched.counts})
    write_json_lf(job_dir / "t1-metrics.json", fetched.metrics)

    delays = {int(q): [float(d) for d in v] for q, v in sealed["delays_s"].items()}
    fits = fit_t1(device.backend, delays, circuits, fetched.counts)
    state = _read_json(job_dir / "sealed.json")
    per_qubit = [
        {
            "qubit": q,
            **fits[q],
            "reading_t1_s": float(state["sources"]["reading"][str(q)][0]),
            "level_t1_s": float(state["sources"]["level"][str(q)][0]),
            "delays_s": delays[q],
        }
        for q in sealed["qubits"]
    ]
    write_json_lf(
        out / "t1-check.json",
        {
            "job_id": job_id,
            "job_number": sealed["job_number"],
            "qiskit_experiments": _library_version(),
            "shots": expected,
            "rep_delay_s": REP_DELAY_S,
            "t_execute": fetched.metrics.get("timestamps", {}).get("running"),
            "quantum_seconds": fetched.metrics.get("usage", {}).get("quantum_seconds"),
            "median_relative_se": statistics.median(r["relative_se"] for r in per_qubit),
            "qubits": per_qubit,
        },
    )
    # The marker is written last: a write that fails before it leaves the day to be scored again.
    qualities: dict[str, int] = {}
    for fit in fits.values():
        qualities[str(fit["quality"])] = qualities.get(str(fit["quality"]), 0) + 1
    write_json_lf(
        job_dir / "t1-operations.json",
        {
            "status": "fitted",
            "job_id": job_id,
            "qubits": len(fits),
            "fit_quality": qualities,
            "quantum_seconds": fetched.metrics.get("usage", {}).get("quantum_seconds"),
        },
    )
    return 0


def _parse_at(value: str) -> datetime:
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise argparse.ArgumentTypeError("the time must carry a zone")
    return stamp.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    modes = parser.add_subparsers(dest="mode", required=True)
    submit = modes.add_parser("submit", help="seal and submit the check")
    submit.add_argument("--frozen-at", default=None)
    submit.add_argument("--prereg", type=Path, default=None)
    score = modes.add_parser("score", help="fetch the check's results and fit them")
    score.add_argument("--sealed-dir", type=Path, required=True)
    for mode in (submit, score):
        mode.add_argument("--job-dir", type=Path, required=True)
        mode.add_argument("--repo", type=Path, default=Path("."))
        mode.add_argument("--env-file", type=Path, default=Path(".env"))
        mode.add_argument("--local-live", type=Path, default=None, help="rehearsal")
        mode.add_argument("--local-execute-at", type=_parse_at, default=None, help="rehearsal")
    args = parser.parse_args(argv)
    local = args.local_live is not None
    if local and args.local_execute_at is None:
        parser.error("--local-live needs --local-execute-at")

    try:
        if args.mode == "score":
            # Before any network: a sealed folder inside either would be committed.
            refuse_sealed_inside(args.sealed_dir, args.job_dir.parent, args.repo)
        if args.mode == "submit" and not local:
            # Before any network and before the token is read.
            submission = _read_json(args.job_dir / "submission.json")
            check_frozen(
                args.repo, args.frozen_at, args.prereg, str(submission["controls_file_sha256"])
            )
        device: T1Device
        if local:
            device = LocalDevice(
                _read_json(args.local_live),
                execute_at=args.local_execute_at,
                store=args.job_dir.parent / "local-jobs",
                seed=SEED + 1,
            )
        else:
            device = ibm_device(args.env_file)
        if args.mode == "submit":
            run_submit(job_dir=args.job_dir, device=device, local=local)
            print(f"check submitted: {args.job_dir}")
            return 0
        return run_score(job_dir=args.job_dir, device=device, sealed_dir=args.sealed_dir)
    except RefusedError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
