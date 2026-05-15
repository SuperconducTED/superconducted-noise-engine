"""Smoke-runs AerSimulator against an empty noise model for sanity-check timing."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Final

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
ENSEMBLE_SIZES: Final[list[int]] = [1, 8, 16]


def run_ensemble(
    circuit: QuantumCircuit, members: list[FuzzyNoiseModel], shots: int
) -> dict[str, int]:
    """Run each ensemble member and aggregate counts into a single dictionary.

    The simulator is allocated once and reused for all members to avoid
    unnecessary backend construction overhead.
    """
    counts: dict[str, int] = {}

    sim = AerSimulator()

    for nm in members:
        prepared_circuit, actual_noise_model = nm.prepare(circuit.copy())
        transpiled_circuit = transpile(prepared_circuit, backend=sim)
        result = sim.run(transpiled_circuit, shots=shots, noise_model=actual_noise_model).result()
        for k, v in result.get_counts().items():
            counts[k] = counts.get(k, 0) + v
    return counts


def generate_safe_ensemble(snapshot: CalibrationSnapshot, n: int) -> list[FuzzyNoiseModel]:
    """Construct a `FuzzyNoiseModelEnsemble` with conservative default MFs.

    Uses the `BasicCalibrationVectorizer` to infer the input dimension from
    the provided snapshot and builds a small grid of Gaussian MFs per input.
    """
    vectorizer = BasicCalibrationVectorizer()
    try:
        dummy_features = vectorizer.extract(snapshot)
        feature_dim = (
            dummy_features.shape[0] if hasattr(dummy_features, "shape") else len(dummy_features)
        )
    except Exception:
        feature_dim = 1

    mfs_list: list[list[GaussianMF]] = []
    for _ in range(max(1, feature_dim)):
        mfs_list.append([GaussianMF(center=0.0, sigma=0.02), GaussianMF(center=0.01, sigma=0.02)])

    ensemble_iter = FuzzyNoiseModelEnsemble(
        calibration=snapshot,
        feature_extractor=vectorizer,
        rule_base=TSKRuleBase.from_grid(per_input_mfs=mfs_list, output_dim=2),
        defuzzifier=WeightedAverageDefuzzifier(),
        squashing=ProbabilityClip(),
        channel_projector=KrausChannelProjector(NoOpNormalization()),
        fuzzification_strategy=PostGateFuzzification(),
        ensemble_size=n,
    )
    return list(ensemble_iter)


def main() -> None:
    snapshot = CalibrationSnapshot(
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

    circuit = qft_circuit(1)

    print("--- Ensemble Scaling Tests (Real Concretes) ---")
    for n in ENSEMBLE_SIZES:
        members = generate_safe_ensemble(snapshot, n)
        t0 = time.perf_counter()
        counts = run_ensemble(circuit, members, SHOTS_PER_MEMBER)
        elapsed = time.perf_counter() - t0
        total_shots = n * SHOTS_PER_MEMBER
        print(f"N={n} elapsed={elapsed:.2f}s total_shots={total_shots}")
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
