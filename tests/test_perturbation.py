"""Member perturbation and ensemble seeding (issue #64, PR-A1).

Section 1 is the identity pin. It was written and committed before the
ensemble's wiring changed, against the code ``main`` had at ``cd277a64``, so
history shows it passing on the old ``__iter__``. Everything after it must
keep it green: with no perturbation the ensemble yields the members it
yielded before #64.

The pin is relational where it is exact. A member's ``crisp_params`` is
compared bit for bit with a :class:`FuzzyNoiseModel` built directly from the
same dependencies, which holds on any machine. The literal values are a
second, looser check under a stated tolerance, because a libm difference
between machines moves the last digits (PR #149 measured 3.7e-14 between the
laptop and the desktop on another quantity).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from superconducted.benchmarks.circuits import ghz_state_circuit
from superconducted.benchmarks.harness import simulate_engine
from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.calibration.loader import UNIT_SCALE
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.defuzzification import WeightedAverageDefuzzifier
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.integration.aer_factory import (
    FuzzyNoiseModel,
    FuzzyNoiseModelEnsemble,
    first_viable_seed,
)
from superconducted.types import CalibrationSnapshot

DEVICE_BASIS = ("cz", "id", "rx", "rz", "sx", "x")

#: Seed of the rule base's random consequents. ``first_viable_seed`` returns it
#: for this grid on the committed fixture; the first test asserts that, so a
#: change in the search shows up there and not as a confusing value mismatch.
RULE_BASE_SEED = 1

#: ``crisp_params`` (gamma, lambda; dimensionless probabilities) of every member
#: of the default ensemble on the gate-bearing ``ibm_fez`` fixture with the
#: grid below and ``RULE_BASE_SEED``. Captured on the laptop (Python 3.12.10,
#: NumPy 2.4.4) at ``main`` ``cd277a64``, before #64 touched ``__iter__``.
PINNED_CRISP_PARAMS = (0.0010631876854835232, 0.018299147946441743)

#: Relative tolerance for the literal above. It covers a last-digits libm
#: difference between machines and nothing larger: the smallest effect #64 is
#: built to produce, a member moved by a relative jitter of 1e-3, is many
#: orders of magnitude above it.
PIN_RTOL = 1e-9


def _dependencies(snapshot: CalibrationSnapshot, seed: int) -> dict[str, Any]:
    """The seven injected dependencies of one model, as constructor keywords.

    The ratified 3x3x3 Gaussian grid, laid out as ``tests/conftest.py`` does
    for issue #58: per feature, three centres evenly spaced over the range of
    the fixture's per-qubit values and ``sigma`` a quarter of that range, in
    the vectorizer's units (SI seconds for T1 and T2, dimensionless for the
    readout error). Consequents are a seeded random draw (ADR-024).
    """
    per_input_mfs: list[list[GaussianMF]] = []
    for field in ("T1", "T2", "readout_error"):
        values = [
            float(entry["value"]) * UNIT_SCALE[str(entry["unit"])]
            for qubit in snapshot.properties["qubits"]
            for entry in qubit
            if entry.get("name") == field
            and entry.get("value") is not None
            and math.isfinite(float(entry["value"]))
        ]
        lo, hi = min(values), max(values)
        sigma = (hi - lo) * 0.25
        per_input_mfs.append(
            [GaussianMF(center=float(center), sigma=sigma) for center in np.linspace(lo, hi, 3)]
        )
    return {
        "calibration": snapshot,
        "feature_extractor": BasicCalibrationVectorizer(),
        "rule_base": TSKRuleBase.from_grid(
            per_input_mfs=per_input_mfs,
            output_dim=2,
            consequent_init="random",
            rng=np.random.default_rng(seed),
        ),
        "defuzzifier": WeightedAverageDefuzzifier(),
        "squashing": ProbabilityClip(),
        "channel_projector": KrausChannelProjector(NoOpNormalization()),
        "fuzzification_strategy": PostGateFuzzification(),
    }


def _ensemble(
    snapshot: CalibrationSnapshot, size: int, **ensemble_kwargs: Any
) -> FuzzyNoiseModelEnsemble:
    """An ensemble over ``_dependencies``; ``ensemble_kwargs`` reach the constructor."""
    return FuzzyNoiseModelEnsemble(
        **_dependencies(snapshot, RULE_BASE_SEED), ensemble_size=size, **ensemble_kwargs
    )


#: Constructor keywords under which the ensemble must behave as it did before
#: #64. Step 1 has only the empty set; the wiring step adds the spellings of
#: "no perturbation" it introduces, and the tests below run unchanged on each.
IDENTITY_KWARGS: list[dict[str, Any]] = [{}]
IDENTITY_IDS = ["no_keyword"]

# --------------------------------------------------------------------------
# 1. The identity pin (acceptance criterion 1)
# --------------------------------------------------------------------------


def test_the_pinned_seed_is_the_first_viable_one(benchmark_snapshot: CalibrationSnapshot) -> None:
    """The pin's seed is what ``first_viable_seed`` picks, and ``build`` stays pure in it."""

    def build(seed: int) -> list[FuzzyNoiseModel]:
        return list(FuzzyNoiseModelEnsemble(**_dependencies(benchmark_snapshot, seed)))

    members, seed = first_viable_seed(build, context="issue #64 identity pin")

    assert seed == RULE_BASE_SEED
    assert len(members) == 32
    again = build(seed)
    assert all(
        np.array_equal(a.crisp_params, b.crisp_params) for a, b in zip(members, again, strict=True)
    )


@pytest.mark.parametrize("ensemble_kwargs", IDENTITY_KWARGS, ids=IDENTITY_IDS)
def test_every_member_equals_a_directly_built_model(
    benchmark_snapshot: CalibrationSnapshot, ensemble_kwargs: dict[str, Any]
) -> None:
    """Exact on any machine: a member is the model its dependencies give, bit for bit."""
    direct = FuzzyNoiseModel(**_dependencies(benchmark_snapshot, RULE_BASE_SEED))
    ensemble = _ensemble(benchmark_snapshot, 5, **ensemble_kwargs)

    members = list(ensemble)

    assert len(ensemble) == 5
    assert len(members) == 5
    assert not direct.is_degenerate
    for member in members:
        assert member.crisp_params.dtype == np.float64
        assert np.array_equal(member.crisp_params, direct.crisp_params)


@pytest.mark.parametrize("ensemble_kwargs", IDENTITY_KWARGS, ids=IDENTITY_IDS)
def test_members_match_the_values_captured_before_the_wiring_changed(
    benchmark_snapshot: CalibrationSnapshot, ensemble_kwargs: dict[str, Any]
) -> None:
    """The literal pin, under ``PIN_RTOL``; see the module docstring for why not exact."""
    for member in _ensemble(benchmark_snapshot, 3, **ensemble_kwargs):
        assert member.crisp_params.shape == (2,)
        assert member.crisp_params == pytest.approx(PINNED_CRISP_PARAMS, rel=PIN_RTOL, abs=0.0)


@pytest.mark.parametrize("ensemble_kwargs", IDENTITY_KWARGS, ids=IDENTITY_IDS)
def test_iterating_twice_gives_the_same_members(
    benchmark_snapshot: CalibrationSnapshot, ensemble_kwargs: dict[str, Any]
) -> None:
    """One ensemble object, two passes: identical members both times."""
    ensemble = _ensemble(benchmark_snapshot, 4, **ensemble_kwargs)

    first = [member.crisp_params.copy() for member in ensemble]
    second = [member.crisp_params.copy() for member in ensemble]

    assert all(np.array_equal(a, b) for a, b in zip(first, second, strict=True))


@pytest.mark.parametrize("ensemble_kwargs", IDENTITY_KWARGS, ids=IDENTITY_IDS)
def test_identical_members_preserve_the_density_matrix_exactly(
    benchmark_snapshot: CalibrationSnapshot, ensemble_kwargs: dict[str, Any]
) -> None:
    """#58 section 6.3 from this side of the change: ``rho_ens == rho_1`` exactly.

    The mixture of N identical states is that state, and the harness's mean
    reproduces it bit for bit only while the members really are identical.
    ``tests/test_harness.py`` holds the same pin for #58; this one runs on
    every spelling of "no perturbation", so a default path that starts
    perturbing fails here with the perturbation named.
    """
    circuit = ghz_state_circuit(2)
    single = simulate_engine(
        [circuit],
        _ensemble(benchmark_snapshot, 1, **ensemble_kwargs),
        basis_gates=DEVICE_BASIS,
        mode="density_matrix",
    )[0]
    mixture = simulate_engine(
        [circuit],
        _ensemble(benchmark_snapshot, 3, **ensemble_kwargs),
        basis_gates=DEVICE_BASIS,
        mode="density_matrix",
    )[0]

    assert single.density_matrix is not None and mixture.density_matrix is not None
    assert mixture.metadata is not None and all(mixture.metadata["noise_instructions"])
    assert np.array_equal(mixture.density_matrix, single.density_matrix)
