import json
from pathlib import Path
from typing import Any

import pytest
from qiskit import QuantumCircuit
from scripts.first_ensemble_run import _load_snapshot, run_ensemble


class DummyMember:
    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts

    def prepare(self, circuit: QuantumCircuit) -> tuple[QuantumCircuit, Any]:
        return circuit, object()


class DummyResult:
    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts

    def result(self) -> "DummyResult":
        return self

    def get_counts(self) -> dict[str, int]:
        return self._counts


class DummySimulator:
    def __init__(self, responses: list[dict[str, int]]) -> None:
        self._responses = responses
        self.calls: list[tuple[int, Any]] = []

    def run(self, circuit: QuantumCircuit, shots: int, noise_model: Any) -> DummyResult:
        self.calls.append((shots, noise_model))
        return DummyResult(self._responses.pop(0))


def test_run_ensemble_aggregates_counts(monkeypatch: Any) -> None:
    expected_counts = [{"0": 9, "1": 6}, {"0": 3, "1": 0}]
    monkeypatch.setattr(
        "scripts.first_ensemble_run.transpile", lambda circuit, backend=None: circuit
    )

    sim = DummySimulator(list(expected_counts))
    members = [DummyMember({}), DummyMember({})]
    actual = run_ensemble(members, QuantumCircuit(1), shots=1024, simulator=sim)

    assert actual == {"0": 6, "1": 3}


def test_default_mfs_for_feature_raises_on_unknown() -> None:
    from scripts.first_ensemble_run import _default_mfs_for_feature

    with pytest.raises(ValueError, match="unknown feature"):
        _default_mfs_for_feature("not_a_feature")


def test_default_mfs_for_feature_raises_on_unknown_placement() -> None:
    from scripts.first_ensemble_run import _default_mfs_for_feature

    with pytest.raises(ValueError, match="unknown placement"):
        _default_mfs_for_feature("mean_T1", "diagonal")


@pytest.mark.parametrize("placement", ["endpoint", "interior"])
def test_three_mfs_per_feature(placement: str) -> None:
    """ADR-010 ratifies 3x3x3; from_grid multiplies, so K_i must be 3."""
    from scripts.first_ensemble_run import FEATURE_SCALES, _default_mfs_for_feature

    for feature_name in FEATURE_SCALES:
        assert len(_default_mfs_for_feature(feature_name, placement)) == 3


@pytest.mark.parametrize("placement", ["endpoint", "interior"])
def test_grid_builds_27_rules(placement: str) -> None:
    """The ratified baseline, asserted on the object the script actually builds.

    Regression guard for Issue #31: the helper previously returned two MFs
    per feature, which silently produced 2x2x2 = 8 rules against a ledger
    that says 27.
    """
    from scripts.first_ensemble_run import FEATURE_SCALES, _default_mfs_for_feature

    from superconducted.fuzzy.tsk import TSKRuleBase

    per_input_mfs = [_default_mfs_for_feature(name, placement) for name in FEATURE_SCALES]
    rule_base = TSKRuleBase.from_grid(per_input_mfs=per_input_mfs, output_dim=2)

    assert rule_base.input_dim == 3
    assert rule_base.n_rules == 27


@pytest.mark.parametrize("placement", ["endpoint", "interior"])
def test_upper_range_is_covered(placement: str) -> None:
    """No feature's upper half may be left without a membership function.

    The second defect in Issue #31: with centers only at ``lo`` and
    ``lo + span/2``, long T1/T2 and high readout error — the states the
    noise model most needs to discriminate — fired nothing appreciable.
    """
    from scripts.first_ensemble_run import FEATURE_SCALES, _default_mfs_for_feature

    for feature_name, (_lo, hi) in FEATURE_SCALES.items():
        mfs = _default_mfs_for_feature(feature_name, placement)
        best_at_hi = max(mf.degree(hi).midpoint for mf in mfs)
        assert best_at_hi >= 0.5, f"{feature_name} at hi under {placement}: {best_at_hi}"


def test_placement_layouts_differ() -> None:
    """The two layouts under comparison must actually be different."""
    from scripts.first_ensemble_run import mf_centers

    assert mf_centers(0.0, 1.0, "endpoint") == (0.0, 0.5, 1.0)
    assert mf_centers(0.0, 1.0, "interior") != mf_centers(0.0, 1.0, "endpoint")


def test_comparison_metrics_are_deterministic() -> None:
    """The placement comparison must be reproducible run to run.

    It is pure arithmetic with no RNG, so two calls must agree exactly.
    This is what lets Burak's desktop numbers be compared bit-for-bit
    against the laptop's.
    """
    from scripts.compare_mf_placement import placement_metrics

    assert placement_metrics("endpoint") == placement_metrics("endpoint")
    assert placement_metrics("endpoint") != placement_metrics("interior")


@pytest.mark.slow
def test_run_ensemble_real_aer_one_qubit() -> None:
    """End-to-end pipeline: fuzzy snapshot -> FuzzyNoiseModel -> Aer.

    Closes the gap left by test_run_ensemble_aggregates_counts, which
    only verifies aggregation via DummySimulator monkeypatching.
    """
    from qiskit_aer import AerSimulator
    from scripts.first_ensemble_run import (
        _synthetic_snapshot,
        generate_safe_ensemble,
    )

    snapshot = _synthetic_snapshot()
    members = generate_safe_ensemble(snapshot, n=1)
    assert len(members) == 1

    qc = QuantumCircuit(1)
    qc.h(0)
    qc.measure_all()

    _, prepared_nm = members[0].prepare(qc.copy())
    assert prepared_nm.noise_instructions, (
        "expected non-empty noise_instructions on prepared NoiseModel"
    )

    sim = AerSimulator()
    counts = run_ensemble(members, qc, shots=256, simulator=sim)
    assert sum(counts.values()) > 0


def test_load_snapshot(tmp_path: Path) -> None:
    data = {
        "backend": "ibm_fez",
        "timestamp": "2026-05-01T00:00:00Z",
        "schema_version": "1.0",
        "properties": {"qubits": [[{"name": "T1", "value": 50e-6}]]},
        "target": None,
        "configuration": None,
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    snapshot = _load_snapshot(path)

    assert snapshot.backend == "ibm_fez"
    assert snapshot.timestamp.isoformat() == "2026-05-01T00:00:00+00:00"
    assert snapshot.schema_version == "1.0"
    assert snapshot.properties == data["properties"]
    assert snapshot.target is None
    assert snapshot.configuration is None


@pytest.mark.slow
@pytest.mark.parametrize("placement", ["endpoint", "interior"])
def test_consequent_seed_search_is_deterministic(placement: str) -> None:
    """The seed search must pick the same seed every run, on any machine.

    Issue #31: the script hard-coded rng=default_rng(0), which produced a
    non-degenerate channel with the old 8-rule grid and a degenerate one
    with the ratified 27-rule grid. The search replaces that lucky draw.
    """
    from scripts.first_ensemble_run import (
        _synthetic_snapshot,
        generate_safe_ensemble_with_seed,
    )

    snapshot = _synthetic_snapshot()
    members_a, seed_a = generate_safe_ensemble_with_seed(snapshot, 1, placement)
    members_b, seed_b = generate_safe_ensemble_with_seed(snapshot, 1, placement)

    assert seed_a == seed_b
    assert len(members_a) == len(members_b) == 1


@pytest.mark.slow
@pytest.mark.parametrize("placement", ["endpoint", "interior"])
def test_selected_seed_is_non_degenerate(placement: str) -> None:
    """Whatever seed the search returns must yield a real (non-identity) channel."""
    import numpy as np
    from scripts.first_ensemble_run import (
        _synthetic_snapshot,
        generate_safe_ensemble_with_seed,
    )

    members, _seed = generate_safe_ensemble_with_seed(_synthetic_snapshot(), 1, placement)

    for member in members:
        crisp = member.crisp_params
        assert crisp.size >= 2
        assert np.any(crisp[:2] > 0)


def test_seed_limit_must_be_positive() -> None:
    from scripts.first_ensemble_run import (
        _synthetic_snapshot,
        generate_safe_ensemble_with_seed,
    )

    with pytest.raises(ValueError, match="seed_limit must be positive"):
        generate_safe_ensemble_with_seed(_synthetic_snapshot(), 1, "endpoint", seed_limit=0)
