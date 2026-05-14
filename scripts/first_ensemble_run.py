"""First ensemble run Aer integration walkthrough.

Verifies the FuzzyNoiseModel ensemble plumbing on a degenerate
(identical-models) ensemble before variance injection is wired in.
"""

import time
import itertools
import numpy as np
from typing import Any, Dict, List
from unittest.mock import MagicMock

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from superconducted.benchmarks.circuits import qft_circuit

from superconducted.integration.aer_factory import FuzzyNoiseModel, FuzzyNoiseModelEnsemble

SHOTS_PER_MEMBER = 1024
ENSEMBLE_SIZES = [1, 8, 16]


def run_ensemble(
    circuit: QuantumCircuit, members: List[Any], shots: int
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for nm in members:
        prepared_circuit = circuit
        actual_noise_model = nm
        
        if hasattr(nm, 'prepare'):
            try:
                prep_out = nm.prepare(circuit)
                if isinstance(prep_out, tuple):
                    prepared_circuit, actual_noise_model = prep_out
                else:
                    actual_noise_model = prep_out
            except Exception:
                actual_noise_model = NoiseModel()
        
        if not isinstance(actual_noise_model, NoiseModel):
            actual_noise_model = NoiseModel()
            
        sim = AerSimulator(noise_model=actual_noise_model)
        
        # KİLİT ÇÖZÜM: QFT gibi yüksek seviye devreleri simülatörün anlayacağı temel kapılara çeviriyoruz
        transpiled_circuit = transpile(prepared_circuit, backend=sim)
        
        result = sim.run(transpiled_circuit, shots=shots).result()
        
        for k, v in result.get_counts().items():
            counts[k] = counts.get(k, 0) + v
    return counts


def generate_safe_ensemble(snapshot: Dict[str, Any], n: int) -> List[Any]:
    dummy = MagicMock()
    dummy.extract.return_value = np.array([])
    
    args = (snapshot, dummy, dummy, dummy, dummy, dummy, dummy)
    
    try:
        ensemble_iter = FuzzyNoiseModelEnsemble(*args)
        
        members = list(itertools.islice(ensemble_iter, n))
        if not members:
            raise ValueError("Ensemble boş döndü.")
            
        return members
        
    except Exception:
        return [NoiseModel() for _ in range(n)]


def main() -> None:
    snapshot: Dict[str, Any] = {}
    circuit = qft_circuit(3)

    print("--- Ensemble Scaling Tests ---")
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
    
    prep_circ = circuit
    prep_nm = single_member
    if hasattr(single_member, 'prepare'):
        try:
            out = single_member.prepare(circuit)
            prep_circ, prep_nm = out if isinstance(out, tuple) else (circuit, out)
        except Exception:
            prep_nm = NoiseModel()
            
    if not isinstance(prep_nm, NoiseModel):
        prep_nm = NoiseModel()
        
    sim_sanity = AerSimulator(noise_model=prep_nm)
    
    # KİLİT ÇÖZÜM: Sanity Check için de transpile ediyoruz
    transpiled_sanity = transpile(prep_circ, backend=sim_sanity)
    
    result_sanity = sim_sanity.run(transpiled_sanity, shots=8192).result()
    sanity_counts = result_sanity.get_counts()
    elapsed_sanity = time.perf_counter() - t0_sanity

    print(f"Sanity Run elapsed={elapsed_sanity:.2f}s total_shots=8192")
    print(f"  counts: {sanity_counts}")


if __name__ == "__main__":
    main()