"""Smoke-runs AerSimulator against an empty noise model for sanity-check timing."""

import time
from datetime import datetime, timezone
from typing import Dict, List

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from superconducted.benchmarks.circuits import qft_circuit

# Gerçek Sınıfların İçe Aktarılması
from superconducted.types import CalibrationSnapshot
from superconducted.integration.aer_factory import FuzzyNoiseModel, FuzzyNoiseModelEnsemble
from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.fuzzy.defuzzification import WeightedAverageDefuzzifier
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.membership import GaussianMF
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.fuzzification import PostGateFuzzification

SHOTS_PER_MEMBER = 1024
ENSEMBLE_SIZES = [1, 8, 16]


def run_ensemble(
    circuit: QuantumCircuit, members: List[FuzzyNoiseModel], shots: int
) -> Dict[str, int]:
    """Runs a list of prepared FuzzyNoiseModels on AerSimulator and aggregates counts."""
    counts: Dict[str, int] = {}
    
    # Copilot Optimizasyonu: Simülatörü döngü dışında 1 kez yaratıyoruz
    sim = AerSimulator()

    for nm in members:
        # Devrelerin birbirini kirletmemesi için .copy() kullanıyoruz
        prep_out = nm.prepare(circuit.copy())
        prepared_circuit, actual_noise_model = prep_out if isinstance(prep_out, tuple) else (circuit, prep_out)

        # Decompose high-level gates (e.g. QFTGate) into Aer's basis before run()
        transpiled_circuit = transpile(prepared_circuit, backend=sim)

        # Modele özel noise_model'i doğrudan run() içine veriyoruz
        result = sim.run(transpiled_circuit, shots=shots, noise_model=actual_noise_model).result()

        for k, v in result.get_counts().items():
            counts[k] = counts.get(k, 0) + v
    return counts


def generate_safe_ensemble(snapshot: CalibrationSnapshot, n: int) -> List[FuzzyNoiseModel]:
    """Constructs a FuzzyNoiseModelEnsemble using real concrete dependencies."""
    vectorizer = BasicCalibrationVectorizer()

    # Vectorizer çıktı boyutunu snapshot'tan belirliyoruz.
    try:
        dummy_features = vectorizer.extract(snapshot)
        feature_dim = dummy_features.shape[0] if hasattr(dummy_features, "shape") else len(dummy_features)
    except Exception:
        feature_dim = 1

    mfs_list: list[list[GaussianMF]] = []
    for _ in range(max(1, feature_dim)):
        mfs_list.append(
            [
                GaussianMF(center=0.0, sigma=0.02),
                GaussianMF(center=0.01, sigma=0.02),
            ]
        )

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
        timestamp=datetime.now(timezone.utc),
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
    prep_out = single_member.prepare(circuit.copy())
    prep_circ, prep_nm = prep_out if isinstance(prep_out, tuple) else (circuit, single_member)

    sim_sanity = AerSimulator()
    transpiled_sanity = transpile(prep_circ, backend=sim_sanity)
    result_sanity = sim_sanity.run(transpiled_sanity, shots=8192, noise_model=prep_nm).result()
    sanity_counts = result_sanity.get_counts()
    elapsed_sanity = time.perf_counter() - t0_sanity

    print(f"Sanity Run elapsed={elapsed_sanity:.2f}s total_shots=8192")
    print(f"  counts: {sanity_counts}")


if __name__ == "__main__":
    main()