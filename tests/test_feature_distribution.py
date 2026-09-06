"""Tests for the feature distribution survey script."""

import pytest
from scripts.feature_distribution import _compute_stats

def test_compute_stats_empty() -> None:
    """Test that an empty list returns all None values except n_usable=0."""
    n, std, p10, p50, p90 = _compute_stats([])
    assert n == 0
    assert std is None
    assert p10 is None
    assert p50 is None
    assert p90 is None

def test_compute_stats_normal() -> None:
    """Test normal computation of statistics (percentiles and std with ddof=1)."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    n, std, p10, p50, p90 = _compute_stats(values)
    assert n == 5
    assert std == pytest.approx(15.811, rel=1e-3)
    assert p10 == pytest.approx(14.0)
    assert p50 == pytest.approx(30.0)
    assert p90 == pytest.approx(46.0)

def test_compute_stats_single_value() -> None:
    """Test single value behavior (standard deviation requires at least 2 values)."""
    n, std, p10, p50, p90 = _compute_stats([42.0])
    assert n == 1
    assert std is None
    assert p10 == 42.0
    assert p50 == 42.0
    assert p90 == 42.0