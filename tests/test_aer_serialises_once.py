"""Aer serialises a noise model once per run, not once per shot (issue #64 PR-A1, step 5).

ADR-002's architectural invariant is that Aer has no per-shot Python hook:
``NoiseModel.to_dict`` runs once at submission and the C++ controller takes
over. Every ensemble design in this project rests on it, because it is why
sample-level uncertainty has to be realised by building N models and not by
regenerating one model N times inside a run.

Until now the invariant was a sentence in ``integration/aer_factory.py``'s
docstring. This file measures it. The numbers asserted here were measured
first, on qiskit-aer 0.17.2 with qiskit 2.4.1 (the project's pins): one call
of ``NoiseModel.to_dict`` per run for 1, 1024 and 8192 shots, under the
automatic and the density-matrix methods, with the model passed to ``run`` or
to the simulator's constructor; none without a noise model.

The tests pin that behaviour and not the version. On an Aer upgrade that
serialises more than once per run they fail, and that failure is the signal
to re-read ADR-002, not a number to update.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, QuantumError, depolarizing_error

from superconducted.benchmarks.circuits import ghz_state_circuit, qft_circuit
from superconducted.benchmarks.harness import simulate_engine
from superconducted.integration.aer_factory import FuzzyNoiseModelEnsemble

DEVICE_BASIS = ("cz", "id", "rx", "rz", "sx", "x")

#: Shots of a multi-shot run, as the plan fixes them.
SHOTS = 1024


class SerialisationSpy:
    """Counts calls of ``NoiseModel.to_dict`` and ``QuantumError.to_dict`` on any instance."""

    def __init__(self) -> None:
        self.model_calls = 0
        self.error_calls = 0

    def during(self, action: Callable[[], object]) -> tuple[int, int]:
        """Run ``action`` and return how many model and error serialisations it caused."""
        model_before, error_before = self.model_calls, self.error_calls
        action()
        return self.model_calls - model_before, self.error_calls - error_before


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> Iterator[SerialisationSpy]:
    """Wrap the two class attributes, so a copy Aer makes of a model is counted too."""
    counter = SerialisationSpy()
    model_to_dict = NoiseModel.to_dict
    error_to_dict = QuantumError.to_dict

    def counted_model_to_dict(self: NoiseModel, *args: object, **kwargs: object) -> object:
        counter.model_calls += 1
        return model_to_dict(self, *args, **kwargs)

    def counted_error_to_dict(self: QuantumError, *args: object, **kwargs: object) -> object:
        counter.error_calls += 1
        return error_to_dict(self, *args, **kwargs)

    monkeypatch.setattr(NoiseModel, "to_dict", counted_model_to_dict)
    monkeypatch.setattr(QuantumError, "to_dict", counted_error_to_dict)
    yield counter


def _three_x_gates() -> QuantumCircuit:
    """Three ``X`` gates and a final measurement: three noise locations, ideal outcome ``1``."""
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.x(0)
    circuit.x(0)
    circuit.measure_all()
    return circuit


def _depolarizing_on_x() -> NoiseModel:
    model = NoiseModel(basis_gates=["x"])
    model.add_quantum_error(depolarizing_error(0.1, 1), "x", [0])
    return model


def assert_serialised_once(model_calls: int) -> None:
    """The guard's one assertion, shared so the negative control fails the same line."""
    assert model_calls == 1, (
        f"NoiseModel.to_dict ran {model_calls} times in one run; ADR-002 assumes exactly one. "
        "Re-read ADR-002 before changing this number."
    )


# --------------------------------------------------------------------------
# 1. The spy and the guard can both fail
# --------------------------------------------------------------------------


def test_the_spy_counts_a_direct_call(spy: SerialisationSpy) -> None:
    """A count of zero would also pass a careless "at most once" check; this one is not zero."""
    model_calls, error_calls = spy.during(lambda: _depolarizing_on_x().to_dict())

    assert (model_calls, error_calls) == (1, 1)


def test_no_noise_model_means_no_serialisation(spy: SerialisationSpy) -> None:
    """The spy counts noise-model serialisation and nothing else a run does."""
    simulator = AerSimulator()

    calls = spy.during(lambda: simulator.run(_three_x_gates(), shots=SHOTS).result())

    assert calls == (0, 0)


def test_the_guard_fails_on_a_per_shot_serialiser(spy: SerialisationSpy) -> None:
    """Negative control: a runner that serialises once per shot trips the same assertion."""
    model = _depolarizing_on_x()

    def per_shot_runner() -> None:
        for _ in range(SHOTS):
            model.to_dict()

    model_calls, _ = spy.during(per_shot_runner)

    assert model_calls == SHOTS
    with pytest.raises(AssertionError, match="ADR-002"):
        assert_serialised_once(model_calls)


# --------------------------------------------------------------------------
# 2. Aer itself (acceptance criterion 7)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["automatic", "density_matrix"])
@pytest.mark.parametrize("passed_to", ["run", "constructor"])
def test_one_serialisation_per_multi_shot_run(
    spy: SerialisationSpy, method: str, passed_to: str
) -> None:
    """1024 shots, one circuit, one ``to_dict``: and the noise still reaches many shots."""
    model = _depolarizing_on_x()
    if passed_to == "constructor":
        simulator = AerSimulator(method=method, noise_model=model)
        options: dict[str, object] = {}
    else:
        simulator = AerSimulator(method=method)
        options = {"noise_model": model}
    counts: dict[str, int] = {}

    def run() -> None:
        result = simulator.run(_three_x_gates(), shots=SHOTS, seed_simulator=5, **options).result()
        counts.update(result.get_counts())

    model_calls, error_calls = spy.during(run)

    assert_serialised_once(model_calls)
    assert error_calls == 1  # one error in the model, serialised with it
    assert sum(counts.values()) == SHOTS
    # The one serialised model acted in more than one shot: the ideal circuit
    # never gives "0", and 0.1 depolarizing on three gates gives it about 13% of the time.
    assert 50 < counts["0"] < 250


@pytest.mark.parametrize("method", ["automatic", "density_matrix"])
def test_the_number_of_serialisations_does_not_depend_on_shots(
    spy: SerialisationSpy, method: str
) -> None:
    """The invariant itself: 1 shot, 1024 shots and 8192 shots serialise the same number of times."""
    observed = []
    for shots in (1, SHOTS, 8192):
        simulator = AerSimulator(method=method)
        model = _depolarizing_on_x()
        observed.append(
            spy.during(
                lambda simulator=simulator, model=model, shots=shots: simulator.run(
                    _three_x_gates(), shots=shots, noise_model=model
                ).result()
            )
        )

    assert observed == [(1, 1), (1, 1), (1, 1)]


# --------------------------------------------------------------------------
# 3. The engine through the harness: one serialisation per member per circuit
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "shots"), [("counts", 1), ("counts", SHOTS), ("density_matrix", SHOTS)]
)
def test_the_harness_serialises_once_per_member_and_circuit(
    spy: SerialisationSpy,
    make_benchmark_ensemble: Callable[..., FuzzyNoiseModelEnsemble],
    mode: str,
    shots: int,
) -> None:
    """Three members and two circuits are six runs, so six serialisations, at any shot count.

    This is the ensemble design of ADR-002 seen from the spy: uncertainty comes
    from the number of models, each serialised once, never from shots.
    """
    circuits = [ghz_state_circuit(2), qft_circuit(2)]
    ensemble = make_benchmark_ensemble(3)

    model_calls, error_calls = spy.during(
        lambda: simulate_engine(
            circuits,
            ensemble,
            basis_gates=DEVICE_BASIS,
            mode=mode,  # type: ignore[arg-type]
            shots=shots,
            seed=11,
        )
    )

    assert model_calls == len(ensemble) * len(circuits) == 6
    assert error_calls > 0  # the engine installed noise, so there was something to serialise


def test_the_harness_error_serialisations_do_not_depend_on_shots(
    spy: SerialisationSpy,
    make_benchmark_ensemble: Callable[..., FuzzyNoiseModelEnsemble],
) -> None:
    """Per-error serialisation is per model too: the same count at 1 shot and at 1024."""
    observed = [
        spy.during(
            lambda shots=shots: simulate_engine(
                [ghz_state_circuit(2)],
                make_benchmark_ensemble(2),
                basis_gates=DEVICE_BASIS,
                shots=shots,
                seed=11,
            )
        )
        for shots in (1, SHOTS)
    ]

    assert observed[0] == observed[1]
    assert observed[0][0] == 2
