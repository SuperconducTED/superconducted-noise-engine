"""The decision rule of PR #135's section 3.12, as ``scripts/hardware_submit.py`` computes it.

Criteria 17 to 22 of the stage 2 plan in ``docs/implementations/2026-11-05-hardware-test-submission.md``.
Every expected value is computed directly in the test, not read back from the code under test.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import numpy as np
import pytest
import scripts.hardware_submit as hs
from scripts.hardware_reading_vs_level import QubitSource, binomial_se, p1_closed_form

DAY = date(2026, 11, 10)


def test_the_critical_values_are_scipys() -> None:
    stats = pytest.importorskip("scipy.stats")
    for df, value in hs.T95.items():
        assert value == pytest.approx(float(stats.t.ppf(0.95, df)), abs=1e-12)
    assert pytest.approx(float(stats.norm.ppf(0.9)), abs=1e-12) == hs.Z90


def test_the_batches_are_the_pre_registrations() -> None:
    assert hs.ARM_A_BATCHES == ((0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10), (11, 12, 13))
    assert hs.ARM_B_BATCHES == ((0, 1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12))


def test_d_is_level_minus_other_so_negative_favours_level() -> None:
    rows = [
        {"abs_err_level": "0.01", "abs_err_reading": "0.05", "date": DAY},
        {"abs_err_level": "nan", "abs_err_reading": "0.05", "date": DAY},
    ]
    ((d, when),) = hs.level_minus_other(rows, "reading")
    assert d == pytest.approx(-0.04)
    assert when == DAY


def _direct_t(batch_values: list[list[float]]) -> tuple[float, int]:
    means = [sum(v) / len(v) for v in batch_values if v]
    q = len(means)
    mean = sum(means) / q
    sd = math.sqrt(sum((m - mean) ** 2 for m in means) / (q - 1))
    return mean / (sd / math.sqrt(q)), q


def test_batch_means_match_a_direct_computation_with_unequal_rows() -> None:
    per_batch = [[-0.03, -0.01, -0.02], [-0.05], [-0.02, 0.01], [-0.04, -0.03, -0.06, -0.01]]
    items = [0, 4, 8, 11]
    values = [(v, items[b]) for b, vs in enumerate(per_batch) for v in vs]
    out = hs.batch_means_test(values, hs.ARM_A_BATCHES, side=-1)
    t, q = _direct_t(per_batch)
    assert out["q"] == q == 4
    assert out["t"] == pytest.approx(t)
    assert out["critical"] == hs.T95[3]
    assert out["passes"] is (t < -hs.T95[3])
    assert out["batch_rows"] == [3, 1, 2, 4]


def test_one_empty_batch_is_dropped_and_two_make_it_inconclusive() -> None:
    three = [(-0.03, 0), (-0.02, 1), (-0.05, 4), (-0.04, 11), (-0.045, 12)]
    out = hs.batch_means_test(three, hs.ARM_A_BATCHES, side=-1)
    t, q = _direct_t([[-0.03, -0.02], [-0.05], [], [-0.04, -0.045]])
    assert out["q"] == q == 3 and out["critical"] == hs.T95[2]
    assert out["t"] == pytest.approx(t)
    assert out["inconclusive"] is False
    two = [(-0.03, 0), (-0.05, 4)]
    out = hs.batch_means_test(two, hs.ARM_A_BATCHES, side=-1)
    assert out["inconclusive"] is True and out["passes"] is False and out["t"] is None


def test_equal_batch_means_fail_because_sd_is_zero() -> None:
    values = [(-0.02, i) for i in (0, 4, 8, 11)]
    out = hs.batch_means_test(values, hs.ARM_A_BATCHES, side=-1)
    assert out["sd_zero"] is True and out["passes"] is False


def test_the_side_decides_which_tail_passes() -> None:
    values = [(v, i) for v, i in ((0.30, 0), (0.25, 4), (0.35, 7), (0.28, 10))]
    assert hs.batch_means_test(values, hs.ARM_B_BATCHES, side=1)["passes"] is True
    assert hs.batch_means_test(values, hs.ARM_B_BATCHES, side=-1)["passes"] is False


def test_an_item_outside_every_batch_is_refused() -> None:
    with pytest.raises(ValueError, match="in no batch"):
        hs.batch_means_test([(0.1, 14)], hs.ARM_A_BATCHES, side=-1)


def test_the_t1_fit_recovers_a_planted_ratio() -> None:
    level = QubitSource(100e-6, 120e-6, 0.02, 0.01)
    planted = 0.3
    truth = QubitSource(level.t1 * math.exp(planted), level.t2, level.e10, level.e01)
    shots = 2048
    taus = [10e-6, 50e-6, 100e-6, 150e-6, 200e-6, 300e-6]
    points = [(t, round(shots * p1_closed_form(t, truth)), shots) for t in taus]
    fitted = hs.fit_log_t1_ratio(points, level)
    assert fitted is not None and abs(fitted - planted) <= 0.01


def test_the_t1_fit_needs_points_and_a_usable_level() -> None:
    assert hs.fit_log_t1_ratio([], QubitSource(1e-4, 1e-4, 0.0, 0.0)) is None
    assert hs.fit_log_t1_ratio([(1e-5, 10, 100)], QubitSource(-1.0, 1e-4, 0.0, 0.0)) is None


def test_c_and_s_res_recover_a_planted_slope_and_spread() -> None:
    rng = np.random.default_rng(20261108)
    x = rng.normal(0.0, 0.4, 4000)
    y = 0.5 * x + rng.normal(0.0, 0.2, 4000)
    out = hs.slope_and_spread(list(zip(x.tolist(), y.tolist(), strict=True)))
    assert out["c"] == pytest.approx(0.5, abs=0.02)
    assert out["s_res"] == pytest.approx(0.2, abs=0.02)
    assert out["qubit_days"] == 4000


def test_c_is_undefined_without_disagreement() -> None:
    assert hs.slope_and_spread([(0.0, 0.1), (0.0, -0.1)])["c"] is None
    assert hs.slope_and_spread([])["c"] is None


def _state(levels: dict[int, float], lo: dict[int, float], hi: dict[int, float]) -> dict[str, Any]:
    return {
        "sources": {
            "level": {str(q): [t, t, 0.02, 0.01] for q, t in levels.items()},
            "band_lo": {str(q): [t, t, 0.02, 0.01] for q, t in lo.items()},
            "band_hi": {str(q): [t, t, 0.02, 0.01] for q, t in hi.items()},
        }
    }


def _row(qubit: int, tau: float, p_hat: float, shots: int = 2048) -> dict[str, Any]:
    return {"qubit": str(qubit), "tau_s": str(tau), "p_hat": str(p_hat), "shots": str(shots)}


def test_no_information_coverage_matches_a_direct_computation() -> None:
    levels = {1: 100e-6, 2: 200e-6, 3: 50e-6}
    lo = {1: 80e-6, 2: 150e-6, 3: 40e-6}
    hi = {1: 130e-6, 2: 260e-6, 3: 70e-6}
    state = _state(levels, lo, hi)
    rows = [_row(1, 100e-6, 0.60), _row(2, 100e-6, 0.40), _row(3, 50e-6, 0.75)]
    nominal, widened = hs.no_information_coverage(rows, state)

    expect_nominal, expect_widened = [], []
    for r in rows:
        q, tau, p_hat = int(r["qubit"]), float(r["tau_s"]), float(r["p_hat"])
        widen = binomial_se(p_hat, 2048)
        n_hit = w_hit = 0
        others = [o for o in levels if o != q]
        for o in others:
            ratio = levels[o] / levels[q]
            ends = sorted(
                p1_closed_form(tau, QubitSource(b * ratio, b * ratio, 0.02, 0.01))
                for b in (lo[q], hi[q])
            )
            n_hit += ends[0] <= p_hat <= ends[1]
            w_hit += ends[0] - widen <= p_hat <= ends[1] + widen
        expect_nominal.append(n_hit / len(others))
        expect_widened.append(w_hit / len(others))
    assert nominal == pytest.approx(expect_nominal)
    assert widened == pytest.approx(expect_widened)
    # Each row sits inside exactly one neighbour's moved band, so the shares are not all 0 or 1.
    assert nominal == [0.5, 0.5, 0.5]


def test_no_information_coverage_needs_another_qubit() -> None:
    state = _state({1: 100e-6}, {1: 80e-6}, {1: 130e-6})
    assert hs.no_information_coverage([_row(1, 100e-6, 0.45)], state) == ([], [])


def _cond(passes: bool, mean_d: float | None) -> dict[str, Any]:
    return {"passes": passes, "mean_d": mean_d}


@pytest.mark.parametrize(
    ("kwargs", "row"),
    [
        (
            {"inconclusive": True, "a1": _cond(True, -0.1), "a2": _cond(True, -0.1), "a3": True},
            "too few completed days",
        ),
        (
            {"inconclusive": False, "a1": _cond(True, -0.1), "a2": _cond(True, -0.1), "a3": True},
            "A1, A2 and A3 pass",
        ),
        (
            {"inconclusive": False, "a1": _cond(True, -0.1), "a2": _cond(True, -0.1), "a3": False},
            "A1 and A2 pass, A3 fails",
        ),
        (
            {"inconclusive": False, "a1": _cond(True, -0.1), "a2": _cond(False, 0.0), "a3": True},
            "A2's mean D at or above zero",
        ),
        (
            {"inconclusive": False, "a1": _cond(True, -0.1), "a2": _cond(False, -0.01), "a3": True},
            "A1 passes, A2 does not",
        ),
        (
            {
                "inconclusive": False,
                "a1": _cond(False, -0.1),
                "a2": _cond(False, -0.01),
                "a3": True,
            },
            "A1 and A2 both fail, both mean D below zero",
        ),
        (
            {
                "inconclusive": False,
                "a1": _cond(False, 0.02),
                "a2": _cond(False, -0.01),
                "a3": True,
            },
            "anything else",
        ),
    ],
)
def test_every_row_of_the_s1_table_is_reached(kwargs: dict[str, Any], row: str) -> None:
    assert hs.s1_reading(**kwargs)[0] == row


@pytest.mark.parametrize(
    ("s1", "inconclusive", "passes", "row"),
    [
        (True, False, True, "S1 and Arm B pass"),
        (True, False, False, "S1 passes, Arm B does not"),
        (False, False, True, "Arm B passes, S1 does not"),
        (False, False, False, "neither passes"),
        (True, True, False, "Arm B inconclusive"),
    ],
)
def test_every_row_of_the_arm_b_table_is_reached(
    s1: bool, inconclusive: bool, passes: bool, row: str
) -> None:
    out = hs.arm_b_reading(s1_passes=s1, inconclusive=inconclusive, passes=passes)
    assert out[0] == row


def test_the_report_computes_the_descriptive_figures_from_sealed_forecasts(tmp_path: Any) -> None:
    from scripts.hardware_reading_vs_level import _write_tsv, write_json_lf

    folder = tmp_path / "2026-11-10"
    folder.mkdir()
    levels = {1: 100e-6, 2: 200e-6}
    reading = {1: 150e-6, 2: 150e-6}
    sources = {
        "level": {str(q): [t, t, 0.02, 0.01] for q, t in levels.items()},
        "reading": {str(q): [t, t, 0.02, 0.01] for q, t in reading.items()},
        "band_lo": {str(q): [t * 0.8, t, 0.02, 0.01] for q, t in levels.items()},
        "band_hi": {str(q): [t * 1.3, t, 0.02, 0.01] for q, t in levels.items()},
    }
    write_json_lf(folder / "sealed.json", {"sources": sources})
    rows = []
    for q, t1 in levels.items():
        truth = QubitSource(t1 * 1.1, t1, 0.02, 0.01)
        for tau_dt in (5_000, 12_500, 25_000, 50_000, 75_000, 100_000):
            tau = tau_dt * 4e-9
            p = p1_closed_form(tau, truth)
            rows.append(
                {
                    "stratum": "discriminating",
                    "qubit": q,
                    "tau_dt": tau_dt,
                    "tau_s": tau,
                    "shots": 2048,
                    "ones": round(2048 * p),
                    "p_hat": round(2048 * p) / 2048,
                    "abs_err_reading": 0.05,
                    "abs_err_level": 0.01,
                    "abs_err_reading_at_execution": 0.04,
                    "band_covered": 1,
                    "band_covered_widened": 1,
                    "band_width": 0.1,
                }
            )
    _write_tsv(folder / "arm-a.tsv", rows)
    out = hs.run_report(tmp_path, first_day=DAY, today=DAY)
    a4 = out["arm_a"]["A4_band_calibration_report"]
    assert a4["no_information_coverage"] is not None
    assert out["arm_a"]["c_and_s_res"]["qubit_days"] == 2
