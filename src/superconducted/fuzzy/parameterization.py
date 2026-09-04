"""Data-driven fuzzy parameterization.

Bridges empirical archive statistics with the fuzzy inference engine,
replacing hard-coded shape parameters with distribution-aware bounds.
"""
from __future__ import annotations

import itertools
import math
from typing import Any, Callable, List, Optional, Sequence, Type

import numpy as np
import numpy.typing as npt


from superconducted.fuzzy.tsk import TSKRule, TSKRuleBase

from superconducted.interfaces import CalibrationFeatureExtractor
from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.calibration.storage import CalibrationSnapshot
from superconducted.fuzzy.membership import (
    GaussianMF,
    IntervalGaussianMF,
    TanhMF,
    TanhSigmoidMF
)


class ClampingFeatureExtractor(CalibrationFeatureExtractor):
    """FR-12: Wraps BasicCalibrationVectorizer to clamp outliers to the [p1, p99] range.
    
    Protects the fuzzy inference engine from anomalies (e.g., infinite or 
    negative coherence times) by snapping out-of-bound values to the known
    empirical percentiles.
    """
    
    def __init__(self, p1_bounds: npt.NDArray[np.float64], p99_bounds: npt.NDArray[np.float64]) -> None:
        self._base = BasicCalibrationVectorizer()
        self._p1 = np.array(p1_bounds, dtype=np.float64)
        self._p99 = np.array(p99_bounds, dtype=np.float64)
        
    @property
    def output_dim(self) -> int:
        return self._base.output_dim
        
    @property
    def feature_names(self) -> tuple[str, ...]:
        return self._base.feature_names
        
    def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
        raw = self._base.extract(snapshot)
        # Apply strict clipping based on the archived statistical boundaries
        return np.clip(raw, self._p1, self._p99)


def _quantile_layout(samples: npt.NDArray[np.float64], k: int) -> dict[str, np.ndarray]:
    """Section 6.3: Computes the p1-p99 quantile binning layout for k levels."""
    
    # Linear interpolation required to move every center fluidly
    def Q(p: npt.NDArray[np.float64] | float) -> np.ndarray:
        return np.quantile(samples, p, method="linear")

    lo = float(Q(0.01))
    hi = float(Q(0.99))

    # Bin edges: e_0 to e_k
    j_e = np.arange(k + 1, dtype=np.float64)
    e = Q(0.01 + 0.98 * j_e / k)

    # Centers (bin-mid quantiles): c_1 to c_k
    j_c = np.arange(1, k + 1, dtype=np.float64)
    c = Q(0.01 + 0.98 * (j_c - 0.5) / k)

    # Reach: r_j = max(c_j - e_(j-1), e_j - c_j)
    r = np.maximum(c - e[:-1], e[1:] - c)
    
    # Margin & Slope parameters based on half-membership offsets
    m = r / 4.0
    s = math.atanh(0.8) / m

    return {"lo": lo, "hi": hi, "e": e, "c": c, "r": r, "m": m, "s": s}


def partition_anchors(
    samples: npt.NDArray[np.float64], 
    k: int = 3, 
    *, 
    placement: str = "quantile"
) -> npt.NDArray[np.float64]:
    """FR-6: Anchors for every shape are the layout centers (c_j)."""
    if placement != "quantile":
        raise ValueError(f"Placement strategy '{placement}' not supported.")
    
    layout = _quantile_layout(samples, k)
    return layout["c"]


def grid_partition(
    shape: Type[Any],
    samples: npt.NDArray[np.float64],
    k: int = 3,
    *,
    placement: str = "quantile",
    qubit_spread: Optional[float] = None
) -> List[Any]:
    """Section 6.3: Generates MFs bounded by empirical snapshot data quantiles."""
    if placement != "quantile":
        raise ValueError(f"Placement strategy '{placement}' not supported.")

    layout = _quantile_layout(samples, k)
    lo, e, c, r, m = layout["lo"], layout["e"], layout["c"], layout["r"], layout["m"]

    mfs = []
    
    if shape is GaussianMF:
        for j in range(k):
            sigma = r[j] / math.sqrt(2 * math.log(2))
            mfs.append(GaussianMF(c[j], sigma))
            
    elif shape is IntervalGaussianMF:
        if qubit_spread is None or qubit_spread <= 0:
            raise ValueError("IntervalGaussianMF requires strictly positive qubit_spread.")
        for j in range(k):
            sigma_low = r[j] / math.sqrt(2 * math.log(2))
            sigma_high = math.sqrt(sigma_low**2 + qubit_spread**2)
            mfs.append(IntervalGaussianMF(c[j], sigma_low, sigma_high))
            
    elif shape is TanhSigmoidMF:
        min_m = np.min(m)
        slope = math.atanh(0.8) / min_m
        for j in range(k):
            # Level 1 offsets its center to lo - m_1 to sit exactly at 0.98 membership on lo
            center = lo - m[0] if j == 0 else e[j]
            mfs.append(TanhSigmoidMF(center, slope))
            
    elif shape is TanhMF:
        for j in range(k):
            m_L = (c[j] - e[j]) / 4.0
            m_R = (e[j+1] - c[j]) / 4.0
            
            left = e[j] - m_L
            right = e[j+1] + m_R
            
            slope_left = math.atanh(0.8) / m_L
            slope_right = math.atanh(0.8) / m_R
            
            mfs.append(TanhMF(left, right, slope_left, slope_right))
            
    else:
        # TrapezoidalMF, TriangularMF, TanhBellMF are deferred to the M2 commit (FR-5)
        raise NotImplementedError(f"Mapping for {shape.__name__} has not landed yet (FR-5).")

    return mfs


def anchored_rule_base(
    per_input_mfs: Sequence[Sequence[Any]],
    target_fn: Callable[[npt.NDArray[np.float64]], npt.NDArray[np.float64]],
    *,
    anchors: Sequence[npt.NDArray[np.float64]]
) -> TSKRuleBase:
    """FR-6, Section 6.4: Constructs a TSKRuleBase mapped to empirical anchors."""
    input_dim = len(per_input_mfs)
    
    if len(anchors) != input_dim:
        raise ValueError(f"Expected {input_dim} anchor arrays, got {len(anchors)}")
        
    for i in range(input_dim):
        if len(anchors[i]) != len(per_input_mfs[i]):
            raise ValueError(
                f"Input {i}: length of anchors ({len(anchors[i])}) "
                f"must match length of MFs ({len(per_input_mfs[i])})."
            )

    mf_product = list(itertools.product(*per_input_mfs))
    anchor_product = list(itertools.product(*anchors))
    
    rules = []
    expected_out_dim = None

    for mf_tuple, anchor_tuple in zip(mf_product, anchor_product):
        x_r = np.array(anchor_tuple, dtype=np.float64)
        y_target = target_fn(x_r)
        
        if not np.all(np.isfinite(y_target)):
            raise ValueError(f"Target function returned non-finite values for anchor {x_r}")
            
        if expected_out_dim is None:
            expected_out_dim = y_target.shape[0]
        elif y_target.shape[0] != expected_out_dim:
            raise ValueError(f"Inconsistent output_dim. Expected {expected_out_dim}, got {y_target.shape[0]}")
            
        # Create a fresh zero-order consequent array.
        consequent = np.zeros((expected_out_dim, input_dim + 1), dtype=np.float64)
        consequent[:, -1] = y_target
        
        rules.append(TSKRule(antecedent_mfs=list(mf_tuple), consequent=consequent))
        
    return TSKRuleBase(rules)