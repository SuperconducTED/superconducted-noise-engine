# ruff: noqa: E501
"""How close do real Aer density matrices come to metrics.py's two tolerances?

    python docs/evidence/issue-64-pr-a1-acceptance/tolerance_probe.py      (cwd: the worktree, PYTHONPATH=".;src")

_DIAGONAL_TOLERANCE = 1e-12 (diagonal outside [0, 1], or imaginary part) and
_TRACE_TOLERANCE = 1e-9 (trace away from 1). For each density matrix the
harness returns on the cases below, print the diagonal's minimum, its largest
imaginary part, and the trace's distance from 1.
"""

import math

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer.noise import NoiseModel, depolarizing_error
from tests.conftest import _benchmark_ensemble_for_seed, benchmark_snapshot

from superconducted.benchmarks.circuits import ghz_state_circuit, qft_circuit
from superconducted.benchmarks.harness import simulate_engine, simulate_reference
from superconducted.integration.aer_factory import first_viable_seed

BASIS = ("cz", "id", "rx", "rz", "sx", "x")
snapshot = benchmark_snapshot.__wrapped__()
_, seed = first_viable_seed(lambda s: list(_benchmark_ensemble_for_seed(snapshot, s)))

cases = {}
for name, circuit in (
    ("ghz2", ghz_state_circuit(2)),
    ("ghz3", ghz_state_circuit(3)),
    ("qft3", qft_circuit(3)),
):
    for size in (1, 3):
        result = simulate_engine(
            [circuit],
            _benchmark_ensemble_for_seed(snapshot, seed, size),
            basis_gates=BASIS,
            mode="density_matrix",
        )[0]
        cases[f"engine {name} N={size}"] = result.density_matrix
for p in (0.0, 0.1, 0.3, 0.9):
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.measure_all()
    model = NoiseModel(basis_gates=["x"])
    if p:
        model.add_quantum_error(depolarizing_error(p, 1), "x", [0])
    cases[f"depolarizing p={p}"] = simulate_reference(
        [circuit], model, basis_gates=["x"], mode="density_matrix"
    )[0].density_matrix

worst_low = worst_imag = worst_trace = 0.0
for name, rho in cases.items():
    diagonal = np.diagonal(rho)
    low = float(np.real(diagonal).min())
    high = float(np.real(diagonal).max())
    imag = float(np.abs(np.imag(diagonal)).max())
    trace = abs(math.fsum(np.real(diagonal).tolist()) - 1.0)
    worst_low, worst_imag, worst_trace = (
        min(worst_low, low),
        max(worst_imag, imag),
        max(worst_trace, trace),
    )
    print(
        f"{name:22s} dim {rho.shape[0]:2d}  min diag {low:.3e}  max diag {high:.6f}  max |imag| {imag:.1e}  |trace - 1| {trace:.1e}"
    )
print(
    f"\n{len(cases)} matrices: most negative diagonal entry {worst_low:.3e}, largest |imag| {worst_imag:.1e}, largest |trace - 1| {worst_trace:.1e}"
)
