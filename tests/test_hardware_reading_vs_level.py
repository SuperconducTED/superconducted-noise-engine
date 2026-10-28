"""Tests for the offline half of the #125 hardware test (scripts/hardware_reading_vs_level.py).

Synthetic inputs, plus the configuration and properties bundled offline with
``qiskit_ibm_runtime``'s ``FakeFez`` as a real-shaped ``ibm_fez`` document. No git, no network.
"""

from __future__ import annotations

import copy
import math
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime.fake_provider import FakeFez
from qiskit_ibm_runtime.models import BackendProperties
from scripts.hardware_reading_vs_level import (
    GHZ_IDEAL,
    SLOTS,
    GateTable,
    Job,
    QubitSource,
    UnusableSourceError,
    _calendar_axis,
    _single_qubit_part,
    apply_readout,
    archived_backend,
    arm_a_circuit,
    build_predictor_noise,
    calendar_block_bootstrap,
    choose_layouts,
    connected_triples,
    coupled_pairs,
    delay_slots,
    gate_table,
    ghz_idle_circuit,
    hellinger_fidelity,
    p1_closed_form,
    paired_bootstrap,
    score_arm_a,
    score_arm_b,
    shot_free_distribution,
    sources_from_rows,
    spearman,
    substitute_level,
    transpile_layout,
    truth_readout,
    usable_cz_error,
    x_to_measure_intervals,
)
from scripts.hardware_test_predictors import PredictorRow

DT = 4e-9


@pytest.fixture(scope="module")
def fez_doc() -> dict[str, Any]:
    backend = FakeFez()
    backend._set_props_dict_from_json()
    props = copy.deepcopy(backend._props_dict)
    stamp = props["last_update_date"]
    props["last_update_date"] = stamp.isoformat() if isinstance(stamp, datetime) else stamp
    for entries in props["qubits"]:
        for entry in entries:
            if isinstance(entry.get("date"), datetime):
                entry["date"] = entry["date"].isoformat()
    for gate in props["gates"]:
        for param in gate["parameters"]:
            if isinstance(param.get("date"), datetime):
                param["date"] = param["date"].isoformat()
    return {"configuration": backend._get_conf_dict_from_json(), "properties": props}


# --- Arm A -----------------------------------------------------------------------------------


def test_delay_slots_are_the_seven_union_points_rounded_to_dt() -> None:
    slots = delay_slots(100e-6, 40e-6, dt=DT)
    expected = [0, 12500, 25000, 50000, 5000, 10000, 20000]
    assert slots == expected
    assert SLOTS[0][0] == "zero"


def test_equal_reading_and_level_leave_six_slots() -> None:
    slots = delay_slots(100e-6, 100e-6, dt=DT)
    assert slots[4:] == [None, None, None]
    assert sum(s is not None for s in slots) == 4  # zero plus three shared delays


def test_short_non_zero_delay_is_raised_to_min_length() -> None:
    slots = delay_slots(10e-9, 1e-6, dt=DT, min_length=2)
    assert slots[1] == 2  # 0.5 x 10 ns is 1.25 dt, raised to 2
    assert slots[2] is None  # 1 x 10 ns rounds to 2 dt, a repeat of the raised slot


@pytest.mark.parametrize("bad", [math.nan, 0.0, -1e-6])
def test_delay_slots_need_positive_t1(bad: float) -> None:
    with pytest.raises(UnusableSourceError):
        delay_slots(bad, 1e-4, dt=DT)


def test_arm_a_circuit_ends_every_delay_at_one_measurement() -> None:
    qc = arm_a_circuit(3, {2: 100, 5: 10, 7: None}, {2: 6, 5: 6, 7: 6}, n_qubits=8)
    assert qc.metadata["qubits"] == [2, 5]  # qubit 7 is excluded in this slot
    per_qubit: dict[int, list[tuple[str, int]]] = {2: [], 5: []}
    for instruction in qc.data:
        name = instruction.operation.name
        if name == "barrier":
            continue
        q = qc.find_bit(instruction.qubits[0]).index
        duration = int(instruction.operation.params[0]) if name == "delay" else 0
        per_qubit[q].append((name, duration))
    assert per_qubit[2] == [("x", 0), ("delay", 100), ("measure", 0)]
    assert per_qubit[5] == [("delay", 90), ("x", 0), ("delay", 10), ("measure", 0)]


def test_arm_a_circuit_without_an_active_qubit_is_refused() -> None:
    with pytest.raises(ValueError, match="no active qubit"):
        arm_a_circuit(1, {0: None}, {0: 6}, n_qubits=2)


def test_scheduled_interval_from_x_to_measure_equals_tau(fez_doc: dict[str, Any]) -> None:
    target = archived_backend(fez_doc).target
    durations = {0: 250, 1: 0, 2: 4000}
    x_len = {q: round(float(target["x"][(q,)].duration) / DT) for q in durations}
    qc = arm_a_circuit(0, durations, x_len, n_qubits=target.num_qubits)
    assert x_to_measure_intervals(qc, target) == durations


def test_closed_form_limits_and_middle() -> None:
    src = QubitSource(t1=100e-6, t2=80e-6, e10=0.03, e01=0.01)
    assert p1_closed_form(0.0, src) == pytest.approx(0.97)
    assert p1_closed_form(1.0, src) == pytest.approx(0.01)
    s = math.exp(-1.0)
    assert p1_closed_form(100e-6, src) == pytest.approx(0.97 * s + 0.01 * (1 - s))


def test_closed_form_refuses_an_unusable_source() -> None:
    with pytest.raises(UnusableSourceError):
        p1_closed_form(1e-6, QubitSource(math.nan, 1e-4, 0.01, 0.01))


# --- readout, fidelity, sources --------------------------------------------------------------


def test_readout_matrix_maps_true_to_read_per_qubit_little_endian() -> None:
    one = apply_readout(np.array([0.0, 1.0]), [0.1], [0.02])
    assert one == pytest.approx([0.1, 0.9])
    # two qubits, the state |q1 = 0, q0 = 1> (index 1); only qubit 0 can flip, by e10 = 0.2
    two = apply_readout(np.array([0.0, 1.0, 0.0, 0.0]), [0.2, 0.0], [0.0, 0.0])
    assert two == pytest.approx([0.2, 0.8, 0.0, 0.0])
    # qubit 1 prepared 0 reads 1 with e01 = 0.3
    three = apply_readout(np.array([1.0, 0.0, 0.0, 0.0]), [0.0, 0.0], [0.0, 0.3])
    assert three == pytest.approx([0.7, 0.0, 0.3, 0.0])


def test_hellinger_fidelity_is_one_on_itself_and_zero_when_disjoint() -> None:
    assert hellinger_fidelity(GHZ_IDEAL, GHZ_IDEAL) == pytest.approx(1.0)
    disjoint = np.zeros(8)
    disjoint[3] = 1.0
    assert hellinger_fidelity(disjoint, GHZ_IDEAL) == pytest.approx(0.0)


def _rows(q: int, values: dict[str, tuple[float, float, float, float]]) -> list[PredictorRow]:
    """values[quantity] = (reading, level, band_lo, band_hi)."""
    return [
        PredictorRow(q, quantity, r, lv, lo, hi, 30, 30, math.log(r / lv), "", 30)
        for quantity, (r, lv, lo, hi) in values.items()
    ]


def test_sources_take_band_readout_from_the_level_and_execution_from_its_rows() -> None:
    rows = _rows(
        0,
        {
            "T1": (1e-4, 2e-4, 1.5e-4, 2.5e-4),
            "T2": (8e-5, 9e-5, 7e-5, 1.1e-4),
            "prob_meas0_prep1": (0.03, 0.02, 0.01, 0.04),
            "prob_meas1_prep0": (0.01, 0.005, 0.002, 0.02),
        },
    )
    later = _rows(0, {"T1": (3e-4, 1.0, 1.0, 1.0), "T2": (1e-4, 1.0, 1.0, 1.0)})
    src = sources_from_rows(rows, later)
    assert src["reading"][0] == QubitSource(1e-4, 8e-5, 0.03, 0.01)
    assert src["level"][0] == QubitSource(2e-4, 9e-5, 0.02, 0.005)
    assert src["band_lo"][0] == QubitSource(1.5e-4, 7e-5, 0.02, 0.005)
    assert src["band_hi"][0] == QubitSource(2.5e-4, 1.1e-4, 0.02, 0.005)
    assert src["reading_at_execution"][0].t1 == 3e-4
    assert math.isnan(src["reading_at_execution"][0].e10)


def test_relaxation_usability_follows_adr_027() -> None:
    assert QubitSource(1e-4, 2e-4, 0.0, 0.0).usable_for_relaxation()
    assert not QubitSource(1e-4, 2.01e-4, 0.0, 0.0).usable_for_relaxation()
    assert not QubitSource(1e-4, 1e-4, 1.2, 0.0).usable_for_relaxation()


# --- Arm B -----------------------------------------------------------------------------------


def test_connected_triples_put_the_shared_neighbour_in_the_middle() -> None:
    pairs = coupled_pairs([[0, 1], [1, 0], [1, 2], [2, 3], [1, 4]])
    assert connected_triples(pairs, {0, 1, 2, 3, 4}) == [(1, 0, 2), (1, 0, 4), (1, 2, 4), (2, 1, 3)]
    assert connected_triples(pairs, {0, 1, 2}) == [(1, 0, 2)]


def test_dead_or_missing_cz_errors_are_not_usable() -> None:
    assert usable_cz_error(0.003)
    assert usable_cz_error(0.75)
    assert not usable_cz_error(1.0)  # a dead pair
    assert not usable_cz_error(None)
    assert not usable_cz_error(math.nan)


@pytest.mark.parametrize(
    ("n", "expected"),
    [(11, [0, 2, 4, 6, 8, 10]), (8, [0, 1, 3, 4, 6, 7]), (3, [0, 1, 2]), (6, [0, 1, 2, 3, 4, 5])],
)
def test_choose_layouts_spans_best_to_worst_with_halves_rounded_up(
    n: int, expected: list[int]
) -> None:
    predicted = [((i, i + 1000, i + 2000), 1.0 - i / 100) for i in range(n)]
    assert [t[0] for t in choose_layouts(predicted)] == expected


def test_choose_layouts_breaks_ties_by_the_sorted_triple() -> None:
    # sorted, (5, 1, 9) is (1, 5, 9), which comes before (2, 3, 4)
    predicted = [((2, 3, 4), 0.5), ((5, 1, 9), 0.5)]
    assert choose_layouts(predicted, k=2) == [(5, 1, 9), (2, 3, 4)]


def test_ghz_idle_circuit_idles_every_qubit_before_measuring() -> None:
    qc = ghz_idle_circuit(1000)
    names = [i.operation.name for i in qc.data]
    assert names.count("delay") == 3 and names.count("measure") == 3
    assert names.index("delay") > max(i for i, n in enumerate(names) if n == "cx")
    assert max(i for i, n in enumerate(names) if n == "delay") < names.index("measure")


def _gates(lengths: float = 36e-9, cz: float = 0.003) -> GateTable:
    return GateTable(
        {(g, q): lengths for g in ("sx", "x") for q in range(3)},
        {frozenset((0, 1)): cz, frozenset((0, 2)): cz},
    )


def test_builder_relaxes_x_and_delay_with_the_sources_t1() -> None:
    src = {q: QubitSource(50e-6, 60e-6, 0.0, 0.0) for q in range(3)}
    model = build_predictor_noise(src, qubits=[0], gates=_gates(), dt=DT, n_qubits=3)
    qc = QuantumCircuit(3)
    qc.x(0)
    qc.delay(5000, 0, unit="dt")  # 20 us
    p = shot_free_distribution(qc, model, [0])
    assert p[1] == pytest.approx(math.exp(-(36e-9 + 20e-6) / 50e-6), rel=1e-9)


def test_builder_cz_channel_is_the_same_for_every_predictor() -> None:
    a = {q: QubitSource(50e-6, 60e-6, 0.0, 0.0) for q in range(3)}
    b = {q: QubitSource(200e-6, 300e-6, 0.1, 0.1) for q in range(3)}
    ma = build_predictor_noise(a, qubits=[0, 1, 2], gates=_gates(), dt=DT, n_qubits=3)
    mb = build_predictor_noise(b, qubits=[0, 1, 2], gates=_gates(), dt=DT, n_qubits=3)
    for pair in [(0, 1), (1, 0), (0, 2), (2, 0)]:
        assert ma._local_quantum_errors["cz"][pair] == mb._local_quantum_errors["cz"][pair]
    assert (1, 2) not in ma._local_quantum_errors["cz"]  # no gate_error, no channel
    assert not ma._local_readout_errors  # readout enters analytically, not in the model
    single = ma._local_quantum_errors["cz"][(0, 1)]
    assert single.probabilities[0] == pytest.approx(1 - 0.004 * 15 / 16)


def test_builder_refuses_t2_above_twice_t1_instead_of_capping() -> None:
    src = {0: QubitSource(50e-6, 101e-6, 0.0, 0.0)}
    with pytest.raises(UnusableSourceError):
        build_predictor_noise(src, qubits=[0], gates=_gates(), dt=DT, n_qubits=1)


def test_builder_refuses_a_dead_cz_pair() -> None:
    src = {q: QubitSource(50e-6, 60e-6, 0.0, 0.0) for q in range(2)}
    with pytest.raises(UnusableSourceError):
        build_predictor_noise(src, qubits=[0, 1], gates=_gates(cz=1.0), dt=DT, n_qubits=2)


def test_transpiled_layout_stays_on_its_triple(fez_doc: dict[str, Any]) -> None:
    target = archived_backend(fez_doc).target
    pairs = coupled_pairs(fez_doc["configuration"]["coupling_map"])
    triple = connected_triples(pairs, set(range(10)))[0]
    out = transpile_layout(ghz_idle_circuit(500), triple, target)
    touched = {out.find_bit(q).index for i in out.data for q in i.qubits}
    assert touched <= set(triple)


# --- the archived snapshot and the truths ----------------------------------------------------


def test_gate_table_reads_lengths_in_seconds_and_cz_errors(fez_doc: dict[str, Any]) -> None:
    table = gate_table(fez_doc["properties"])
    assert 1e-9 < table.lengths[("x", 0)] < 1e-6
    assert table.cz_error and all(isinstance(k, frozenset) for k in table.cz_error)


def test_substituted_level_reads_back_through_backend_properties(fez_doc: dict[str, Any]) -> None:
    level = {0: QubitSource(123.4e-6, 98.7e-6, 0.04, 0.01)}
    doc, kept = substitute_level(fez_doc, level)
    props = BackendProperties.from_dict(copy.deepcopy(doc["properties"]))
    assert props.t1(0) == pytest.approx(123.4e-6, rel=1e-12)
    assert props.t2(0) == pytest.approx(98.7e-6, rel=1e-12)
    assert props.readout_error(0) == pytest.approx(0.025)
    assert props.qubit_property(0, "prob_meas0_prep1")[0] == pytest.approx(0.04)
    assert kept == list(range(1, 156))
    assert fez_doc["properties"]["qubits"][0] != doc["properties"]["qubits"][0]  # copied


def test_truth_readout_is_the_symmetric_readout_error(fez_doc: dict[str, Any]) -> None:
    truth = NoiseModel.from_backend(archived_backend(fez_doc))
    e10, e01 = truth_readout(truth, [0, 1])
    props = BackendProperties.from_dict(copy.deepcopy(fez_doc["properties"]))
    assert e10 == pytest.approx([props.readout_error(0), props.readout_error(1)])
    assert e01 == pytest.approx(e10)


def test_single_qubit_part_keeps_only_that_qubits_instructions() -> None:
    qc = arm_a_circuit(2, {0: 40, 1: 10}, {0: 6, 1: 6}, n_qubits=2)
    part = _single_qubit_part(qc, 1)
    names = [(i.operation.name, part.find_bit(i.qubits[0]).index) for i in part.data]
    assert names == [("delay", 1), ("x", 1), ("delay", 1), ("measure", 1)]


# --- scoring ---------------------------------------------------------------------------------


def _job(controls: list[int]) -> Job:
    sources = {
        name: {q: QubitSource(100e-6, 80e-6, 0.02, 0.01) for q in (0, 1)}
        for name in ("reading", "level", "reading_at_execution")
    }
    sources["band_lo"] = {q: QubitSource(50e-6, 80e-6, 0.02, 0.01) for q in (0, 1)}
    sources["band_hi"] = {q: QubitSource(200e-6, 80e-6, 0.02, 0.01) for q in (0, 1)}
    slots = {0: [0, 25000, None, None, None, None, None], 1: [0, 10, None, None, None, None, None]}
    arm_a = [arm_a_circuit(k, {q: slots[q][k] for q in (0, 1)}, {0: 6, 1: 6}, 2) for k in (0, 1)]
    return Job(
        t_s=datetime(2026, 10, 23, tzinfo=UTC),
        n_qubits=2,
        dt=DT,
        discriminating=[0],
        controls=controls,
        sources=sources,
        slots=slots,
        arm_a=arm_a,
        layouts=[(0, 1, 2), (3, 4, 5)],
        arm_b=[],
        arm_b_predicted={
            "reading": [0.9, 0.8],
            "level": [0.7, 0.8],
            "reading_at_execution": [None, 0.5],
            "band_lo": [0.6, 0.6],
            "band_hi": [None, None],
        },
    )


def test_score_arm_a_reads_each_qubits_own_clbit() -> None:
    job = _job(controls=[1])
    # slot 0: clbit 0 (qubit 0) reads 1 in 100 of 200 shots, clbit 1 (qubit 1) never
    counts = [{"01": 100, "00": 100}, {"11": 50, "10": 150}]
    rows = score_arm_a(job, counts, shots=200)
    by = {(r["qubit"], r["slot"]): r for r in rows}
    assert by[(0, "zero")]["p_hat"] == pytest.approx(0.5)
    assert by[(1, "zero")]["p_hat"] == pytest.approx(0.0)
    assert by[(0, "level_x0.5")]["p_hat"] == pytest.approx(0.25)
    assert by[(1, "level_x0.5")]["p_hat"] == pytest.approx(1.0)
    assert (
        by[(1, "zero")]["stratum"] == "control" and by[(0, "zero")]["stratum"] == "discriminating"
    )
    row = by[(0, "level_x0.5")]
    expected = p1_closed_form(100e-6, job.sources["level"][0])
    assert row["p_level"] == pytest.approx(expected)
    assert row["abs_err_level"] == pytest.approx(abs(0.25 - expected))
    assert row["band_p_lo"] < row["band_p_hi"]


def test_band_coverage_widens_by_one_binomial_standard_error() -> None:
    job = _job(controls=[])
    rows = score_arm_a(job, [{"01": 197, "00": 3}, {"01": 50, "00": 150}], shots=200)
    zero = next(r for r in rows if r["qubit"] == 0 and r["slot"] == "zero")
    # both band ends give 0.98 at tau = 0; p_hat 0.985 lies outside, and one standard error
    # (0.0086 at 200 shots) brings the band's top to 0.9886, which covers it
    assert zero["band_covered"] == 0 and zero["band_covered_widened"] == 1


def test_score_arm_b_skips_missing_predictions_and_finds_the_best_pick() -> None:
    job = _job(controls=[])
    ideal = {"000": 2048, "111": 2048}
    worse = {"000": 1500, "111": 1500, "011": 1096}
    out = score_arm_b(job, [worse, ideal], shots=4096)
    assert out["measured"][1] == pytest.approx(1.0)
    assert out["reading"]["best_pick_hit"] == 0  # picks layout 0, measured best is layout 1
    assert out["level"]["best_pick_hit"] == 1
    assert out["reading_at_execution"]["n_predicted"] == 1
    assert out["band_hi"]["best_pick_hit"] is None


def test_spearman_uses_average_ranks() -> None:
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)
    assert spearman([1, 1, 2], [1, 2, 3]) == pytest.approx(math.sqrt(3) / 2)
    assert math.isnan(spearman([1, 1, 1], [1, 2, 3]))


def test_paired_bootstrap_rows_and_row_weighted_groups() -> None:
    lo, hi = paired_bootstrap([0.5] * 10)
    assert lo == hi == pytest.approx(0.5)
    # two groups: one of three rows at 1, one of one row at 0; drawing both gives 0.75, not 0.5
    lo, hi = paired_bootstrap([1, 1, 1, 0], groups=["a", "a", "a", "b"], level=0.0)
    assert lo == pytest.approx(0.75) and hi == pytest.approx(0.75)


def test_calendar_axis_keeps_empty_dates() -> None:
    d0 = date(2026, 11, 1)
    first, n_days = _calendar_axis([d0, d0 + timedelta(days=9), d0 + timedelta(days=2)])
    assert (first, n_days) == (d0, 10)


def test_calendar_block_bootstrap_covering_blocks_return_the_row_weighted_mean() -> None:
    d0 = date(2026, 11, 1)
    dates = [d0, d0, d0 + timedelta(days=5)]
    lo, hi = calendar_block_bootstrap([0.0, 0.0, 3.0], dates, block_days=6, n_boot=50)
    assert lo == pytest.approx(1.0) and hi == pytest.approx(1.0)


def test_calendar_block_bootstrap_redraws_empty_draws() -> None:
    d0 = date(2026, 11, 1)
    lo, hi = calendar_block_bootstrap(
        [1.0, 3.0], [d0, d0 + timedelta(days=20)], block_days=1, n_boot=200
    )
    assert 1.0 <= lo <= hi <= 3.0 and math.isfinite(lo)


def test_json_is_written_with_lf(tmp_path: Path) -> None:
    from scripts.hardware_reading_vs_level import write_json_lf

    path = tmp_path / "criteria.json"
    write_json_lf(path, {"truth1": {"all_pass": True}})
    data = path.read_bytes()
    assert b"\n" in data and b"\r" not in data  # guards Windows; Linux never translates


def test_every_simulated_circuit_gets_its_own_seed() -> None:
    from scripts.hardware_reading_vs_level import SEED_GAP, circuit_seeds

    seeds_a, seeds_b = circuit_seeds(125, 7, 6)
    assert (len(seeds_a), len(seeds_b)) == (7, 6)
    ordered = sorted(seeds_a + seeds_b)
    # Aer seeds shot j as seed + j: neighbouring seeds would replay each other's shots
    assert min(b - a for a, b in pairwise(ordered)) >= SEED_GAP
    assert circuit_seeds(125, 7, 6) == (seeds_a, seeds_b)  # reproducible from the one seed
    assert circuit_seeds(126, 7, 6) != (seeds_a, seeds_b)
