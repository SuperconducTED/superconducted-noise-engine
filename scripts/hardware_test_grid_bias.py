"""Delay-grid bias for the #125 hardware test: which predictor a grid favours under Arm A's score.

Arm A prepares ``|1>``, waits ``tau`` and measures; the design's first-order prediction is
``p_1(tau) = e01 + (1 - e01 - e10) * exp(-tau / T1)``, and a predictor's per-qubit score is the
mean over the grid's delays of ``|p_hat - p_pred|``. Two predictors, ``reading`` (``T1_R``) and
``level`` (``T1_L``), disagree by ``d = log T1_R - log T1_L``. With the truth placed at fraction
``a`` of the way from the reading to the level in log space, the *tie point* ``a*`` is where the
two scores are equal: ``a* = 0.5`` is a neutral grid, ``a* > 0.5`` favours the reading, and
``a* < 0.5`` favours the level.

Everything depends on ``tau / T1`` only, so ``T1_L = 1`` throughout. No archive, no circuit, no
QPU. Plan: ``docs/roadmap/2026-10-24-hardware-test-preregistration-support-plan.md`` §3;
protocol: ``docs/evidence/hardware-reading-vs-level/README.md`` §3.

Usage::

    python -m scripts.hardware_test_grid_bias --out docs/evidence/hardware-reading-vs-level/
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

GRIDS: tuple[str, ...] = ("level", "reading", "union", "midpoint")
GRID_MULTIPLES: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0)
DISAGREEMENTS: tuple[float, ...] = (0.25, 0.37, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
ARM_A_SHOTS = 2048
SCAN_POINTS = 21
TSV_COLUMNS: tuple[str, ...] = (
    "grid",
    "d",
    "shots",
    "tie_point",
    "sign_changes",
    "n_delays_nonzero",
    "level_error_at_half",
    "reading_error_at_half",
)


@dataclass(frozen=True)
class BiasRow:
    grid: str
    d: float
    shots: str
    tie_point: float
    sign_changes: int
    n_delays_nonzero: int
    level_error_at_half: float
    reading_error_at_half: float


def _require_positive(name: str, value: float) -> None:
    if not (math.isfinite(value) and value > 0.0):
        raise ValueError(f"{name} must be finite and positive, got {value!r}")


def decay_probability(
    tau: npt.ArrayLike,
    t1: float,
    *,
    prob_meas0_prep1: float = 0.0,
    prob_meas1_prep0: float = 0.0,
) -> npt.NDArray[np.float64]:
    """Measured ``P(1)`` after ``|1>`` and a delay ``tau``, design §3's first-order form."""
    _require_positive("t1", t1)
    e10, e01 = prob_meas0_prep1, prob_meas1_prep0
    if not (0.0 <= e10 < 1.0 and 0.0 <= e01 < 1.0 and e10 + e01 < 1.0):
        raise ValueError("assignment probabilities must lie in [0, 1) and sum below 1")
    delays = np.asarray(tau, dtype=np.float64)
    if np.any(delays < 0.0) or not np.all(np.isfinite(delays)):
        raise ValueError("delays must be finite and non-negative")
    return e01 + (1.0 - e01 - e10) * np.exp(-delays / t1)


def delay_grid(name: str, t1_reading: float, t1_level: float) -> npt.NDArray[np.float64]:
    """Sorted distinct delays of a named grid, in the unit of the two ``T1`` values."""
    _require_positive("t1_reading", t1_reading)
    _require_positive("t1_level", t1_level)
    multiples = np.array(GRID_MULTIPLES, dtype=np.float64)
    if name == "level":
        delays = multiples * t1_level
    elif name == "reading":
        delays = multiples * t1_reading
    elif name == "union":
        delays = np.concatenate([multiples * t1_level, multiples * t1_reading])
    elif name == "midpoint":
        delays = multiples * math.sqrt(t1_reading * t1_level)
    else:
        raise ValueError(f"unknown grid {name!r}; expected one of {GRIDS}")
    return np.unique(delays)


def _binomial_pmf(n: int, p: float) -> npt.NDArray[np.float64]:
    pmf = np.zeros(n + 1, dtype=np.float64)
    if p <= 0.0:
        pmf[0] = 1.0
        return pmf
    if p >= 1.0:
        pmf[n] = 1.0
        return pmf
    k = np.arange(n + 1, dtype=np.float64)
    log_fact = np.concatenate([[0.0], np.cumsum(np.log(np.arange(1, n + 1, dtype=np.float64)))])
    log_pmf = log_fact[n] - log_fact - log_fact[::-1] + k * math.log(p) + (n - k) * math.log1p(-p)
    result: npt.NDArray[np.float64] = np.exp(log_pmf)
    return result


def expected_abs_error(
    delays: npt.ArrayLike,
    t1_pred: float,
    t1_true: float,
    *,
    shots: int | None = None,
    readout: tuple[float, float] = (0.0, 0.0),
) -> float:
    """Mean over delays of ``E|p_hat - p_pred|``; noiseless when ``shots`` is ``None``.

    ``readout`` is ``(prob_meas0_prep1, prob_meas1_prep0)``, applied to the prediction and to
    the truth alike. With ``shots = n`` the expectation is the exact binomial sum
    ``sum_k Bin(k; n, p_true) |k / n - p_pred|``.
    """
    e10, e01 = readout
    p_pred = decay_probability(delays, t1_pred, prob_meas0_prep1=e10, prob_meas1_prep0=e01)
    p_true = decay_probability(delays, t1_true, prob_meas0_prep1=e10, prob_meas1_prep0=e01)
    if shots is None:
        return float(np.mean(np.abs(p_true - p_pred)))
    if isinstance(shots, bool) or not isinstance(shots, int) or shots <= 0:
        raise ValueError(f"shots must be a positive integer or None, got {shots!r}")
    fractions = np.arange(shots + 1, dtype=np.float64) / shots
    errors = [
        float(np.sum(_binomial_pmf(shots, float(pt)) * np.abs(fractions - pp)))
        for pt, pp in zip(p_true, p_pred, strict=True)
    ]
    return float(np.mean(errors))


def _truth(d: float, a: float) -> float:
    """``T1_true`` at fraction ``a`` from the reading (``exp(d)``) to the level (1)."""
    return math.exp(d * (1.0 - a))


def score_difference(
    grid: str,
    d: float,
    a: float,
    *,
    shots: int | None = None,
    readout: tuple[float, float] = (0.0, 0.0),
) -> float:
    """``level``'s score minus ``reading``'s at truth position ``a``; positive: reading wins."""
    if not (math.isfinite(d) and d != 0.0):
        raise ValueError("d must be finite and non-zero")
    t1_reading, t1_level = math.exp(d), 1.0
    delays = delay_grid(grid, t1_reading, t1_level)
    t1_true = _truth(d, a)
    level_err = expected_abs_error(delays, t1_level, t1_true, shots=shots, readout=readout)
    reading_err = expected_abs_error(delays, t1_reading, t1_true, shots=shots, readout=readout)
    return level_err - reading_err


def sign_changes(
    grid: str, d: float, *, shots: int | None = None, points: int = SCAN_POINTS
) -> int:
    """Sign changes of :func:`score_difference` over an even scan of ``[0, 1]``."""
    values = [score_difference(grid, d, a, shots=shots) for a in np.linspace(0.0, 1.0, points)]
    signs = [v > 0.0 for v in values if v != 0.0]
    return sum(1 for x, y in itertools.pairwise(signs) if x != y)


def tie_point(
    grid: str,
    d: float,
    *,
    shots: int | None = None,
    readout: tuple[float, float] = (0.0, 0.0),
    tol: float = 1e-7,
) -> float:
    """Truth position ``a*`` where the two scores tie, by bisection; ``NaN`` without a crossing."""

    def diff(a: float) -> float:
        return score_difference(grid, d, a, shots=shots, readout=readout)

    lo, hi = 0.0, 1.0
    if not (diff(lo) > 0.0 > diff(hi)):
        return math.nan
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if diff(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def bias_rows(
    *,
    grids: Sequence[str] = GRIDS,
    disagreements: Sequence[float] = DISAGREEMENTS,
    shots_settings: Sequence[int | None] = (None, ARM_A_SHOTS),
) -> list[BiasRow]:
    """Every (grid, signed ``d``, shots) combination of the protocol, none dropped."""
    rows: list[BiasRow] = []
    for grid in grids:
        for size in disagreements:
            for d in (-size, size):
                t1_reading = math.exp(d)
                delays = delay_grid(grid, t1_reading, 1.0)
                for shots in shots_settings:
                    half = _truth(d, 0.5)
                    rows.append(
                        BiasRow(
                            grid=grid,
                            d=d,
                            shots="noiseless" if shots is None else str(shots),
                            tie_point=tie_point(grid, d, shots=shots),
                            sign_changes=sign_changes(grid, d, shots=shots),
                            n_delays_nonzero=int(np.count_nonzero(delays)),
                            level_error_at_half=expected_abs_error(delays, 1.0, half, shots=shots),
                            reading_error_at_half=expected_abs_error(
                                delays, t1_reading, half, shots=shots
                            ),
                        )
                    )
    return rows


def write_rows(out: Path, rows: Sequence[BiasRow]) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "grid-bias.tsv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(TSV_COLUMNS), delimiter="\t")
        writer.writeheader()
        for row in rows:
            record = asdict(row)
            for key in ("d", "tie_point", "level_error_at_half", "reading_error_at_half"):
                record[key] = f"{record[key]:.6f}"
            writer.writerow(record)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = bias_rows()
    path = write_rows(args.out, rows)
    manifest = {
        "grids": list(GRIDS),
        "grid_multiples": list(GRID_MULTIPLES),
        "disagreements": list(DISAGREEMENTS),
        "shots": ["noiseless", ARM_A_SHOTS],
        "readout": "ideal (e01 = e10 = 0)",
        "rows": len(rows),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
    }
    (args.out / "grid-bias-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"wrote {path} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
