"""Smoke-run harness for AerSimulator against a synthetic fuzzy noise ensemble.

This script exercises the end-to-end fuzzy pipeline from a calibration
snapshot through feature extraction, TSK rule-base construction, and Aer
noise-model synthesis.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

from superconducted.benchmarks.circuits import qft_circuit
from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.defuzzification import WeightedAverageDefuzzifier
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.integration.aer_factory import (
    DEFAULT_SEED_SEARCH_LIMIT,
    FuzzyNoiseModel,
    FuzzyNoiseModelEnsemble,
    first_viable_seed,
)
from superconducted.types import CalibrationSnapshot

SHOTS_PER_MEMBER: Final[int] = 1024
ENSEMBLE_SIZES: Final[tuple[int, ...]] = (1, 8, 16)

# ADR-010 ratifies a 3x3x3 (27-rule) baseline grid. `from_grid` builds
# prod_i K_i rules, so K_i must be 3 on each of the three feature
# dimensions produced by `BasicCalibrationVectorizer`.
MFS_PER_FEATURE: Final[int] = 3

# Two candidate center layouts for those three MFs, kept side by side so
# they can be compared empirically (see scripts/compare_mf_placement.py
# and Issue #31). Both use the same sigma, so the comparison isolates
# placement.
#   endpoint · centers at lo, lo + span/2, hi
#             mu == 1 exactly at both range extremes; widest gap between
#             adjacent centers, so the weakest interior coverage.
#   interior · centers at the midpoints of equal thirds
#             uniform spacing, best worst-case coverage; nothing peaks at
#             the extremes.
MF_PLACEMENT_ENDPOINT: Final[str] = "endpoint"
MF_PLACEMENT_INTERIOR: Final[str] = "interior"
MF_PLACEMENTS: Final[tuple[str, ...]] = (MF_PLACEMENT_ENDPOINT, MF_PLACEMENT_INTERIOR)

# Upper bound on the deterministic consequent-seed search. Kept as an alias
# of the library default so the script and `first_viable_seed` cannot drift;
# ADR-024 explains why 64 is generous rather than arbitrary.
CONSEQUENT_SEED_SEARCH_LIMIT: Final[int] = DEFAULT_SEED_SEARCH_LIMIT

# Provisional. Issue #31 chose Option A (the endpoint layout) as the fix;
# the comparison script reports which layout wins on which metric, and
# flipping this constant is the whole cost of changing the decision.
DEFAULT_MF_PLACEMENT: Final[str] = MF_PLACEMENT_ENDPOINT

FEATURE_SCALES: Final[dict[str, tuple[float, float]]] = {
    "mean_T1": (0.0, 100e-6),
    "mean_T2": (0.0, 100e-6),
    "mean_readout_error": (0.0, 0.1),
}


def run_ensemble(
    members: list[FuzzyNoiseModel],
    circuit: QuantumCircuit,
    shots: int,
    simulator: AerSimulator,
) -> dict[str, int]:
    """Run each ensemble member and mean-aggregate counts per ADR-016.

    The ``simulator`` is caller-owned so the caller can warm it before
    timing and share one instance across calls (the smoke harness does
    this to keep the warmup meaningful).

    With rng=default_rng(0) and ADR-015 deferred, members are currently
    identical and the mean equals a single member's behavior. This is
    the documented current state, not a smoke-harness deviation.

    Per-key independent rounding can leave sum(returned.values()) differing
    from `shots` by at most one count per bin in tie/fractional cases.
    The benchmark harness in superconducted.benchmarks.harness preserves
    the count total via SimulationResult.shots = shots * len(members);
    this dict-returning smoke wrapper accepts the small drift.
    """
    if not members:
        raise ValueError("Cannot run with an empty ensemble")

    per_member: list[dict[str, int]] = []
    for nm in members:
        prepared_circuit, actual_noise_model = nm.prepare(circuit.copy())
        transpiled_circuit = transpile(prepared_circuit, backend=simulator)
        result = simulator.run(
            transpiled_circuit, shots=shots, noise_model=actual_noise_model
        ).result()
        per_member.append(dict(result.get_counts()))

    totals: dict[str, int] = {}
    for d in per_member:
        for k, v in d.items():
            totals[k] = totals.get(k, 0) + v
    n = len(per_member)
    return {k: round(v / n) for k, v in totals.items()}


def mf_centers(lo: float, hi: float, placement: str = DEFAULT_MF_PLACEMENT) -> tuple[float, ...]:
    """Return the three Gaussian centers for one feature range.

    ``placement`` selects between the two layouts under comparison in
    Issue #31. Both return ``MFS_PER_FEATURE`` centers spanning
    ``[lo, hi]``; they differ only in where those centers sit.
    """
    if placement not in MF_PLACEMENTS:
        raise ValueError(f"unknown placement {placement!r}; known: {list(MF_PLACEMENTS)}")
    span = hi - lo
    if placement == MF_PLACEMENT_ENDPOINT:
        return (lo, lo + span * 0.5, hi)
    return (lo + span / 6.0, lo + span * 0.5, lo + span * 5.0 / 6.0)


def _default_mfs_for_feature(
    feature_name: str, placement: str = DEFAULT_MF_PLACEMENT
) -> list[GaussianMF]:
    """Three Gaussian MFs covering one feature's physical range.

    Three, not two: ADR-010 ratifies a 3x3x3 (27-rule) baseline and
    `from_grid` multiplies the per-input MF counts, so two MFs per feature
    silently produced an 8-rule grid (Issue #31). The previous two-MF
    version also left the upper half of every range uncovered — no MF was
    centered at or near ``hi`` — which mattered because long T1/T2 and high
    readout error are exactly the calibration states the noise model must
    discriminate.

    Feature-specific numeric ranges are used rather than one shared grid,
    so T1/T2 (seconds) and readout_error (dimensionless) are not treated as
    if they were on the same scale.
    """
    if feature_name not in FEATURE_SCALES:
        raise ValueError(
            f"unknown feature {feature_name!r}; known features: {list(FEATURE_SCALES)}"
        )
    lo, hi = FEATURE_SCALES[feature_name]
    sigma = (hi - lo) * 0.25
    return [GaussianMF(center=c, sigma=sigma) for c in mf_centers(lo, hi, placement)]


def _ensemble_for_seed(
    snapshot: CalibrationSnapshot, n: int, placement: str, seed: int
) -> list[FuzzyNoiseModel]:
    """Build the ensemble for one consequent-init seed, with no viability check."""
    vectorizer = BasicCalibrationVectorizer()
    # Let `extract` raise if the snapshot is invalid; don't silently
    # fallback to a noisy one-dimensional default which masks problems.
    dummy_features = vectorizer.extract(snapshot)
    if dummy_features.shape[0] != vectorizer.output_dim:
        raise ValueError(
            "BasicCalibrationVectorizer returned unexpected feature dimension "
            f"{dummy_features.shape[0]}; expected {vectorizer.output_dim}"
        )

    mfs_list: list[list[GaussianMF]] = []
    for feature_name in vectorizer.feature_names:
        mfs_list.append(_default_mfs_for_feature(feature_name, placement))

    ensemble_iter = FuzzyNoiseModelEnsemble(
        calibration=snapshot,
        feature_extractor=vectorizer,
        rule_base=TSKRuleBase.from_grid(
            per_input_mfs=mfs_list,
            output_dim=2,
            consequent_init="random",
            rng=np.random.default_rng(seed),
        ),
        defuzzifier=WeightedAverageDefuzzifier(),
        squashing=ProbabilityClip(),
        channel_projector=KrausChannelProjector(NoOpNormalization()),
        fuzzification_strategy=PostGateFuzzification(),
        ensemble_size=n,
    )
    return list(ensemble_iter)


def generate_safe_ensemble_with_seed(
    snapshot: CalibrationSnapshot,
    n: int,
    placement: str = DEFAULT_MF_PLACEMENT,
    seed_limit: int = CONSEQUENT_SEED_SEARCH_LIMIT,
) -> tuple[list[FuzzyNoiseModel], int]:
    """Build the ensemble and report which consequent seed produced it.

    `consequent_init="random"` draws consequents from a zero-mean Gaussian,
    so the sign of the defuzzified output is a property of the draw, not of
    the design. A draw whose first two crisp parameters are all non-positive
    yields an identity channel, which makes the smoke run measure nothing.
    That happens with probability exactly 1/4 — see ADR-024, which also
    explains why `from_grid` cannot rule it out on the caller's behalf.

    Rather than hard-coding a seed that happens to work — which is what the
    script did until Issue #31, and which silently broke the moment the grid
    grew from 8 rules to the ratified 27 — this delegates to
    `first_viable_seed`, walking seeds `0, 1, 2, ...` and returning the first
    non-degenerate ensemble. The search is deterministic, so the chosen seed
    is reproducible on any machine.

    Raises `ValueError` if no seed below `seed_limit` yields a viable
    ensemble, which would mean the degeneracy is structural rather than a
    bad draw. The grid this script builds is passed as `context` so it
    appears in that message; the library search cannot know it.
    """
    return first_viable_seed(
        lambda seed: _ensemble_for_seed(snapshot, n, placement, seed),
        seed_limit=seed_limit,
        context=(
            f"Placement was {placement!r} with {MFS_PER_FEATURE} MFs per feature "
            f"({MFS_PER_FEATURE**3} rules)."
        ),
    )


def generate_safe_ensemble(
    snapshot: CalibrationSnapshot, n: int, placement: str = DEFAULT_MF_PLACEMENT
) -> list[FuzzyNoiseModel]:
    """Construct a `FuzzyNoiseModelEnsemble` with conservative default MFs.

    Uses the `BasicCalibrationVectorizer` to infer the input dimension from
    the provided snapshot and builds the ratified 3x3x3 grid of Gaussian MFs:
    `MFS_PER_FEATURE` MFs on each of the vectorizer's three features, which
    `from_grid` expands to 27 rules (ADR-010).

    See `generate_safe_ensemble_with_seed` for the consequent-seed search;
    use that directly if you need to report which seed was used.
    """
    members, _seed = generate_safe_ensemble_with_seed(snapshot, n, placement)
    return members


def _load_snapshot(path: Path) -> CalibrationSnapshot:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    return CalibrationSnapshot(
        backend=str(data["backend"]),
        timestamp=timestamp,
        schema_version=str(data["schema_version"]),
        properties=dict(data["properties"]),
        target=data.get("target"),
        configuration=data.get("configuration"),
    )


def _synthetic_snapshot() -> CalibrationSnapshot:
    return CalibrationSnapshot(
        backend="ibm_fez",
        timestamp=datetime.now(UTC),
        schema_version="1.0",
        properties={
            "qubits": [
                [
                    {"name": "T1", "value": 50e-6},
                    {"name": "T2", "value": 50e-6},
                    {"name": "readout_error", "value": 0.01},
                ]
            ]
        },
        target={},
        configuration={},
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 scripts/first_ensemble_run.py",
        description="Smoke-run AerSimulator against a synthetic fuzzy noise ensemble.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Path to a JSON-formatted CalibrationSnapshot file.",
    )
    parser.add_argument(
        "--qubits",
        type=int,
        default=2,
        help="Number of qubits for the QFT circuit (default: 2).",
    )
    parser.add_argument(
        "--mf-placement",
        choices=MF_PLACEMENTS,
        default=DEFAULT_MF_PLACEMENT,
        help=(
            "Gaussian center layout per feature "
            f"(default: {DEFAULT_MF_PLACEMENT}). See scripts/compare_mf_placement.py."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.qubits <= 0:
        raise ValueError(f"--qubits must be positive; got {args.qubits}")

    snapshot = _load_snapshot(args.snapshot) if args.snapshot else _synthetic_snapshot()

    circuit = qft_circuit(args.qubits)

    # One AerSimulator instance shared across the warmup and every timed
    # run_ensemble call below, so the warmup actually amortizes the C++
    # init of the instance that gets measured (round 4 review).
    simulator = AerSimulator()

    print("--- Ensemble Scaling Tests (Real Concretes) ---")
    for n in ENSEMBLE_SIZES:
        members, consequent_seed = generate_safe_ensemble_with_seed(snapshot, n, args.mf_placement)
        print(f"  [n={n}] mf_placement={args.mf_placement} consequent_seed={consequent_seed}")
        # Warmup the shared AerSimulator instance to amortize C++ init out of
        # the timed run_ensemble calls below.
        prep_circ_w, prep_nm_w = members[0].prepare(circuit.copy())
        transpiled_w = transpile(prep_circ_w, backend=simulator)
        simulator.run(transpiled_w, shots=1, noise_model=prep_nm_w).result()
        t0 = time.perf_counter()
        counts = run_ensemble(members, circuit, SHOTS_PER_MEMBER, simulator)
        elapsed = time.perf_counter() - t0
        print(f"N={n} elapsed={elapsed:.2f}s members={n} shots_per_member={SHOTS_PER_MEMBER}")
        print(f"  counts: {counts}\n")

    print("--- Sanity Check (Single Member, 8192 Shots) ---")
    single_member = generate_safe_ensemble(snapshot, 1)[0]
    t0_sanity = time.perf_counter()
    prep_circ, prep_nm = single_member.prepare(circuit.copy())
    transpiled_sanity = transpile(prep_circ, backend=simulator)
    result_sanity = simulator.run(transpiled_sanity, shots=8192, noise_model=prep_nm).result()
    sanity_counts = result_sanity.get_counts()
    elapsed_sanity = time.perf_counter() - t0_sanity
    print(f"Sanity Run elapsed={elapsed_sanity:.2f}s total_shots=8192")
    print(f"  counts: {sanity_counts}")


if __name__ == "__main__":
    main()
