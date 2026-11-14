# ruff: noqa: E501
"""The #64 PR-A1 acceptance run (criterion 8, step 6).

    PYTHONPATH=src python docs/evidence/issue-64-pr-a1-acceptance/acceptance_run.py      (cwd: the worktree)

Reads one real archived ibm_fez snapshot by blob from a pinned calibration-data commit,
builds the ratified 3x3x3 Gaussian grid on it in the vectorizer's SI units, measures the
engine's sensitivity at the snapshot's feature vector, then runs N = 32 members under
InputVectorPerturbation.relative(x, R_SMOKE) and checks the pass bar written in the
implementation doc's "Plan, 2026-11-14: step 6" before this script ran:

  1. the identity ensemble's 32 members have bit-identical crisp_params;
  2. the jittered ensemble's 32 members are pairwise distinct;
  3. per output, the observed relative spread (sample std over mean) is within
     [0.5, 2] times the first-order prediction s_k = r * sqrt(sum_j E[k][j]^2);
  4. two constructions from one seed agree bit for bit; a second seed changes every member;
  5. every member's vector is inside its bounds; the redraw count is reported.

A control shows bar 3 can fail (r = 0.005 against the prediction for R_SMOKE). R_SMOKE is a
smoke value inside the r range #64's D1 to D5 work fitted (0.0299 to 0.1272, comment
6706908485), never a fitted value. Reads git objects only (GIT_NO_LAZY_FETCH=1), writes
only a temporary copy of the snapshot for CalibrationStorage, prints only. Exit 1 if a bar
fails.
"""

from __future__ import annotations

import hashlib
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.calibration.loader import UNIT_SCALE
from superconducted.calibration.storage import CalibrationStorage, _decode_filename_stem
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.defuzzification import WeightedAverageDefuzzifier
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.integration.aer_factory import (
    FuzzyNoiseModel,
    FuzzyNoiseModelEnsemble,
    first_viable_seed,
)
from superconducted.integration.perturbation import InputVectorPerturbation, OffsetFeatureExtractor
from superconducted.types import CalibrationSnapshot

REF = "b0482277ad54bc910b98445f75e5206f9b5baf30"
PATH = "snapshots/2026-11/ibm_fez/20261113T162759000000Z.json"
EXPECTED_BLOB = "b13ffe3c4821aac7b0d0844155acc2746acd0daf"
N = 32
R_SMOKE = 0.05
R_CONTROL = 0.005
RUN_SEED = 64
OTHER_SEED = 65
STEPS = (1e-3, 1e-4)
OUTPUTS = ("gamma", "lambda")


def git(*args: str) -> bytes:
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
    return subprocess.run(["git", *args], capture_output=True, check=True, env=env).stdout


def load_snapshot() -> CalibrationSnapshot:
    blob = git("rev-parse", f"{REF}:{PATH}").decode().strip()
    data = git("cat-file", "blob", f"{REF}:{PATH}")
    print(f"calibration-data {REF[:8]}  {PATH}")
    print(
        f"  blob {blob} (expected {EXPECTED_BLOB}: {blob == EXPECTED_BLOB}); sha256 of the blob {hashlib.sha256(data).hexdigest()}"
    )
    if blob != EXPECTED_BLOB:
        raise SystemExit("blob id differs from the one written in the plan")
    stem = Path(PATH).stem
    with tempfile.TemporaryDirectory() as root:
        target = Path(root) / "ibm_fez" / f"{stem}.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        snapshot = CalibrationStorage(Path(root)).load("ibm_fez", _decode_filename_stem(stem))
    print(
        f"  loaded: backend {snapshot.backend}, timestamp {snapshot.timestamp.isoformat()}, {len(snapshot.properties['qubits'])} qubits"
    )
    return snapshot


def dependencies(snapshot: CalibrationSnapshot, seed: int) -> dict[str, Any]:
    """The #58 grid layout of tests/conftest.py, on this snapshot, in SI units."""
    per_input_mfs: list[list[GaussianMF]] = []
    for field in ("T1", "T2", "readout_error"):
        values = [
            float(entry["value"]) * UNIT_SCALE[str(entry["unit"])]
            for qubit in snapshot.properties["qubits"]
            for entry in qubit
            if entry.get("name") == field
            and entry.get("value") is not None
            and math.isfinite(float(entry["value"]))
        ]
        lo, hi = min(values), max(values)
        sigma = (hi - lo) * 0.25
        per_input_mfs.append(
            [GaussianMF(center=float(c), sigma=sigma) for c in np.linspace(lo, hi, 3)]
        )
        print(
            f"  grid {field}: centres {[float(c) for c in np.linspace(lo, hi, 3)]}, sigma {sigma:.6g} (from {len(values)} qubits)"
        )
    return {
        "calibration": snapshot,
        "feature_extractor": BasicCalibrationVectorizer(),
        "rule_base": TSKRuleBase.from_grid(
            per_input_mfs=per_input_mfs,
            output_dim=2,
            consequent_init="random",
            rng=np.random.default_rng(seed),
        ),
        "defuzzifier": WeightedAverageDefuzzifier(),
        "squashing": ProbabilityClip(),
        "channel_projector": KrausChannelProjector(NoOpNormalization()),
        "fuzzification_strategy": PostGateFuzzification(),
    }


def main() -> int:
    import superconducted

    print("superconducted imported from", superconducted.__file__)
    print("numpy", np.__version__)
    snapshot = load_snapshot()

    print("\nrule-base seed (first_viable_seed over identity ensembles of 32):")
    grid_cache: dict[int, dict[str, Any]] = {}

    def build(seed: int) -> list[FuzzyNoiseModel]:
        grid_cache[seed] = (
            dependencies(snapshot, seed) if seed not in grid_cache else grid_cache[seed]
        )
        return list(FuzzyNoiseModelEnsemble(**grid_cache[seed]))

    _, seed = first_viable_seed(build, context="issue #64 PR-A1 acceptance run")
    deps = grid_cache[seed]
    print(f"  seed {seed}")

    vectorizer = deps["feature_extractor"]
    names = vectorizer.feature_names
    x = vectorizer.extract(snapshot)
    print(
        f"\nx = {dict(zip(names, x.tolist(), strict=True))}  (T1, T2 in s; readout dimensionless)"
    )

    def at_offset(offset: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """crisp_params, the raw defuzzified output and the vector used, through the step 3 code path."""
        member = OffsetFeatureExtractor(vectorizer, center=x, offset=offset)
        used = member.extract(snapshot)
        model = FuzzyNoiseModel(**{**deps, "feature_extractor": member})
        raw = deps["defuzzifier"].defuzzify(deps["rule_base"].evaluate(used))
        return model.crisp_params.copy(), np.asarray(raw, dtype=np.float64), used

    c0, raw0, _ = at_offset(np.zeros(3))
    print(
        f"crisp_params at x: {dict(zip(OUTPUTS, c0.tolist(), strict=True))}; raw before the clip {raw0.tolist()}; clip binding at x: {bool(np.any((raw0 < 0) | (raw0 > 1)))}"
    )
    if np.any(c0 <= 0):
        print(
            "STOP: an output is 0 at x, so its elasticity is undefined; find the cause (consequents, clip)"
        )
        return 1

    print("\nsensitivity: elasticity E[k][j] = d ln c_k / d ln x_j, central differences")
    elasticity: dict[float, np.ndarray] = {}
    for h in STEPS:
        E = np.zeros((2, 3))
        for j in range(3):
            step = np.zeros(3)
            step[j] = h * x[j]
            c_up, _, used_up = at_offset(step)
            c_down, _, used_down = at_offset(-step)
            E[:, j] = (np.log(c_up) - np.log(c_down)) / math.log(used_up[j] / used_down[j])
        elasticity[h] = E
        for k, out in enumerate(OUTPUTS):
            print(
                f"  h={h:g} {out:6s}: "
                + ", ".join(f"{n} {E[k, j]:+.6f}" for j, n in enumerate(names))
            )
    E_a, E_b = elasticity[STEPS[0]], elasticity[STEPS[1]]
    agree = float(np.max(np.abs(E_a - E_b) / np.maximum(np.abs(E_b), 1e-12)))
    print(f"  largest relative difference between the two steps: {agree:.3e}")
    E = E_b
    norms = np.sqrt(np.sum(E**2, axis=1))
    predicted = R_SMOKE * norms
    for k, out in enumerate(OUTPUTS):
        print(
            f"  {out}: ||E_k|| = {norms[k]:.6f}; predicted relative spread at r = {R_SMOKE}: s = {predicted[k]:.6f}"
        )
    if np.any(norms < 1e-6):
        print(
            "STOP: a sensitivity is near zero; find out whether the consequents, the clip or the jitter cause it"
        )
        return 1

    def jittered(
        seed_value: int, r: float
    ) -> tuple[list[FuzzyNoiseModel], InputVectorPerturbation]:
        perturbation = InputVectorPerturbation.relative(x, r, feature_names=names)
        ensemble = FuzzyNoiseModelEnsemble(
            **deps,
            ensemble_size=N,
            perturbation=perturbation,
            rng=np.random.default_rng(seed_value),
        )
        return list(ensemble), perturbation

    results: dict[str, bool] = {}

    print(f"\nbar 1: identity ensemble, N = {N}")
    identity = np.array([m.crisp_params for m in FuzzyNoiseModelEnsemble(**deps, ensemble_size=N)])
    results["1 identity members bit-identical"] = bool(np.all(identity == identity[0]))
    print(
        f"  distinct rows: {len(np.unique(identity, axis=0))}; equal to the model at x: {bool(np.array_equal(identity[0], c0))}"
    )

    print(
        f"\nbars 2, 3, 5: jittered ensemble, r_smoke = {R_SMOKE} (a smoke value), seed {RUN_SEED}"
    )
    members, perturbation = jittered(RUN_SEED, R_SMOKE)
    C = np.array([m.crisp_params for m in members])
    distinct = len(np.unique(C, axis=0))
    results["2 jittered members pairwise distinct"] = distinct == N
    print(f"  distinct members: {distinct} of {N}")
    observed = C.std(axis=0, ddof=1) / C.mean(axis=0)
    ratio = observed / predicted
    results["3 spread within [0.5, 2] of the prediction"] = bool(
        np.all((ratio >= 0.5) & (ratio <= 2.0))
    )
    for k, out in enumerate(OUTPUTS):
        print(
            f"  {out}: mean {C[:, k].mean():.6g}, observed relative spread {observed[k]:.6f}, predicted {predicted[k]:.6f}, ratio {ratio[k]:.3f}; members from {C[:, k].min():.6g} to {C[:, k].max():.6g}"
        )

    children = np.random.default_rng(RUN_SEED).bit_generator.seed_seq.spawn(N)
    redraws, inside, replay_equal, clip_binding = 0, 0, 0, 0
    for child, member_params in zip(children, C, strict=True):
        g = np.random.default_rng(child)
        for attempt in range(perturbation.max_redraws + 1):
            offset = perturbation.scale * g.standard_normal(3)
            v = perturbation.center + offset
            if all(b.contains(float(c)) for b, c in zip(perturbation.bounds, v, strict=True)):
                break
        redraws += attempt
        inside += all(b.contains(float(c)) for b, c in zip(perturbation.bounds, v, strict=True))
        params, raw, _ = at_offset(offset)
        replay_equal += bool(np.array_equal(params, member_params))
        clip_binding += bool(np.any((raw < 0) | (raw > 1)))
    results["5 every member inside its bounds"] = inside == N
    print(
        f"  replayed draws: {inside} of {N} inside the bounds, {redraws} redraws in all; replayed members equal to the ensemble's: {replay_equal} of {N}; members where the clip binds: {clip_binding}"
    )

    print(f"\nbar 4: reconstruction from seed {RUN_SEED}, and seed {OTHER_SEED}")
    again = np.array([m.crisp_params for m in jittered(RUN_SEED, R_SMOKE)[0]])
    other = np.array([m.crisp_params for m in jittered(OTHER_SEED, R_SMOKE)[0]])
    same = bool(np.array_equal(again, C))
    changed = int(sum(not np.array_equal(a, b) for a, b in zip(other, C, strict=True)))
    results["4 same seed bit-identical, other seed changes every member"] = same and changed == N
    print(
        f"  seed {RUN_SEED} twice bit-identical: {same}; members changed by seed {OTHER_SEED}: {changed} of {N}"
    )

    print(
        f"\ncontrol for bar 3: r = {R_CONTROL} against the prediction for r = {R_SMOKE} (must fall outside [0.5, 2])"
    )
    control = np.array([m.crisp_params for m in jittered(RUN_SEED, R_CONTROL)[0]])
    control_ratio = (control.std(axis=0, ddof=1) / control.mean(axis=0)) / predicted
    print(
        f"  ratios {control_ratio.round(4).tolist()}; outside the bar: {bool(np.all((control_ratio < 0.5) | (control_ratio > 2.0)))}"
    )

    print("\nresult")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print("  ALL PASS" if all(results.values()) else "  NOT ALL PASS")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
