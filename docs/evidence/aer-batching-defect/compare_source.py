"""Compare the code the mechanism reading names, across Aer refs, by function body.

Run with:  python -I compare_source.py

Needs `gh`, and reads Qiskit/qiskit-aer on GitHub, so the `main` column is true only on the day it
ran. Reading is not running: "same" says the source agrees, not that the defect reproduces there.
"""

import re
import subprocess

REFS = ["0.17.2", "0.18.2", "main"]
TARGETS = [
    ("src/controllers/aer_controller.hpp", r"Controller::simulation_methods\("),
    ("src/controllers/aer_controller.hpp", r"Method Controller::automatic_simulation_method\("),
    ("src/noise/quantum_error.hpp", r"void QuantumError::compute_superoperator\(\)"),
    ("src/noise/quantum_error.hpp", r"void QuantumError::compute_kraus\(\)"),
    ("src/noise/quantum_error.hpp", r"void QuantumError::compute_circuits_superoperator\(\)"),
    ("src/noise/quantum_error.hpp", r"void QuantumError::compute_generators_superoperator\(\)"),
    ("src/framework/matrix.hpp", r"inline void matrix<T>::initialize\(size_t rows, size_t cols\)"),
    ("src/noise/noise_model.hpp", r"void NoiseModel::enable_superop_method\(int num_threads\)"),
    ("src/noise/noise_model.hpp", r"void NoiseModel::enable_kraus_method\(int num_threads\)"),
]


def fetch(path: str, ref: str) -> str:
    return subprocess.run(
        [
            "gh",
            "api",
            f"repos/Qiskit/qiskit-aer/contents/{path}?ref={ref}",
            "-H",
            "Accept: application/vnd.github.raw",
        ],
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout


def body(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    if match is None:
        return "<not found>"
    end = text.find("\n}\n", match.start())
    return text[match.start() : end]


cache: dict[tuple[str, str], str] = {}
print(f"{'function':62s} 0.18.2 vs 0.17.2 | main vs 0.17.2")
for path, pattern in TARGETS:
    bodies = {}
    for ref in REFS:
        cache.setdefault((path, ref), fetch(path, ref))
        bodies[ref] = body(cache[(path, ref)], pattern)
    name = pattern.replace("\\", "")[:60]
    print(
        f"{name:62s} {'same' if bodies['0.18.2'] == bodies['0.17.2'] else 'DIFFERS':16s} | "
        f"{'same' if bodies['main'] == bodies['0.17.2'] else 'DIFFERS'}"
    )
    if bodies["main"] != bodies["0.17.2"]:
        old = bodies["0.17.2"].splitlines()
        new = bodies["main"].splitlines()
        for line in sorted(set(new) - set(old))[:6]:
            print("    main adds:", line.strip()[:100])
        for line in sorted(set(old) - set(new))[:6]:
            print("    main drops:", line.strip()[:100])
