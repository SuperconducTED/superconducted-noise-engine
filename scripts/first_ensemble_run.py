"""Smoke-run harness for AerSimulator against a synthetic fuzzy noise ensemble.

This script exercises the end-to-end fuzzy pipeline from a calibration
snapshot through feature extraction, TSK rule-base construction, and Aer
noise-model synthesis.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

from superconducted.benchmarks.circuits import qft_circuit
from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.defuzzification import WeightedAverageDefuzzifier
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.integration.aer_factory import (
    FuzzyNoiseModel,
    FuzzyNoiseModelEnsemble,
)
from superconducted.types import CalibrationSnapshot

SHOTS_PER_MEMBER: Final[int] = 1024
ENSEMBLE_SIZES: Final[tuple[int, ...]] = (1, 8, 16)


def run_ensemble(
    circuit: QuantumCircuit, members: list[FuzzyNoiseModel], shots: int
) -> dict[str, int]:
    """Run each ensemble member and mean-aggregate counts per ADR-016.

    With rng=default_rng(0) and ADR-015 deferred, members are currently
    identical and the mean equals a single member's behavior. This is
    the documented current state, not a smoke-harness deviation.

    Per-key independent rounding can leave sum(returned.values()) differing
    from `shots` by at most one count per bin in tie/fractional cases.
    The benchmark harness in superconducted.benchmarks.harness preserves
    the count total via SimulationResult.shots = shots * len(members);
    this dict-returning smoke wrapper accepts the small drift.
    """
    if not members:
        raise ValueError("Cannot run with an empty ensemble")

    sim = AerSimulator()

    per_member: list[dict[str, int]] = []
    for nm in members:
        prepared_circuit, actual_noise_model = nm.prepare(circuit.copy())
        transpiled_circuit = transpile(prepared_circuit, backend=sim)
        result = sim.run(transpiled_circuit, shots=shots, noise_model=actual_noise_model).result()
        per_member.append(dict(result.get_counts()))

    totals: dict[str, int] = {}
    for d in per_member:
        for k, v in d.items():
            totals[k] = totals.get(k, 0) + v
    n = len(per_member)
    return {k: round(v / n) for k, v in totals.items()}


def _default_mfs_for_feature(feature_name: str) -> list[GaussianMF]:
    # Use feature-specific numeric ranges instead of a single shared grid.
    # This avoids treating T1/T2 and readout_error as if they were on the
    # same [0, 0.01] scale.
    feature_scales: dict[str, tuple[float, float]] = {
        "mean_T1": (0.0, 100e-6),
        "mean_T2": (0.0, 100e-6),
        "mean_readout_error": (0.0, 0.1),
    }
    if feature_name not in feature_scales:
        raise ValueError(
            f"unknown feature {feature_name!r}; known features: {list(feature_scales)}"
        )
    lo, hi = feature_scales[feature_name]
    span = hi - lo
    overlap = span * 0.25
    return [GaussianMF(center=lo, sigma=overlap), GaussianMF(center=lo + span * 0.5, sigma=overlap)]


def generate_safe_ensemble(snapshot: CalibrationSnapshot, n: int) -> list[FuzzyNoiseModel]:
    """Construct a `FuzzyNoiseModelEnsemble` with conservative default MFs.

    Uses the `BasicCalibrationVectorizer` to infer the input dimension from
    the provided snapshot and builds a small grid of Gaussian MFs per input.
    """
    vectorizer = BasicCalibrationVectorizer()
    # Let `extract` raise if the snapshot is invalid; don't silently
    # fallback to a noisy one-dimensional default which masks problems.
    dummy_features = vectorizer.extract(snapshot)
    if dummy_features.shape[0] != vectorizer.output_dim:
        raise ValueError(
            "BasicCalibrationVectorizer returned unexpected feature dimension "
            f"{dummy_features.shape[0]}; expected {vectorizer.output_dim}"
        )

    mfs_list: list[list[GaussianMF]] = []
    for feature_name in vectorizer.feature_names:
        mfs_list.append(_default_mfs_for_feature(feature_name))

    ensemble_iter = FuzzyNoiseModelEnsemble(
        calibration=snapshot,
        feature_extractor=vectorizer,
        rule_base=TSKRuleBase.from_grid(
            per_input_mfs=mfs_list,
            output_dim=2,
            consequent_init="random",
            rng=np.random.default_rng(0),
        ),
        defuzzifier=WeightedAverageDefuzzifier(),
        squashing=ProbabilityClip(),
        channel_projector=KrausChannelProjector(NoOpNormalization()),
        fuzzification_strategy=PostGateFuzzification(),
        ensemble_size=n,
    )
    members = list(ensemble_iter)
    for member in members:
        crisp = member.crisp_params
        if crisp.size < 2 or not np.any(crisp[:2] > 0):
            raise ValueError(
                "Degenerate (identity) channel; bootstrap consequents are zero per ADR-014. "
                "Use consequent_init='random' or annotate timings as installation overhead."
            )
    return members


def _load_snapshot(path: Path) -> CalibrationSnapshot:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    return CalibrationSnapshot(
        backend=str(data["backend"]),
        timestamp=timestamp,
        schema_version=str(data["schema_version"]),
        properties=dict(data["properties"]),
        target=data.get("target"),
        configuration=data.get("configuration"),
    )


def _synthetic_snapshot() -> CalibrationSnapshot:
    return CalibrationSnapshot(
        backend="ibm_fez",
        timestamp=datetime.now(UTC),
        schema_version="1.0",
        properties={
            "qubits": [
                [
                    {"name": "T1", "value": 50e-6},
                    {"name": "T2", "value": 50e-6},
                    {"name": "readout_error", "value": 0.01},
                ]
            ]
        },
        target={},
        configuration={},
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 scripts/first_ensemble_run.py",
        description="Smoke-run AerSimulator against a synthetic fuzzy noise ensemble.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Path to a JSON-formatted CalibrationSnapshot file.",
    )
    parser.add_argument(
        "--qubits",
        type=int,
        default=2,
        help="Number of qubits for the QFT circuit (default: 2).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.qubits <= 0:
        raise ValueError(f"--qubits must be positive; got {args.qubits}")

    snapshot = _load_snapshot(args.snapshot) if args.snapshot else _synthetic_snapshot()

    circuit = qft_circuit(args.qubits)

    print("--- Ensemble Scaling Tests (Real Concretes) ---")
    for n in ENSEMBLE_SIZES:
        members = generate_safe_ensemble(snapshot, n)
        # Warmup to amortize cold start (simulator construction, transpile)
        sim_warm = AerSimulator()
        prep_circ_w, prep_nm_w = members[0].prepare(circuit.copy())
        transpiled_w = transpile(prep_circ_w, backend=sim_warm)
        sim_warm.run(transpiled_w, shots=1, noise_model=prep_nm_w).result()
        t0 = time.perf_counter()
        counts = run_ensemble(circuit, members, SHOTS_PER_MEMBER)
        elapsed = time.perf_counter() - t0
        print(f"N={n} elapsed={elapsed:.2f}s members={n} shots_per_member={SHOTS_PER_MEMBER}")
        print(f"  counts: {counts}\n")

    print("--- Sanity Check (Single Member, 8192 Shots) ---")
    single_member = generate_safe_ensemble(snapshot, 1)[0]
    t0_sanity = time.perf_counter()
    prep_circ, prep_nm = single_member.prepare(circuit.copy())
    sim_sanity = AerSimulator()
    transpiled_sanity = transpile(prep_circ, backend=sim_sanity)
    result_sanity = sim_sanity.run(transpiled_sanity, shots=8192, noise_model=prep_nm).result()
    sanity_counts = result_sanity.get_counts()
    elapsed_sanity = time.perf_counter() - t0_sanity
    print(f"Sanity Run elapsed={elapsed_sanity:.2f}s total_shots=8192")
    print(f"  counts: {sanity_counts}")


if __name__ == "__main__":
    main()
