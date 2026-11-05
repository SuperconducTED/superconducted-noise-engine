"""Check-up floor for the #125 discriminating stratum, day by day over the archive.

Protocol: ``docs/evidence/hardware-reading-vs-level/README.md`` §2, committed before this
script. For every evaluation instant it counts, per qubit, the distinct ``T1`` values inside the
30-day window (``w``) beside PR #126's whole-archive ``n_distinct`` (``N``), and reports what
the current rule (``N >= 20``) and each candidate window rule (``w >= k``, ``k`` in 5, 10, 15,
20) do to the selectable set, to qubit 72 and to the eight-qubit selection. It reuses PR #126's
``collect``, ``predictor_rows``, ``select_discriminating`` and ``propose_controls`` unchanged,
so the selection measured is the one the test runs. It takes no decision.

Usage, from the repository root::

    PYTHONPATH=src python docs/evidence/hardware-reading-vs-level/measure_checkup_floor.py \\
        --repo . --ref 5828b4a29fabc245aa096e530852249a3496dc5b \\
        --out docs/evidence/hardware-reading-vs-level/
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.hardware_test_predictors import (  # noqa: E402
    QUANTITIES,
    WINDOW_DAYS,
    Collected,
    FileRecord,
    PredictorRow,
    collect,
    predictor_rows,
    propose_controls,
    select_discriminating,
)

from superconducted.training.dataset import iter_archive, resolve_archive_ref  # noqa: E402

GUARD_AT = datetime(2026, 10, 23, 9, 34, 56, tzinfo=UTC)
GUARD = {
    "files": 2249,
    "states": 924,
    "q72_n_distinct": 29,
    "discriminating": [148, 108, 72, 132, 155, 10, 80, 77],
    "controls": [105, 112, 48, 140],
}
CURRENT_FLOOR = 20
WINDOW_FLOORS = (5, 10, 15, 20)
TOP = 8
CONTROLS = 4
EVAL_HOUR = 12
Q72 = 72
T1 = QUANTITIES.index("T1")


def _subset(collected: Collected, at: datetime) -> Collected:
    """What ``collect(..., until=at)`` returns, without walking the archive again."""
    return Collected(
        files=[f for f in collected.files if f.time <= at],
        states=[s for s in collected.states if s.time <= at],
        skipped=Counter(collected.skipped),
    )


def _window(collected: Collected, at: datetime) -> list[FileRecord]:
    lo = at - timedelta(days=WINDOW_DAYS)
    return [s for s in collected.states if lo < s.time <= at]


def window_counts(window: list[FileRecord], n_qubits: int) -> tuple[list[int], list[float]]:
    """Per qubit: distinct finite positive ``T1`` values in the window, and the modal share."""
    counts: list[int] = []
    shares: list[float] = []
    for q in range(n_qubits):
        vals = [float(s.values[q, T1]) for s in window if q < s.values.shape[0]]
        good = [v for v in vals if math.isfinite(v) and v > 0.0]
        tally = Counter(good)
        counts.append(len(tally))
        shares.append(max(tally.values()) / len(window) if tally and window else math.nan)
    return counts, shares


def _top(rows: list[PredictorRow], w: list[int] | None, floor: int) -> list[int]:
    """PR #126's selection, on ``n_distinct`` (current rule) or on the window count."""
    t1_rows = [r for r in rows if r.quantity == "T1"]
    if w is not None:
        t1_rows = [replace(r, n_distinct=w[r.qubit]) for r in t1_rows]
    return [p["qubit"] for p in select_discriminating(t1_rows, k=TOP, min_distinct=floor)]


def _instants(collected: Collected) -> list[datetime]:
    first = min(s.time for s in collected.states) + timedelta(days=WINDOW_DAYS)
    last = max(f.time for f in collected.files)
    day = first.replace(hour=EVAL_HOUR, minute=0, second=0, microsecond=0)
    if day < first:
        day += timedelta(days=1)
    out: list[datetime] = []
    while day <= last:
        out.append(day)
        day += timedelta(days=1)
    return out


def guard(collected: Collected) -> dict[str, Any]:
    sub = _subset(collected, GUARD_AT)
    rows = predictor_rows(sub, at=GUARD_AT, live=None)
    q72 = next(r for r in rows if r.qubit == Q72 and r.quantity == "T1")
    picked = select_discriminating(rows, k=TOP)
    controls = propose_controls(sub, k=CONTROLS, exclude={p["qubit"] for p in picked})
    observed = {
        "files": len(sub.files),
        "states": len(sub.states),
        "q72_n_distinct": q72.n_distinct,
        "discriminating": [p["qubit"] for p in picked],
        "controls": [c["qubit"] for c in controls],
    }
    mismatches = {
        k: {"expected": v, "observed": observed[k]} for k, v in GUARD.items() if observed[k] != v
    }
    return {
        "at": GUARD_AT.isoformat(),
        "passed": not mismatches and not sub.skipped,
        "observed": observed,
        "mismatches": mismatches,
        "skipped": dict(sub.skipped),
        "discriminating_d": [round(p["log_disagreement"], 4) for p in picked],
    }


def day_row(collected: Collected, at: datetime, n_qubits: int) -> dict[str, Any]:
    rows = predictor_rows(collected, at=at, live=None)
    t1 = {r.qubit: r for r in rows if r.quantity == "T1"}
    w, share = window_counts(_window(collected, at), n_qubits)
    selectable = [q for q, r in t1.items() if math.isfinite(r.log_disagreement)]
    current_admitted = [q for q in selectable if t1[q].n_distinct >= CURRENT_FLOOR]
    current_top = _top(rows, None, CURRENT_FLOOR)
    out: dict[str, Any] = {
        "at": at.isoformat(),
        "selectable": len(selectable),
        "excluded_current": len(selectable) - len(current_admitted),
    }
    for k in WINDOW_FLOORS:
        out[f"excluded_w{k}"] = sum(1 for q in selectable if w[q] < k)
    r72 = t1[Q72]
    out.update(
        {
            "w_72": w[Q72],
            "N_72": r72.n_distinct,
            "modal_share_72": round(share[Q72], 4) if math.isfinite(share[Q72]) else "",
            "d_72": round(r72.log_disagreement, 4) if math.isfinite(r72.log_disagreement) else "",
            "admit_72_current": int(Q72 in current_admitted),
            "top8_72_current": int(Q72 in current_top),
        }
    )
    for k in WINDOW_FLOORS:
        top_k = _top(rows, w, k)
        out[f"admit_72_w{k}"] = int(Q72 in selectable and w[Q72] >= k)
        out[f"top8_72_w{k}"] = int(Q72 in top_k)
        out[f"overlap_w{k}"] = len(set(top_k) & set(current_top))
    out["top8_below_current"] = sum(1 for q in current_top if t1[q].log_disagreement < 0.0)
    below = sorted(
        (-t1[q].log_disagreement for q in current_admitted if t1[q].log_disagreement < 0.0),
        reverse=True,
    )
    above = sorted(
        (t1[q].log_disagreement for q in current_admitted if t1[q].log_disagreement > 0.0),
        reverse=True,
    )
    overall = sorted((abs(t1[q].log_disagreement) for q in current_admitted), reverse=True)
    out["n_admitted_below"] = len(below)
    out["n_admitted_above"] = len(above)
    out["absd_8th_current"] = round(overall[TOP - 1], 4) if len(overall) >= TOP else ""
    out["absd_4th_below"] = round(below[TOP // 2 - 1], 4) if len(below) >= TOP // 2 else ""
    out["absd_4th_above"] = round(above[TOP // 2 - 1], 4) if len(above) >= TOP // 2 else ""
    out["admitted_below_share_current"] = (
        round(
            sum(1 for q in current_admitted if t1[q].log_disagreement < 0.0)
            / len(current_admitted),
            4,
        )
        if current_admitted
        else ""
    )
    if current_top:
        q_lo = min(current_top, key=lambda q: min(t1[q].reading, t1[q].level))
        q_hi = max(current_top, key=lambda q: max(t1[q].reading, t1[q].level))
        out["union_shortest_us"] = round(0.5 * min(t1[q_lo].reading, t1[q_lo].level) * 1e6, 3)
        out["union_longest_us"] = round(2.0 * max(t1[q_hi].reading, t1[q_hi].level) * 1e6, 3)
        for tag, q in (("shortest", q_lo), ("longest", q_hi)):
            out[f"union_{tag}_qubit"] = q
            out[f"union_{tag}_reading_us"] = round(t1[q].reading * 1e6, 3)
            out[f"union_{tag}_level_us"] = round(t1[q].level * 1e6, 3)
    else:
        for tag in ("shortest", "longest"):
            for col in ("us", "qubit", "reading_us", "level_us"):
                out[f"union_{tag}_{col}"] = ""
    out["top8_current"] = " ".join(str(q) for q in current_top)
    return out


def qubit_rows(collected: Collected, n_qubits: int) -> list[dict[str, Any]]:
    rows = predictor_rows(_subset(collected, GUARD_AT), at=GUARD_AT, live=None)
    t1 = {r.qubit: r for r in rows if r.quantity == "T1"}
    w, share = window_counts(_window(collected, GUARD_AT), n_qubits)
    out = []
    for q in range(n_qubits):
        r = t1[q]
        out.append(
            {
                "qubit": q,
                "w": w[q],
                "N": r.n_distinct,
                "modal_share": round(share[q], 4) if math.isfinite(share[q]) else "",
                "d": round(r.log_disagreement, 4) if math.isfinite(r.log_disagreement) else "",
                "level_us": round(r.level * 1e6, 3) if math.isfinite(r.level) else "",
                "reading_us": round(r.reading * 1e6, 3) if math.isfinite(r.reading) else "",
            }
        )
    return out


def controls(collected: Collected, n_qubits: int) -> dict[str, Any]:
    sub = _subset(collected, GUARD_AT)
    rows = predictor_rows(sub, at=GUARD_AT, live=None)
    w, _ = window_counts(_window(collected, GUARD_AT), n_qubits)
    out: dict[str, Any] = {
        "at": GUARD_AT.isoformat(),
        "note": (
            "propose_controls keeps its own whole-archive floor of 20; "
            "a window floor adds its exclusions"
        ),
    }
    rules: list[tuple[str, list[int] | None, int]] = [("current", None, CURRENT_FLOOR)]
    rules += [(f"w{k}", w, k) for k in WINDOW_FLOORS]
    for name, counts, floor in rules:
        below = {q for q in range(n_qubits) if counts is not None and counts[q] < floor}
        top = _top(rows, counts, floor)
        after = propose_controls(sub, k=CONTROLS, exclude=set(top) | below)
        first = propose_controls(sub, k=CONTROLS, exclude=below)
        out[name] = {
            "top8": top,
            "controls_after_selection": [c["qubit"] for c in after],
            "controls_first": [c["qubit"] for c in first],
            "scatter_first": [round(c["log_t1_scatter"], 4) for c in first],
        }
    nearest = propose_controls(sub, k=10, exclude=set())
    out["nearest_median_ten"] = {
        "median_scatter": round(nearest[0]["median_scatter"], 4) if nearest else None,
        "qubits": [c["qubit"] for c in nearest],
        "scatter": [round(c["log_t1_scatter"], 4) for c in nearest],
    }
    return out


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def summarise(days: list[dict[str, Any]]) -> dict[str, Any]:
    def spread(key: str) -> dict[str, float]:
        vals = np.array([float(d[key]) for d in days])
        return {
            "median": float(np.median(vals)),
            "min": float(vals.min()),
            "max": float(vals.max()),
        }

    out: dict[str, Any] = {"days": len(days), "excluded_current": spread("excluded_current")}
    for k in WINDOW_FLOORS:
        out[f"excluded_w{k}"] = spread(f"excluded_w{k}")
        out[f"overlap_w{k}"] = spread(f"overlap_w{k}")
        out[f"days_72_admitted_w{k}"] = sum(int(d[f"admit_72_w{k}"]) for d in days)
        out[f"days_72_in_top8_w{k}"] = sum(int(d[f"top8_72_w{k}"]) for d in days)
    out["days_72_admitted_current"] = sum(int(d["admit_72_current"]) for d in days)
    out["days_72_in_top8_current"] = sum(int(d["top8_72_current"]) for d in days)
    out["top8_below_current_distribution"] = dict(
        sorted(Counter(int(d["top8_below_current"]) for d in days).items())
    )
    shares = [
        float(d["admitted_below_share_current"])
        for d in days
        if d["admitted_below_share_current"] != ""
    ]
    out["admitted_below_share_current"] = {
        "median": float(np.median(shares)),
        "min": float(min(shares)),
        "max": float(max(shares)),
    }
    for key in ("absd_8th_current", "absd_4th_below", "absd_4th_above"):
        vals = [float(d[key]) for d in days if d[key] != ""]
        out[key] = {
            "median": float(np.median(vals)),
            "min": float(min(vals)),
            "max": float(max(vals)),
            "days": len(vals),
        }
    out["union_longest_us"] = spread("union_longest_us")
    out["union_shortest_us"] = spread("union_shortest_us")
    spans = [d for d in days if d["union_shortest_us"] != ""]
    for tag, pick in (("shortest", min), ("longest", max)):
        day = pick(spans, key=lambda d: float(d[f"union_{tag}_us"]))
        out[f"union_{tag}_extreme"] = {
            "at": day["at"],
            "us": day[f"union_{tag}_us"],
            "qubit": day[f"union_{tag}_qubit"],
            "reading_us": day[f"union_{tag}_reading_us"],
            "level_us": day[f"union_{tag}_level_us"],
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--ref", required=True)
    parser.add_argument("--backend", default="ibm_fez")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    sha = resolve_archive_ref(args.repo, args.ref)
    started = time.time()
    collected = collect(
        iter_archive(args.repo, sha), backend=args.backend, until=datetime(9999, 1, 1, tzinfo=UTC)
    )
    collected_s = time.time() - started
    args.out.mkdir(parents=True, exist_ok=True)
    checked = guard(collected)
    summary: dict[str, Any] = {
        "ref": sha,
        "backend": args.backend,
        "files": len(collected.files),
        "states": len(collected.states),
        "skipped": dict(collected.skipped),
        "guard": checked,
        "collect_seconds": round(collected_s, 1),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
    }
    if not checked["passed"]:
        (args.out / "checkup-floor-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(json.dumps(checked, indent=2))
        print("reproduction guard failed; no per-day figure is written", file=sys.stderr)
        return 1
    n_qubits = max(f.values.shape[0] for f in collected.files)
    instants = _instants(collected)
    days = [day_row(collected, at, n_qubits) for at in instants]
    _write_tsv(args.out / "checkup-floor-days.tsv", days)
    _write_tsv(args.out / "checkup-floor-qubits.tsv", qubit_rows(collected, n_qubits))
    (args.out / "checkup-floor-controls.json").write_text(
        json.dumps(controls(collected, n_qubits), indent=2), encoding="utf-8"
    )
    summary.update(
        {
            "instants": {
                "first": instants[0].isoformat(),
                "last": instants[-1].isoformat(),
                "count": len(instants),
            },
            "eval_hour_utc": EVAL_HOUR,
            "window_days": WINDOW_DAYS,
            "current_floor": CURRENT_FLOOR,
            "window_floors": list(WINDOW_FLOORS),
            "results": summarise(days),
            "total_seconds": round(time.time() - started, 1),
        }
    )
    (args.out / "checkup-floor-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary["results"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
