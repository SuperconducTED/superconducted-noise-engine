"""What a no-information predictor scores on the #125 decision rule's thresholds.

Protocol: ``docs/roadmap/2026-10-24-issue-125-preregistration.md`` section 3.8, committed before
this script. Two computations, no archive and no hardware:

- **Arm B, exactly.** Six layouts, 13 Arm B jobs (job 1 is Arm A only). Under null (i) each
  predictor's ranking is an independent uniform random permutation of the measured order. All
  720 rankings are enumerated for one job, giving the joint distribution of ``sum d^2`` and
  "top layout is the measured best"; it is convolved over 13 jobs. With ``reading``, ``level``
  and ``band`` independent and identically distributed, every pass probability is a sum over
  ``reading``'s joint outcome. A Monte Carlo run checks the exact figures.
- **Arm A condition A1, by simulation.** Per-row error differences ``D = u_day + e_row`` with mean
  zero (the two predictors equally accurate), ``u_day`` a stationary AR(1) over 14 days carrying a
  share ``rho`` of the variance, 56 rows a day. The circular block bootstrap's 90% percentile
  interval of the mean is computed at block lengths 1 and 3; reported: the share of runs whose
  interval lies wholly on one named side (the false-pass rate of the one-sided claim).

Run from the repository root::

    python docs/evidence/hardware-reading-vs-level/null_values.py
        --out docs/evidence/hardware-reading-vs-level/

(one command, split here for width)
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

N_LAYOUTS = 6
N_ARM_B_JOBS = 13
N_DAYS = 14
ROWS_PER_DAY = 56  # eight discriminating qubits, seven delays
N_RUNS = 2000
N_RESAMPLES = 2000
BLOCK_LENGTHS = (1, 3)
PHIS = (0.0, 0.5)
RHOS = (0.0, 0.3, 0.7)
ROOT_SEED = 1251028
MC_CHECK_DRAWS = 200_000


def one_job_joint() -> np.ndarray:
    """Joint pmf of (sum d^2 / 2, top hit) for one uniform random ranking of six layouts.

    Shape ``(S + 1, 2)`` with ``S = max(sum d^2) / 2 = 35``; ``sum d^2`` is always even.
    """
    max_half = sum((N_LAYOUTS - 1 - 2 * i) ** 2 for i in range(N_LAYOUTS)) // 2
    counts = np.zeros((max_half + 1, 2))
    for perm in itertools.permutations(range(N_LAYOUTS)):
        ssd = sum((p - i) ** 2 for i, p in enumerate(perm))
        counts[ssd // 2, 1 if perm[0] == 0 else 0] += 1
    return counts / math.factorial(N_LAYOUTS)


def convolve_jobs(joint: np.ndarray, n_jobs: int) -> np.ndarray:
    """Distribution of (total sum d^2 / 2, total top hits) over ``n_jobs`` independent jobs."""
    s_one, h_one = joint.shape
    total = np.zeros(((s_one - 1) * n_jobs + 1, (h_one - 1) * n_jobs + 1))
    total[0, 0] = 1.0
    for _ in range(n_jobs):
        nxt = np.zeros_like(total)
        for s in range(s_one):
            for h in range(h_one):
                p = joint[s, h]
                if p == 0.0:
                    continue
                nxt[s:, h:] += p * total[: total.shape[0] - s, : total.shape[1] - h]
        total = nxt
    return total


def arm_b_null(total: np.ndarray) -> dict[str, float]:
    """Pass probabilities of B1, B2 and their joint under null (i).

    ``total[s, h]``: probability that a predictor's 13-job total is ``2 s`` in ``sum d^2`` and
    ``h`` top hits. "At least as well" on mean Spearman is ``s_pred <= s_reading``; "at least as
    often" is ``h_pred >= h_reading``.
    """
    p_s = total.sum(axis=1)
    p_h = total.sum(axis=0)
    cdf_s = np.cumsum(p_s)  # P(S <= s)
    sf_h = np.cumsum(p_h[::-1])[::-1]  # P(H >= h)
    # P(S <= s and H >= h): cumulative over s ascending, over h descending
    both = np.cumsum(np.cumsum(total[:, ::-1], axis=1)[:, ::-1], axis=0)

    q1 = cdf_s[:, None] * np.ones_like(total)
    q2 = np.ones_like(total) * sf_h[None, :]
    qj = both
    neither = 1.0 - q1 - q2 + qj  # P(not B1 and not B2) for one predictor

    def expect(x: np.ndarray) -> float:
        return float((total * x).sum())

    return {
        "b1_level": expect(q1),
        "b2_level": expect(q2),
        "b1_and_b2_level": expect(qj),
        "b1_level_or_band": expect(1.0 - (1.0 - q1) ** 2),
        "b2_level_or_band": expect(1.0 - (1.0 - q2) ** 2),
        "joint_one_predictor_meets_both": expect(1.0 - (1.0 - qj) ** 2),
        "joint_each_condition_by_either": expect(
            1.0 - (1.0 - q1) ** 2 - (1.0 - q2) ** 2 + neither**2
        ),
        "p_tie_b1_level": float((p_s**2).sum()),
        "p_tie_b2_level": float((p_h**2).sum()),
    }


def arm_b_monte_carlo(rng: np.random.Generator, draws: int) -> dict[str, float]:
    """The same pass probabilities by direct simulation, as a check on the exact computation."""
    perms = np.array(list(itertools.permutations(range(N_LAYOUTS))))
    ssd = ((perms - np.arange(N_LAYOUTS)) ** 2).sum(axis=1)
    hit = (perms[:, 0] == 0).astype(int)
    idx = rng.integers(0, len(perms), size=(3, draws, N_ARM_B_JOBS))
    s = ssd[idx].sum(axis=2)
    h = hit[idx].sum(axis=2)
    r, lv, bd = 0, 1, 2
    b1 = s[lv] <= s[r]
    b2 = h[lv] >= h[r]
    b1b = s[bd] <= s[r]
    b2b = h[bd] >= h[r]
    return {
        "b1_level": float(b1.mean()),
        "b2_level": float(b2.mean()),
        "b1_and_b2_level": float((b1 & b2).mean()),
        "b1_level_or_band": float((b1 | b1b).mean()),
        "b2_level_or_band": float((b2 | b2b).mean()),
        "joint_one_predictor_meets_both": float(((b1 & b2) | (b1b & b2b)).mean()),
        "joint_each_condition_by_either": float(((b1 | b1b) & (b2 | b2b)).mean()),
    }


def ar1_day_effects(rng: np.random.Generator, n_runs: int, phi: float, rho: float) -> np.ndarray:
    """Stationary AR(1) day effects with variance ``rho``, shape ``(n_runs, N_DAYS)``."""
    u = np.empty((n_runs, N_DAYS))
    u[:, 0] = rng.normal(0.0, math.sqrt(rho), n_runs)
    innov_sd = math.sqrt(rho * (1.0 - phi**2))
    for t in range(1, N_DAYS):
        u[:, t] = phi * u[:, t - 1] + rng.normal(0.0, innov_sd, n_runs)
    return u


def block_indices(rng: np.random.Generator, n_resamples: int, block: int) -> np.ndarray:
    """Circular block bootstrap day indices, shape ``(n_resamples, N_DAYS)``."""
    n_blocks = -(-N_DAYS // block)
    starts = rng.integers(0, N_DAYS, size=(n_resamples, n_blocks))
    offsets = np.arange(block)
    idx = (starts[:, :, None] + offsets[None, None, :]) % N_DAYS
    return idx.reshape(n_resamples, n_blocks * block)[:, :N_DAYS]


def arm_a_false_pass(rng: np.random.Generator, phi: float, rho: float) -> dict[str, Any]:
    """Share of null runs whose 90% interval lies wholly below zero, per block length."""
    u = ar1_day_effects(rng, N_RUNS, phi, rho)
    # every day has the same row count, so the row-weighted mean is the mean of day means
    e_mean = rng.normal(0.0, math.sqrt((1.0 - rho) / ROWS_PER_DAY), (N_RUNS, N_DAYS))
    day_means = u + e_mean
    out: dict[str, Any] = {}
    for block in BLOCK_LENGTHS:
        below = 0
        for run in range(N_RUNS):
            idx = block_indices(rng, N_RESAMPLES, block)
            boot = day_means[run][idx].mean(axis=1)
            if np.quantile(boot, 0.95) < 0.0:
                below += 1
        rate = below / N_RUNS
        out[f"block_{block}"] = {
            "false_pass_rate": rate,
            "mc_standard_error": math.sqrt(rate * (1.0 - rate) / N_RUNS),
        }
    return out


def write_json_lf(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON with LF line endings, so its recorded hash is the same on every checkout."""
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    root = np.random.SeedSequence(ROOT_SEED)
    cases = [(phi, rho) for phi in PHIS for rho in RHOS]
    children = root.spawn(len(cases) + 1)

    joint = one_job_joint()
    total = convolve_jobs(joint, N_ARM_B_JOBS)
    if not math.isclose(float(total.sum()), 1.0, abs_tol=1e-12):
        print(f"error: convolved pmf sums to {total.sum()!r}", file=sys.stderr)
        return 1
    exact = arm_b_null(total)
    mc = arm_b_monte_carlo(np.random.default_rng(children[-1]), MC_CHECK_DRAWS)
    check = {}
    for key, value in mc.items():
        se = math.sqrt(max(exact[key] * (1.0 - exact[key]), 1e-12) / MC_CHECK_DRAWS)
        z = (value - exact[key]) / se
        check[key] = {"monte_carlo": value, "z": z}
        if abs(z) > 4.0:
            print(f"error: Monte Carlo check failed for {key}: z = {z:.2f}", file=sys.stderr)
            return 1

    arm_a = []
    for (phi, rho), child in zip(cases, children[:-1], strict=True):
        result = arm_a_false_pass(np.random.default_rng(child), phi, rho)
        arm_a.append({"phi": phi, "rho": rho, **result})
        print(
            f"A1 phi={phi} rho={rho}: "
            + ", ".join(
                f"{k} {v['false_pass_rate']:.4f} (se {v['mc_standard_error']:.4f})"
                for k, v in result.items()
            )
        )

    payload = {
        "protocol": "docs/roadmap/2026-10-24-issue-125-preregistration.md section 3.8",
        "arm_b": {
            "null": "(i) independent uniform random rankings of six layouts",
            "n_layouts": N_LAYOUTS,
            "n_jobs": N_ARM_B_JOBS,
            "exact": exact,
            "monte_carlo_check": {"draws": MC_CHECK_DRAWS, "per_key": check},
        },
        "arm_a_a1": {
            "null": "row error differences u_day + e_row, mean zero, u_day stationary AR(1)",
            "n_days": N_DAYS,
            "rows_per_day": ROWS_PER_DAY,
            "n_runs": N_RUNS,
            "n_resamples": N_RESAMPLES,
            "interval": "90% percentile, pass when the upper end is below zero",
            "cases": arm_a,
        },
        "seed": {
            "root": ROOT_SEED,
            "spawn": "one child per (phi, rho) case, last for the Arm B check",
        },
        "numpy": np.__version__,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    write_json_lf(args.out / "null-values.json", payload)
    for key in sorted(exact):
        print(f"B {key}: {exact[key]:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
