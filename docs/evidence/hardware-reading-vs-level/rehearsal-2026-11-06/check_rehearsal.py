# ruff: noqa: E501
"""Compare a rehearsal's outputs with what criteria 2, 3 and 4 ask. Prints each check and its evidence.

python check_rehearsal.py <output root> <clone>
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

OUT, CLONE = Path(sys.argv[1]), Path(sys.argv[2])
failures: list[str] = []


def check(name: str, passed: bool, evidence: object = "") -> None:
    print(f"{'pass' if passed else 'FAIL'}  {name}  {evidence}"[:200])
    if not passed:
        failures.append(name)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --- criterion 2 -----------------------------------------------------------------------------------
print("criterion 2: build at a past instant matches the dry run on the same inputs")
manifest = read(CLONE / "docs/evidence/hardware-reading-vs-level/dry-run-2026-11-05/manifest.json")
c2 = OUT / "c2" / "2026-10-23"
sealed = read(c2 / "sealed.json")
check(
    "discriminating",
    sealed["discriminating"] == manifest["discriminating"],
    sealed["discriminating"],
)
check("controls", sealed["controls"] == manifest["controls"], sealed["controls"])
slots = {q: [v or 0 for v in s] for q, s in sealed["slots"].items()}
wanted = {q: [v or 0 for v in s] for q, s in manifest["slots_dt"].items()}
check("slots", slots == wanted, f"{len(slots)} qubits")
check("layouts", sealed["layouts"] == manifest["layouts"], sealed["layouts"])
submission = read(c2 / "submission.json")
check(
    "the archive commit is named",
    submission["ref_sha"] == manifest["ref_sha"],
    submission["ref_sha"][:12],
)
check(
    "the controls hash matches",
    submission["controls_file_sha256"] == manifest["controls_file_sha256"],
)

# --- criteria 3 and 4 ------------------------------------------------------------------------------
print("criterion 3: the cycle over three days, the middle one absent")
days = [ln.split() for ln in (OUT / "days.txt").read_text(encoding="utf-8").splitlines()]
first = next(d[1] for d in days if d[0] == "first")
report = read(OUT / "jobs" / "report.json")
statuses = [d["status"] for d in report["days"]]
print("  days:", report["days"])
check("first day declared", report["first_day"] == first, first)
check("three days on the axis", len(statuses) == 3, statuses)
check("the middle day is empty", statuses[1] == "empty", statuses[1])
check("the report is marked interim", report["complete"] is False and bool(report["interim_note"]))
rows = report["arm_a"]["rows"]
print("  rows:", rows, " reading:", report["reading"])
check(
    "the three-day calendar gives no interval",
    report["arm_a"]["A1_level_beats_reading"]["interval"] is None,
)
print("  A1:", report["arm_a"]["A1_level_beats_reading"])
print("  A2:", report["arm_a"]["A2_level_beats_reading_at_execution"])
print(
    "  A3:",
    report["arm_a"]["A3_sign_holds_on_controls"],
    " A4:",
    report["arm_a"]["A4_band_covers_nominal_within_widening"],
)
print("  B:", report["arm_b"])

jobs = {str(p.name): p for p in (OUT / "jobs").iterdir() if p.is_dir() and p.name[0].isdigit()}
check("no folder for the middle day", len(jobs) == 2, sorted(jobs))
ordered = sorted(jobs)
day1, day3 = jobs[ordered[0]], jobs[ordered[1]]
for label, folder, number, arms in (("day 1", day1, 1, "A"), ("day 3", day3, 3, "AB")):
    submission = read(folder / "submission.json")
    check(
        f"{label}: job number and arms",
        (submission["job_number"], submission["arms"]) == (number, arms),
    )

check(
    "day 1 was scored the next morning",
    (day1 / "arm-a.tsv").exists() and (day1 / "daily-summary.json").exists(),
)
check("day 1 has no Arm B", not (day1 / "arm-b.json").exists())
check("day 3 was scored the morning after", (day3 / "arm-a.tsv").exists())
check("day 3 has Arm B", (day3 / "arm-b.json").exists())
check(
    "the routine wrote no job on the missing day",
    not any(d["status"] != "empty" for d in report["days"][1:2]),
)
check(
    "rows from both days reach the report",
    rows["discriminating"] == 2 * 8 * 7 and rows["control"] == 2 * 4 * 7,
    rows,
)
metrics = read(day1 / "metrics.json")
live_days = {d[0]: d for d in days if d[0] != "first"}
check(
    "day 1 keeps its own execution time",
    metrics["timestamps"]["running"].startswith(first),
    metrics["timestamps"]["running"],
)

with (day1 / "arm-a.tsv").open(encoding="utf-8", newline="") as handle:
    table = list(csv.DictReader(handle, delimiter="\t"))
sealed1 = read(day1 / "sealed.json")
expected_rows = (len(sealed1["discriminating"]) + len(sealed1["controls"])) * 7
check("day 1 rows: 12 qubits on 7 slots", len(table) == expected_rows, len(table))
execution = {r["qubit"]: r["abs_err_reading_at_execution"] for r in table}
check("the execution reading was filled in", all(v not in ("", "nan") for v in execution.values()))

print("the T1 check through the routine")
check("day 1 submitted the check", (day1 / "t1-job_id.txt").exists())
check("day 3 has no check", not (day3 / "t1-job_id.txt").exists())
if (day1 / "t1-check.json").exists():
    t1 = read(day1 / "t1-check.json")
    check("the check names its library version", t1["qiskit_experiments"] == "0.14.2")
    live_t1 = {}
    live_doc = read(OUT / "live-1.json")
    for q, entries in enumerate(live_doc["properties"]["qubits"]):
        for e in entries:
            if e["name"] == "T1":
                live_t1[q] = float(e["value"]) * 1e-6
    for row in t1["qubits"]:
        built = live_t1[row["qubit"]]
        off = abs(row["t1_s"] - built) / row["stderr_s"]
        print(
            f"  Q{row['qubit']:<4d} fitted {row['t1_s'] * 1e6:7.1f} us, se {row['relative_se']:6.1%}, built from {built * 1e6:7.1f} us, {off:4.1f} se away, {row['quality']}"
        )
        check(f"Q{row['qubit']} fit agrees with the simulator's T1", off <= 4.0)
else:
    check("day 1 fitted the check", False, "no t1-check.json")

print("criterion 4: a later snapshot as the live document")
for label, folder, name in (("day 1", day1, "live-1.json"), ("day 3", day3, "live-3.json")):
    doc = read(OUT / name)
    state = read(folder / "sealed.json")
    submission = read(folder / "submission.json")
    saved = folder / "live-properties.json"
    check(
        f"{label}: the manifest names the saved document's hash",
        hashlib.sha256(saved.read_bytes()).hexdigest() == submission["live_properties_sha256"],
    )
    check(
        f"{label}: the saved document is the live one",
        read(saved)["properties"]["last_update_date"] == doc["properties"]["last_update_date"],
        doc["properties"]["last_update_date"],
    )
    t1s = {}
    for q, entries in enumerate(doc["properties"]["qubits"]):
        for e in entries:
            if e["name"] == "T1":
                t1s[q] = float(e["value"]) * 1e-6
    reading = state["sources"]["reading"]
    close = all(abs(float(reading[str(q)][0]) - t1s[q]) < 1e-12 for q in state["discriminating"])
    check(f"{label}: reading comes from the live document", close, state["discriminating"])
    t_s = submission["t_s"]
    stamp = doc["properties"]["last_update_date"]
    print(f"  {label}: t_s {t_s}, live document stamped {stamp}")
    with (folder / "predictors.tsv").open(encoding="utf-8", newline="") as handle:
        predictors = list(csv.DictReader(handle, delimiter="\t"))
    print("  predictors columns:", [c for c in predictors[0] if "t1" in c.lower()][:8])
    with (folder / "arm-a.tsv").open(encoding="utf-8", newline="") as handle:
        scored = list(csv.DictReader(handle, delimiter="\t"))
    differ = sum(r["abs_err_reading"] != r["abs_err_reading_at_execution"] for r in scored)
    check(
        f"{label}: the live state is new, so reading and the execution reading differ",
        differ > 0,
        f"{differ} of {len(scored)} rows",
    )

a1, a2 = (
    report["arm_a"]["A1_level_beats_reading"],
    report["arm_a"]["A2_level_beats_reading_at_execution"],
)
check(
    "A1 and A2 are different comparisons here",
    a1["mean_difference"] != a2["mean_difference"],
    (a1["mean_difference"], a2["mean_difference"]),
)

print()
print(f"{len(failures)} failures: {failures}" if failures else "all checks pass")
raise SystemExit(1 if failures else 0)
