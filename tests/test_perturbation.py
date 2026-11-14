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
import dataclasses
import inspect
import math
from typing import Any, cast

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
from superconducted.integration.perturbation import (
    POSITIVE,
    UNIT_INTERVAL,
    FeatureBound,
    IdentityPerturbation,
    InputVectorPerturbation,
    OffsetFeatureExtractor,
    bounds_for,
)
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


# --------------------------------------------------------------------------
# 4. Input-vector jitter (acceptance criterion 4, and criterion 2 for it; step 3,
#    D6 option A, #64 comment 6863593077)
# --------------------------------------------------------------------------

NAMES = ("mean_T1", "mean_T2", "mean_readout_error")

#: A typical ``ibm_fez`` vector in the vectorizer's units: T1 and T2 in SI
#: seconds, the readout error dimensionless.
X = np.array([1.0e-4, 8.0e-5, 0.015])

#: Stand-ins for the rule base and defuzzifier, which the jitter passes through
#: untouched and never calls.
RULE_BASE = cast(RuleBase, object())
DEFUZZIFIER = cast(Defuzzifier, object())


class _ScriptedNormals:
    """Stands in for numpy's ``Generator`` inside ``perturb``.

    Hands out the given rows as successive ``standard_normal(size)`` results
    and records each call's ``size``, so a test can see how many draws were
    made and which one was kept.
    """

    def __init__(self, *rows: list[float]) -> None:
        self._rows = [np.array(row, dtype=np.float64) for row in rows]
        self.sizes: list[Any] = []

    def standard_normal(self, size: Any) -> npt.NDArray[np.float64]:
        self.sizes.append(size)
        if len(self.sizes) > len(self._rows):
            raise AssertionError(f"draw {len(self.sizes)} was not scripted")
        return self._rows[len(self.sizes) - 1].copy()


def _jitter(
    perturbation: InputVectorPerturbation,
    rng: Any,
    extractor: CalibrationFeatureExtractor | None = None,
) -> OffsetFeatureExtractor:
    """Member 0's extractor under ``perturbation``, after checking the pass-through."""
    out = perturbation.perturb(
        0,
        cast(np.random.Generator, rng),
        feature_extractor=extractor or BasicCalibrationVectorizer(),
        rule_base=RULE_BASE,
        defuzzifier=DEFUZZIFIER,
    )
    assert out[1] is RULE_BASE and out[2] is DEFUZZIFIER
    assert isinstance(out[0], OffsetFeatureExtractor)
    return out[0]


def _other_snapshot(snapshot: CalibrationSnapshot) -> CalibrationSnapshot:
    """The same snapshot with qubit 0's T1 raised by half, so its feature vector differs."""
    properties = copy.deepcopy(snapshot.properties)
    for entry in properties["qubits"][0]:
        if entry.get("name") == "T1":
            entry["value"] = float(entry["value"]) * 1.5
    return dataclasses.replace(snapshot, properties=properties)


def test_the_scale_and_r_have_no_default() -> None:
    """File 03 Q2a: no code path picks the scale, so neither entry point offers one."""
    init = inspect.signature(InputVectorPerturbation.__init__).parameters
    relative = inspect.signature(InputVectorPerturbation.relative).parameters
    for parameter in (init["center"], init["scale"], init["bounds"], relative["r"]):
        assert parameter.default is inspect.Parameter.empty
    assert init["max_redraws"].default == 64
    with pytest.raises(TypeError):
        InputVectorPerturbation(X, bounds=bounds_for(NAMES))  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        InputVectorPerturbation.relative(X, feature_names=NAMES)  # type: ignore[call-arg]


def test_relative_sets_the_centre_the_scale_and_the_bounds() -> None:
    perturbation = InputVectorPerturbation.relative(X, 0.1, feature_names=NAMES)

    assert np.array_equal(perturbation.center, X)
    assert np.array_equal(perturbation.scale, 0.1 * np.abs(X))
    assert perturbation.bounds == (POSITIVE, POSITIVE, UNIT_INTERVAL)
    assert perturbation.r == 0.1
    assert perturbation.feature_names == NAMES
    assert perturbation.max_redraws == 64


def test_an_explicit_scale_records_no_r_and_no_names() -> None:
    """The departure written in the step 3 plan: ``r`` reads ``None`` without ``relative``."""
    perturbation = InputVectorPerturbation(X, [1e-6, 1e-6, 1e-3], bounds=bounds_for(NAMES))

    assert perturbation.r is None
    assert perturbation.feature_names is None


def test_the_centre_and_scale_are_copies_and_read_only() -> None:
    x = X.copy()
    perturbation = InputVectorPerturbation.relative(x, 0.1, feature_names=NAMES)
    x[0] = 5.0

    assert perturbation.center[0] == 1.0e-4
    assert perturbation.scale[0] == 0.1 * 1.0e-4
    for array in (perturbation.center, perturbation.scale):
        with pytest.raises(ValueError, match="read-only"):
            array[0] = 1.0
    for name in ("center", "scale", "r", "bounds", "max_redraws", "feature_names"):
        with pytest.raises(AttributeError):
            setattr(perturbation, name, None)


@pytest.mark.parametrize("r", [0, 0.0, -0.1, math.nan, math.inf, True, "0.1"])
def test_relative_refuses_an_r_that_is_not_a_finite_positive_number(r: Any) -> None:
    with pytest.raises(ValueError, match="finite positive"):
        InputVectorPerturbation.relative(X, r, feature_names=NAMES)


def test_relative_needs_one_known_name_per_feature() -> None:
    with pytest.raises(ValueError, match="2 feature names"):
        InputVectorPerturbation.relative(X, 0.1, feature_names=NAMES[:2])
    with pytest.raises(ValueError, match="no bound is defined"):
        InputVectorPerturbation.relative(X, 0.1, feature_names=("mean_T1", "mean_T2", "gate"))


def test_the_bounds_table_and_an_unknown_name() -> None:
    assert bounds_for(NAMES) == (POSITIVE, POSITIVE, UNIT_INTERVAL)
    assert bounds_for(()) == ()
    with pytest.raises(ValueError, match="'foo'"):
        bounds_for(("mean_T1", "foo"))


def test_a_bound_admits_its_closed_ends_and_nothing_non_finite() -> None:
    assert not POSITIVE.contains(0.0)
    assert POSITIVE.contains(5e-324)
    assert not POSITIVE.contains(-5e-324)
    assert not POSITIVE.contains(math.inf)
    assert not POSITIVE.contains(math.nan)
    assert UNIT_INTERVAL.contains(0.0)
    assert UNIT_INTERVAL.contains(1.0)
    assert not UNIT_INTERVAL.contains(math.nextafter(1.0, 2.0))
    assert not UNIT_INTERVAL.contains(-5e-324)
    assert not UNIT_INTERVAL.contains(math.nan)
    # The finiteness rule, not the open end, is what keeps inf out of a closed infinite end.
    closed_to_infinity = FeatureBound(0.0, math.inf, low_open=False, high_open=False)
    assert closed_to_infinity.contains(1.0e300)
    assert not closed_to_infinity.contains(math.inf)
    with pytest.raises(ValueError, match="low <= high"):
        FeatureBound(1.0, 0.0, low_open=False, high_open=False)


@pytest.mark.parametrize(
    "center",
    [
        [0.0, 8.0e-5, 0.015],
        [-1.0e-4, 8.0e-5, 0.015],
        [1.0e-4, 8.0e-5, 1.5],
        [1.0e-4, 8.0e-5, -0.01],
        [math.nan, 8.0e-5, 0.015],
        [1.0e-4, math.inf, 0.015],
    ],
    ids=["t1_zero", "t1_negative", "readout_above_1", "readout_below_0", "nan", "inf"],
)
def test_a_centre_outside_its_bounds_is_refused_at_construction(center: list[float]) -> None:
    """Bengisu's D6 note: the error names the centre, not "redraws exhausted"."""
    with pytest.raises(ValueError, match="center"):
        InputVectorPerturbation(center, [1e-6, 1e-6, 1e-3], bounds=bounds_for(NAMES))


@pytest.mark.parametrize(
    ("scale", "bounds", "max_redraws", "match"),
    [
        ([1e-6, -1e-6, 1e-3], None, 64, "non-negative"),
        ([1e-6, math.nan, 1e-3], None, 64, "finite"),
        ([1e-6, 1e-6], None, 64, "shape"),
        ([1e-6, 1e-6, 1e-3], (POSITIVE, POSITIVE), 64, "FeatureBound"),
        ([1e-6, 1e-6, 1e-3], None, -1, "max_redraws"),
        ([1e-6, 1e-6, 1e-3], None, 1.5, "max_redraws"),
        ([1e-6, 1e-6, 1e-3], None, True, "max_redraws"),
    ],
    ids=[
        "negative",
        "nan",
        "length",
        "bounds",
        "redraws_negative",
        "redraws_float",
        "redraws_bool",
    ],
)
def test_the_constructor_refuses_a_bad_scale_bounds_or_redraw_count(
    scale: list[float], bounds: Any, max_redraws: Any, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        InputVectorPerturbation(
            X,
            scale,
            bounds=bounds_for(NAMES) if bounds is None else bounds,
            max_redraws=max_redraws,
        )


@pytest.mark.parametrize(
    "first",
    [[-11.0, 0.5, 0.0], [0.0, -13.0, 0.0], [0.0, 0.0, -11.0], [0.0, 0.0, 700.0]],
    ids=["t1_below_0", "t2_below_0", "readout_below_0", "readout_above_1"],
)
def test_a_first_draw_outside_a_bound_is_redrawn_not_clipped(first: list[float]) -> None:
    """D1: the whole vector is redrawn; every component of the kept offset is the second draw's."""
    perturbation = InputVectorPerturbation.relative(X, 0.1, feature_names=NAMES)
    second = [0.5, -0.3, 0.2]
    rng = _ScriptedNormals(first, second)

    member = _jitter(perturbation, rng)

    assert rng.sizes == [3, 3]
    assert np.array_equal(member.offset, perturbation.scale * np.array(second))
    assert np.array_equal(member.center, X)


def test_an_open_end_is_redrawn_at_the_end_itself_and_a_closed_end_is_kept() -> None:
    """``center + scale * z`` lands exactly on 0 for T1 (open) and on 0 and 1 for the readout (closed)."""
    perturbation = InputVectorPerturbation(
        [1.0e-4, 1.0e-4, 0.5], [1.0e-4, 0.0, 0.5], bounds=bounds_for(NAMES)
    )

    at_open_end = _ScriptedNormals([-1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
    member = _jitter(perturbation, at_open_end)
    assert at_open_end.sizes == [3, 3]
    assert np.array_equal(member.offset, [0.0, 0.0, 0.0])

    for z in (1.0, -1.0):
        at_closed_end = _ScriptedNormals([0.0, 0.0, z])
        member = _jitter(perturbation, at_closed_end)
        assert at_closed_end.sizes == [3]
        assert (member.center + member.offset)[2] == (1.0 if z > 0 else 0.0)


@pytest.mark.parametrize("bad", [math.inf, -math.inf, math.nan], ids=["inf", "minus_inf", "nan"])
def test_a_non_finite_draw_is_redrawn(bad: float) -> None:
    perturbation = InputVectorPerturbation.relative(X, 0.1, feature_names=NAMES)
    rng = _ScriptedNormals([bad, 0.0, 0.0], [0.1, 0.1, 0.1])

    member = _jitter(perturbation, rng)

    assert rng.sizes == [3, 3]
    assert np.all(np.isfinite(member.offset))


@pytest.mark.parametrize("max_redraws", [0, 2])
def test_exhausted_redraws_raise_after_exactly_max_redraws_plus_one_draws(max_redraws: int) -> None:
    perturbation = InputVectorPerturbation.relative(
        X, 0.1, feature_names=NAMES, max_redraws=max_redraws
    )
    rng = _ScriptedNormals(*([[-11.0, 0.0, 0.0]] * (max_redraws + 1)))

    with pytest.raises(
        ValueError, match=f"member 0: no draw inside the bounds after {max_redraws + 1}"
    ):
        _jitter(perturbation, rng)
    assert rng.sizes == [3] * (max_redraws + 1)


def _first_inside(perturbation: InputVectorPerturbation, rows: list[Any]) -> int:
    """Index of the first row whose candidate is inside every bound."""
    for k, z in enumerate(rows):
        candidate = perturbation.center + perturbation.scale * z
        if all(b.contains(float(v)) for b, v in zip(perturbation.bounds, candidate, strict=True)):
            return k
    raise AssertionError("no row inside")


def test_a_real_generator_is_read_one_vector_per_attempt() -> None:
    """The draw pattern D6's measurement modelled: ``standard_normal(3)`` per attempt, nothing else.

    Replayed against a second generator from the same seed, on seeds whose
    first draw is out of bounds (so the redraw path runs) and on one whose
    first draw is kept.
    """
    perturbation = InputVectorPerturbation.relative(X, 0.6, feature_names=NAMES)

    def rows(seed: int) -> list[Any]:
        replay = np.random.default_rng(seed)
        return [replay.standard_normal(3) for _ in range(65)]

    redrawn = [seed for seed in range(200) if _first_inside(perturbation, rows(seed)) > 0][:3]
    kept = [seed for seed in range(200) if _first_inside(perturbation, rows(seed)) == 0][:1]
    assert len(redrawn) == 3 and len(kept) == 1

    for seed in redrawn + kept:
        k = _first_inside(perturbation, rows(seed))
        rng = np.random.default_rng(seed)
        member = _jitter(perturbation, rng)
        assert np.array_equal(member.offset, perturbation.scale * rows(seed)[k])
        after = np.random.default_rng(seed)
        for _ in range(k + 1):
            after.standard_normal(3)
        assert rng.bit_generator.state == after.bit_generator.state


def test_the_member_extractor_returns_its_vector_and_refuses_another_snapshot(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """D6 option A's guard: one object, one feature vector; stateless across calls."""
    vectorizer = BasicCalibrationVectorizer()
    x = vectorizer.extract(benchmark_snapshot)
    perturbation = InputVectorPerturbation.relative(x, 0.05, feature_names=vectorizer.feature_names)
    member = _jitter(perturbation, np.random.default_rng(1), vectorizer)

    first = member.extract(benchmark_snapshot)
    second = member.extract(benchmark_snapshot)

    assert np.array_equal(first, x + member.offset)
    assert np.array_equal(first, second) and first is not second
    assert all(b.contains(float(v)) for b, v in zip(perturbation.bounds, first, strict=True))
    assert member.wrapped is vectorizer
    assert member.output_dim == vectorizer.output_dim
    assert member.feature_names == vectorizer.feature_names
    for array in (member.center, member.offset):
        with pytest.raises(ValueError, match="read-only"):
            array[0] = 1.0
    with pytest.raises(ValueError, match="serves the one feature vector"):
        member.extract(_other_snapshot(benchmark_snapshot))


def test_a_directly_built_member_extractor_checks_its_shapes() -> None:
    vectorizer = BasicCalibrationVectorizer()
    with pytest.raises(ValueError, match="center has 2 entries"):
        OffsetFeatureExtractor(vectorizer, center=[1.0e-4, 8.0e-5], offset=[0.0, 0.0])
    with pytest.raises(ValueError, match="offset shape"):
        OffsetFeatureExtractor(vectorizer, center=X, offset=[0.0, 0.0])


def test_perturb_refuses_an_extractor_of_another_shape_or_names(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    vectorizer = BasicCalibrationVectorizer()
    renamed = _Shifted(vectorizer, np.zeros(3), names=("a", "b", "c"))
    relative = InputVectorPerturbation.relative(X, 0.1, feature_names=NAMES)

    with pytest.raises(ValueError, match="returns 4 features"):
        _jitter(relative, np.random.default_rng(1), _Shifted(vectorizer, np.zeros(3), dim=4))
    with pytest.raises(ValueError, match="names its features"):
        _jitter(relative, np.random.default_rng(1), renamed)
    # Built with an explicit scale, the object knows no names and checks none.
    explicit = InputVectorPerturbation(X, relative.scale, bounds=relative.bounds)
    assert _jitter(explicit, np.random.default_rng(1), renamed).feature_names == ("a", "b", "c")


def test_perturb_mutates_nothing_and_reads_only_its_generator(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    deps = _dependencies(benchmark_snapshot, RULE_BASE_SEED)
    vectorizer = deps["feature_extractor"]
    rule_base = deps["rule_base"]
    defuzzifier = deps["defuzzifier"]
    consequents = [rule.consequent_params.copy() for rule in rule_base.rules]
    x = vectorizer.extract(benchmark_snapshot)
    perturbation = InputVectorPerturbation.relative(x, 0.05, feature_names=vectorizer.feature_names)
    center, scale = perturbation.center.copy(), perturbation.scale.copy()

    out = perturbation.perturb(
        3,
        np.random.default_rng(5),
        feature_extractor=vectorizer,
        rule_base=rule_base,
        defuzzifier=defuzzifier,
    )

    assert out[1] is rule_base and out[2] is defuzzifier
    assert isinstance(out[0], OffsetFeatureExtractor) and out[0].wrapped is vectorizer
    assert out[0].output_dim == vectorizer.output_dim
    assert out[0].feature_names == vectorizer.feature_names
    assert np.array_equal(perturbation.center, center)
    assert np.array_equal(perturbation.scale, scale)
    assert np.array_equal(vectorizer.extract(benchmark_snapshot), x)
    assert all(
        np.array_equal(rule.consequent_params, before)
        for rule, before in zip(rule_base.rules, consequents, strict=True)
    )
    again = perturbation.perturb(
        3,
        np.random.default_rng(5),
        feature_extractor=vectorizer,
        rule_base=rule_base,
        defuzzifier=defuzzifier,
    )
    assert isinstance(again[0], OffsetFeatureExtractor)
    assert np.array_equal(again[0].offset, out[0].offset)


#: Dimensionless. A smoke value chosen only so that members differ; nothing
#: reads it as a fitted scale (D2 fits ``r``; this PR does not).
R_SMOKE_TEST = 0.05


def _jittered_ensemble(
    snapshot: CalibrationSnapshot, perturbed_at: CalibrationSnapshot, seed: int
) -> FuzzyNoiseModelEnsemble:
    """Four members over ``snapshot``, jittered around ``perturbed_at``'s vector."""
    vectorizer = BasicCalibrationVectorizer()
    perturbation = InputVectorPerturbation.relative(
        vectorizer.extract(perturbed_at), R_SMOKE_TEST, feature_names=vectorizer.feature_names
    )
    return _ensemble(snapshot, 4, perturbation=perturbation, rng=np.random.default_rng(seed))


def test_jittered_members_differ_repeat_and_follow_their_seed(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    ensemble = _jittered_ensemble(benchmark_snapshot, benchmark_snapshot, 64)

    first = [member.crisp_params.copy() for member in ensemble]
    second = [member.crisp_params.copy() for member in ensemble]
    rebuilt = [
        m.crisp_params for m in _jittered_ensemble(benchmark_snapshot, benchmark_snapshot, 64)
    ]
    other = [m.crisp_params for m in _jittered_ensemble(benchmark_snapshot, benchmark_snapshot, 65)]

    assert all(not np.array_equal(first[i], first[j]) for i in range(4) for j in range(i + 1, 4))
    assert all(np.array_equal(a, b) for a, b in zip(first, second, strict=True))
    assert all(np.array_equal(a, b) for a, b in zip(first, rebuilt, strict=True))
    assert not any(np.array_equal(a, b) for a, b in zip(first, other, strict=True))


def test_an_ensemble_over_another_snapshot_is_refused(
    benchmark_snapshot: CalibrationSnapshot,
) -> None:
    """The perturbation was built at one snapshot's vector; members over another fail loudly."""
    ensemble = _jittered_ensemble(_other_snapshot(benchmark_snapshot), benchmark_snapshot, 64)

    with pytest.raises(ValueError, match="serves the one feature vector"):
        list(ensemble)


def test_accepted_draws_follow_the_normal_truncated_at_the_bound() -> None:
    """The second route for D1: the redraw keeps a truncated Gaussian, not a clipped one.

    With ``center = 1`` and ``scale = 1`` on ``mean_T1`` and no jitter
    elsewhere, a draw is kept exactly when ``z > -1``, so the kept ``z`` is a
    standard normal truncated below at -1: mean ``phi(1) / Phi(1) = 0.28760``,
    standard deviation 0.7935. 20,000 members from one fixed seed; the
    tolerance is five standard errors (0.028). Clipping would instead put
    15.9% of the members exactly on 0.
    """
    perturbation = InputVectorPerturbation(
        [1.0, 1.0, 0.5], [1.0, 0.0, 0.0], bounds=bounds_for(NAMES)
    )
    rng = np.random.default_rng(20261114)
    z = np.array([_jitter(perturbation, rng).offset[0] for _ in range(20_000)])

    phi = math.exp(-0.5) / math.sqrt(2.0 * math.pi)
    big_phi = 0.5 * math.erfc(-1.0 / math.sqrt(2.0))
    mean = phi / big_phi
    sd = math.sqrt(1.0 - mean - mean**2)
    assert z.min() > -1.0
    assert abs(z.mean() - mean) < 5.0 * sd / math.sqrt(z.size)
