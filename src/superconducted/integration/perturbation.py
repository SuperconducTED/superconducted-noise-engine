"""Member perturbations for the Aer ensemble.

A perturbation is what makes the members of a
:class:`~superconducted.integration.aer_factory.FuzzyNoiseModelEnsemble`
differ (ADR-015, Issue #64). Each one implements
:class:`~superconducted.interfaces.MemberPerturbation`: given a member's index
and that member's own random generator, it returns the feature extractor,
rule base and defuzzifier the member is built from.

Status:

- :class:`IdentityPerturbation`: full. The default, under which members are
  identical, as they were before Issue #64.
- :class:`InputVectorPerturbation` and :class:`OffsetFeatureExtractor`: full.
  Additive Gaussian jitter of the feature vector with a relative scale,
  redrawn on a bound violation and never clipped (Issue #64 D1), the
  perturbation holding the vector it jitters (D6, option A).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

from ..interfaces import (
    CalibrationFeatureExtractor,
    Defuzzifier,
    MemberPerturbation,
    RuleBase,
)
from ..types import CalibrationSnapshot


class IdentityPerturbation(MemberPerturbation):
    """Return the three dependencies unchanged, so every member is the same model.

    This is what the ensemble uses when it is given no perturbation, and it
    is the regression guard for Issue #64: under it the ensemble yields the
    members it yielded before the perturbation slot existed, and the
    density-matrix identity ``rho_ens == rho_1`` of Issue #58 still holds.
    """

    def perturb(
        self,
        index: int,
        rng: np.random.Generator,
        *,
        feature_extractor: CalibrationFeatureExtractor,
        rule_base: RuleBase,
        defuzzifier: Defuzzifier,
    ) -> tuple[CalibrationFeatureExtractor, RuleBase, Defuzzifier]:
        """Return ``(feature_extractor, rule_base, defuzzifier)`` as given.

        The returned objects are the inputs themselves, not copies. ``index``
        is ignored and ``rng`` is not read, so an ensemble under this
        perturbation needs no seed. No side effects.
        """
        return feature_extractor, rule_base, defuzzifier


@dataclass(frozen=True)
class FeatureBound:
    """The interval one feature of the input vector must stay in.

    ``low`` and ``high`` are in the feature's own units; ``low_open`` and
    ``high_open`` say whether each end is excluded. A non-finite value is
    never inside, so an upper end of ``inf`` does not admit ``inf`` itself.
    Immutable.
    """

    low: float
    high: float
    low_open: bool
    high_open: bool

    def __post_init__(self) -> None:
        if math.isnan(self.low) or math.isnan(self.high) or not self.low <= self.high:
            raise ValueError(
                f"FeatureBound needs low <= high, got low={self.low}, high={self.high}"
            )

    def contains(self, value: float) -> bool:
        """Whether ``value`` is finite and inside the interval, ends as declared."""
        if not math.isfinite(value):
            return False
        above_low = value > self.low if self.low_open else value >= self.low
        below_high = value < self.high if self.high_open else value <= self.high
        return above_low and below_high


#: ``(0, inf)``, open at 0: a coherence time is positive (Issue #64 D1).
POSITIVE: Final[FeatureBound] = FeatureBound(0.0, math.inf, low_open=True, high_open=True)

#: ``[0, 1]``, closed at both ends: a probability (Issue #64 D1).
UNIT_INTERVAL: Final[FeatureBound] = FeatureBound(0.0, 1.0, low_open=False, high_open=False)

#: Feature name -> its bound. The bounds do not depend on units, so the
#: vectorizer's SI-seconds vector and the archive's microsecond vector, which
#: share these names, get the same ones.
_BOUND_BY_FEATURE: Final[dict[str, FeatureBound]] = {
    "mean_T1": POSITIVE,
    "mean_T2": POSITIVE,
    "mean_readout_error": UNIT_INTERVAL,
}


def bounds_for(feature_names: Sequence[str]) -> tuple[FeatureBound, ...]:
    """The bound of each named feature, in order.

    ``mean_T1`` and ``mean_T2`` get :data:`POSITIVE`; ``mean_readout_error``
    gets :data:`UNIT_INTERVAL`. Any other name raises ``ValueError``: a
    feature with no stated bound has no redraw rule, and guessing one would
    let a jitter cross a physical limit unseen. Pure.
    """
    unknown = [name for name in feature_names if name not in _BOUND_BY_FEATURE]
    if unknown:
        raise ValueError(
            f"no bound is defined for features {unknown}; known: {sorted(_BOUND_BY_FEATURE)}"
        )
    return tuple(_BOUND_BY_FEATURE[name] for name in feature_names)


def _read_only_vector(values: npt.ArrayLike, name: str) -> npt.NDArray[np.float64]:
    """A float64 1-D copy of ``values`` that cannot be written through."""
    array = np.array(values, dtype=np.float64, copy=True)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"{name} must be a non-empty 1-D vector, got shape {array.shape}")
    array.flags.writeable = False
    return array


class OffsetFeatureExtractor(CalibrationFeatureExtractor):
    """The wrapped extractor's output plus a fixed offset, for one feature vector.

    Built by :class:`InputVectorPerturbation` for one member. ``center`` is the
    vector the offset was drawn at and ``offset`` the member's jitter, both in
    the wrapped extractor's units. :meth:`extract` refuses any snapshot whose
    vector is not exactly ``center``, because the offset and the redraw rule
    were decided for that vector alone (D6, option A).

    Holds no state that :meth:`extract` changes, so repeated calls agree;
    ``FuzzyNoiseModel`` extracts more than once.
    """

    def __init__(
        self,
        wrapped: CalibrationFeatureExtractor,
        *,
        center: npt.ArrayLike,
        offset: npt.ArrayLike,
    ) -> None:
        self._wrapped = wrapped
        self._center = _read_only_vector(center, "center")
        self._offset = _read_only_vector(offset, "offset")
        if self._offset.shape != self._center.shape:
            raise ValueError(
                f"offset shape {self._offset.shape} does not match center shape "
                f"{self._center.shape}"
            )
        if self._center.size != wrapped.output_dim:
            raise ValueError(
                f"center has {self._center.size} entries but {type(wrapped).__name__} "
                f"returns {wrapped.output_dim}"
            )

    def extract(self, snapshot: CalibrationSnapshot) -> npt.NDArray[np.float64]:
        """Return the wrapped vector plus the offset, in the wrapped units.

        Raises ``ValueError`` if the wrapped vector is not exactly ``center``:
        the offset was drawn for that vector, and on any other the bound
        check it passed says nothing. The returned array is a new one.
        """
        values = np.asarray(self._wrapped.extract(snapshot), dtype=np.float64)
        if values.shape != self._center.shape or not np.array_equal(values, self._center):
            raise ValueError(
                f"{type(self._wrapped).__name__} returned {values.tolist()} for this snapshot, "
                f"but the offset was drawn at {self._center.tolist()}; an "
                "InputVectorPerturbation serves the one feature vector it was built for"
            )
        return values + self._offset

    @property
    def output_dim(self) -> int:
        """The wrapped extractor's; the offset changes values, not the shape."""
        return self._wrapped.output_dim

    @property
    def feature_names(self) -> tuple[str, ...]:
        """The wrapped extractor's names, unchanged."""
        return self._wrapped.feature_names

    @property
    def wrapped(self) -> CalibrationFeatureExtractor:
        """The extractor whose output is offset."""
        return self._wrapped

    @property
    def center(self) -> npt.NDArray[np.float64]:
        """The vector the offset was drawn at (read-only array)."""
        return self._center

    @property
    def offset(self) -> npt.NDArray[np.float64]:
        """The member's jitter, added to the wrapped output (read-only array)."""
        return self._offset


class InputVectorPerturbation(MemberPerturbation):
    """Jitter the feature vector with additive Gaussian noise, redrawn at a bound.

    Member ``i`` sees ``center + scale * z`` with ``z ~ N(0, I_d)`` drawn from
    its own generator (Issue #64 D1). An attempt with any component outside
    its bound, or not finite, is discarded and the whole vector redrawn, up to
    ``max_redraws`` times after the first, then ``ValueError``. Nothing is
    clipped: clipping would pile members on the bound and narrow the band,
    while the redraw keeps each member a draw from the Gaussian truncated to
    the bounds.

    The object holds the vector it jitters (D6, option A, #64 comment
    6863593077), so one object serves one feature vector. ``center`` and
    ``scale`` are in the extractor's units (SI seconds for ``mean_T1`` and
    ``mean_T2`` from ``BasicCalibrationVectorizer``, dimensionless for
    ``mean_readout_error``). There is no default scale: no code path picks
    one (File 03 Q2a).

    Args:
        center: The unperturbed feature vector, finite and inside ``bounds``.
        scale: The jitter's standard deviation per feature, finite and at
            least 0, same length as ``center``.
        bounds: One :class:`FeatureBound` per feature.
        max_redraws: Redraws allowed after the first attempt, an integer at
            least 0.

    Raises:
        ValueError: On any of the conditions above, naming which.
    """

    def __init__(
        self,
        center: npt.ArrayLike,
        scale: npt.ArrayLike,
        *,
        bounds: Sequence[FeatureBound],
        max_redraws: int = 64,
    ) -> None:
        self._center = _read_only_vector(center, "center")
        self._scale = _read_only_vector(scale, "scale")
        d = self._center.size
        if self._scale.shape != self._center.shape:
            raise ValueError(
                f"scale shape {self._scale.shape} does not match center shape {self._center.shape}"
            )
        if not np.all(np.isfinite(self._scale)) or np.any(self._scale < 0):
            raise ValueError(f"scale must be finite and non-negative, got {self._scale.tolist()}")
        self._bounds = tuple(bounds)
        if len(self._bounds) != d or not all(isinstance(b, FeatureBound) for b in self._bounds):
            raise ValueError(f"bounds must be {d} FeatureBound values, got {self._bounds!r}")
        outside = [j for j in range(d) if not self._bounds[j].contains(float(self._center[j]))]
        if outside:
            raise ValueError(
                f"center {self._center.tolist()} is not finite and inside its bounds at "
                f"positions {outside}; every draw would be refused"
            )
        if isinstance(max_redraws, bool) or not isinstance(max_redraws, int) or max_redraws < 0:
            raise ValueError(f"max_redraws must be an integer at least 0, got {max_redraws!r}")
        self._max_redraws = max_redraws
        self._r: float | None = None
        self._feature_names: tuple[str, ...] | None = None

    @classmethod
    def relative(
        cls,
        x: npt.ArrayLike,
        r: float,
        *,
        feature_names: Sequence[str],
        max_redraws: int = 64,
    ) -> InputVectorPerturbation:
        """Jitter ``x`` with ``scale = r * abs(x)``, one scalar ``r`` per arm.

        ``x`` is the unperturbed vector, which becomes ``center``; ``r`` is
        dimensionless, finite and positive, with no default (File 03 Q2a: the
        scale is fitted, never chosen by code). The bounds come from
        :func:`bounds_for` on ``feature_names``, which must have one name per
        entry of ``x``. ``max_redraws`` is passed to the constructor
        unchanged; D6's answer names no such argument here, and it is offered
        so that a caller of ``relative`` can set the redraw limit the
        constructor already takes. The returned object records ``r`` and the
        names.
        """
        if isinstance(r, bool) or not isinstance(r, (int, float)) or not math.isfinite(r):
            raise ValueError(f"r must be a finite positive number, got {r!r}")
        if r <= 0:
            raise ValueError(f"r must be a finite positive number, got {r!r}")
        names = tuple(feature_names)
        center = _read_only_vector(x, "x")
        if len(names) != center.size:
            raise ValueError(f"{len(names)} feature names for a vector of {center.size} entries")
        perturbation = cls(
            center,
            float(r) * np.abs(center),
            bounds=bounds_for(names),
            max_redraws=max_redraws,
        )
        perturbation._r = float(r)
        perturbation._feature_names = names
        return perturbation

    def perturb(
        self,
        index: int,
        rng: np.random.Generator,
        *,
        feature_extractor: CalibrationFeatureExtractor,
        rule_base: RuleBase,
        defuzzifier: Defuzzifier,
    ) -> tuple[CalibrationFeatureExtractor, RuleBase, Defuzzifier]:
        """Draw member ``index``'s offset and wrap the extractor with it.

        Each attempt reads exactly one ``rng.standard_normal(d)``. The bound
        test is on ``center + offset``, which is bit for bit what the
        returned extractor gives for a snapshot whose vector is ``center``.
        Returns ``(OffsetFeatureExtractor, rule_base, defuzzifier)``, the last
        two being the inputs themselves. Mutates no input; reads only ``rng``.

        Raises:
            ValueError: If the extractor's ``output_dim`` differs from the
                length of ``center``, or its ``feature_names`` differ from the
                names :meth:`relative` recorded, or no attempt lands inside
                the bounds.
        """
        d = self._center.size
        if feature_extractor.output_dim != d:
            raise ValueError(
                f"{type(feature_extractor).__name__} returns {feature_extractor.output_dim} "
                f"features but this perturbation was built for {d}"
            )
        if (
            self._feature_names is not None
            and tuple(feature_extractor.feature_names) != self._feature_names
        ):
            raise ValueError(
                f"{type(feature_extractor).__name__} names its features "
                f"{feature_extractor.feature_names}, but this perturbation was built for "
                f"{self._feature_names}"
            )
        for _ in range(self._max_redraws + 1):
            offset = self._scale * rng.standard_normal(d)
            candidate = self._center + offset
            if all(self._bounds[j].contains(float(candidate[j])) for j in range(d)):
                member = OffsetFeatureExtractor(
                    feature_extractor, center=self._center, offset=offset
                )
                return member, rule_base, defuzzifier
        raise ValueError(
            f"member {index}: no draw inside the bounds after {self._max_redraws + 1} attempts "
            f"(center {self._center.tolist()}, scale {self._scale.tolist()})"
        )

    @property
    def center(self) -> npt.NDArray[np.float64]:
        """The unperturbed vector, in the extractor's units (read-only array)."""
        return self._center

    @property
    def scale(self) -> npt.NDArray[np.float64]:
        """The jitter's standard deviation per feature, same units (read-only array)."""
        return self._scale

    @property
    def bounds(self) -> tuple[FeatureBound, ...]:
        """One bound per feature."""
        return self._bounds

    @property
    def max_redraws(self) -> int:
        """Redraws allowed after the first attempt."""
        return self._max_redraws

    @property
    def r(self) -> float | None:
        """The relative scale :meth:`relative` was given, or ``None``.

        ``None`` when the object was built with an explicit ``scale``; then
        no single ``r`` describes it.
        """
        return self._r

    @property
    def feature_names(self) -> tuple[str, ...] | None:
        """The names :meth:`relative` checked the bounds against, or ``None``."""
        return self._feature_names
