"""Tests for the controlled benchmark-resolution measurement."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from qiskit import transpile
from scripts.resolution_measurement import (
    ResolutionRow,
    _controlled_model,
    eligible_operations_from_snapshot,
    measure_resolution,
    smallest_resolved_delta,
    write_tsv,
)

from superconducted.benchmarks.circuits import ghz_state_circuit
from superconducted.benchmarks.metrics import R2Score
from superconducted.types import SimulationResult


def _counts(values: dict[str, int]) -> SimulationResult:
    return SimulationResult(
        shots=sum(values.values()), backend_label="test", counts=Counter(values)
    )


def _row(circuit: str, mode: str, metric: str, delta: float, resolved: bool) -> ResolutionRow:
    return ResolutionRow(
        circuit=circuit,
        mode=mode,  # type: ignore[arg-type]
        metric=metric,
        gamma_a=0.1,
        lambda_a=0.2,
        gamma_b=0.1 + delta,
        gamma_delta=delta,
        repeats=2,
        shots=128,
        seed=7,
        baseline_mean=0.01,
        baseline_sample_sd=0.001,
        threshold=0.013,
        between_mean=0.02 if resolved else 0.01,
        margin=0.007 if resolved else -0.003,
        resolved=resolved,
        qiskit="test",
        qiskit_aer="test",
    )


def test_one_minus_r2_has_discrepancy_orientation() -> None:
    """Raw R2 falls, so its discrepancy rises, as a controlled shift grows."""
    metric = R2Score()
    baseline = _counts({"0": 700, "1": 300})
    shifted_less = _counts({"0": 650, "1": 350})
    shifted = _counts({"0": 600, "1": 400})

    raw = [metric.compute(baseline, candidate) for candidate in (baseline, shifted_less, shifted)]
    discrepancy = [1.0 - value for value in raw]

    assert raw[0] == pytest.approx(1.0)
    assert raw[0] > raw[1] > raw[2]
    assert discrepancy[0] == pytest.approx(0.0)
    assert discrepancy[0] < discrepancy[1] < discrepancy[2]


def test_protocol_threshold_requires_every_counts_cell() -> None:
    """One easy cell cannot make the protocol-level counts claim resolve."""
    cells = (
        ("qft_n3", "hellinger"),
        ("qft_n3", "one_minus_r2"),
        ("ghz_n3", "hellinger"),
        ("ghz_n3", "one_minus_r2"),
    )
    rows = [_row(circuit, "counts", metric, 0.1, True) for circuit, metric in cells]
    rows += [_row(circuit, "counts", metric, 0.01, True) for circuit, metric in cells]
    rows[-1] = replace(rows[-1], resolved=False)

    assert smallest_resolved_delta(rows, "counts") == pytest.approx(0.1)


def test_protocol_threshold_rejects_missing_cells() -> None:
    """An incomplete experiment cannot produce a protocol-level claim."""
    rows = [_row("qft_n3", "counts", "hellinger", 0.1, True)]

    with pytest.raises(ValueError, match="incomplete counts cells"):
        smallest_resolved_delta(rows, "counts")


def test_protocol_threshold_rejects_missing_mode() -> None:
    """An absent mode is invalid, not evidence that no ladder value resolves."""
    with pytest.raises(ValueError, match="no density_matrix rows"):
        smallest_resolved_delta([], "density_matrix")


EVIDENCE = Path(__file__).parents[1] / "docs" / "evidence" / "resolution-measurement"
FIXTURE = (
    Path(__file__).parent / "fixtures" / "calibration" / "ibm_fez_20260513T121322Z_with_gates.json"
)
# ddof=1 spread of the fixture's per-qubit sx gamma target over its 155 usable
# qubits; the 2026-10-21 ladder is this value times 8, 4, 2, 1, 1/2, 1/4, 1/8.
S_GAMMA = 7.600232779751463e-05


@pytest.mark.slow
@pytest.mark.parametrize(
    ("tsv_name", "deltas", "eligible"),
    [
        ("resolution.tsv", [0.1, 0.01, 0.001, 0.0001], False),
        (
            "resolution-2026-10-21-spread-ladder.tsv",
            [S_GAMMA * k for k in (8, 4, 2, 1, 0.5, 0.25, 0.125)],
            True,
        ),
    ],
    ids=("2026-09-06-placeholder", "2026-10-21-spread-ladder"),
)
def test_measurement_regenerates_committed_tsv(
    tsv_name: str, deltas: list[float], eligible: bool, tmp_path: Path
) -> None:
    """Regeneration obeys NFR-1's exact/local and 1e-12/cross-machine contracts."""
    result = measure_resolution(
        gamma=0.00017266737044123665,
        lam=0.0006630210259092216,
        deltas=deltas,
        repeats=32,
        shots=4096,
        seed=58,
        basis_gates=["cz", "id", "rx", "rz", "sx", "x"],
        eligible_operations=eligible_operations_from_snapshot(FIXTURE) if eligible else None,
    )

    assert len(result.rows) == 6 * len(deltas)
    assert {row.circuit for row in result.rows} == {"qft_n3", "ghz_n3"}
    assert {row.metric for row in result.rows} == {
        "hellinger",
        "one_minus_r2",
        "one_minus_state_fidelity",
    }
    regenerated = tmp_path / tsv_name
    committed = EVIDENCE / tsv_name
    write_tsv(regenerated, result.rows)

    # Serialization of one set of rows is byte-stable on the same machine.
    regenerated_again = tmp_path / "resolution-again.tsv"
    write_tsv(regenerated_again, result.rows)
    assert regenerated.read_bytes() == regenerated_again.read_bytes()

    with regenerated.open(encoding="utf-8", newline="") as handle:
        regenerated_reader = csv.DictReader(handle, delimiter="\t")
        regenerated_fields = regenerated_reader.fieldnames
        regenerated_rows = list(regenerated_reader)
    with committed.open(encoding="utf-8", newline="") as handle:
        committed_reader = csv.DictReader(handle, delimiter="\t")
        committed_fields = committed_reader.fieldnames
        committed_rows = list(committed_reader)

    assert regenerated_fields == committed_fields
    assert len(regenerated_rows) == len(committed_rows)
    measured_fields = {
        "baseline_mean",
        "baseline_sample_sd",
        "threshold",
        "between_mean",
        "margin",
    }
    for regenerated_row, committed_row in zip(regenerated_rows, committed_rows, strict=True):
        if committed_row["mode"] == "counts":
            # Seeded multinomial draws are exact under the pinned Qiskit/Aer stack.
            assert regenerated_row == committed_row
            continue
        for field in committed_fields or ():
            if field in measured_fields:
                assert float(regenerated_row[field]) == pytest.approx(
                    float(committed_row[field]), rel=0.0, abs=1e-12
                )
            else:
                # Protocol, inputs, provenance, ordering, and verdict stay exact.
                assert regenerated_row[field] == committed_row[field]


def test_engine_true_eligibility_leaves_virtual_rz_noise_free() -> None:
    """With ADR-028 eligibility the controlled model noises what the engine does.

    The 2026-09-06 protocol (no eligibility) also damps the zero-length virtual
    ``rz``; the engine has not since PR #96, which is why the 2026-10-21 run
    passes the fixture's policy.
    """
    compiled = transpile(
        ghz_state_circuit(3),
        basis_gates=["cz", "id", "rx", "rz", "sx", "x"],
        optimization_level=1,
        seed_transpiler=0,
    )
    assert "rz" in compiled.count_ops()
    eligible = eligible_operations_from_snapshot(FIXTURE)
    assert {name for name, _qubits in eligible} == {"id", "rx", "sx", "x"}

    _, every = _controlled_model(
        compiled, gamma=1e-3, lam=1e-3, basis=("cz", "id", "rx", "rz", "sx", "x"), eligible=None
    )
    _, engine_true = _controlled_model(
        compiled,
        gamma=1e-3,
        lam=1e-3,
        basis=("cz", "id", "rx", "rz", "sx", "x"),
        eligible=eligible,
    )

    assert "rz" in every.noise_instructions
    assert "rz" not in engine_true.noise_instructions
    assert set(engine_true.noise_instructions) == set(every.noise_instructions) - {"rz"}


def test_empty_eligibility_is_rejected() -> None:
    with pytest.raises(ValueError, match="eligible_operations is empty"):
        measure_resolution(
            gamma=0.1,
            lam=0.1,
            deltas=[0.01],
            repeats=2,
            shots=8,
            seed=1,
            basis_gates=["sx"],
            eligible_operations=frozenset(),
        )
