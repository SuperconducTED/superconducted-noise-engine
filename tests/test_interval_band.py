"""The interval band and its coverage metric (issue #64 PR-A1, step 4).

``interval_band`` turns the members of an ensemble into a per-outcome band,
and ``IntervalCoverage`` says how much of a reference distribution's mass
lies inside it. Section 3 holds ADR-022's six properties as named tests,
which is the bar for anything that lands in ``benchmarks/metrics.py``.

Conventions used throughout: an outcome is a Qiskit bitstring, so in a key
the rightmost character is qubit 0; probabilities are dimensionless; counts
are normalised by each result's own total.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix
from qiskit_aer.noise import NoiseModel, depolarizing_error

from superconducted.benchmarks.harness import simulate_reference
from superconducted.benchmarks.metrics import IntervalBand, IntervalCoverage, interval_band
from superconducted.interfaces import BenchmarkMetric
from superconducted.types import SimulationResult


def counts(outcomes: dict[str, int]) -> SimulationResult:
    """A real counts-mode ``SimulationResult`` (ADR-022: no mocks)."""
    return SimulationResult(
        shots=sum(outcomes.values()), backend_label="test", counts=Counter(outcomes)
    )


def state(diagonal: Sequence[float]) -> SimulationResult:
    """A real density-matrix ``SimulationResult`` that is diagonal with these entries."""
    matrix = np.diag(np.asarray(diagonal, dtype=np.complex128))
    return SimulationResult(shots=1, backend_label="test", density_matrix=matrix)


def summed(members: Sequence[SimulationResult]) -> SimulationResult:
    """The sum aggregate of counts-mode members (ADR-016's default)."""
    total: Counter[str] = Counter()
    for member in members:
        assert member.counts is not None
        total.update(member.counts)
    return counts(dict(total))


#: The ticket's hand-derived example (section 6.3, property 6), as counts at 100 shots.
MEMBER_A = {"00": 40, "01": 30, "10": 20, "11": 10}
MEMBER_B = {"00": 60, "01": 20, "10": 10, "11": 10}
MEMBER_C = {"00": 50, "01": 30, "10": 20}  # outcome 11 absent, so its probability is 0
REFERENCE_Q = {"00": 50, "01": 35, "10": 10, "11": 5}


def example_members() -> list[SimulationResult]:
    return [counts(MEMBER_A), counts(MEMBER_B), counts(MEMBER_C)]


# --------------------------------------------------------------------------
# 1. interval_band (acceptance criterion 5)
# --------------------------------------------------------------------------


def test_the_hand_derived_min_max_band() -> None:
    """Section 6.3: ``00: [0.4, 0.6]``, ``01: [0.2, 0.3]``, ``10: [0.1, 0.2]``, ``11: [0.0, 0.1]``."""
    band = interval_band(example_members(), alpha=0.0)

    assert band.support == ("00", "01", "10", "11")
    assert np.array_equal(band.lower, np.array([40, 20, 10, 0]) / 100)
    assert np.array_equal(band.upper, np.array([60, 30, 20, 10]) / 100)
    assert band.alpha == 0.0
    assert band.method == "linear"
    assert band.n_members == 3


def test_alpha_is_required_and_has_no_default() -> None:
    """D2 fixes ``alpha`` with ``r`` as one pair, so no band is built without naming it."""
    with pytest.raises(TypeError, match="alpha"):
        interval_band(example_members())  # type: ignore[call-arg]


@pytest.mark.parametrize("alpha", [-0.1, 0.5, 0.7, math.nan, math.inf, -math.inf])
def test_alpha_outside_the_half_open_interval_is_refused(alpha: float) -> None:
    with pytest.raises(ValueError, match="alpha"):
        interval_band(example_members(), alpha=alpha)


def test_a_band_needs_at_least_two_members() -> None:
    """A band of one member is a point."""
    with pytest.raises(ValueError, match="at least two members"):
        interval_band([counts(MEMBER_A)], alpha=0.0)
    with pytest.raises(ValueError, match="at least two members"):
        interval_band([], alpha=0.0)


def test_mixed_modes_are_refused() -> None:
    with pytest.raises(ValueError, match="mixed"):
        interval_band([counts({"0": 3, "1": 1}), state([0.75, 0.25])], alpha=0.0)


def test_an_unknown_quantile_method_is_refused() -> None:
    with pytest.raises(ValueError, match="nonsense"):
        interval_band(example_members(), alpha=0.1, method="nonsense")


#: Every ``method`` numpy 2.4 accepts in ``numpy.quantile``.
QUANTILE_METHODS = [
    "inverted_cdf",
    "averaged_inverted_cdf",
    "closest_observation",
    "interpolated_inverted_cdf",
    "hazen",
    "weibull",
    "linear",
    "median_unbiased",
    "normal_unbiased",
    "lower",
    "higher",
    "midpoint",
    "nearest",
]


@pytest.mark.parametrize("method", QUANTILE_METHODS)
def test_the_min_max_band_is_exactly_the_per_outcome_minimum_and_maximum(method: str) -> None:
    """``alpha = 0`` must give min and max with no interpolation residue, under any method.

    PR-A2's invariant (the sum aggregate lies inside the ``alpha = 0`` band)
    is exact only if the band's edges are members' own values.
    """
    rng = np.random.default_rng(64)
    for _ in range(200):
        n_members = int(rng.integers(2, 33))
        table = rng.integers(0, 50, size=(n_members, 4))
        table[:, 0] += 1  # every member has a positive total
        members = [counts({format(i, "02b"): int(v) for i, v in enumerate(row)}) for row in table]
        probabilities = table / table.sum(axis=1, keepdims=True)

        band = interval_band(members, alpha=0.0, method=method)

        assert band.method == method
        assert np.array_equal(band.lower, probabilities.min(axis=0))
        assert np.array_equal(band.upper, probabilities.max(axis=0))


def test_the_central_band_is_numpys_quantile_and_sits_inside_the_min_max_band() -> None:
    """D2's band: the central ``1 - 2 alpha`` of 32 members, per outcome."""
    rng = np.random.default_rng(32)
    table = rng.integers(1, 200, size=(32, 4))
    members = [counts({format(i, "02b"): int(v) for i, v in enumerate(row)}) for row in table]
    probabilities = table / table.sum(axis=1, keepdims=True)

    central = interval_band(members, alpha=0.1)
    outer = interval_band(members, alpha=0.0)

    expected = np.quantile(probabilities, [0.1, 0.9], axis=0, method="linear")
    assert np.array_equal(central.lower, expected[0])
    assert np.array_equal(central.upper, expected[1])
    assert central.alpha == 0.1 and central.n_members == 32
    assert np.all(outer.lower <= central.lower) and np.all(central.upper <= outer.upper)
    assert np.any(outer.lower < central.lower) and np.any(central.upper < outer.upper)


def test_the_method_is_passed_to_numpy_and_stored() -> None:
    members = example_members()

    linear = interval_band(members, alpha=0.25)
    lower = interval_band(members, alpha=0.25, method="lower")

    assert lower.method == "lower"
    assert not np.array_equal(linear.lower, lower.lower)
    probabilities = np.array([[40, 30, 20, 10], [60, 20, 10, 10], [50, 30, 20, 0]]) / 100
    assert np.array_equal(lower.lower, np.quantile(probabilities, 0.25, axis=0, method="lower"))


def test_a_central_band_need_not_contain_the_member_mean() -> None:
    """Bengisu's counterexample (PR-A plan, section 11): 31 members at 0.1 and one at 0.9.

    The 10th and 90th percentiles are both 0.1, the mean is 0.125, and the
    band is reported as it is, not widened to take the mean in.
    """
    members = [counts({"0": 9, "1": 1})] * 31 + [counts({"0": 1, "1": 9})]

    band = interval_band(members, alpha=0.1)

    index = band.support.index("1")
    assert band.lower[index] == 0.1 and band.upper[index] == 0.1
    mean = sum(1 / 10 if i < 31 else 9 / 10 for i in range(32)) / 32
    assert mean == pytest.approx(0.125)
    assert not band.lower[index] <= mean <= band.upper[index]


def test_density_matrix_members_use_qiskits_bit_order() -> None:
    """Outcome ``"01"`` is qubit 0 in state 1: index 1 of the diagonal, rightmost character.

    The convention is taken from Qiskit itself, so an asymmetric state pins it:
    ``X`` on qubit 0 of two qubits.
    """
    circuit = QuantumCircuit(2)
    circuit.x(0)
    qiskit_probabilities = DensityMatrix.from_instruction(circuit).probabilities_dict()
    assert qiskit_probabilities == {"01": pytest.approx(1.0)}
    excited = SimulationResult(
        shots=1,
        backend_label="test",
        density_matrix=np.asarray(DensityMatrix.from_instruction(circuit).data),
    )

    band = interval_band([excited, state([0.0, 0.5, 0.25, 0.25])], alpha=0.0)

    assert band.support == ("00", "01", "10", "11")
    assert band.lower.tolist() == [0.0, 0.5, 0.0, 0.0]
    assert band.upper.tolist() == [0.0, 1.0, 0.25, 0.25]


def test_density_matrix_members_must_agree_on_the_number_of_qubits() -> None:
    with pytest.raises(ValueError, match="same shape"):
        interval_band([state([0.5, 0.5]), state([0.25, 0.25, 0.25, 0.25])], alpha=0.0)


def test_a_density_matrix_that_is_not_a_qubit_register_is_refused() -> None:
    with pytest.raises(ValueError, match="power of two"):
        interval_band([state([0.5, 0.25, 0.25]), state([0.5, 0.25, 0.25])], alpha=0.0)


def test_a_rounding_level_negative_diagonal_is_clamped_and_a_real_one_is_refused() -> None:
    """A simulator can return ``-1e-17`` for an exact zero; ``-1e-6`` is not a state."""
    band = interval_band([state([1.0 + 1e-17, -1e-17]), state([0.5, 0.5])], alpha=0.0)
    assert band.lower.tolist() == [0.5, 0.0]
    assert band.upper.tolist() == [1.0, 0.5]

    with pytest.raises(ValueError, match="diagonal"):
        interval_band([state([1.000001, -1e-6]), state([0.5, 0.5])], alpha=0.0)


def test_a_complex_diagonal_is_refused() -> None:
    """A diagonal with an imaginary part is not a probability vector; nothing is discarded."""
    matrix = np.array([[0.5 + 0.1j, 0.0], [0.0, 0.5 - 0.1j]], dtype=np.complex128)
    complex_diagonal = SimulationResult(shots=1, backend_label="test", density_matrix=matrix)

    with pytest.raises(ValueError, match="diagonal"):
        interval_band([complex_diagonal, state([0.5, 0.5])], alpha=0.0)


def test_a_matrix_whose_trace_is_not_one_is_refused() -> None:
    """The diagonal is read as probabilities with no renormalisation, so it must sum to 1."""
    with pytest.raises(ValueError, match="trace"):
        interval_band([state([0.25, 0.25]), state([0.5, 0.5])], alpha=0.0)


def test_an_empty_counts_member_is_refused() -> None:
    empty = SimulationResult(shots=1, backend_label="test", counts=Counter())
    with pytest.raises(ValueError, match="empty"):
        interval_band([empty, counts({"0": 1})], alpha=0.0)


def test_a_negative_count_is_refused() -> None:
    """A ``Counter`` can hold one; a band or a coverage built on it would mean nothing."""
    negative = SimulationResult(
        shots=5, backend_label="test", counts=Counter({"0": 3, "1": 3, "2": -1})
    )

    with pytest.raises(ValueError, match="non-negative"):
        interval_band([negative, counts({"0": 1, "1": 1, "2": 1})], alpha=0.0)


# --------------------------------------------------------------------------
# 2. IntervalBand, the value (acceptance criterion 5)
# --------------------------------------------------------------------------


def _band(**overrides: object) -> IntervalBand:
    fields: dict[str, object] = {
        "support": ("0", "1"),
        "lower": np.array([0.2, 0.3]),
        "upper": np.array([0.4, 0.8]),
        "alpha": 0.1,
        "method": "linear",
        "n_members": 32,
    }
    fields.update(overrides)
    return IntervalBand(**fields)  # type: ignore[arg-type]


def test_a_valid_band_is_accepted() -> None:
    band = _band()
    assert band.support == ("0", "1")
    assert band.lower.dtype == np.float64 and band.upper.dtype == np.float64


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"lower": np.array([0.5, 0.3])}, "lower <= upper"),
        ({"lower": np.array([-0.1, 0.3])}, r"\[0, 1\]"),
        ({"upper": np.array([0.4, 1.1])}, r"\[0, 1\]"),
        ({"lower": np.array([math.nan, 0.3])}, "finite"),
        ({"upper": np.array([0.4, math.inf])}, "finite"),
        ({"lower": np.array([0.2])}, "length"),
        ({"upper": np.array([0.4, 0.8, 0.9])}, "length"),
        ({"support": ("0", "1", "2")}, "length"),
        ({"support": ("0", "0")}, "distinct"),
        ({"lower": np.array([[0.2, 0.3]]), "upper": np.array([[0.4, 0.8]])}, "one-dimensional"),
        ({"alpha": 0.5}, "alpha"),
        ({"alpha": -0.01}, "alpha"),
        ({"alpha": math.nan}, "alpha"),
        ({"n_members": 1}, "at least two members"),
        ({"method": ""}, "method"),
    ],
)
def test_an_invalid_band_is_refused(overrides: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _band(**overrides)


def test_a_band_copies_and_freezes_its_arrays() -> None:
    """The defect of issue #148, not repeated here: the caller's arrays stay the caller's."""
    lower, upper = np.array([0.2, 0.3]), np.array([0.4, 0.8])

    band = _band(lower=lower, upper=upper)
    lower[0] = 0.9
    upper[1] = 0.0

    assert band.lower.tolist() == [0.2, 0.3] and band.upper.tolist() == [0.4, 0.8]
    with pytest.raises(ValueError, match="read-only"):
        band.lower[0] = 0.0
    with pytest.raises(ValueError, match="read-only"):
        band.upper[0] = 1.0


# --------------------------------------------------------------------------
# 3. IntervalCoverage: ADR-022's six properties (acceptance criterion 6)
# --------------------------------------------------------------------------


def test_coverage_is_named_and_is_not_a_benchmark_metric() -> None:
    """FR-9: a band is not a ``SimulationResult``, so the two-result ABC does not fit."""
    metric = IntervalCoverage()
    assert metric.name == "interval_coverage"
    assert not isinstance(metric, BenchmarkMetric)


@pytest.mark.parametrize(
    "reference",
    [
        counts(REFERENCE_Q),
        counts({format(i, "03b"): 1 for i in range(7)}),  # sevenths do not sum to 1.0 in floats
        counts({"0": 1, "1": 2}),
        counts({"00": 3, "01": 11, "10": 17, "11": 23}),
        state([1 / 7, 2 / 7, 3 / 7, 1 / 7]),
        state([0.1, 0.2, 0.3, 0.4]),
        # A trace of 1 + 1e-10, inside the accepted tolerance: dividing the
        # diagonal by it would move every probability off the band's edge.
        state([0.25, 0.25, 0.25, 0.25 + 1e-10]),
    ],
    ids=[
        "ticket_example",
        "sevenths",
        "thirds",
        "primes",
        "state_sevenths",
        "state_tenths",
        "state_trace_off",
    ],
)
def test_adr022_property_1_identity(reference: SimulationResult) -> None:
    """A zero-width band at ``q`` covers all of ``q``: exactly 1.0, no tolerance."""
    band = interval_band([reference, reference], alpha=0.0)

    assert IntervalCoverage().compute(band, reference) == 1.0


def test_adr022_property_2_asymmetry() -> None:
    """Coverage takes a band and a point; swapping the roles of two ensembles changes it."""
    wide = [counts({"0": 20, "1": 80}), counts({"0": 80, "1": 20})]
    narrow = [counts({"0": 55, "1": 45}), counts({"0": 57, "1": 43})]
    metric = IntervalCoverage()

    wide_covers_narrow = metric.compute(interval_band(wide, alpha=0.0), summed(narrow))
    narrow_covers_wide = metric.compute(interval_band(narrow, alpha=0.0), summed(wide))

    assert wide_covers_narrow == 1.0
    assert narrow_covers_wide == 0.0
    assert wide_covers_narrow != narrow_covers_wide


def test_adr022_property_3_bounds() -> None:
    """Coverage is a share of the reference's mass, so it lies in ``[0, 1]``."""
    rng = np.random.default_rng(22)
    metric = IntervalCoverage()
    seen = set()
    for _ in range(300):
        n_members = int(rng.integers(2, 12))
        members = [
            counts({format(i, "02b"): int(v) + (i == 0) for i, v in enumerate(row)})
            for row in rng.integers(0, 30, size=(n_members, 4))
        ]
        reference = counts(
            {format(i, "02b"): int(v) + (i == 3) for i, v in enumerate(rng.integers(0, 30, 4))}
        )
        value = metric.compute(interval_band(members, alpha=float(rng.uniform(0, 0.4))), reference)
        assert 0.0 <= value <= 1.0
        seen.add(value)
    # Not vacuous: the sample reaches both ends and the interior.
    assert 0.0 in seen and 1.0 in seen and any(0.0 < value < 1.0 for value in seen)


def test_adr022_property_4_monotonicity_under_band_widening() -> None:
    """Nested bands: the wider one covers at least as much of any reference."""
    rng = np.random.default_rng(4)
    metric = IntervalCoverage()
    strictly_more = 0
    for _ in range(300):
        members = [
            counts({format(i, "02b"): int(v) + 1 for i, v in enumerate(row)})
            for row in rng.integers(0, 40, size=(16, 4))
        ]
        reference = counts(
            {format(i, "02b"): int(v) + 1 for i, v in enumerate(rng.integers(0, 40, 4))}
        )
        coverages = [
            metric.compute(interval_band(members, alpha=alpha), reference)
            for alpha in (0.4, 0.25, 0.1, 0.0)
        ]
        assert coverages == sorted(coverages)
        strictly_more += coverages[0] < coverages[-1]
    assert strictly_more > 0


def _depolarized(
    p: float, *, shots: int | None = None, seed: int | None = None
) -> SimulationResult:
    """``X`` on ``|0>`` then Aer's one-qubit depolarizing error of strength ``p``.

    The exact outcome probabilities are ``(p / 2, 1 - p / 2)`` for ``("0", "1")``.
    ``shots=None`` returns the exact density matrix.
    """
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.measure_all()
    model = NoiseModel(basis_gates=["x"])
    if p:
        model.add_quantum_error(depolarizing_error(p, 1), "x", [0])
    if shots is None:
        return simulate_reference([circuit], model, basis_gates=["x"], mode="density_matrix")[0]
    return simulate_reference([circuit], model, basis_gates=["x"], shots=shots, seed=seed)[0]


def test_adr022_property_4_monotonicity_with_aers_depolarizing_noise_exact() -> None:
    """Members at ``p`` in ``{0.1, 0.2, 0.3}``: a reference is covered iff its ``p`` is in range.

    Density-matrix mode, so no shot noise. Coverage is 1 inside the members'
    range, edges included, and 0 outside, so it never increases as the
    reference's ``p`` moves away from the range.
    """
    band = interval_band([_depolarized(p) for p in (0.1, 0.2, 0.3)], alpha=0.0)
    metric = IntervalCoverage()

    assert band.support == ("0", "1")
    assert band.lower == pytest.approx([0.05, 0.85]) and band.upper == pytest.approx([0.15, 0.95])
    inside = [metric.compute(band, _depolarized(p)) for p in (0.1, 0.15, 0.2, 0.25, 0.3)]
    below = [metric.compute(band, _depolarized(p)) for p in (0.09, 0.05, 0.0)]
    above = [metric.compute(band, _depolarized(p)) for p in (0.31, 0.5, 0.9)]
    assert inside == [1.0] * 5
    assert below == [0.0] * 3
    assert above == [0.0] * 3


def test_adr022_property_4_monotonicity_with_aers_depolarizing_noise_counts() -> None:
    """The same statement at 20,000 shots, with references more than 3 sigma from an edge.

    One standard error of an outcome frequency near 0.1 is about 0.002 here.
    The inside reference (``p = 0.2``, frequency 0.10) is 0.05 from both edges
    and the outside one (``p = 0.6``, frequency 0.30) is 0.15 above the band.
    """
    members = [_depolarized(p, shots=20_000, seed=13 + i) for i, p in enumerate((0.1, 0.3))]
    band = interval_band(members, alpha=0.0)
    metric = IntervalCoverage()

    assert metric.compute(band, _depolarized(0.2, shots=20_000, seed=99)) == 1.0
    assert metric.compute(band, _depolarized(0.6, shots=20_000, seed=99)) == 0.0


def test_adr022_property_5_determinism() -> None:
    """Same members, reference, ``alpha`` and method: the same band and the same coverage."""

    def run() -> tuple[IntervalBand, float]:
        members = [_depolarized(p, shots=4_000, seed=7 + i) for i, p in enumerate((0.1, 0.2, 0.3))]
        band = interval_band(members, alpha=0.1)
        return band, IntervalCoverage().compute(band, _depolarized(0.18, shots=4_000, seed=5))

    (band_a, value_a), (band_b, value_b) = run(), run()

    assert band_a.support == band_b.support
    assert np.array_equal(band_a.lower, band_b.lower)
    assert np.array_equal(band_a.upper, band_b.upper)
    assert value_a == value_b


def test_adr022_property_6_reference_value() -> None:
    """The ticket's hand-derived example: outcomes 00, 10 and 11 are inside, 01 is not.

    Mass-weighted coverage is ``0.50 + 0.10 + 0.05 = 0.65`` exactly; a count of
    covered outcomes would give ``3 / 4``, which this value rules out.
    """
    band = interval_band(example_members(), alpha=0.0)

    value = IntervalCoverage().compute(band, counts(REFERENCE_Q))

    assert value == 0.65
    assert value != 0.75


# --------------------------------------------------------------------------
# 4. IntervalCoverage: edges, support and input checks
# --------------------------------------------------------------------------


def test_both_edges_are_inclusive() -> None:
    """A reference sitting exactly on the lower or the upper edge is inside (section 6.3)."""
    band = interval_band([counts({"0": 40, "1": 60}), counts({"0": 60, "1": 40})], alpha=0.0)
    metric = IntervalCoverage()

    assert metric.compute(band, counts({"0": 40, "1": 60})) == 1.0
    assert metric.compute(band, counts({"0": 60, "1": 40})) == 1.0
    assert metric.compute(band, counts({"0": 39, "1": 61})) == 0.0
    assert metric.compute(band, counts({"0": 61, "1": 39})) == 0.0


def test_reference_mass_on_an_outcome_no_member_saw_is_uncovered() -> None:
    """The band there is ``[0, 0]``; the mass counts against coverage and nothing is dropped."""
    band = interval_band([counts({"00": 50, "01": 50}), counts({"00": 60, "01": 40})], alpha=0.0)
    assert band.support == ("00", "01")

    value = IntervalCoverage().compute(band, counts({"00": 55, "01": 25, "11": 20}))

    assert value == 0.55  # 00 is inside; 01 is below the band; 11 was never seen


def test_a_zero_count_outcome_in_the_reference_changes_nothing() -> None:
    band = interval_band([counts({"00": 50, "01": 50}), counts({"00": 60, "01": 40})], alpha=0.0)
    metric = IntervalCoverage()

    with_zero = metric.compute(band, counts({"00": 55, "01": 45, "11": 0}))

    assert with_zero == metric.compute(band, counts({"00": 55, "01": 45})) == 1.0


def test_a_density_matrix_reference_is_scored_against_a_counts_band() -> None:
    """The reference's exact probabilities against sampled members: the same outcome keys."""
    band = interval_band([counts({"0": 40, "1": 60}), counts({"0": 60, "1": 40})], alpha=0.0)

    assert IntervalCoverage().compute(band, state([0.5, 0.5])) == 1.0
    assert IntervalCoverage().compute(band, state([0.3, 0.7])) == 0.0


def test_a_reference_on_another_register_is_refused() -> None:
    """Three-bit outcomes against a two-bit band would otherwise score a silent zero."""
    band = interval_band([counts({"00": 1, "01": 1}), counts({"00": 1, "11": 1})], alpha=0.0)

    with pytest.raises(ValueError, match="outcome keys"):
        IntervalCoverage().compute(band, counts({"000": 1, "001": 1}))


def test_an_empty_reference_is_refused() -> None:
    band = interval_band([counts({"0": 1, "1": 1}), counts({"0": 1, "1": 3})], alpha=0.0)
    empty = SimulationResult(shots=1, backend_label="test", counts=Counter())

    with pytest.raises(ValueError, match="empty"):
        IntervalCoverage().compute(band, empty)


def test_a_reference_with_a_negative_count_is_refused() -> None:
    """Without the refusal this reference scores 1.2: both positive outcomes are covered."""
    band = interval_band(
        [counts({"0": 3, "1": 3, "2": 0}), counts({"0": 3, "1": 3, "2": 0})], alpha=0.0
    )
    wide = IntervalBand(
        support=band.support,
        lower=np.zeros(3),
        upper=np.ones(3),
        alpha=0.0,
        method="linear",
        n_members=2,
    )
    negative = SimulationResult(
        shots=5, backend_label="test", counts=Counter({"0": 3, "1": 3, "2": -1})
    )

    with pytest.raises(ValueError, match="non-negative"):
        IntervalCoverage().compute(wide, negative)


def test_coverage_reads_the_band_it_is_given(recwarn: pytest.WarningsRecorder) -> None:
    """A hand-built band, not only one from ``interval_band``: FR-9's signature."""
    band = IntervalBand(
        support=("0", "1"),
        lower=np.array([0.0, 0.5]),
        upper=np.array([0.2, 1.0]),
        alpha=0.0,
        method="linear",
        n_members=2,
    )
    probabilities: npt.NDArray[np.float64] = np.array([0.25, 0.75])

    value = IntervalCoverage().compute(band, state(probabilities.tolist()))

    assert value == 0.75  # outcome 0 at 0.25 is above [0, 0.2]; outcome 1 is inside
    assert len(recwarn) == 0
