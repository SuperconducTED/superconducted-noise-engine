"""Tests for the controlled benchmark-resolution measurement."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from scripts.resolution_measurement import (
    ResolutionRow,
    measure_resolution,
    smallest_resolved_delta,
    write_tsv,
)

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


@pytest.mark.slow
def test_measurement_is_deterministic_and_complete(tmp_path: Path) -> None:
    """Fixed inputs produce the six required cells and byte-identical TSVs locally."""
    kwargs = {
        "gamma": 0.001,
        "lam": 0.002,
        "deltas": [0.1],
        "repeats": 2,
        "shots": 128,
        "seed": 19,
        "basis_gates": ["cz", "id", "rx", "rz", "sx", "x"],
    }
    first = measure_resolution(**kwargs)
    second = measure_resolution(**kwargs)

    assert first.rows == second.rows
    assert len(first.rows) == 6
    assert {row.circuit for row in first.rows} == {"qft_n3", "ghz_n3"}
    assert {row.metric for row in first.rows} == {
        "hellinger",
        "one_minus_r2",
        "one_minus_state_fidelity",
    }
    first_path = tmp_path / "first.tsv"
    second_path = tmp_path / "second.tsv"
    write_tsv(first_path, first.rows)
    write_tsv(second_path, second.rows)
    assert first_path.read_bytes() == second_path.read_bytes()
