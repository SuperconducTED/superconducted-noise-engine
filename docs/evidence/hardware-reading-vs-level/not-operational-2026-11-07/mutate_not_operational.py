# ruff: noqa: E501
"""Amendment 20's rule, criterion 15: remove each new line and confirm a test fails.

    python mutate_not_operational.py <repo root> <status file>

Restores from a backup made here, never via git. Each mutant asserts its pattern is found exactly
once, so a mutant that changes nothing cannot pass as caught. Every pytest run has its own time
limit and writes one status line, because a hung run looks exactly like a working one.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

READING = "scripts/hardware_reading_vs_level.py"
SUBMIT = "scripts/hardware_submit.py"
TESTS = "tests/test_hardware_submit.py"
LIMIT_S = 300

SELECT = (
    "operational or dead or left_out or marked or high_or_null or missing_gate or another_gate "
    "or no_control_rows or control_rows_that_exist or healthy_device or absent_from or gate_error"
)

MUTANTS = [
    (
        READING,
        "sx signal dropped",
        'if entry.get("gate") not in ("x", "sx") or len(qubits) != 1:',
        'if entry.get("gate") not in ("x",) or len(qubits) != 1:',
    ),
    (
        READING,
        "x signal dropped",
        'if entry.get("gate") not in ("x", "sx") or len(qubits) != 1:',
        'if entry.get("gate") not in ("sx",) or len(qubits) != 1:',
    ),
    (
        READING,
        "any gate carries the signal",
        'if entry.get("gate") not in ("x", "sx") or len(qubits) != 1:',
        "if len(qubits) != 1:",
    ),
    (
        READING,
        "two-qubit entries read too",
        'if entry.get("gate") not in ("x", "sx") or len(qubits) != 1:',
        'if entry.get("gate") not in ("x", "sx", "cz"):',
    ),
    (
        READING,
        "target signal dropped",
        "dead = {q for q in range(int(target.num_qubits)) if not _operational_qubit(target, q)}",
        "dead: set[int] = set()",
    ),
    (
        READING,
        "threshold lowered",
        "if value is not None and float(value) >= 1.0:",
        "if value is not None and float(value) >= 0.99:",
    ),
    (
        READING,
        "threshold strict",
        "if value is not None and float(value) >= 1.0:",
        "if value is not None and float(value) > 1.0:",
    ),
    (
        READING,
        "null counts as a signal",
        "if value is not None and float(value) >= 1.0:",
        "if value is None or float(value) >= 1.0:",
    ),
    (READING, "every parameter read", 'if parameter.get("name") != "gate_error":', "if False:"),
    (
        READING,
        "measure dropped from the target check",
        'return all((qubit,) in target[name] for name in ("x", "sx", "measure"))',
        'return all((qubit,) in target[name] for name in ("x", "sx"))',
    ),
    (
        READING,
        "x dropped from the target check",
        'return all((qubit,) in target[name] for name in ("x", "sx", "measure"))',
        'return all((qubit,) in target[name] for name in ("sx", "measure"))',
    ),
    (
        READING,
        "sx dropped from the target check",
        'return all((qubit,) in target[name] for name in ("x", "sx", "measure"))',
        'return all((qubit,) in target[name] for name in ("x", "measure"))',
    ),
    (
        READING,
        "build_job ignores the marker",
        'dead = set(not_operational_qubits(snapshot["properties"], live_target))',
        "dead = set()",
    ),
    (
        READING,
        "the dry run reads the marker",
        'if live_target is not None:\n        dead = set(not_operational_qubits(snapshot["properties"], live_target))',
        'if True:\n        dead = set(not_operational_qubits(snapshot["properties"], target))',
    ),
    (
        READING,
        "build_job's guard removed",
        '        if missing:\n            raise ValueError(f"selected qubits are not operational at t_s: {missing}")\n',
        "",
    ),
    (READING, "Arm B keeps a dead qubit", "        and q not in dead\n", ""),
    (
        SUBMIT,
        "run_build ignores the marker",
        'dead = not_operational_qubits(live["properties"], device.target)',
        "dead: list[int] = []",
    ),
    (
        SUBMIT,
        "dead rows stay candidates",
        "[r for r in rows if r.qubit not in dead], k=N_DISCRIMINATING, controls=set(controls)",
        "rows, k=N_DISCRIMINATING, controls=set(controls)",
    ),
    (
        SUBMIT,
        "frozen set may be selected",
        "[r for r in rows if r.qubit not in dead], k=N_DISCRIMINATING, controls=set(controls)",
        "[r for r in rows if r.qubit not in dead], k=N_DISCRIMINATING, controls=set()",
    ),
    (
        SUBMIT,
        "dead control still runs",
        "running_controls = [q for q in controls if q not in dead]",
        "running_controls = list(controls)",
    ),
    (
        SUBMIT,
        "selection logs the frozen set",
        'selection["controls"] = running_controls',
        'selection["controls"] = controls',
    ),
    (
        SUBMIT,
        "left-out log empty",
        'selection["controls_left_out"] = [q for q in controls if q in dead]',
        'selection["controls_left_out"] = []',
    ),
    (
        SUBMIT,
        "not-operational log empty",
        'selection["not_operational"] = dead',
        'selection["not_operational"] = []',
    ),
    (SUBMIT, "build_job gets the frozen set", "controls=running_controls,", "controls=controls,"),
    (
        SUBMIT,
        "no control rows meets A3",
        "(gap := _mean(g for g, _ in _gaps(control, name))) is not None and gap > 0.0",
        "(gap := _mean(g for g, _ in _gaps(control, name))) is None or gap > 0.0",
    ),
]


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    status = Path(sys.argv[2])
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([".", "src"]), "PYTHONIOENCODING": "utf-8"}
    command = [
        sys.executable,
        "-m",
        "pytest",
        TESTS,
        "-x",
        "-q",
        "-p",
        "no:cacheprovider",
        "-k",
        SELECT,
    ]
    backup = {name: (root / name).read_bytes() for name in (READING, SUBMIT)}
    survived = timed_out = 0

    def line(text: str) -> None:
        with status.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')} {text}\n")

    try:
        # Every mutant's pattern is checked before any test runs, so a stale list fails at once.
        for name, label, old, _ in MUTANTS:
            found = backup[name].decode("utf-8").replace("\r\n", "\n").count(old)
            assert found == 1, f"{label}: pattern found {found} times in {name}"
        line(f"start: {len(MUTANTS)} mutants, all patterns found once")
        baseline = subprocess.run(
            command, cwd=root, env=env, capture_output=True, text=True, timeout=LIMIT_S, check=False
        )
        line(f"baseline exit {baseline.returncode}")
        assert baseline.returncode == 0, baseline.stdout[-2000:]
        for name, label, old, new in MUTANTS:
            text = backup[name].decode("utf-8")
            crlf = "\r\n" in text
            mutated = text.replace("\r\n", "\n").replace(old, new)
            (root / name).write_bytes(
                (mutated.replace("\n", "\r\n") if crlf else mutated).encode("utf-8")
            )
            try:
                run = subprocess.run(
                    command,
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=LIMIT_S,
                    check=False,
                )
                caught = run.returncode != 0
                survived += not caught
                line(f"{'caught  ' if caught else 'SURVIVED'} {label}")
            except subprocess.TimeoutExpired:
                timed_out += 1
                line(f"TIMEOUT  {label}")
            finally:
                (root / name).write_bytes(backup[name])
    finally:
        for name, data in backup.items():
            (root / name).write_bytes(data)
    line(f"RUN END: {len(MUTANTS)} mutants, {survived} survived, {timed_out} timed out")
    return 1 if survived or timed_out else 0


if __name__ == "__main__":
    sys.exit(main())
