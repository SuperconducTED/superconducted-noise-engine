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

import copy
import math
from typing import Any

import numpy as np
import numpy.typing as npt
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
from superconducted.integration.perturbation import IdentityPerturbation
from superconducted.interfaces import (
    CalibrationFeatureExtractor,
    Defuzzifier,
    MemberPerturbation,
    RuleBase,
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
#: #64. Step 1 had only the empty set (commit ``75b86dbb``); the wiring step
#: added the spellings of "no perturbation" it introduced, and the tests of
#: section 1 run unchanged on each. The generator in the last entry is shared
#: between tests on purpose: an identity perturbation must not read it.
IDENTITY_KWARGS: list[dict[str, Any]] = [
    {},
    {"perturbation": None},
    {"perturbation": IdentityPerturbation()},
    {"perturbation": IdentityPerturbation(), "rng": np.random.default_rng(64)},
]
IDENTITY_IDS = ["no_keyword", "none", "identity", "identity_seeded"]

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


# --------------------------------------------------------------------------
# 2. The interface and the identity (acceptance criterion 2, for the identity)
# --------------------------------------------------------------------------


class _Shifted(CalibrationFeatureExtractor):
    """The wrapped extractor's output plus a fixed shift, in the wrapped units.

    A test double for section 3, so the seeding is tested before the real
    wrapper exists. ``names`` and ``dim`` override what it reports, for the
    contract tests.
    """

    def __init__(
        self,
        wrapped: CalibrationFeatureExtractor,
        shift: npt.NDArray[np.float64],
        *,
        names: tuple[str, ...] | None = None,
        dim: int | None = None,
    ) -> None:
        self._wrapped = wrapped
        self._shift = shift
        self._names = names
        self._dim = dim

    def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
        return self._wrapped.extract(snapshot) + self._shift

    @property
    def output_dim(self) -> int:
        return self._wrapped.output_dim if self._dim is None else self._dim

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self._wrapped.feature_names if self._names is None else self._names


#: Seconds. A twentieth of the fixture's ``mean_T1`` (about 1.55e-4 s). A smoke
#: value chosen only so that members differ; nothing reads it as a physical scale.
T1_SHIFT_PER_SIGMA = 7.5e-6


class _RecordingJitter(MemberPerturbation):
    """Shift ``mean_T1`` by ``T1_SHIFT_PER_SIGMA`` times a standard normal; record each call."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, npt.NDArray[np.float64], Any, Any, Any]] = []

    def perturb(
        self,
        index: int,
        rng: np.random.Generator,
        *,
        feature_extractor: CalibrationFeatureExtractor,
        rule_base: RuleBase,
        defuzzifier: Defuzzifier,
    ) -> tuple[CalibrationFeatureExtractor, RuleBase, Defuzzifier]:
        draw = rng.standard_normal(3)
        self.calls.append((index, draw.copy(), feature_extractor, rule_base, defuzzifier))
        shift = np.array([T1_SHIFT_PER_SIGMA * draw[0], 0.0, 0.0])
        return _Shifted(feature_extractor, shift), rule_base, defuzzifier


class _ContractBreaker(MemberPerturbation):
    """Returns a tuple that breaks FR-1's shape contract in the way ``mode`` names."""

    def __init__(self, mode: str, other_rule_base: RuleBase) -> None:
        self._mode = mode
        self._other = other_rule_base

    def perturb(
        self,
        index: int,
        rng: np.random.Generator,
        *,
        feature_extractor: CalibrationFeatureExtractor,
        rule_base: RuleBase,
        defuzzifier: Defuzzifier,
    ) -> tuple[CalibrationFeatureExtractor, RuleBase, Defuzzifier]:
        zero = np.zeros(3)
        if self._mode == "feature_names":
            return _Shifted(feature_extractor, zero, names=("a", "b", "c")), rule_base, defuzzifier
        if self._mode == "extractor_output_dim":
            return _Shifted(feature_extractor, zero, dim=4), rule_base, defuzzifier
        return feature_extractor, self._other, defuzzifier


def test_member_perturbation_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        MemberPerturbation()  # type: ignore[abstract]


def test_identity_returns_the_same_objects_and_draws_nothing(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """The identity hands back its three inputs, reads no randomness, mutates nothing."""
    deps = _dependencies(benchmark_snapshot, RULE_BASE_SEED)
    extractor = deps["feature_extractor"]
    rule_base = deps["rule_base"]
    defuzzifier = deps["defuzzifier"]
    consequents = [rule.consequent_params.copy() for rule in rule_base.rules]
    rng = np.random.default_rng(3)
    state = copy.deepcopy(rng.bit_generator.state)

    out = IdentityPerturbation().perturb(
        7, rng, feature_extractor=extractor, rule_base=rule_base, defuzzifier=defuzzifier
    )

    assert out[0] is extractor and out[1] is rule_base and out[2] is defuzzifier
    assert rng.bit_generator.state == state
    assert all(
        np.array_equal(rule.consequent_params, before)
        for rule, before in zip(rule_base.rules, consequents, strict=True)
    )


# --------------------------------------------------------------------------
# 3. Ensemble seeding (acceptance criterion 3)
# --------------------------------------------------------------------------


def test_each_member_gets_its_index_the_base_objects_and_its_own_stream(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """Member ``i`` is perturbed from the ensemble's own dependencies, never from member ``i - 1``'s."""
    jitter = _RecordingJitter()
    deps = _dependencies(benchmark_snapshot, RULE_BASE_SEED)
    ensemble = FuzzyNoiseModelEnsemble(
        **deps, ensemble_size=4, perturbation=jitter, rng=np.random.default_rng(11)
    )

    members = list(ensemble)

    assert len(ensemble) == 4 and len(members) == 4
    assert [call[0] for call in jitter.calls] == [0, 1, 2, 3]
    for _, _, extractor, rule_base, defuzzifier in jitter.calls:
        assert extractor is deps["feature_extractor"]
        assert rule_base is deps["rule_base"]
        assert defuzzifier is deps["defuzzifier"]
    draws = [call[1] for call in jitter.calls]
    assert all(not np.array_equal(draws[0], other) for other in draws[1:])


def test_member_streams_are_the_spawned_children_of_the_callers_seed_sequence(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """FR-6's derivation, pinned exactly: child ``i`` of ``rng.bit_generator.seed_seq``."""
    jitter = _RecordingJitter()
    list(_ensemble(benchmark_snapshot, 4, perturbation=jitter, rng=np.random.default_rng(11)))

    children = np.random.default_rng(11).bit_generator.seed_seq.spawn(4)
    expected = [np.random.default_rng(child).standard_normal(3) for child in children]

    assert len(jitter.calls) == 4
    assert all(
        np.array_equal(call[1], draw) for call, draw in zip(jitter.calls, expected, strict=True)
    )


def test_perturbed_members_differ_and_the_returned_tuple_is_what_builds_them(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """Each member's ``crisp_params`` is the model of the tuple ``perturb`` returned for it."""
    jitter = _RecordingJitter()
    deps = _dependencies(benchmark_snapshot, RULE_BASE_SEED)
    members = list(
        FuzzyNoiseModelEnsemble(
            **deps, ensemble_size=4, perturbation=jitter, rng=np.random.default_rng(11)
        )
    )

    params = [member.crisp_params for member in members]
    assert all(not np.array_equal(params[0], other) for other in params[1:])
    for member, call in zip(members, jitter.calls, strict=True):
        shift = np.array([T1_SHIFT_PER_SIGMA * call[1][0], 0.0, 0.0])
        direct = FuzzyNoiseModel(
            **{**deps, "feature_extractor": _Shifted(deps["feature_extractor"], shift)}
        )
        assert np.array_equal(member.crisp_params, direct.crisp_params)


def test_iterating_a_perturbed_ensemble_twice_gives_identical_members(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """The stored seed sequences are not consumed by drawing (the ticket's FR-6 note)."""
    jitter = _RecordingJitter()
    ensemble = _ensemble(benchmark_snapshot, 4, perturbation=jitter, rng=np.random.default_rng(11))

    first = [member.crisp_params.copy() for member in ensemble]
    second = [member.crisp_params.copy() for member in ensemble]

    assert all(np.array_equal(a, b) for a, b in zip(first, second, strict=True))
    assert len(jitter.calls) == 8
    assert all(np.array_equal(jitter.calls[i][1], jitter.calls[i + 4][1]) for i in range(4))


def test_two_constructions_from_one_seed_agree_and_another_seed_differs(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    def build(seed: int) -> list[npt.NDArray[np.float64]]:
        ensemble = _ensemble(
            benchmark_snapshot,
            4,
            perturbation=_RecordingJitter(),
            rng=np.random.default_rng(seed),
        )
        return [member.crisp_params for member in ensemble]

    assert all(np.array_equal(a, b) for a, b in zip(build(11), build(11), strict=True))
    assert not all(np.array_equal(a, b) for a, b in zip(build(11), build(12), strict=True))


def test_build_stays_a_pure_function_of_the_seed_under_a_perturbation(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """``first_viable_seed`` needs ``build(seed)`` to depend on the seed and nothing else."""

    def build(seed: int) -> list[FuzzyNoiseModel]:
        return list(
            FuzzyNoiseModelEnsemble(
                **_dependencies(benchmark_snapshot, seed),
                ensemble_size=3,
                perturbation=_RecordingJitter(),
                rng=np.random.default_rng(seed),
            )
        )

    first, seed_a = first_viable_seed(build)
    second, seed_b = first_viable_seed(build)

    assert seed_a == seed_b
    assert all(
        np.array_equal(a.crisp_params, b.crisp_params) for a, b in zip(first, second, strict=True)
    )


def test_construction_and_iteration_leave_the_callers_stream_untouched(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """Members draw from spawned children; the caller's generator yields what it would have."""
    rng = np.random.default_rng(11)
    state = copy.deepcopy(rng.bit_generator.state)

    list(_ensemble(benchmark_snapshot, 4, perturbation=_RecordingJitter(), rng=rng))

    assert rng.bit_generator.state == state
    assert rng.standard_normal() == np.random.default_rng(11).standard_normal()


def test_an_unseeded_non_identity_perturbation_is_refused(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """An unseeded perturbed ensemble could not be reproduced (ADR-024's lesson)."""
    with pytest.raises(ValueError, match="needs a seeded rng"):
        _ensemble(benchmark_snapshot, 4, perturbation=_RecordingJitter())
    with pytest.raises(ValueError, match="needs a seeded rng"):
        _ensemble(benchmark_snapshot, 4, perturbation=_RecordingJitter(), rng=None)

    # The identity needs no seed: it reads no randomness.
    assert len(_ensemble(benchmark_snapshot, 4, perturbation=IdentityPerturbation())) == 4
    assert len(_ensemble(benchmark_snapshot, 4, perturbation=None, rng=None)) == 4


class _SeedSequenceWithoutSpawn(np.random.bit_generator.ISeedSequence):
    """A legal seed for a bit generator that cannot produce children."""

    def generate_state(
        self, n_words: int, dtype: type[np.uint32] | type[np.uint64] = np.uint32
    ) -> npt.NDArray[Any]:
        return np.random.SeedSequence(1).generate_state(n_words, dtype)


def test_a_generator_whose_seed_sequence_cannot_spawn_is_refused(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """Named at construction, instead of an ``AttributeError`` from inside numpy."""
    rng = np.random.Generator(np.random.PCG64(_SeedSequenceWithoutSpawn()))

    with pytest.raises(ValueError, match="spawnable seed sequence"):
        _ensemble(benchmark_snapshot, 4, perturbation=_RecordingJitter(), rng=rng)


@pytest.mark.parametrize(
    ("mode", "match"),
    [
        ("feature_names", "feature_names"),
        ("extractor_output_dim", "output_dim"),
        ("rule_base_output_dim", "output_dim"),
        ("rule_base_input_dim", "input_dim"),
    ],
)
def test_a_perturbation_that_breaks_the_shape_contract_is_refused(
    benchmark_snapshot: CalibrationSnapshot, mode: str, match: str
) -> None:
    """FR-1: the returned extractor and rule base keep the base objects' names and dimensions."""
    inputs, outputs = (2, 2) if mode == "rule_base_input_dim" else (3, 3)
    mfs = [[GaussianMF(center=0.0, sigma=1.0)] for _ in range(inputs)]
    other = TSKRuleBase.from_grid(per_input_mfs=mfs, output_dim=outputs)
    ensemble = _ensemble(
        benchmark_snapshot,
        2,
        perturbation=_ContractBreaker(mode, other),
        rng=np.random.default_rng(0),
    )

    with pytest.raises(ValueError, match=match):
        list(ensemble)
