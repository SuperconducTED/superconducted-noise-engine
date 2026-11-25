"""Probe behind the #161 member-band plan (2026-11-25). Reads no document at or after 2026-09-01.

    GIT_NO_LAZY_FETCH=1 PYTHONPATH=src python docs/evidence/fuzzy-band-members/probe.py <ref>

``<ref>`` is a ``calibration-data`` commit whose August 2026 ``ibm_fez`` blobs are local (run on
2026-11-25 with ``superconducted-noise-engine/calibration-data`` at ``4f6e6cbe``).

1. Builds a perturbed ``FuzzyNoiseModelEnsemble`` on one live and one backfilled document
   (``configuration`` null), with ``ArchiveUnitFeatureExtractor`` and
   ``InputVectorPerturbation.relative``, the centre taken from that extractor's own output.
2. Times a member on the ensemble path and on the lean path (extract, evaluate, defuzzify, squash).
3. Compares the identity member's ``crisp_params[:2]`` with the trainer's own prediction path.

The rule base has random consequents, so its values mean nothing physically; the probe measures
construction, cost and parity only. Timings need an otherwise idle machine (lesson L-093). The
figures in the plan come from a run of the throwaway copy of this script, made on 2026-11-25 before
it was committed here; this copy has the same logic and is owed one re-run on an idle machine
before any figure is cited again (lesson L-047).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from superconducted.calibration.features import ArchiveUnitFeatureExtractor
from superconducted.calibration.loader import parse_snapshot
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.defuzzification import WeightedAverageDefuzzifier
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.integration import aer_factory
from superconducted.integration.aer_factory import FuzzyNoiseModelEnsemble
from superconducted.integration.perturbation import InputVectorPerturbation
from superconducted.training import anfis
from superconducted.training.dataset import _decode_filename_stem
from superconducted.types import CalibrationSnapshot

CUT = "20260901"
ENV = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}


def show(ref: str, path: str) -> dict[str, Any]:
    out = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, check=True, env=ENV)
    loaded: dict[str, Any] = json.loads(out.stdout.decode("utf-8"))
    return loaded


def main(ref: str) -> None:
    print("superconducted from", aer_factory.__file__)
    names = subprocess.run(
        ["git", "ls-tree", "--name-only", ref, "snapshots/2026-08/ibm_fez/"],
        capture_output=True,
        check=True,
        text=True,
        env=ENV,
    ).stdout.split()
    names = [n for n in names if os.path.basename(n)[:8] < CUT]
    live = next(
        n
        for n in names
        if os.path.basename(n) < "20260805T234531" and show(ref, n).get("configuration")
    )
    backfilled = next(
        n
        for n in names
        if os.path.basename(n) > "20260806" and show(ref, n).get("configuration") is None
    )
    print("latest timestamp loaded:", max(os.path.basename(live), os.path.basename(backfilled)))

    extractor = ArchiveUnitFeatureExtractor()
    for label, path in (("live", live), ("backfilled", backfilled)):
        doc = show(ref, path)
        parsed = parse_snapshot(doc, source=path)
        snap = CalibrationSnapshot(
            backend=parsed.backend_name,
            timestamp=_decode_filename_stem(Path(path).stem),
            schema_version=str(doc.get("schema_version", "1.0.0")),
            properties=doc["properties"],
            target=doc.get("target"),
            configuration=doc.get("configuration"),
        )
        x = np.asarray(extractor.extract(snap), dtype=np.float64)
        print(f"\n[{label}] {path} names={extractor.feature_names} x={x.tolist()}")
        mfs = [
            [GaussianMF(center=float(c), sigma=abs(float(v)) * 0.3) for c in (v * 0.7, v, v * 1.3)]
            for v in x
        ]
        rule_base = TSKRuleBase.from_grid(
            per_input_mfs=mfs, output_dim=2, consequent_init="random", rng=np.random.default_rng(1)
        )
        deps: dict[str, Any] = {
            "calibration": snap,
            "feature_extractor": extractor,
            "rule_base": rule_base,
            "defuzzifier": WeightedAverageDefuzzifier(),
            "squashing": ProbabilityClip(),
            "channel_projector": KrausChannelProjector(NoOpNormalization()),
            "fuzzification_strategy": PostGateFuzzification(),
        }
        identity = next(iter(FuzzyNoiseModelEnsemble(**deps, ensemble_size=1)))
        engine = identity.crisp_params[:2]
        trainer = ProbabilityClip().squash(anfis._predict(rule_base, x[None, :])[0])[:2]
        relative = float(np.max(np.abs(engine - trainer) / np.maximum(np.abs(trainer), 1e-300)))
        same = "equal" if np.array_equal(engine, trainer) else f"max rel diff {relative}"
        print("identity crisp[:2]", engine.tolist(), "trainer squashed", trainer.tolist(), same)

        perturbation = InputVectorPerturbation.relative(
            x, 0.05, feature_names=extractor.feature_names
        )
        ensemble = FuzzyNoiseModelEnsemble(
            **deps, ensemble_size=32, rng=np.random.default_rng(7), perturbation=perturbation
        )
        start = time.perf_counter()
        members = np.stack([m.crisp_params[:2] for m in ensemble])
        per_member_ensemble = (time.perf_counter() - start) / 32
        start = time.perf_counter()
        for i in range(32):
            fe, rb, dz = ensemble._perturbed(i)
            ProbabilityClip().squash(dz.defuzzify(rb.evaluate(fe.extract(snap))))
        per_member_lean = (time.perf_counter() - start) / 32
        print(
            f"members: shape {members.shape}, at 0 per component {(members <= 0).sum(0).tolist()}, "
            f"q10..q90 {np.quantile(members, [0.1, 0.9], axis=0).tolist()}"
        )
        print(
            f"per member: ensemble {per_member_ensemble * 1e3:.2f} ms, "
            f"lean {per_member_lean * 1e3:.3f} ms"
        )


if __name__ == "__main__":
    main(sys.argv[1])
