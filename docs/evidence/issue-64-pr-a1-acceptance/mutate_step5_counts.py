# ruff: noqa: E501
"""What the two simulated Aer behaviours actually do to the count, not only which tests fail.

    python docs/evidence/issue-64-pr-a1-acceptance/mutate_step5_counts.py <python exe> <dir holding aer_mutant_plugin.py>   (cwd: the worktree)

Runs one 1024-shot run under each AER_MUTANT mode in a fresh interpreter with
the plugin imported, and prints how many times NoiseModel.to_dict was called.
Expected if the plugin does what its docstring says: none 1, extra 2, per_shot 1025.
"""

import os
import subprocess
import sys

py, plugin_dir = sys.argv[1], sys.argv[2]
CODE = r"""
import aer_mutant_plugin  # noqa: F401  (applies the mutation named by AER_MUTANT)
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error
calls = [0]
original = NoiseModel.to_dict
def spy(self, *a, **k):
    calls[0] += 1
    return original(self, *a, **k)
NoiseModel.to_dict = spy
qc = QuantumCircuit(1); qc.x(0); qc.measure_all()
nm = NoiseModel(basis_gates=["x"]); nm.add_quantum_error(depolarizing_error(0.1, 1), "x", [0])
for method in ("automatic", "density_matrix"):
    calls[0] = 0
    AerSimulator(method=method).run(qc, shots=1024, noise_model=nm).result()
    print(method, calls[0])
"""
for mode in ("", "extra", "per_shot"):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(["src", plugin_dir]), "AER_MUTANT": mode}
    out = subprocess.run([py, "-c", CODE], capture_output=True, text=True, env=env)
    print(
        f"{mode or 'none':9s}", out.stdout.strip().replace("\n", " | ") or out.stderr.strip()[-400:]
    )
