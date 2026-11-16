"""The band in Arm B (PR #140, Burak's review 5923046322): expectations before the re-run, and the
check after it.

    python band_rerun.py expect <reference folder>
    python band_rerun.py check <reference folder> <new folder>

(this file is `docs/evidence/hardware-reading-vs-level/band-arm-b-2026-11-16/band_rerun.py`).

`expect` reads only the committed `arm-b-truth1.tsv` and `arm-b-truth2.tsv` of a reference dry-run
folder (`measured_fidelity`, `predicted_band_lo`, `predicted_band_hi`) and prints, per truth, what
the band's Arm B score must be: per layout the sorted interval, its midpoint, whether it covers the
measured fidelity, its width; then the number of layouts with a band, the Spearman correlation of
the midpoints with the measured fidelities, whether the highest midpoint is the measured best, and
the number and share covered. It is a second route: it shares no code with
`scripts/hardware_reading_vs_level.py` (its own average-rank Spearman, its own parsing).

`check` compares a re-run folder with the reference under the expectations written in
`docs/implementations/2026-10-28-hardware-test-offline-half.md`, section "2026-11-16: the band in
Arm B". Exit 0 when every expectation holds, 1 otherwise. Reads only; writes nothing.
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
from pathlib import Path
from typing import Any

TRUTHS = ("truth1", "truth2")
OLD_COLUMNS = (
    "layout",
    "measured_fidelity",
    "predicted_reading",
    "predicted_level",
    "predicted_reading_at_execution",
    "predicted_band_lo",
    "predicted_band_hi",
)
NEW_COLUMNS = ("band_lo", "band_hi", "band_midpoint", "band_covered")
IDENTICAL_FILES = ("arm-a-truth1.tsv", "arm-a-truth2.tsv", "selection.json", "manifest.json")
NEW_ARM_B_KEYS = ("band",)  # added under criteria[truth]["4_arm_b"]["per_predictor"]
TOLERANCE = 1e-9  # the TSVs carry ten significant digits


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _number(text: str) -> float | None:
    return None if text == "" else float(text)


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def _spearman(x: list[float], y: list[float]) -> float:
    if len(x) < 2:
        return math.nan
    rx, ry = _ranks(x), _ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0.0 or syy == 0.0:
        return math.nan
    return sxy / math.sqrt(sxx * syy)


def expected_band(rows: list[dict[str, str]]) -> dict[str, Any]:
    measured = [float(r["measured_fidelity"]) for r in rows]
    per_layout: list[dict[str, Any] | None] = []
    for r, m in zip(rows, measured, strict=True):
        a, b = _number(r["predicted_band_lo"]), _number(r["predicted_band_hi"])
        if a is None or b is None:
            per_layout.append(None)
            continue
        lo, hi = min(a, b), max(a, b)
        per_layout.append(
            {
                "layout": r["layout"],
                "lo": lo,
                "hi": hi,
                "midpoint": (lo + hi) / 2.0,
                "covered": int(lo <= m <= hi),
                "width": hi - lo,
            }
        )
    usable = [i for i, v in enumerate(per_layout) if v is not None]
    mids = [per_layout[i]["midpoint"] for i in usable]  # type: ignore[index]
    best = max(range(len(measured)), key=lambda i: measured[i])
    pick = max(usable, key=lambda i: per_layout[i]["midpoint"]) if usable else None  # type: ignore[index]
    n_covered = sum(per_layout[i]["covered"] for i in usable)  # type: ignore[index]
    return {
        "per_layout": per_layout,
        "n_predicted": len(usable),
        "spearman": _spearman(mids, [measured[i] for i in usable]),
        "best_pick_hit": None if pick is None else int(pick == best),
        "n_covered": n_covered,
        "coverage": n_covered / len(usable) if usable else math.nan,
    }


def expect(reference: Path) -> int:
    for truth in TRUTHS:
        band = expected_band(_rows(reference / f"arm-b-{truth}.tsv"))
        print(f"{truth}:")
        for row in band["per_layout"]:
            if row is None:
                print("  (no band)")
                continue
            print(
                f"  {row['layout']:<12} lo {row['lo']:.10g}  hi {row['hi']:.10g}  "
                f"mid {row['midpoint']:.10g}  covered {row['covered']}  width {row['width']:.10g}"
            )
        print(
            f"  n_predicted {band['n_predicted']}  spearman {band['spearman']:.10g}  "
            f"best_pick_hit {band['best_pick_hit']}  covered {band['n_covered']} of "
            f"{band['n_predicted']} ({band['coverage']:.10g})"
        )
    return 0


def _strip_new(criteria: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(json.dumps(criteria))
    for truth in TRUTHS:
        arm_b = out[truth]["4_arm_b"]
        for key in NEW_ARM_B_KEYS:
            arm_b["per_predictor"].pop(key, None)
            arm_b["unpredictable"].pop(key, None)
    return out


def _close(a: float, b: float) -> bool:
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= TOLERANCE


def check(reference: Path, new: Path) -> int:
    failures = 0

    def verdict(ok: bool, text: str) -> None:
        nonlocal failures
        failures += not ok
        print(f"{'hold' if ok else 'FAIL'}  {text}")

    for name in IDENTICAL_FILES:
        same = (reference / name).read_bytes().replace(b"\r\n", b"\n") == (
            new / name
        ).read_bytes().replace(b"\r\n", b"\n")
        verdict(same, f"{name} identical to the reference")
    criteria_new = json.loads((new / "criteria.json").read_text(encoding="utf-8"))
    criteria_ref = json.loads((reference / "criteria.json").read_text(encoding="utf-8"))
    for truth in TRUTHS:
        new_rows = _rows(new / f"arm-b-{truth}.tsv")
        ref_rows = _rows(reference / f"arm-b-{truth}.tsv")
        verdict(
            [[r[c] for c in OLD_COLUMNS] for r in new_rows]
            == [[r[c] for c in OLD_COLUMNS] for r in ref_rows],
            f"arm-b-{truth}.tsv: the seven reference columns identical",
        )
        verdict(
            list(new_rows[0]) == [*OLD_COLUMNS, *NEW_COLUMNS],
            f"arm-b-{truth}.tsv: columns are the reference's plus {', '.join(NEW_COLUMNS)}",
        )
        band = expected_band(ref_rows)
        cells_ok = True
        for row, want in zip(new_rows, band["per_layout"], strict=True):
            if want is None:
                cells_ok &= all(row[c] == "" for c in NEW_COLUMNS)
                continue
            cells_ok &= _close(float(row["band_lo"]), want["lo"])
            cells_ok &= _close(float(row["band_hi"]), want["hi"])
            cells_ok &= _close(float(row["band_midpoint"]), want["midpoint"])
            cells_ok &= int(row["band_covered"]) == want["covered"]
        verdict(cells_ok, f"arm-b-{truth}.tsv: band columns equal the expectation")
        got = criteria_new[truth]["4_arm_b"]["per_predictor"].get("band", {})
        verdict(
            got.get("n_predicted") == band["n_predicted"]
            and got.get("best_pick_hit") == band["best_pick_hit"]
            and got.get("n_covered") == band["n_covered"]
            and _close(float(got.get("spearman", math.nan)), band["spearman"])
            and _close(float(got.get("coverage", math.nan)), band["coverage"]),
            f"criteria.json {truth}: the band's score equals the expectation",
        )
        verdict(
            criteria_new[truth]["4_arm_b"]["unpredictable"].get("band") == [],
            f"criteria.json {truth}: no layout without a band",
        )
        verdict(
            all(
                criteria_new[truth][k]["pass"]
                for k in ("1_sampling", "2_offset", "3_direction", "4_arm_b", "5_timing")
            ),
            f"criteria.json {truth}: all five criteria pass",
        )
    verdict(
        _strip_new(criteria_new) == criteria_ref,
        "criteria.json identical to the reference once the band's keys are removed",
    )
    print("RESULT:", "every expectation holds" if failures == 0 else f"{failures} failed")
    return 0 if failures == 0 else 1


def main(argv: list[str]) -> int:
    # LF on every platform, so a redirected output commits as the repository stores text
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(newline="\n")
    if len(argv) == 2 and argv[0] == "expect":
        return expect(Path(argv[1]))
    if len(argv) == 3 and argv[0] == "check":
        return check(Path(argv[1]), Path(argv[2]))
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
