# ruff: noqa: E501
"""Reproduce the two findings of Burak's review 5928253730 on PR #155.

    PYTHONPATH=".;src" python docs/evidence/issue-64-pr-a1-acceptance/review_5928253730_repro.py      (cwd: the worktree)

Run first on the head the review read (f7fd365d), before any fix, then again after
the fix; each line says what happened, so the two outputs can be compared.

1. A non-finite diagonal entry in a density-matrix result. NaN fails every `<` and
   `>` comparison, so it passes the range and trace checks of `_outcome_probabilities`.
   Printed: what `interval_band` does with such a member, and what
   `IntervalCoverage.compute` returns for such a reference (a NaN real part, a NaN
   imaginary part, an infinite imaginary part), plus the same question for a counts
   result holding a NaN count.
2. A subclass of `IdentityPerturbation` that draws from its generator. The
   ensemble's seed exemption tests `isinstance`, so such a subclass may be built
   without `rng`; printed: whether construction is refused and, if not, whether two
   ensembles built the same way give the same draws.

Prints only. Exit 0 whatever it finds.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from tests.test_perturbation import _dependencies

from superconducted.benchmarks.metrics import IntervalCoverage, interval_band
from superconducted.integration.aer_factory import FuzzyNoiseModelEnsemble
from superconducted.integration.perturbation import IdentityPerturbation
from superconducted.interfaces import CalibrationFeatureExtractor, Defuzzifier, RuleBase
from superconducted.types import CalibrationSnapshot, SimulationResult


def dm(diagonal: list[complex]) -> SimulationResult:
    return SimulationResult(
        shots=1,
        backend_label="probe",
        density_matrix=np.diag(np.array(diagonal, dtype=np.complex128)),
    )


def attempt(label: str, call: Any) -> None:
    try:
        value = call()
    except ValueError as error:
        print(f"  {label}: ValueError: {str(error)[:110]}")
        return
    print(f"  {label}: returned {value!r}")


def _band_summary(b: Any) -> str:
    return f"band lower {b.lower.tolist()}, upper {b.upper.tolist()}"


print("1. non-finite diagonal entries")
good = dm([0.5, 0.5])
band = interval_band([good, good], alpha=0.0)
for name, diagonal in (
    ("NaN real part", [complex(math.nan, 0.0), 0.5]),
    ("NaN imaginary part", [complex(0.5, math.nan), 0.5]),
    ("infinite imaginary part", [complex(0.5, math.inf), 0.5]),
):
    attempt(
        f"interval_band with one member's {name}",
        lambda d=diagonal: _band_summary(interval_band([good, dm(d)], alpha=0.0)),
    )
    attempt(
        f"IntervalCoverage of a reference with a {name}",
        lambda d=diagonal: IntervalCoverage().compute(band, dm(d)),
    )


counts_band = interval_band(
    [SimulationResult(shots=10, backend_label="probe", counts=Counter({"0": 5, "1": 5}))] * 2,
    alpha=0.0,
)
nan_counts = SimulationResult(
    shots=10, backend_label="probe", counts=Counter({"0": math.nan, "1": 5})
)
attempt(
    "IntervalCoverage of a counts reference with a NaN count",
    lambda: IntervalCoverage().compute(counts_band, nan_counts),
)

print("\n2. a stochastic subclass of IdentityPerturbation, built without rng")


class NoisyIdentity(IdentityPerturbation):
    """An identity in name only: it reads one draw per member."""

    def __init__(self) -> None:
        self.draws: list[float] = []

    def perturb(
        self,
        index: int,
        rng: np.random.Generator,
        *,
        feature_extractor: CalibrationFeatureExtractor,
        rule_base: RuleBase,
        defuzzifier: Defuzzifier,
    ) -> tuple[CalibrationFeatureExtractor, RuleBase, Defuzzifier]:
        self.draws.append(float(rng.standard_normal()))
        return feature_extractor, rule_base, defuzzifier


root = Path("tests/fixtures/calibration/ibm_fez_20260513T121322Z_with_gates.json")
data = json.loads(root.read_text(encoding="utf-8"))
snapshot = CalibrationSnapshot(
    backend=str(data["backend"]),
    timestamp=datetime.fromisoformat(str(data["timestamp"]).replace("Z", "+00:00")),
    schema_version=str(data["schema_version"]),
    properties=data["properties"],
    target=data.get("target"),
    configuration=data.get("configuration"),
)
runs: list[list[float]] = []
for _ in range(2):
    noisy = NoisyIdentity()
    try:
        ensemble = FuzzyNoiseModelEnsemble(
            **_dependencies(snapshot, 1), ensemble_size=3, perturbation=noisy
        )
    except ValueError as error:
        print(f"  construction without rng: ValueError: {str(error)[:110]}")
        break
    list(ensemble)
    runs.append(noisy.draws)
else:
    print(
        f"  construction without rng: accepted twice; first draws {runs[0][:2]} and {runs[1][:2]}; equal: {runs[0] == runs[1]}"
    )
