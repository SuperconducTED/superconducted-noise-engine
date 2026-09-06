"""Data-driven fuzzy parameterization.

Bridges empirical archive statistics with the fuzzy inference engine,
replacing hard-coded shape parameters with distribution-aware bounds.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

from superconducted.fuzzy.membership import GaussianMF, IntervalGaussianMF, TanhMF, TanhSigmoidMF
from superconducted.fuzzy.tsk import TSKRule, TSKRuleBase
from superconducted.interfaces import CalibrationFeatureExtractor, MembershipFunction
from superconducted.types import CalibrationSnapshot


class ClampingFeatureExtractor(CalibrationFeatureExtractor):
    """FR-12: Wraps an inner extractor to clamp outliers to the [lo, hi] range.

    Protects the fuzzy inference engine from anomalies (e.g., infinite or
    negative coherence times) by snapping out-of-bound values to the known
    empirical percentiles.
    """

    def __init__(
        self,
        inner: CalibrationFeatureExtractor,
        lo: npt.NDArray[np.float64],
        hi: npt.NDArray[np.float64],
    ) -> None:
        self._inner = inner
        self._lo = np.array(lo, dtype=np.float64)
        self._hi = np.array(hi, dtype=np.float64)

        if self._lo.ndim != 1 or self._hi.ndim != 1:
            raise ValueError("Bounds must be 1-dimensional arrays.")
        if (
            self._lo.shape[0] != self._inner.output_dim
            or self._hi.shape[0] != self._inner.output_dim
        ):
            raise ValueError("Bounds dimensions must match the inner extractor's output_dim.")
        if not np.all(np.isfinite(self._lo)) or not np.all(np.isfinite(self._hi)):
            raise ValueError("Bounds must contain only finite numbers.")
        if not np.all(self._lo < self._hi):
            raise ValueError("Lower bounds (lo) must be strictly less than upper bounds (hi).")

        self._extraction_count = 0
        self._vector_count = 0
        self._clamped_component_count = 0

    @property
    def output_dim(self) -> int:
        return self._inner.output_dim

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self._inner.feature_names

    @property
    def extraction_count(self) -> int:
        return self._extraction_count

    @property
    def vector_count(self) -> int:
        return self._vector_count

    @property
    def clamped_component_count(self) -> int:
        return self._clamped_component_count

    def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
        raw = self._inner.extract(snapshot)

        self._extraction_count += 1
        self._vector_count += 1 if raw.ndim <= 1 else raw.shape[0]

        out_of_bounds = (raw < self._lo) | (raw > self._hi)
        self._clamped_component_count += int(np.sum(out_of_bounds))

        return np.clip(raw, self._lo, self._hi)


def _compute_layout(
    samples: npt.NDArray[np.float64], k: int, placement: str
) -> dict[str, np.ndarray]:
    """Computes layout centers (c), edges (e), and reaches (r) for supported strategies."""
    if k < 2:
        raise ValueError(f"Number of partitions (k) must be at least 2, got {k}")
    if samples.ndim != 1:
        raise ValueError(f"Samples must be a 1-dimensional array, got {samples.ndim}D")
    if not np.all(np.isfinite(samples)):
        raise ValueError("Samples array must contain only finite numbers")

    lo = float(np.quantile(samples, 0.01, method="linear"))
    hi = float(np.quantile(samples, 0.99, method="linear"))

    if placement == "quantile":

        def q_fn(p: npt.NDArray[np.float64] | float) -> Any:
            return np.quantile(samples, p, method="linear")

        j_e = np.arange(k + 1, dtype=np.float64)
        e = q_fn(0.01 + 0.98 * j_e / k)

        if not np.all(np.diff(e) > 0):
            raise ValueError(
                "Tied quantiles detected; variance is too low to create valid partitions."
            )

        j_c = np.arange(1, k + 1, dtype=np.float64)
        c = q_fn(0.01 + 0.98 * (j_c - 0.5) / k)
        r = np.maximum(c - e[:-1], e[1:] - c)

    elif placement == "endpoint":
        c = np.linspace(lo, hi, k)
        spacing = (hi - lo) / (k - 1)
        e = np.linspace(lo - spacing / 2, hi + spacing / 2, k + 1)
        r = np.full(k, spacing)

    elif placement == "interior":
        spacing = (hi - lo) / (k + 1)
        c = np.linspace(lo + spacing, hi - spacing, k)
        e = np.linspace(lo + spacing / 2, hi - spacing / 2, k + 1)
        r = np.full(k, spacing)

    else:
        raise ValueError(f"Placement strategy '{placement}' not supported.")

    m = r / 4.0
    return {"lo": lo, "hi": hi, "e": e, "c": c, "r": r, "m": m}


def partition_anchors(
    samples: npt.NDArray[np.float64], k: int = 3, *, placement: str = "quantile"
) -> npt.NDArray[np.float64]:
    """FR-6: Anchors for every shape are the layout centers (c_j)."""
    layout = _compute_layout(samples, k, placement)
    return layout["c"]


def grid_partition(
    shape: type[MembershipFunction],
    samples: npt.NDArray[np.float64],
    k: int = 3,
    *,
    placement: str = "quantile",
    qubit_spread: float | None = None,
) -> list[MembershipFunction]:
    """Section 6.3: Generates MFs bounded by empirical snapshot data quantiles."""

    if shape is not IntervalGaussianMF and qubit_spread is not None:
        raise ValueError(f"qubit_spread is not supported for T1 shape {shape.__name__}.")

    layout = _compute_layout(samples, k, placement)
    lo, e, c, r, m = layout["lo"], layout["e"], layout["c"], layout["r"], layout["m"]

    mfs: list[MembershipFunction] = []

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
            center = lo - m[0] if j == 0 else e[j]
            mfs.append(TanhSigmoidMF(center, slope))

    elif shape is TanhMF:
        for j in range(k):
            m_l = (c[j] - e[j]) / 4.0
            m_r = (e[j + 1] - c[j]) / 4.0

            min_m = min(m_l, m_r)
            slope = math.atanh(0.8) / min_m

            left = e[j] - m_l
            right = e[j + 1] + m_r

            mfs.append(TanhMF(left, right, slope, slope))

    else:
        raise NotImplementedError(f"Mapping for {shape.__name__} has not landed yet (FR-5).")

    return mfs


def anchored_rule_base(
    per_input_mfs: Sequence[Sequence[MembershipFunction]],
    target_fn: Callable[[npt.NDArray[np.float64]], npt.NDArray[np.float64]],
    *,
    anchors: Sequence[npt.NDArray[np.float64]],
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
    expected_out_dim = 0

    for mf_tuple, anchor_tuple in zip(mf_product, anchor_product, strict=True):
        x_r = np.array(anchor_tuple, dtype=np.float64)
        y_target = target_fn(x_r)

        if not np.all(np.isfinite(y_target)):
            raise ValueError(f"Target function returned non-finite values for anchor {x_r}")

        if expected_out_dim == 0:
            expected_out_dim = y_target.shape[0]
        elif y_target.shape[0] != expected_out_dim:
            raise ValueError(
                f"Inconsistent output_dim. Expected {expected_out_dim}, got {y_target.shape[0]}"
            )

        consequent = np.zeros((expected_out_dim, input_dim + 1), dtype=np.float64)
        consequent[:, -1] = y_target

        rules.append(TSKRule(antecedent_mfs=list(mf_tuple), consequent_params=consequent))

    return TSKRuleBase(rules=rules, input_dim=input_dim, output_dim=expected_out_dim)
