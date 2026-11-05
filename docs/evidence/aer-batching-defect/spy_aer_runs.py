"""A pytest plugin that records every Aer execution a test suite performs.

Run from the repository root, with this folder and `src` on the path:

    python -m pytest tests -q -p spy_aer_runs

Wraps `AerBackend._execute_circuits_job`, which every Aer execution passes whether it came from
`AerSimulator.run`, `BackendSamplerV2` or `qiskit_aer.primitives`. It changes nothing about the run.
Prints a summary at the end, including every execution that held more than one circuit. It cannot see
a subprocess a test starts; the static audit lists those.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest
from qiskit import QuantumCircuit
from qiskit_aer.backends.aerbackend import AerBackend

records: list[dict[str, Any]] = []
current = {"test": "(outside a test)"}
original = AerBackend._execute_circuits_job


def has_kraus(noise_model: Any) -> bool:
    if noise_model is None:
        return False
    return any(
        instruction["name"] in ("kraus", "superop")
        for error in noise_model.to_dict().get("errors", [])
        for circuit in error.get("instructions", [])
        for instruction in circuit
    )


def spy(self: AerBackend, circuits: Any, parameter_binds: Any, run_options: Any, *a: Any, **k: Any):
    count = 1 if isinstance(circuits, QuantumCircuit) else len(circuits)
    noise_model = run_options.get("noise_model", getattr(self.options, "noise_model", None))
    records.append(
        {
            "test": current["test"],
            "circuits": count,
            "method": run_options.get("method", getattr(self.options, "method", None)),
            "noise": noise_model is not None,
            "kraus": has_kraus(noise_model) if count > 1 else None,
        }
    )
    return original(self, circuits, parameter_binds, run_options, *a, **k)


AerBackend._execute_circuits_job = spy


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):
    current["test"] = item.nodeid
    yield
    current["test"] = "(outside a test)"


def pytest_terminal_summary(terminalreporter: Any) -> None:
    write = terminalreporter.write_line
    write("")
    write("=== Aer executions seen by spy_aer_runs ===")
    write(f"executions {len(records)}")
    write(f"tests with at least one {len({r['test'] for r in records})}")
    histogram = Counter(r["circuits"] for r in records)
    write(f"circuits per execution {dict(sorted(histogram.items()))}")
    methods = Counter(str(r["method"]) for r in records)
    write(f"method option {dict(sorted(methods.items()))}")
    noisy = sum(1 for r in records if r["noise"])
    write(f"with a noise model {noisy}")
    many = [r for r in records if r["circuits"] > 1]
    write(f"executions with more than one circuit {len(many)}")
    for record in many:
        write(
            f"  {record['test']}: {record['circuits']} circuits, method {record['method']}, "
            f"noise {record['noise']}, kraus or superop in model {record['kraus']}"
        )
