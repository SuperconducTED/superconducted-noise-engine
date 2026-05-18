"""Numerical correctness of membership-function shapes."""

from __future__ import annotations

import numpy as np
import pytest

from superconducted.fuzzy.membership import (
    GaussianMF,
    IntervalGaussianMF,
    TanhBellMF,
    TanhMF,
    TanhSigmoidMF,
    TrapezoidalMF,
    TriangularMF,
)


class TestGaussianMF:
    def test_peak_at_center(self) -> None:
        mf = GaussianMF(center=2.0, sigma=0.5)
        assert mf.degree(2.0).midpoint == pytest.approx(1.0)

    def test_decays_off_center(self) -> None:
        mf = GaussianMF(center=0.0, sigma=1.0)
        assert mf.degree(5.0).midpoint < 1e-5

    def test_is_t1(self) -> None:
        mf = GaussianMF(center=0.0, sigma=1.0)
        d = mf.degree(0.5)
        assert d.is_crisp
        assert not mf.is_interval_type2

    def test_parameters_round_trip(self) -> None:
        mf = GaussianMF(center=1.5, sigma=0.3)
        params = mf.parameters()
        assert params.shape == (2,)
        assert np.allclose(params, [1.5, 0.3])
        mf.set_parameters(np.array([2.0, 0.5], dtype=np.float64))
        assert np.allclose(mf.parameters(), [2.0, 0.5])

    def test_invalid_sigma(self) -> None:
        with pytest.raises(ValueError):
            GaussianMF(center=0.0, sigma=0.0)
        with pytest.raises(ValueError):
            GaussianMF(center=0.0, sigma=-1.0)

    def test_set_parameters_validates(self) -> None:
        mf = GaussianMF(center=0.0, sigma=1.0)
        with pytest.raises(ValueError):
            mf.set_parameters(np.array([1.0, -0.5]))


class TestTriangularMF:
    def test_peak_and_feet(self) -> None:
        mf = TriangularMF(0.0, 1.0, 2.0)
        assert mf.degree(0.0).midpoint == pytest.approx(0.0)
        assert mf.degree(1.0).midpoint == pytest.approx(1.0)
        assert mf.degree(2.0).midpoint == pytest.approx(0.0)

    def test_linear_rise(self) -> None:
        mf = TriangularMF(0.0, 1.0, 2.0)
        assert mf.degree(0.5).midpoint == pytest.approx(0.5)
        assert mf.degree(1.5).midpoint == pytest.approx(0.5)

    def test_invalid_ordering(self) -> None:
        with pytest.raises(ValueError):
            TriangularMF(2.0, 1.0, 0.0)
        with pytest.raises(ValueError):
            TriangularMF(0.0, 0.0, 1.0)


class TestTrapezoidalMF:
    def test_plateau(self) -> None:
        mf = TrapezoidalMF(0.0, 1.0, 2.0, 3.0)
        assert mf.degree(1.5).midpoint == pytest.approx(1.0)
        assert mf.degree(1.0).midpoint == pytest.approx(1.0)
        assert mf.degree(2.0).midpoint == pytest.approx(1.0)

    def test_ramps(self) -> None:
        mf = TrapezoidalMF(0.0, 1.0, 2.0, 3.0)
        assert mf.degree(0.5).midpoint == pytest.approx(0.5)
        assert mf.degree(2.5).midpoint == pytest.approx(0.5)

    def test_invalid_ordering(self) -> None:
        with pytest.raises(ValueError):
            TrapezoidalMF(0.0, 2.0, 1.0, 3.0)


class TestTanhMF:
    def test_peak_between_feet(self) -> None:
        mf = TanhMF(left=-1.0, right=1.0, slope_left=10.0, slope_right=10.0)
        peak = mf.degree(0.0).midpoint
        assert 0.9 <= peak <= 1.0

    def test_decays_outside(self) -> None:
        mf = TanhMF(left=-1.0, right=1.0, slope_left=10.0, slope_right=10.0)
        assert mf.degree(-3.0).midpoint < 0.05
        assert mf.degree(3.0).midpoint < 0.05

    def test_invalid_geometry(self) -> None:
        with pytest.raises(ValueError):
            TanhMF(left=1.0, right=0.0, slope_left=1.0, slope_right=1.0)
        with pytest.raises(ValueError):
            TanhMF(left=0.0, right=1.0, slope_left=-1.0, slope_right=1.0)


class TestIntervalGaussianMF:
    def test_at_center_both_one(self) -> None:
        mf = IntervalGaussianMF(center=0.0, sigma_low=0.5, sigma_high=1.0)
        d = mf.degree(0.0)
        assert d.low == pytest.approx(1.0)
        assert d.high == pytest.approx(1.0)

    def test_off_center_low_le_high(self) -> None:
        mf = IntervalGaussianMF(center=0.0, sigma_low=0.5, sigma_high=1.0)
        d = mf.degree(1.0)
        assert d.low <= d.high
        assert 0.0 <= d.low <= 1.0
        assert 0.0 <= d.high <= 1.0

    def test_is_it2(self) -> None:
        mf = IntervalGaussianMF(center=0.0, sigma_low=0.5, sigma_high=1.0)
        assert mf.is_interval_type2

    def test_validation(self) -> None:
        with pytest.raises(ValueError):
            IntervalGaussianMF(center=0.0, sigma_low=1.0, sigma_high=0.5)
        with pytest.raises(ValueError):
            IntervalGaussianMF(center=0.0, sigma_low=-0.1, sigma_high=1.0)

    def test_parameters_round_trip(self) -> None:
        mf = IntervalGaussianMF(center=2.0, sigma_low=0.3, sigma_high=0.7)
        params = mf.parameters()
        assert params.shape == (3,)
        mf2 = IntervalGaussianMF(center=0.0, sigma_low=0.1, sigma_high=0.2)
        mf2.set_parameters(params)
        assert np.allclose(mf2.parameters(), params)


class TestTanhSigmoidMF:
    def test_tanh_sigmoid_range(self) -> None:
        """Test that TanhSigmoidMF outputs are bounded within (0, 1) and exactly 0.5 at center."""
        mf = TanhSigmoidMF(center=5.0, slope=1.0)
        # Check the interval midpoint value
        assert 0.0 <= mf.degree(5.0).midpoint <= 1.0
        assert mf.degree(5.0).midpoint == pytest.approx(0.5)

    def test_tanh_sigmoid_monotonicity(self) -> None:
        """Test that a positive slope results in a monotonically increasing function."""
        mf = TanhSigmoidMF(center=0.0, slope=2.0)
        assert mf.degree(-1.0).midpoint < mf.degree(0.0).midpoint < mf.degree(1.0).midpoint

    def test_tanh_sigmoid_extreme_inputs(self) -> None:
        """Test asymptotic behavior at extreme limits."""
        mf = TanhSigmoidMF(center=0.0, slope=1.0)
        assert mf.degree(100.0).midpoint == pytest.approx(1.0, abs=1e-5)
        assert mf.degree(-100.0).midpoint == pytest.approx(0.0, abs=1e-5)

    def test_tanh_sigmoid_invalid_slope(self) -> None:
        """Test that setting an invalid zero slope raises a ValueError."""
        with pytest.raises(ValueError):
            TanhSigmoidMF(center=2.0, slope=0.0)

class TestTanhBellMF:
    def test_tanh_bell_range_and_peak(self) -> None:
        """Test range compliance and that the midpoint approaches 1 for wide spans."""
        mf = TanhBellMF(left=2.0, right=8.0, slope=2.0)
        midpoint_val = mf.degree(5.0).midpoint
        assert 0.0 <= midpoint_val <= 1.0
        assert midpoint_val == pytest.approx(1.0, abs=1e-2)

    def test_tanh_bell_symmetry(self) -> None:
        """Test that the bell function is symmetric around its midpoint."""
        mf = TanhBellMF(left=2.0, right=8.0, slope=1.5)
        assert mf.degree(4.0).midpoint == pytest.approx(mf.degree(6.0).midpoint)
        assert mf.degree(1.0).midpoint == pytest.approx(mf.degree(9.0).midpoint)

    def test_tanh_bell_extremes(self) -> None:
        """Test decay behavior outside the transitions."""
        mf = TanhBellMF(left=-2.0, right=2.0, slope=1.0)
        assert mf.degree(100.0).midpoint == pytest.approx(0.0, abs=1e-5)
        assert mf.degree(-100.0).midpoint == pytest.approx(0.0, abs=1e-5)

    def test_tanh_bell_invalid_params(self) -> None:
        """Test parameter validation rules for slope and boundaries."""
        with pytest.raises(ValueError):
            TanhBellMF(left=5.0, right=5.0, slope=1.0)
        with pytest.raises(ValueError):
            TanhBellMF(left=2.0, right=8.0, slope=0.0)
