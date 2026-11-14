# ruff: noqa: E501
"""How often does qiskit-aer call NoiseModel.to_dict and QuantumError.to_dict in one run?

    python docs/evidence/issue-64-pr-a1-acceptance/to_dict_probe.py      (any cwd; needs only qiskit and qiskit-aer)

Measured before the guard test is written, so the test asserts the number
found and not a number assumed. The spy wraps the class attribute, so it
counts calls on any instance, including a deep copy Aer may make.
"""

import qiskit
import qiskit_aer
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, QuantumError, depolarizing_error

print("qiskit", qiskit.__version__, "qiskit-aer", qiskit_aer.__version__)

calls = {"model": 0, "error": 0}
_model_to_dict = NoiseModel.to_dict
_error_to_dict = QuantumError.to_dict


def model_spy(self, *args, **kwargs):
    calls["model"] += 1
    return _model_to_dict(self, *args, **kwargs)


def error_spy(self, *args, **kwargs):
    calls["error"] += 1
    return _error_to_dict(self, *args, **kwargs)


NoiseModel.to_dict = model_spy
QuantumError.to_dict = error_spy


def circuit(final_measure: bool) -> QuantumCircuit:
    qc = QuantumCircuit(1)
    qc.x(0)
    qc.x(0)
    qc.x(0)
    if final_measure:
        qc.measure_all()
    else:
        qc.save_density_matrix()
    return qc


def model() -> NoiseModel:
    nm = NoiseModel(basis_gates=["x"])
    nm.add_quantum_error(depolarizing_error(0.1, 1), "x", [0])
    return nm


# The spy fires at all: a direct call is counted.
calls.update(model=0, error=0)
model().to_dict()
print("direct call: model", calls["model"], "error", calls["error"])

for method in ("automatic", "density_matrix"):
    for how in ("run option", "constructor option"):
        for shots in (1, 1024, 8192):
            nm = model()
            sim = (
                AerSimulator(method=method, noise_model=nm)
                if how == "constructor option"
                else AerSimulator(method=method)
            )
            calls.update(model=0, error=0)
            kwargs = {"shots": shots, "seed_simulator": 5}
            if how == "run option":
                kwargs["noise_model"] = nm
            result = sim.run(circuit(final_measure=True), **kwargs).result()
            total = sum(result.get_counts().values())
            print(
                f"{method:15s} {how:18s} shots {shots:5d}: model.to_dict {calls['model']}, error.to_dict {calls['error']}, counts sum {total}, minority outcome {result.get_counts().get('0', 0)}"
            )

# Density-matrix state mode, as the harness runs it: a save instruction and shots=1.
nm = model()
calls.update(model=0, error=0)
result = (
    AerSimulator(method="density_matrix")
    .run(circuit(final_measure=False), shots=1, noise_model=nm)
    .result()
)
print(
    "density_matrix, save_density_matrix, shots 1: model.to_dict",
    calls["model"],
    "error.to_dict",
    calls["error"],
)

# Two circuits in one run, for the record only (the project runs one circuit per run, NC-097).
nm = model()
calls.update(model=0, error=0)
AerSimulator().run([circuit(True), circuit(True)], shots=1024, noise_model=nm).result()
print(
    "automatic, two circuits in one run, shots 1024: model.to_dict",
    calls["model"],
    "error.to_dict",
    calls["error"],
)

# No noise model at all.
calls.update(model=0, error=0)
AerSimulator().run(circuit(True), shots=1024).result()
print(
    "automatic, no noise model, shots 1024: model.to_dict",
    calls["model"],
    "error.to_dict",
    calls["error"],
)
