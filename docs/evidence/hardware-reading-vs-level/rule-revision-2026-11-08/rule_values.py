"""#125 rule revision, N1 to N7: the new rules with no information, and with a synthetic edge.

Protocol: ``README.md`` in this folder, committed before this script produced a number. NumPy only,
no archive, no project code. Definitions are the README's section 3: batch means over four fixed
batches, two empty-batch rules (``V1`` inconclusive on any empty batch, ``V2`` drop empty batches
while at least three remain), ``sd = 0`` fails; Arm B on 13 jobs in batches of 4, 3, 3, 3.

Run from the repository root::

    python docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/rule_values.py
        --out docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/

(one command, split here for width)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

N_DAYS = 14
ROWS_PER_DAY = 56
PHIS = (0.0, 0.5)
RHOS = (0.0, 0.3, 0.7)
ROOT_SEED = 20261108
N_RUNS = 20_000
N_RUNS_BOOT = 2_000
N_RESAMPLES = 2_000
BLOCK_DAYS = 3
ARM_A_BATCHES = [np.asarray(b) for b in np.array_split(np.arange(N_DAYS), 4)]
N_ARM_B = 13
ARM_B_BATCHES = [np.asarray(b) for b in np.array_split(np.arange(N_ARM_B), 4)]
N_LAYOUTS = 6
# One-sided 95% points of Student t with 2 and 3 degrees of freedom.
T95 = {2: 2.919985580355516, 3: 2.353363434801823}
KS_A = (1, 2, 3, 4)
KS_B = (1, 2, 3)
PLACEMENTS = ("random", "consecutive")
RULES = ("V1", "V2")
CALIBRATION_CASE = (0.5, 0.3)
TARGETS = {"strong": 0.976, "moderate": 0.50}


def check_critical_values() -> str:
    """Compare the hard-coded critical values with SciPy when it is installed."""
    try:
        from scipy import stats
    except ImportError:
        return "SciPy not installed: hard-coded values used unchecked"
    for df, value in T95.items():
        exact = float(stats.t.ppf(0.95, df))
        if not math.isclose(exact, value, rel_tol=0.0, abs_tol=1e-12):
            raise SystemExit(f"error: t_0.95,{df} is {exact!r}, not {value!r}")
    return "matches SciPy to 1e-12"


def day_means(
    rng: np.random.Generator, n_runs: int, phi: float, rho: float, shift: float = 0.0
) -> np.ndarray:
    """Per-day mean of D under section 3.8's model, shape ``(n_runs, N_DAYS)``.

    ``D = shift + u_day + e_row`` with unit total variance per row, ``u_day`` a stationary AR(1)
    carrying ``rho`` of it. With 56 rows every day, a day's mean is ``shift + u_day + mean(e)``.
    """
    u = np.empty((n_runs, N_DAYS))
    u[:, 0] = rng.normal(0.0, math.sqrt(rho), n_runs)
    innovation = math.sqrt(rho * (1.0 - phi**2))
    for t in range(1, N_DAYS):
        u[:, t] = phi * u[:, t - 1] + rng.normal(0.0, innovation, n_runs)
    e = rng.normal(0.0, math.sqrt((1.0 - rho) / ROWS_PER_DAY), (n_runs, N_DAYS))
    return shift + u + e


def present_mask(
    rng: np.random.Generator, n_runs: int, n_items: int, k: int, placement: str
) -> np.ndarray:
    """``True`` where an item (a day or a job) has rows; ``k`` missed, at random or in one run."""
    present = np.ones((n_runs, n_items), dtype=bool)
    if k == 0:
        return present
    if placement == "random":
        missed = np.argsort(rng.random((n_runs, n_items)), axis=1)[:, :k]
    elif placement == "consecutive":
        start = rng.integers(0, n_items - k + 1, n_runs)
        missed = start[:, None] + np.arange(k)[None, :]
    else:
        raise ValueError(placement)
    np.put_along_axis(present, missed, False, axis=1)
    return present


def batch_rule(
    values: np.ndarray, present: np.ndarray, batches: list[np.ndarray], rule: str, side: int
) -> dict[str, np.ndarray]:
    """Per run: does the batch-means rule pass, is it inconclusive, was a batch empty, was sd zero.

    ``values`` holds one mean per item with equal rows per item, so a batch's row-pooled mean is the
    mean of its present items. ``side`` is -1 when a pass needs ``t < -t95`` (Arm A) and +1 when it
    needs ``t > t95`` (Arm B).
    """
    sums = np.stack([np.where(present[:, b], values[:, b], 0.0).sum(axis=1) for b in batches], 1)
    counts = np.stack([present[:, b].sum(axis=1) for b in batches], 1)
    empty = counts == 0
    q = len(batches)
    nonempty = (~empty).sum(axis=1)
    usable = nonempty == q if rule == "V1" else nonempty >= 3
    m = np.where(empty, np.nan, sums / np.maximum(counts, 1))
    filled = np.where(empty, 0.0, m)
    n = np.maximum(nonempty, 1)
    mean = filled.sum(axis=1) / n
    dev = np.where(empty, 0.0, m - mean[:, None])
    var = (dev**2).sum(axis=1) / np.maximum(nonempty - 1, 1)
    sd = np.sqrt(var)
    sd_zero = usable & (sd == 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = mean / (sd / np.sqrt(n))
    crit = np.where(nonempty >= 4, T95[3], T95[2])
    passes = usable & ~sd_zero & (side * t > crit)
    return {"pass": passes, "inconclusive": ~usable, "empty": empty.any(axis=1), "sd0": sd_zero}


def rates(outcome: dict[str, np.ndarray]) -> dict[str, float]:
    n = outcome["pass"].size
    out = {key: float(value.mean()) for key, value in outcome.items()}
    out["pass_se"] = math.sqrt(max(out["pass"] * (1.0 - out["pass"]), 1e-12) / n)
    return out


def arm_a_cases(seeds: dict[str, np.random.SeedSequence]) -> dict[str, Any]:
    """N1 and N2: the null at full calendar and with missed days."""
    out: dict[str, Any] = {}
    for phi in PHIS:
        for rho in RHOS:
            name = f"phi={phi},rho={rho}"
            rng = np.random.default_rng(seeds[f"A:{name}"])
            values = day_means(rng, N_RUNS, phi, rho)
            case: dict[str, Any] = {
                "full": rates(
                    batch_rule(
                        values,
                        present_mask(rng, N_RUNS, N_DAYS, 0, "random"),
                        ARM_A_BATCHES,
                        "V1",
                        -1,
                    )
                )
            }
            for k in KS_A:
                for placement in PLACEMENTS:
                    present = present_mask(rng, N_RUNS, N_DAYS, k, placement)
                    for rule in RULES:
                        outcome = batch_rule(values, present, ARM_A_BATCHES, rule, -1)
                        case[f"k={k},{placement},{rule}"] = rates(outcome)
            out[name] = case
    return out


def calibrate_shift(base: np.ndarray, target: float) -> float:
    """The shift whose full-calendar pass rate is ``target`` on fixed draws (bisection)."""
    present = np.ones_like(base, dtype=bool)
    lo, hi = -2.0, 0.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        rate = batch_rule(base + mid, present, ARM_A_BATCHES, "V1", -1)["pass"].mean()
        if rate < target:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def arm_a_power(seeds: dict[str, np.random.SeedSequence]) -> dict[str, Any]:
    """N3: a synthetic edge, calibrated at one case, under the misses of N2."""
    phi, rho = CALIBRATION_CASE
    rng = np.random.default_rng(seeds["power"])
    base = day_means(rng, N_RUNS, phi, rho)
    out: dict[str, Any] = {"case": {"phi": phi, "rho": rho}, "unit": "per-row sd of D"}
    for label, target in TARGETS.items():
        shift = calibrate_shift(base, target)
        values = base + shift
        entry: dict[str, Any] = {"target": target, "shift": shift}
        entry["full"] = rates(
            batch_rule(values, np.ones_like(values, dtype=bool), ARM_A_BATCHES, "V1", -1)
        )
        for k in KS_A:
            for placement in PLACEMENTS:
                present = present_mask(rng, N_RUNS, N_DAYS, k, placement)
                for rule in RULES:
                    entry[f"k={k},{placement},{rule}"] = rates(
                        batch_rule(values, present, ARM_A_BATCHES, rule, -1)
                    )
        out[label] = entry
    return out


def spearman_random(rng: np.random.Generator, n_runs: int) -> np.ndarray:
    """Spearman of a uniform random ranking of six layouts with the measured order, per job."""
    perm = np.argsort(rng.random((n_runs, N_ARM_B, N_LAYOUTS)), axis=2)
    d2 = ((perm - np.arange(N_LAYOUTS)[None, None, :]) ** 2).sum(axis=2)
    return 1.0 - 6.0 * d2 / (N_LAYOUTS * (N_LAYOUTS**2 - 1))


def arm_b_cases(seeds: dict[str, np.random.SeedSequence]) -> dict[str, Any]:
    """N4: the paired rule under null (i), full and with missed jobs."""
    rng = np.random.default_rng(seeds["armb"])
    delta = spearman_random(rng, N_RUNS) - spearman_random(rng, N_RUNS)
    out: dict[str, Any] = {
        "null": "(i) independent uniform rankings of six layouts per job",
        "full": rates(batch_rule(delta, np.ones_like(delta, dtype=bool), ARM_B_BATCHES, "V1", 1)),
        "null_ii": "identical rankings: every Delta is 0, sd = 0, fails by definition",
    }
    for k in KS_B:
        for placement in PLACEMENTS:
            present = present_mask(rng, N_RUNS, N_ARM_B, k, placement)
            for rule in RULES:
                out[f"k={k},{placement},{rule}"] = rates(
                    batch_rule(delta, present, ARM_B_BATCHES, rule, 1)
                )
    return out


def block_bootstrap(seeds: dict[str, np.random.SeedSequence]) -> dict[str, Any]:
    """N6: block 3 at 90%, the scorer's 15 drawn days against the 14-day cut, same draws."""
    n_blocks = math.ceil(N_DAYS / BLOCK_DAYS)
    offsets = np.arange(BLOCK_DAYS)
    out: dict[str, Any] = {}
    for phi in PHIS:
        for rho in RHOS:
            name = f"phi={phi},rho={rho}"
            rng = np.random.default_rng(seeds[f"boot:{name}"])
            values = day_means(rng, N_RUNS_BOOT, phi, rho)
            kept = cut = 0
            for run in range(N_RUNS_BOOT):
                starts = rng.integers(0, N_DAYS, size=(N_RESAMPLES, n_blocks))
                days = ((starts[:, :, None] + offsets[None, None, :]) % N_DAYS).reshape(
                    N_RESAMPLES, -1
                )
                upper_kept = np.quantile(values[run][days].mean(axis=1), 0.95)
                upper_cut = np.quantile(values[run][days[:, :N_DAYS]].mean(axis=1), 0.95)
                kept += int(upper_kept < 0.0)
                cut += int(upper_cut < 0.0)
            out[name] = {
                "scorer_15_days": kept / N_RUNS_BOOT,
                "cut_to_14_days": cut / N_RUNS_BOOT,
                "mc_se_about": math.sqrt(0.1 * 0.9 / N_RUNS_BOOT),
            }
    return out


def peeking(seeds: dict[str, np.random.SeedSequence]) -> dict[str, Any]:
    """N7: stop at the first look that passes, against one look at day 14."""
    first_look = {"V1": 12, "V2": 9}
    out: dict[str, Any] = {}
    for phi in PHIS:
        for rho in RHOS:
            name = f"phi={phi},rho={rho}"
            rng = np.random.default_rng(seeds[f"peek:{name}"])
            values = day_means(rng, N_RUNS, phi, rho)
            case: dict[str, Any] = {}
            for rule in RULES:
                any_pass = np.zeros(N_RUNS, dtype=bool)
                for look in range(first_look[rule], N_DAYS + 1):
                    present = np.zeros((N_RUNS, N_DAYS), dtype=bool)
                    present[:, :look] = True
                    outcome = batch_rule(values, present, ARM_A_BATCHES, rule, -1)
                    any_pass |= outcome["pass"]
                    if look == N_DAYS:
                        fixed = float(outcome["pass"].mean())
                case[rule] = {
                    "first_look_day": first_look[rule],
                    "fixed_day_14": fixed,
                    "stop_at_first_pass": float(any_pass.mean()),
                }
            out[name] = case
    return out


def placement_check(seeds: dict[str, np.random.SeedSequence]) -> dict[str, Any]:
    """The hand-counted empty-batch shares for consecutive misses, against the masks' own."""
    rng = np.random.default_rng(seeds["check"])
    out: dict[str, Any] = {}
    for k, exact in ((3, 2 / 12), (4, 6 / 11)):
        present = present_mask(rng, N_RUNS, N_DAYS, k, "consecutive")
        counts = np.stack([present[:, b].sum(axis=1) for b in ARM_A_BATCHES], 1)
        share = float((counts == 0).any(axis=1).mean())
        se = math.sqrt(exact * (1.0 - exact) / N_RUNS)
        z = (share - exact) / se
        out[f"k={k}"] = {"exact": exact, "measured": share, "z": z}
        if abs(z) > 4.0:
            raise SystemExit(f"error: consecutive k={k} empty-batch share {share} is not {exact}")
    return out


def write_json_lf(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    names = ["check", "power", "armb"]
    names += [
        f"{p}:phi={phi},rho={rho}" for p in ("A", "boot", "peek") for phi in PHIS for rho in RHOS
    ]
    seeds = dict(zip(names, np.random.SeedSequence(ROOT_SEED).spawn(len(names)), strict=True))

    payload: dict[str, Any] = {
        "protocol": "docs/evidence/hardware-reading-vs-level/rule-revision-2026-11-08/README.md",
        "critical_values": {
            "t95": {str(k): v for k, v in T95.items()},
            "check": check_critical_values(),
        },
        "seed": {"root": ROOT_SEED, "children": names},
        "n_runs": N_RUNS,
        "n_runs_bootstrap": N_RUNS_BOOT,
        "n_resamples": N_RESAMPLES,
        "numpy": np.__version__,
    }
    payload["placement_check"] = placement_check(seeds)
    payload["N1_N2_arm_a"] = arm_a_cases(seeds)
    payload["N3_power"] = arm_a_power(seeds)
    payload["N4_arm_b"] = arm_b_cases(seeds)
    payload["N6_block3"] = block_bootstrap(seeds)
    payload["N7_peeking"] = peeking(seeds)

    args.out.mkdir(parents=True, exist_ok=True)
    write_json_lf(args.out / "rule-values.json", payload)
    for name, case in payload["N1_N2_arm_a"].items():
        print(f"N1 {name}: {case['full']['pass']:.4f} (se {case['full']['pass_se']:.4f})")
    print("N4 full:", round(payload["N4_arm_b"]["full"]["pass"], 4))
    print("check:", payload["placement_check"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
