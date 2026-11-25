"""Per-member predicted (gamma, lambda) and their quantile band, for the fuzzy band's ladder row.

Issue #161 (gate L4), decision 1 (comment 7102611064): the fuzzy band is the 10% and 90% quantiles
of the members' predicted ``(gamma, lambda)``, in target space, before a conformal step whose form
is still open. Plan and criteria: ``docs/implementations/2026-11-25-member-target-band.md``.

What this module adds, and what it reuses:

- Members come from :class:`~superconducted.integration.aer_factory.FuzzyNoiseModelEnsemble` with
  :class:`~superconducted.integration.perturbation.InputVectorPerturbation` (PR-A1, #155). A
  member's ``crisp_params`` are its ``(gamma, lambda)`` under ``KrausChannelProjector``'s
  contract (entry 0 amplitude damping, entry 1 phase damping), after ``ProbabilityClip``. Nothing
  here re-implements the perturbation or the ensemble's seeding.
- :class:`TargetBand` is the target-space counterpart of
  :class:`~superconducted.benchmarks.metrics.IntervalBand`, which is over a circuit's outcome
  probabilities and so is not the ladder's band (#161, point A1 of comment 7037945584).

What it is not: a calibrated predictive interval. The band cuts the central ``1 - 2 alpha`` of
these members; how far the truth falls inside is what the conformal step and the ladder measure.
Nothing in this module reads the archive or any ladder row; the scoring script that does comes
after the pre-registration commit (#161, protocol item 1).

No argument here has a default that the pre-registration must fix: ``alpha``, the quantile
``method``, the member count, the jitter scale ``r`` and each state's seed are all required.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

import numpy as np
import numpy.typing as npt

from superconducted.calibration.features import ArchiveUnitFeatureExtractor
from superconducted.calibration.loader import parse_snapshot
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.integration.aer_factory import FuzzyNoiseModelEnsemble
from superconducted.integration.perturbation import InputVectorPerturbation
from superconducted.interfaces import Defuzzifier, RuleBase
from superconducted.types import CalibrationSnapshot

#: The two targets, in the order of ``crisp_params`` (ADR-027; ``is_identity_damping``).
TARGET_NAMES: Final[tuple[str, str]] = ("gamma", "lambda")


def snapshot_from_document(document: Mapping[str, Any], *, source: str) -> CalibrationSnapshot:
    """The engine's snapshot for one archive document, as the training-set builder makes it.

    ``parse_snapshot`` runs first, so a document it refuses raises ``CalibrationParseError``
    here too. The returned snapshot carries the document's own ``properties``, ``target`` and
    ``configuration`` (``None`` on backfilled documents) as ``training/dataset.py::_row`` does.
    ``timestamp`` is the document's own field; it does not enter the extractor, the rule base or
    the gate-eligibility parse, so it cannot move a member. ``source`` labels diagnostics. Pure.
    """
    parsed = parse_snapshot(document, source=source)
    return CalibrationSnapshot(
        backend=parsed.backend_name,
        timestamp=datetime.fromisoformat(str(document["timestamp"]).replace("Z", "+00:00")),
        schema_version=str(document.get("schema_version", "1.0.0")),
        properties=document["properties"],
        target=document.get("target"),
        configuration=document.get("configuration"),
    )


def _dependencies(
    snapshot: CalibrationSnapshot, *, rule_base: RuleBase, defuzzifier: Defuzzifier
) -> dict[str, Any]:
    """The engine as built, for one snapshot: the seven constructor keywords of an ensemble.

    The extractor is ``ArchiveUnitFeatureExtractor`` because the training TSV is in archive
    units (microseconds for T1 and T2; ``training/dataset.py``), so a rule base fitted on it reads
    the same vector. ``ProbabilityClip`` is the engine's default squashing and the one
    ``is_identity_damping`` is written for. The projector and the fuzzification strategy do not
    touch ``crisp_params``; the constructor needs them.
    """
    return {
        "calibration": snapshot,
        "feature_extractor": ArchiveUnitFeatureExtractor(),
        "rule_base": rule_base,
        "defuzzifier": defuzzifier,
        "squashing": ProbabilityClip(),
        "channel_projector": KrausChannelProjector(NoOpNormalization()),
        "fuzzification_strategy": PostGateFuzzification(),
    }


def ensemble_for_state(
    snapshot: CalibrationSnapshot,
    *,
    rule_base: RuleBase,
    defuzzifier: Defuzzifier,
    r: float,
    size: int,
    seed: np.random.SeedSequence,
) -> FuzzyNoiseModelEnsemble:
    """A perturbed ensemble of ``size`` members around one state's own feature vector.

    The centre ``x`` is ``ArchiveUnitFeatureExtractor``'s output on ``snapshot``, bit for bit,
    because the perturbation refuses any other vector; member ``k`` sees
    ``x + r |x| z_k`` (PR-A1). ``r`` is the dimensionless jitter scale, finite and positive.
    ``rule_base`` must have two outputs, ``(gamma, lambda)``; ``defuzzifier`` must accept its
    firing type (``WeightedAverageDefuzzifier`` for T1, ``NieTanDefuzzifier`` for IT2).

    ``seed`` is copied before use, so the result is a function of its entropy and spawn key:
    the same ``SeedSequence`` passed twice gives the same members, and the caller's object is not
    advanced. (The ensemble spawns its members' children from the sequence it is given, and
    spawning moves a sequence's counter.)

    Raises ``ValueError`` for a rule base without exactly two outputs, and whatever
    ``InputVectorPerturbation.relative`` and the ensemble raise for ``r`` and ``size``.
    """
    if rule_base.output_dim != len(TARGET_NAMES):
        raise ValueError(
            f"rule_base must have {len(TARGET_NAMES)} outputs (gamma, lambda); "
            f"got output_dim {rule_base.output_dim}"
        )
    dependencies = _dependencies(snapshot, rule_base=rule_base, defuzzifier=defuzzifier)
    extractor = dependencies["feature_extractor"]
    centre = np.asarray(extractor.extract(snapshot), dtype=np.float64)
    perturbation = InputVectorPerturbation.relative(
        centre, r, feature_names=extractor.feature_names
    )
    own_seed = np.random.SeedSequence(
        entropy=seed.entropy, spawn_key=seed.spawn_key, pool_size=seed.pool_size
    )
    return FuzzyNoiseModelEnsemble(
        **dependencies,
        ensemble_size=size,
        rng=np.random.default_rng(own_seed),
        perturbation=perturbation,
    )


def member_targets(ensemble: FuzzyNoiseModelEnsemble) -> npt.NDArray[np.float64]:
    """Each member's predicted ``(gamma, lambda)``, one row per member, in member order.

    Iterates ``ensemble`` once and stacks ``crisp_params[:2]``: dimensionless probabilities in
    ``[0, 1]`` after ``ProbabilityClip``. Returns a new read-only float64 array of shape
    ``(len(ensemble), 2)``. Raises whatever the ensemble raises while building a member.
    """
    rows = [np.array(member.crisp_params[:2], dtype=np.float64) for member in ensemble]
    table = np.stack(rows)
    table.flags.writeable = False
    return table


def _check_alpha(alpha: float) -> None:
    """Raise ``ValueError`` unless ``0 <= alpha < 0.5`` (NaN fails)."""
    if not 0.0 <= alpha < 0.5:
        raise ValueError(f"alpha must satisfy 0 <= alpha < 0.5; got {alpha}")


def _read_only(values: npt.ArrayLike, dtype: type) -> npt.NDArray[Any]:
    array: npt.NDArray[Any] = np.array(values, dtype=dtype, copy=True)
    array.flags.writeable = False
    return array


@dataclass(frozen=True, slots=True, eq=False)
class TargetBand:
    """The members' quantile band for ``(gamma, lambda)`` at one state.

    For component ``j`` of :data:`TARGET_NAMES`, ``lower[j]`` and ``upper[j]`` are the
    ``alpha`` and ``1 - alpha`` sample quantiles of the members' values under the named
    ``numpy.quantile`` ``method``. ``at_lower[j]`` and ``at_upper[j]`` count the members exactly
    at 0 and at 1, where ``ProbabilityClip`` piles a member whose raw output left ``[0, 1]``; a
    band with many members at a bound has an edge set by the clip, not by the model. All values
    are dimensionless.

    Arrays are copied on construction and made read-only. Raises ``ValueError`` when an array
    is not of shape ``(2,)``, a value is not finite or lies outside ``[0, 1]``, ``lower > upper``
    anywhere, ``alpha`` is outside ``[0, 0.5)``, ``method`` is empty, ``n_members < 2``, or a
    count is negative or above ``n_members``.
    """

    lower: npt.NDArray[np.float64]
    upper: npt.NDArray[np.float64]
    at_lower: npt.NDArray[np.int64]
    at_upper: npt.NDArray[np.int64]
    alpha: float
    method: str
    n_members: int
    names: tuple[str, str] = TARGET_NAMES

    def __post_init__(self) -> None:
        lower = _read_only(self.lower, np.float64)
        upper = _read_only(self.upper, np.float64)
        at_lower = _read_only(self.at_lower, np.int64)
        at_upper = _read_only(self.at_upper, np.int64)
        width = len(TARGET_NAMES)
        if any(array.shape != (width,) for array in (lower, upper, at_lower, at_upper)):
            raise ValueError(f"TargetBand arrays must have shape ({width},)")
        if tuple(self.names) != TARGET_NAMES:
            raise ValueError(f"TargetBand names must be {TARGET_NAMES}; got {self.names}")
        if not (np.all(np.isfinite(lower)) and np.all(np.isfinite(upper))):
            raise ValueError("TargetBand lower and upper must be finite")
        if lower.min() < 0.0 or upper.max() > 1.0:
            raise ValueError("TargetBand lower and upper must lie in [0, 1]")
        if np.any(lower > upper):
            raise ValueError("TargetBand requires lower <= upper for both targets")
        _check_alpha(self.alpha)
        if not self.method:
            raise ValueError("TargetBand method must name a numpy.quantile method")
        if self.n_members < 2:
            raise ValueError(f"TargetBand needs at least two members; got {self.n_members}")
        for counts in (at_lower, at_upper):
            if counts.min() < 0 or counts.max() > self.n_members:
                raise ValueError("TargetBand clip counts must lie in [0, n_members]")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)
        object.__setattr__(self, "at_lower", at_lower)
        object.__setattr__(self, "at_upper", at_upper)
        object.__setattr__(self, "alpha", float(self.alpha))
        object.__setattr__(self, "n_members", int(self.n_members))
        object.__setattr__(self, "names", TARGET_NAMES)


def target_band(members: npt.ArrayLike, *, alpha: float, method: str) -> TargetBand:
    """The ``alpha`` and ``1 - alpha`` quantile band of a member table, per target.

    ``members`` has shape ``(n_members, 2)``, columns in :data:`TARGET_NAMES` order, as
    :func:`member_targets` returns; at least two members, every value finite and in ``[0, 1]``.
    ``alpha`` and ``method`` have no default: the pre-registration fixes them (decision 1 fixes
    the levels at 10% and 90%, so ``alpha = 0.10``). ``method`` is passed to ``numpy.quantile``.

    No side effects; the input is not kept. Raises ``ValueError`` on any condition above, and on
    a ``method`` ``numpy.quantile`` does not know.
    """
    table = np.array(members, dtype=np.float64, copy=True)
    width = len(TARGET_NAMES)
    if table.ndim != 2 or table.shape[1] != width:
        raise ValueError(f"members must have shape (n_members, {width}); got {table.shape}")
    if table.shape[0] < 2:
        raise ValueError(
            f"a band needs at least two members; got {table.shape[0]} (one member is a point)"
        )
    if not np.all(np.isfinite(table)):
        raise ValueError("members must be finite")
    if table.min() < 0.0 or table.max() > 1.0:
        raise ValueError("members must lie in [0, 1]")
    if not (isinstance(alpha, float | int) and not isinstance(alpha, bool)) or math.isnan(alpha):
        raise ValueError(f"alpha must satisfy 0 <= alpha < 0.5; got {alpha}")
    _check_alpha(alpha)
    if not method:
        raise ValueError("method must name a numpy.quantile method")
    try:
        lower, upper = np.quantile(table, [alpha, 1.0 - alpha], axis=0, method=method)  # type: ignore[call-overload]
    except (ValueError, TypeError) as error:
        raise ValueError(f"method {method!r} is not a numpy.quantile method: {error}") from error
    return TargetBand(
        lower=lower,
        upper=upper,
        at_lower=(table == 0.0).sum(axis=0),
        at_upper=(table == 1.0).sum(axis=0),
        alpha=float(alpha),
        method=method,
        n_members=int(table.shape[0]),
    )
