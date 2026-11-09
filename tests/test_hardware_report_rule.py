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


def _days(n: int) -> list[date]:
    from datetime import timedelta

    return [DAY + timedelta(days=i) for i in range(n)]


def test_c_interval_with_x_one_is_the_block_bootstrap_of_the_mean() -> None:
    """Amendment 37's "same circular 3-day calendar blocks": with every ``x`` equal to 1, ``c`` is
    the row mean of ``y``, so the interval must be ``calendar_block_bootstrap``'s, to the float.
    Days 3 and 9 are empty and stay on the axis; the others hold one to three rows.
    """
    from scripts.hardware_reading_vs_level import calendar_block_bootstrap

    rng = np.random.default_rng(37)
    days = _days(14)
    dates = [d for i, d in enumerate(days) if i not in (3, 9) for _ in range(1 + i % 3)]
    ys = rng.normal(0.2, 0.3, len(dates)).tolist()
    span = (days[0], days[-1])
    got = hs.c_block_interval(
        [(1.0, y, d) for y, d in zip(ys, dates, strict=True)], span=span, seed=8
    )
    want = calendar_block_bootstrap(ys, dates, block_days=3, seed=8, span=span)
    assert got == list(want)


def test_c_interval_refits_the_slope_on_each_draw() -> None:
    """The draws computed here directly: each one's ``sum(x y) / sum(x^2)`` over its days."""
    rng = np.random.default_rng(38)
    days = _days(6)
    points = [(float(rng.normal(0.0, 0.5)), 0.0, d) for d in days for _ in range(2)]
    points = [(x, (0.2 if i < 6 else 1.0) * x + 0.01 * i, d) for i, (x, _, d) in enumerate(points)]
    got = hs.c_block_interval(points, span=(days[0], days[-1]), seed=5, n_boot=500)
    sxy = np.zeros(6)
    sxx = np.zeros(6)
    for x, y, d in points:
        sxy[(d - DAY).days] += x * y
        sxx[(d - DAY).days] += x * x
    draw_rng = np.random.default_rng(5)
    slopes = []
    while len(slopes) < 500:
        picked = ((draw_rng.integers(0, 6, size=2)[:, None] + np.arange(3)) % 6).reshape(-1)
        slopes.append(sxy[picked].sum() / sxx[picked].sum())
    assert got == pytest.approx(list(np.quantile(slopes, [0.05, 0.95])), abs=1e-12)
    assert got is not None and got[1] - got[0] > 0.1


def test_an_exact_slope_gives_a_zero_width_interval() -> None:
    days = _days(8)
    points = [(x, 0.7 * x, d) for d in days for x in (0.3, -0.5)]
    got = hs.c_block_interval(points, span=(days[0], days[-1]), seed=1)
    assert got == pytest.approx([0.7, 0.7], abs=1e-12)


def test_c_interval_waits_for_a_fourth_day() -> None:
    four = _days(4)
    points = [(0.4, 0.1 * (i + 1), d) for i, d in enumerate(four)]
    assert hs.c_block_interval(points[:3], span=(four[0], four[2]), seed=1) is None
    got = hs.c_block_interval(points, span=(four[0], four[3]), seed=1)
    assert got is not None and len(got) == 2 and got[0] <= got[1]


def test_a_draw_with_no_points_is_drawn_again() -> None:
    """Seven days, points on day 0 only: two 3-day blocks often miss it, and such a draw has no
    slope, so it must be drawn again rather than enter the percentiles."""
    days = _days(7)
    points = [(0.5, 0.35, days[0]), (-0.2, -0.14, days[0])]
    got = hs.c_block_interval(points, span=(days[0], days[-1]), seed=3, n_boot=200)
    assert got == pytest.approx([0.7, 0.7], abs=1e-12)


def test_c_interval_is_none_without_points_or_disagreement() -> None:
    days = _days(5)
    span = (days[0], days[-1])
    assert hs.c_block_interval([], span=span, seed=1) is None
    assert hs.c_block_interval([(0.0, 0.3, d) for d in days], span=span, seed=1) is None


def test_the_third_seed_leaves_a1_and_a2s_seeds_alone() -> None:
    two = np.random.SeedSequence(hs.SEED).generate_state(2, dtype=np.uint32)
    three = np.random.SeedSequence(hs.SEED).generate_state(3, dtype=np.uint32)
    assert three[:2].tolist() == two.tolist()


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


def test_a_row_whose_band_cannot_be_moved_gives_no_value_and_the_rest_keep_theirs() -> None:
    """A band end with no positive ``T1`` has no ``p_1``, so that row has no share."""
    levels = {1: 100e-6, 2: 200e-6, 3: 50e-6}
    lo = {1: 80e-6, 2: 150e-6, 3: 40e-6}
    hi = {1: 130e-6, 2: 260e-6, 3: 70e-6}
    rows = [_row(1, 100e-6, 0.60), _row(2, 100e-6, 0.40), _row(3, 50e-6, 0.75)]
    nominal, widened = hs.no_information_coverage(rows, _state(levels, lo, hi))
    unusable = hs.no_information_coverage(rows, _state(levels, {**lo, 3: 0.0}, hi))
    assert unusable == (nominal[:2], widened[:2])


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
        (
            # A mean D of exactly zero is not below zero.
            {
                "inconclusive": False,
                "a1": _cond(False, 0.0),
                "a2": _cond(False, -0.01),
                "a3": True,
            },
            "anything else",
        ),
    ],
)
def test_every_row_of_the_s1_table_is_reached(kwargs: dict[str, Any], row: str) -> None:
    assert hs.s1_reading(**kwargs) == (row, hs.S1_READINGS[row])


@pytest.mark.parametrize(
    ("s1", "inconclusive", "passes", "row"),
    [
        (True, False, True, "S1 and Arm B pass"),
        (True, False, False, "S1 passes, Arm B does not"),
        (False, False, True, "Arm B passes, S1 does not"),
        (False, False, False, "S1 does not pass and Arm B does not"),
        (True, True, False, "Arm B inconclusive"),
    ],
)
def test_every_row_of_the_arm_b_table_is_reached(
    s1: bool, inconclusive: bool, passes: bool, row: str
) -> None:
    out = hs.arm_b_reading(s1_passes=s1, inconclusive=inconclusive, passes=passes)
    assert out == (row, hs.ARM_B_READINGS[row])


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
    # Every field the report states, with its value (the mutation pass found them unread).
    assert set(a4) == {
        "part_of_s1",
        "stratum",
        "rows",
        "nominal",
        "coverage",
        "coverage_widened",
        "mean_width",
        "no_information_coverage",
        "no_information_coverage_widened",
    }
    assert a4["stratum"] == "discriminating" and a4["nominal"] == 0.80
    assert a4["mean_width"] == pytest.approx(0.1)
    state = {"sources": sources}
    as_read = [{k: str(v) for k, v in r.items()} for r in rows]
    nominal, widened = hs.no_information_coverage(as_read, state)
    assert a4["no_information_coverage"] == pytest.approx(sum(nominal) / len(nominal))
    assert a4["no_information_coverage_widened"] == pytest.approx(sum(widened) / len(widened))
    assert out["arm_a"]["minimum_days"] == 10
    level_of = {q: QubitSource(t, t, 0.02, 0.01) for q, t in levels.items()}
    xs, ys = [], []
    for q in levels:
        points = [(float(r["tau_s"]), int(r["ones"]), 2048) for r in rows if r["qubit"] == q]
        xs.append(math.log(reading[q]) - math.log(levels[q]))
        ys.append(hs.fit_log_t1_ratio(points, level_of[q]))
    c = sum(x * y for x, y in zip(xs, ys, strict=True)) / sum(x * x for x in xs)
    assert out["arm_a"]["c_and_s_res"]["c"] == pytest.approx(c)
    expected_b = hs.arm_b_reading(s1_passes=False, inconclusive=True, passes=False)
    assert out["arm_b_reading"] == {"row": expected_b[0], "reading": expected_b[1]}
    assert a4["no_information_coverage"] is not None
    assert out["arm_a"]["c_and_s_res"]["qubit_days"] == 2


# --- what the mutation pass found untested (criterion 25) -------------------------------------------


def test_the_fit_grid_is_amendment_30s() -> None:
    assert hs.FIT_GRID[0] == -3.0 and hs.FIT_GRID[-1] == 3.0
    assert len(hs.FIT_GRID) == 1201
    assert np.diff(hs.FIT_GRID) == pytest.approx(0.005)


def test_the_t1_fit_is_the_grid_maximum_of_a_direct_likelihood() -> None:
    """A large ``e01`` makes the readout term matter, so a wrong readout model moves the maximum."""
    level = QubitSource(100e-6, 120e-6, 0.05, 0.40)
    truth = QubitSource(level.t1 * math.exp(-0.42), level.t2, level.e10, level.e01)
    shots = 1_000_000
    taus = [10e-6, 30e-6, 60e-6, 100e-6, 160e-6, 250e-6]
    points = [(t, round(shots * p1_closed_form(t, truth)), shots) for t in taus]

    def log_lik(x: float) -> float:
        total = 0.0
        for tau, ones, n in points:
            survive = math.exp(-tau / (level.t1 * math.exp(x)))
            p = (1.0 - level.e10) * survive + level.e01 * (1.0 - survive)
            total += ones * math.log(p) + (n - ones) * math.log1p(-p)
        return total

    grid = [float(x) for x in hs.FIT_GRID]
    direct = max(grid, key=log_lik)
    assert hs.fit_log_t1_ratio(points, level) == direct
    assert direct == pytest.approx(-0.42, abs=0.0051)


def test_an_inconclusive_result_carries_no_statistic() -> None:
    out = hs.batch_means_test([(-0.03, 0), (-0.05, 4)], hs.ARM_A_BATCHES, side=-1)
    assert out == {
        "batch_means": [-0.03, -0.05, None, None],
        "batch_rows": [1, 1, 0, 0],
        "q": 2,
        "mean_of_batches": None,
        "t": None,
        "critical": None,
        "sd_zero": False,
        "inconclusive": True,
        "passes": False,
    }


def test_a_decided_result_names_its_mean_and_is_not_sd_zero() -> None:
    per_batch = [[-0.03, -0.01], [-0.05], [-0.02, 0.01], [-0.04]]
    values = [(v, (0, 4, 8, 11)[b]) for b, vs in enumerate(per_batch) for v in vs]
    out = hs.batch_means_test(values, hs.ARM_A_BATCHES, side=-1)
    means = [sum(v) / len(v) for v in per_batch]
    assert out["mean_of_batches"] == pytest.approx(sum(means) / 4)
    assert out["sd_zero"] is False


@pytest.mark.parametrize("side", [1, -1])
def test_a_t_equal_to_the_critical_value_does_not_pass(
    side: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Amendment 25's rule is strict: ``t > t95`` (Arm B) and ``t < -t95`` (Arm A)."""
    batches = ((0,), (1,), (2,))
    values = [(side * v, i) for i, v in enumerate((1.0, 2.0, 3.0))]
    t = 2.0 / (1.0 / math.sqrt(3))  # mean 2, sd 1, q 3: the code's own arithmetic
    monkeypatch.setitem(hs.T95, 2, t)
    assert hs.batch_means_test(values, batches, side=side)["passes"] is False
    monkeypatch.setitem(hs.T95, 2, math.nextafter(t, 0.0))
    assert hs.batch_means_test(values, batches, side=side)["passes"] is True


def test_c_and_s_res_without_points_or_without_disagreement_name_their_count() -> None:
    assert hs.slope_and_spread([]) == {"c": None, "s_res": None, "qubit_days": 0}
    assert hs.slope_and_spread([(0.0, 0.1), (0.0, -0.1)]) == {
        "c": None,
        "s_res": None,
        "qubit_days": 2,
    }


UNEVEN_LEVELS = {1: 100e-6, 2: 200e-6, 3: 50e-6, 4: 400e-6}
UNEVEN_LO = {1: 80e-6, 2: 150e-6, 3: 40e-6, 4: 250e-6}
UNEVEN_HI = {1: 130e-6, 2: 260e-6, 3: 70e-6, 4: 600e-6}


def _uneven_rows() -> list[dict[str, Any]]:
    return [
        _row(1, 100e-6, 0.55),
        _row(2, 100e-6, 0.40),
        _row(3, 50e-6, 0.70),
        _row(4, 150e-6, 0.30),
    ]


def _direct_no_information(
    rows: list[dict[str, Any]], levels: dict[int, float], lo: dict[int, float], hi: dict[int, float]
) -> tuple[list[float], list[float]]:
    nominal, widened = [], []
    for r in rows:
        q, tau, p_hat = int(r["qubit"]), float(r["tau_s"]), float(r["p_hat"])
        widen = binomial_se(p_hat, 2048)
        others = [o for o in levels if o != q]
        n_hit = w_hit = 0
        for o in others:
            ratio = levels[o] / levels[q]
            ends = sorted(
                p1_closed_form(tau, QubitSource(b * ratio, b * ratio, 0.02, 0.01))
                for b in (lo[q], hi[q])
            )
            n_hit += ends[0] <= p_hat <= ends[1]
            w_hit += ends[0] - widen <= p_hat <= ends[1] + widen
        nominal.append(n_hit / len(others))
        widened.append(w_hit / len(others))
    return nominal, widened


def test_no_information_coverage_matches_a_direct_computation_on_an_uneven_day() -> None:
    rows = _uneven_rows()
    out = hs.no_information_coverage(rows, _state(UNEVEN_LEVELS, UNEVEN_LO, UNEVEN_HI))
    expect = _direct_no_information(rows, UNEVEN_LEVELS, UNEVEN_LO, UNEVEN_HI)
    assert out[0] == pytest.approx(expect[0]) and out[1] == pytest.approx(expect[1])
    # Not degenerate: a row read against the wrong qubit would change a share.
    assert len(set(out[1])) == 3


@pytest.mark.parametrize("end", ["band_lo", "band_hi"])
def test_a_qubit_with_a_band_end_missing_gives_no_value_and_stays_a_neighbour(end: str) -> None:
    rows = _uneven_rows()
    state = _state(UNEVEN_LEVELS, UNEVEN_LO, UNEVEN_HI)
    full = hs.no_information_coverage(rows, state)
    del state["sources"][end]["3"]
    nominal, widened = hs.no_information_coverage(rows, state)
    assert nominal == [v for i, v in enumerate(full[0]) if i != 2]
    assert widened == [v for i, v in enumerate(full[1]) if i != 2]


def test_a_qubit_with_an_unusable_level_is_neither_a_row_nor_a_neighbour() -> None:
    rows = _uneven_rows()
    state = _state(UNEVEN_LEVELS, UNEVEN_LO, UNEVEN_HI)
    state["sources"]["level"]["3"] = [50e-6, 50e-6, 1.5, 0.01]  # e10 outside [0, 1]
    without = {q: t for q, t in UNEVEN_LEVELS.items() if q != 3}
    kept = [r for r in rows if r["qubit"] != "3"]
    expect = _direct_no_information(kept, without, UNEVEN_LO, UNEVEN_HI)
    out = hs.no_information_coverage(rows, state)
    assert out[0] == pytest.approx(expect[0]) and out[1] == pytest.approx(expect[1])


@pytest.mark.parametrize(("e10", "p_hat"), [(0.5, 0.5), (0.0, 1.0)])
def test_the_moved_band_includes_its_ends(e10: float, p_hat: float) -> None:
    """At ``tau = 0`` every moved band is the single point ``1 - e10``, which ``p_hat`` sits on.

    At ``p_hat = 0.5`` the widening is positive, so the widened band holds it strictly inside; at
    ``p_hat = 1`` the widening is zero, so the widened band's ends are tested too.
    """
    readout = [e10, 0.01]
    state = {
        "sources": {
            name: {"1": [100e-6, 100e-6, *readout], "2": [200e-6, 200e-6, *readout]}
            for name in ("level", "band_lo", "band_hi")
        }
    }
    rows = [_row(1, 0.0, p_hat), _row(2, 0.0, p_hat)]
    assert hs.no_information_coverage(rows, state) == ([1.0, 1.0], [1.0, 1.0])


def test_s_res_is_the_ten_to_ninety_spread_over_twice_z90() -> None:
    """Residuals 0 to 10: the 10th and 90th percentiles are 1 and 9 exactly."""
    points = [(0.0, float(k)) for k in range(1, 11)] + [(1.0, 0.0)]
    out = hs.slope_and_spread(points)
    assert out["c"] == 0.0
    assert out["s_res"] == 8.0 / (2.0 * 1.2815515655446004)
    assert out["qubit_days"] == 11


def _sealed_day(
    jobs: Any, day: date, truth_factor: float, reading: dict[int, list[float]] | None = None
) -> None:
    """One sealed day of two discriminating qubits whose true T1 is ``truth_factor`` x level."""
    from scripts.hardware_reading_vs_level import _write_tsv, write_json_lf

    folder = jobs / day.isoformat()
    folder.mkdir()
    levels = {1: 100e-6, 2: 200e-6}
    readings = reading or {q: [150e-6, 150e-6, 0.02, 0.01] for q in levels}
    sources = {
        "level": {str(q): [t, t, 0.02, 0.01] for q, t in levels.items()},
        "reading": {str(q): v for q, v in readings.items()},
        "band_lo": {str(q): [t * 0.8, t, 0.02, 0.01] for q, t in levels.items()},
        "band_hi": {str(q): [t * 1.3, t, 0.02, 0.01] for q, t in levels.items()},
    }
    write_json_lf(folder / "sealed.json", {"sources": sources})
    rows = []
    for q, t1 in levels.items():
        truth = QubitSource(t1 * truth_factor, t1, 0.02, 0.01)
        for tau_dt in (0, 5_000, 12_500, 25_000, 50_000, 75_000, 100_000):
            ones = round(2048 * p1_closed_form(tau_dt * 4e-9, truth))
            rows.append(
                {
                    "stratum": "discriminating",
                    "qubit": q,
                    "tau_dt": tau_dt,
                    "tau_s": tau_dt * 4e-9,
                    "shots": 2048,
                    "ones": ones,
                    "p_hat": ones / 2048,
                    "abs_err_reading": 0.05,
                    "abs_err_level": 0.01,
                    "abs_err_reading_at_execution": 0.04,
                    "band_covered": 1,
                    "band_covered_widened": 1,
                    "band_width": 0.1,
                }
            )
    _write_tsv(folder / "arm-a.tsv", rows)


def test_c_takes_each_qubit_days_own_rows(tmp_path: Any) -> None:
    """Two days with different true T1: a fit that mixed the days would give another ``c``."""
    from datetime import timedelta

    second = DAY + timedelta(days=1)
    _sealed_day(tmp_path, DAY, 1.1)
    _sealed_day(tmp_path, second, 0.7)
    out = hs.run_report(tmp_path, first_day=DAY, today=second)["arm_a"]["c_and_s_res"]
    assert out["qubit_days"] == 4
    xs, ys = [], []
    for factor in (1.1, 0.7):
        for t1 in (100e-6, 200e-6):
            truth = QubitSource(t1 * factor, t1, 0.02, 0.01)
            points = []
            for tau_dt in (5_000, 12_500, 25_000, 50_000, 75_000, 100_000):
                ones = round(2048 * p1_closed_form(tau_dt * 4e-9, truth))
                points.append((tau_dt * 4e-9, ones, 2048))
            xs.append(math.log(150e-6) - math.log(t1))
            ys.append(hs.fit_log_t1_ratio(points, QubitSource(t1, t1, 0.02, 0.01)))
    assert out["c"] == pytest.approx(
        sum(x * y for x, y in zip(xs, ys, strict=True)) / sum(x * x for x in xs)
    )


@pytest.mark.parametrize(
    "reading",
    [
        {2: [150e-6, 150e-6, 0.02, 0.01]},  # qubit 1 has no reading
        {1: [-1.0, 150e-6, 0.02, 0.01], 2: [150e-6, 150e-6, 0.02, 0.01]},  # unusable
    ],
)
def test_a_qubit_day_without_a_usable_reading_is_left_out_of_c(
    tmp_path: Any, reading: dict[int, list[float]]
) -> None:
    _sealed_day(tmp_path, DAY, 1.1, reading=reading)
    out = hs.run_report(tmp_path, first_day=DAY, today=DAY)["arm_a"]["c_and_s_res"]
    assert out["qubit_days"] == 1


def test_the_report_gives_c_its_interval_from_the_fourth_day(tmp_path: Any) -> None:
    """The report's interval is ``c_block_interval`` over its own qubit-days, with the third seed
    word and the run's calendar; on the third day it has none."""
    days = _days(4)
    factors = (1.1, 0.7, 1.3, 0.9)
    short, full = tmp_path / "three", tmp_path / "four"
    short.mkdir()
    full.mkdir()
    for i, (day, factor) in enumerate(zip(days, factors, strict=True)):
        _sealed_day(full, day, factor)
        if i < 3:
            _sealed_day(short, day, factor)
    third = hs.run_report(short, first_day=DAY, today=days[2])["arm_a"]["c_and_s_res"]
    assert third["c_interval_90"] is None and third["c_interval_block_days"] == 3
    assert third["qubit_days"] == 6
    out = hs.run_report(full, first_day=DAY, today=days[3])["arm_a"]["c_and_s_res"]
    points = []
    for day, factor in zip(days, factors, strict=True):
        for t1 in (100e-6, 200e-6):
            truth = QubitSource(t1 * factor, t1, 0.02, 0.01)
            fit_points = []
            for tau_dt in (5_000, 12_500, 25_000, 50_000, 75_000, 100_000):
                ones = round(2048 * p1_closed_form(tau_dt * 4e-9, truth))
                fit_points.append((tau_dt * 4e-9, ones, 2048))
            fit = hs.fit_log_t1_ratio(fit_points, QubitSource(t1, t1, 0.02, 0.01))
            assert fit is not None
            points.append((math.log(150e-6) - math.log(t1), fit, day))
    seed = int(np.random.SeedSequence(hs.SEED).generate_state(3, dtype=np.uint32)[2])
    want = hs.c_block_interval(points, span=(days[0], days[3]), seed=seed)
    assert want is not None and out["c_interval_90"] == want
    assert want[0] < want[1]
    assert out["c_interval_block_days"] == 3 and out["qubit_days"] == 8


# Amendment 29 as amendment 37 amends it (the pre-registration on main at d929424a, PR #135's
# merge), copied by hand, backticks dropped. This branch does not carry that document.
AMENDMENT_29_S1 = {
    "too few completed days": "Inconclusive: nothing is read.",
    "A1, A2 and A3 pass": "S1 passes: level beats both readings, and most of the deviation is gone "
    "by execution. A4 reports how well the band is calibrated; c and s_res (amendment 30) say how "
    "much of the scatter is physical.",
    "A1 and A2 pass, A3 fails": "S1 not supported: the controls disagree in sign, or the run has "
    "no control rows. The discriminating result is reported as specific to the selected qubits, "
    "with no claim about the chip.",
    "A2's mean D at or above zero": "S1 fails: reading_at_execution is at least as good as level, "
    "so the scatter is what the device does between readings (design §7).",
    "A1 passes, A2 does not": "Staleness: level beats the submission-time reading but not, by the "
    "rule, the execution-time one (design §7).",
    "A1 and A2 both fail, both mean D below zero": "No claim: the data do not separate the "
    "predictors. The estimates are reported, not read.",
    "anything else": "Reported as observed, with no S1 reading.",
}
AMENDMENT_29_ARM_B = {
    "S1 and Arm B pass": "S1 passes for the engineer's purpose too: level ranks layouts better "
    "than reading (design §7).",
    "S1 passes, Arm B does not": "S1 holds for decay prediction, not for ranking layouts: the "
    "engineer's-purpose claim is not made.",
    "Arm B passes, S1 does not": "No claim from Arm B alone.",
    "Arm B inconclusive": "Nothing is added.",
    "S1 does not pass and Arm B does not": "Nothing is added.",
}


def test_the_readings_are_amendment_29s_words() -> None:
    assert hs.S1_READINGS == AMENDMENT_29_S1
    assert hs.ARM_B_READINGS == AMENDMENT_29_ARM_B
