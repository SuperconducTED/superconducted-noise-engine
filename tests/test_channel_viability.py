"""Channel viability under a randomly initialized rule base (ADR-024, Issue #35).

`consequent_init="random"` draws TSK consequents from a zero-mean Gaussian,
so whether the resulting channel does anything is a property of the draw.
These tests pin the three claims ADR-024 rests on:

1. the degeneracy predicate really does identify the identity channel,
2. it is a pipeline property, not a rule-base property, and
3. the failure rate is exactly 1/4 - invariant to rule count, membership
   function placement, and input vector - so a hard-coded seed is a bet,
   not a default.
"""

from __future__ import annotations

import numpy as np
import pytest
from qiskit.quantum_info import Kraus, SuperOp

from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.defuzzification import WeightedAverageDefuzzifier
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.integration.aer_factory import (
    DEFAULT_SEED_SEARCH_LIMIT,
    FuzzyNoiseModel,
    first_viable_seed,
    is_identity_damping,
)
from superconducted.types import CalibrationSnapshot

# Same physical ranges the smoke script uses, so these tests exercise the
# grid the project actually ships rather than a toy one.
FEATURE_SCALES: dict[str, tuple[float, float]] = {
    "mean_T1": (0.0, 100e-6),
    "mean_T2": (0.0, 100e-6),
    "mean_readout_error": (0.0, 0.1),
}


def _model(snapshot: CalibrationSnapshot, seed: int | None) -> FuzzyNoiseModel:
    """One `FuzzyNoiseModel` over the ratified 3x3x3 grid.

    ``seed=None`` selects `consequent_init="zeros"` - the ADR-014 bootstrap
    default, which is degenerate by construction.
    """
    vectorizer = BasicCalibrationVectorizer()
    mfs_list = []
    for name in vectorizer.feature_names:
        lo, hi = FEATURE_SCALES[name]
        sigma = (hi - lo) * 0.25
        mfs_list.append([GaussianMF(center=float(c), sigma=sigma) for c in np.linspace(lo, hi, 3)])

    rule_base = TSKRuleBase.from_grid(
        per_input_mfs=mfs_list,
        output_dim=2,
        consequent_init="zeros" if seed is None else "random",
        rng=None if seed is None else np.random.default_rng(seed),
    )
    return FuzzyNoiseModel(
        calibration=snapshot,
        feature_extractor=vectorizer,
        rule_base=rule_base,
        defuzzifier=WeightedAverageDefuzzifier(),
        squashing=ProbabilityClip(),
        channel_projector=KrausChannelProjector(NoOpNormalization()),
        fuzzification_strategy=PostGateFuzzification(),
    )


# --------------------------------------------------------------------------
# 1. The predicate
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ([0.0, 0.0], True),
        ([0.3, 0.0], False),
        ([0.0, 0.3], False),
        ([0.3, 0.3], False),
        # Entries past the first two are the projector's business, not ours.
        ([0.0, 0.0, 0.9], True),
        ([0.9, 0.0, 0.0], False),
    ],
)
def test_is_identity_damping_truth_table(params: list[float], expected: bool) -> None:
    assert is_identity_damping(np.asarray(params, dtype=np.float64)) is expected


def test_is_identity_damping_rejects_short_vectors() -> None:
    """A one-entry vector is unreadable, not identity - say so precisely.

    `KrausChannelProjector.project` raises on the same input. Reporting it
    as "degenerate" would name the wrong defect and send the caller looking
    at their RNG seed instead of their `output_dim`.
    """
    with pytest.raises(ValueError, match="at least 2 entries"):
        is_identity_damping(np.asarray([0.5], dtype=np.float64))


def test_degenerate_params_project_to_the_identity_channel() -> None:
    """Ground the predicate in the physics rather than in its own definition.

    Compared as a `SuperOp`, because the Kraus representation at
    gamma = lambda = 0 carries a global phase of -1: the operator is -I, not
    +I. That phase is physically unobservable, so a Kraus-level equality
    check would fail on a channel that is genuinely the identity.
    """
    projector = KrausChannelProjector(NoOpNormalization())
    identity = SuperOp(Kraus([np.eye(2)]))

    degenerate = SuperOp(projector.project(np.array([0.0, 0.0]), "x", (0,)).to_quantumchannel())
    assert degenerate == identity
    assert np.abs(degenerate.data - identity.data).max() == 0.0

    live = SuperOp(projector.project(np.array([0.2, 0.1]), "x", (0,)).to_quantumchannel())
    assert live != identity


# --------------------------------------------------------------------------
# 2. Wiring into the model
# --------------------------------------------------------------------------


def test_zeros_init_is_degenerate(dummy_snapshot: CalibrationSnapshot) -> None:
    """The ADR-014 bootstrap default produces a channel that measures nothing."""
    model = _model(dummy_snapshot, seed=None)
    assert model.crisp_params.tolist() == [0.0, 0.0]
    assert model.is_degenerate is True


def test_is_degenerate_agrees_with_both_entries_zero(
    dummy_snapshot: CalibrationSnapshot,
) -> None:
    """Under `ProbabilityClip`, "no positive entry" and "both exactly zero" coincide.

    Issue #35 asks whether "first two crisp parameters non-positive" is even
    the right test. For this pipeline it is exact, and this is the check that
    says so: the clip maps every non-positive raw output to exactly 0.0, so
    the two formulations cannot come apart. They *would* come apart under
    `SigmoidSquashing`, which is why the predicate documents its scope.
    """
    for seed in range(60):
        crisp = _model(dummy_snapshot, seed).crisp_params
        both_zero = bool(crisp[0] == 0.0 and crisp[1] == 0.0)
        assert is_identity_damping(crisp) is both_zero


# --------------------------------------------------------------------------
# 3. The seed search
# --------------------------------------------------------------------------


def test_first_viable_seed_is_deterministic(dummy_snapshot: CalibrationSnapshot) -> None:
    def build(seed: int) -> list[FuzzyNoiseModel]:
        return [_model(dummy_snapshot, seed)]

    members_a, seed_a = first_viable_seed(build)
    members_b, seed_b = first_viable_seed(build)

    assert seed_a == seed_b
    assert not members_a[0].is_degenerate
    assert members_a[0].crisp_params.tolist() == members_b[0].crisp_params.tolist()


def test_first_viable_seed_returns_the_lowest_viable_seed(
    dummy_snapshot: CalibrationSnapshot,
) -> None:
    """Lowest, not merely any - that is what makes the choice reproducible."""
    _members, seed = first_viable_seed(lambda s: [_model(dummy_snapshot, s)])
    for earlier in range(seed):
        assert _model(dummy_snapshot, earlier).is_degenerate


def test_first_viable_seed_rejects_nonpositive_limit(
    dummy_snapshot: CalibrationSnapshot,
) -> None:
    with pytest.raises(ValueError, match="seed_limit must be positive"):
        first_viable_seed(lambda s: [_model(dummy_snapshot, s)], seed_limit=0)


def test_first_viable_seed_reports_structural_degeneracy(
    dummy_snapshot: CalibrationSnapshot,
) -> None:
    """Exhausting the search means a structural fault, not a run of bad luck."""
    with pytest.raises(ValueError, match="not an unlucky run"):
        first_viable_seed(lambda _s: [_model(dummy_snapshot, None)], seed_limit=4)


def test_first_viable_seed_rejects_empty_ensemble(
    dummy_snapshot: CalibrationSnapshot,
) -> None:
    with pytest.raises(ValueError, match="empty ensemble"):
        first_viable_seed(lambda _s: [])


def test_default_seed_search_limit_is_generous() -> None:
    """At a 1/4 failure rate, 64 draws fail together with probability 4**-64."""
    assert DEFAULT_SEED_SEARCH_LIMIT == 64
    assert 0.25**DEFAULT_SEED_SEARCH_LIMIT < 1e-38


# --------------------------------------------------------------------------
# 4. The rate itself - the claim ADR-024 turns on
# --------------------------------------------------------------------------


def _degeneracy_rate(k_per_input: int, x: list[float], n_draws: int, seed: int) -> float:
    """Fraction of random draws that yield an identity channel.

    Deliberately built straight from the primitives rather than from a
    `FuzzyNoiseModel`, so the measurement isolates the rule base, the
    defuzzifier, and the squashing strategy - the three pieces that decide
    the sign - from calibration parsing.
    """
    rng = np.random.default_rng(seed)
    defuzzifier = WeightedAverageDefuzzifier()
    squashing = ProbabilityClip()
    mfs_list = [
        [GaussianMF(center=float(c), sigma=0.25) for c in np.linspace(0.0, 1.0, k_per_input)]
        for _ in x
    ]
    inputs = np.asarray(x, dtype=np.float64)

    degenerate = 0
    for _ in range(n_draws):
        rule_base = TSKRuleBase.from_grid(
            per_input_mfs=mfs_list, output_dim=2, consequent_init="random", rng=rng
        )
        crisp = squashing.squash(defuzzifier.defuzzify(rule_base.evaluate(inputs)))
        degenerate += is_identity_damping(crisp)
    return degenerate / n_draws


@pytest.mark.parametrize(
    ("k_per_input", "inputs", "rng_seed"),
    [
        (2, [0.5, 0.5, 0.5], 12345),  # 8 rules - the pre-Issue-#31 grid
        (3, [0.5, 0.5, 0.5], 12345),  # 27 rules - the ratified ADR-010 grid
        (4, [0.5, 0.5, 0.5], 12345),  # 64 rules - beyond the baseline
        (3, [0.01, 0.99, 0.5], 999),  # ratified grid, lopsided input vector
    ],
)
def test_degeneracy_rate_is_one_quarter(
    k_per_input: int, inputs: list[float], rng_seed: int
) -> None:
    """P(identity channel) = 1/4, invariant to rule count and input vector.

    Issue #35 reported "one draw in four to one in eight" and attributed the
    spread to rule count and input vector. That spread was an eight-sample
    artifact. Rows 0 and 1 of every consequent matrix are disjoint draws from
    the same zero-mean Gaussian, and weighted-average defuzzification is a
    fixed non-negative linear functional of them, so the two crisp outputs
    are i.i.d. zero-mean. Rule count and input vector move their *variance*,
    never their sign, so the rate cannot move either.

    The RNG seed is fixed, so this is deterministic, not flaky. The band is
    roughly +/- 4 standard errors at n = 2000 (s.e. ~= 0.0097) - wide enough
    never to trip on its own, narrow enough to fail loudly if someone makes
    the initialization positive-biased (rate -> 0) or drops the clip.
    """
    rate = _degeneracy_rate(k_per_input, inputs, n_draws=2000, seed=rng_seed)
    assert 0.21 <= rate <= 0.29, f"expected ~0.25, measured {rate}"


def test_first_viable_seed_includes_caller_context(
    dummy_snapshot: CalibrationSnapshot,
) -> None:
    """Callers describe the grid; the search cannot, since `build` is opaque.

    Without this the smoke script had to re-raise and match on message text
    to tell "structural degeneracy" apart from "bad seed_limit".
    """
    with pytest.raises(ValueError, match="27 rules"):
        first_viable_seed(
            lambda _s: [_model(dummy_snapshot, None)],
            seed_limit=2,
            context="Placement was 'endpoint' with 3 MFs per feature (27 rules).",
        )
