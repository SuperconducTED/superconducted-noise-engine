# ruff: noqa: E501
"""Compare a sealed rehearsal's outputs with criteria 2, 3, 4 and 11, and with amendment 27.

    python check_rehearsal.py <output root> <clone>

An adapted copy of ``rehearsal-2026-11-06/check_rehearsal.py``. The checks of criteria 2, 3 and 4
are the same, read from where the scores now live: the sealed folder, ``<output root>/sealed``.
The report's keys are stage 2's (amendments 24 to 30). New here:

- **sealing on the real path**: every score-derived value in the sealed folder (``ones``,
  ``p_hat``, each error and log score as the TSV writes them, Arm B's measured values, each
  summary figure and every ``T1`` fit number) is looked for, as a whole number, in every file the
  mornings left in the jobs folder outside ``jobs/sealed``, in each morning's routine log and
  record, in the scheduled task's stdout, and in every file of every commit before day 15;
- **what each commit published**: before day 15 no commit holds a scored file; day 15's commit
  adds ``sealed/``, equal to the sealed folder byte for byte;
- **the day-15 report** is complete and lists fourteen days.

Prints each check and its evidence; exit 1 on any failure.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

OUT, CLONE = Path(sys.argv[1]), Path(sys.argv[2])
SEALED, JOBS = OUT / "sealed", OUT / "jobs"
SCORED_NAMES = {
    "results.json",
    "arm-a.tsv",
    "arm-b.json",
    "daily-summary.json",
    "t1-results.json",
    "t1-check.json",
    "report.json",
}
TRIVIAL = {"0", "1", "0.0", "1.0", "nan", "inf", "-inf"}
failures: list[str] = []


def check(name: str, passed: bool, evidence: object = "") -> None:
    print(f"{'pass' if passed else 'FAIL'}  {name}  {evidence}"[:220])
    if not passed:
        failures.append(name)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def floats(node: Any) -> list[float]:
    if isinstance(node, bool) or node is None:
        return []
    if isinstance(node, float):
        return [node]
    if isinstance(node, dict):
        return [x for v in node.values() for x in floats(v)]
    if isinstance(node, list):
        return [x for v in node for x in floats(v)]
    return []


def holds(data: bytes, needle: bytes) -> bool:
    return re.search(rb"(?<![\w.])" + re.escape(needle) + rb"(?![\w])", data) is not None


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(JOBS), *args], check=True, capture_output=True, text=True
    ).stdout


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
report = read(OUT / "report-interim.json")
statuses = [d["status"] for d in report["days"]]
print("  days:", report["days"])
check("first day declared", report["first_day"] == first, first)
check("three days on the axis", len(statuses) == 3, statuses)
check("the outer days are scored", statuses[0] == statuses[2] == "scored", statuses)
check("the middle day is empty", statuses[1] == "empty", statuses[1])
check("the report is marked interim", report["complete"] is False and bool(report["interim_note"]))
arm_a = report["arm_a"]
rows = arm_a["rows"]
print("  rows:", rows, " completed days:", arm_a["completed_days"])
print("  S1:", report["s1"])
print("  Arm B reading:", report["arm_b_reading"])
a1, a2 = arm_a["A1_level_beats_reading"], arm_a["A2_level_beats_reading_at_execution"]
for label, test in (("A1", a1), ("A2", a2)):
    print(
        f"  {label}: rows {test['rows']}, mean_d {test['mean_d']}, batches q {test['batch_means']['q']}, "
        f"passes {test['passes']}, inconclusive {test['inconclusive']}"
    )
print("  A3:", arm_a["A3_sign_holds_on_controls"])
print("  A4:", {k: v for k, v in arm_a["A4_band_calibration_report"].items() if k != "stratum"})
print("  c and s_res:", arm_a["c_and_s_res"])
print("  B:", {k: v for k, v in report["arm_b"].items() if k != "descriptive"})
check("two completed Arm A days", arm_a["completed_days"] == 2, arm_a["completed_days"])
check(
    "two days are too few to decide: S1 inconclusive",
    report["s1"]["row"] == "too few completed days" and not a1["passes"] and not a2["passes"],
    report["s1"]["row"],
)
check(
    "one Arm B job is too few: Arm B inconclusive, adding nothing",
    report["arm_b"]["inconclusive"] is True
    and report["arm_b"]["passes"] is False
    and report["arm_b_reading"]["row"] == "Arm B inconclusive",
    report["arm_b"]["completed_jobs"],
)
check(
    "A4 counts no zero-delay row",
    arm_a["A4_band_calibration_report"]["rows"] < rows["discriminating"],
    (arm_a["A4_band_calibration_report"]["rows"], rows["discriminating"]),
)

jobs = {p.name: p for p in JOBS.iterdir() if p.is_dir() and p.name[0].isdigit()}
check("no folder for the middle day", len(jobs) == 2, sorted(jobs))
ordered = sorted(jobs)
day1, day3 = jobs[ordered[0]], jobs[ordered[1]]
s1, s3 = SEALED / ordered[0], SEALED / ordered[1]
for label, folder, number, arms in (("day 1", day1, 1, "A"), ("day 3", day3, 3, "AB")):
    sub = read(folder / "submission.json")
    check(f"{label}: job number and arms", (sub["job_number"], sub["arms"]) == (number, arms))

check(
    "day 1 was scored the next morning, into the sealed folder",
    (day1 / "operations.json").exists()
    and (s1 / "arm-a.tsv").exists()
    and (s1 / "daily-summary.json").exists(),
)
check("day 1 has no Arm B", not (s1 / "arm-b.json").exists())
check(
    "day 3 was scored the morning after",
    (day3 / "operations.json").exists() and (s3 / "arm-a.tsv").exists(),
)
check("day 3 has Arm B", (s3 / "arm-b.json").exists())
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
check(
    "day 1 keeps its own execution time",
    metrics["timestamps"]["running"].startswith(first),
    metrics["timestamps"]["running"],
)
table = tsv(s1 / "arm-a.tsv")
sealed1 = read(day1 / "sealed.json")
expected_rows = (len(sealed1["discriminating"]) + len(sealed1["controls"])) * 7
check("day 1 rows: 12 qubits on 7 slots", len(table) == expected_rows, len(table))
execution = {r["qubit"]: r["abs_err_reading_at_execution"] for r in table}
check("the execution reading was filled in", all(v not in ("", "nan") for v in execution.values()))

print("the T1 check through the routine")
check("day 1 submitted the check", (day1 / "t1-job_id.txt").exists())
check("day 3 has no check", not (day3 / "t1-job_id.txt").exists())
if (s1 / "t1-check.json").exists():
    t1 = read(s1 / "t1-check.json")
    check("the check names its library version", t1["qiskit_experiments"] == "0.14.2")
    live_t1 = {}
    for q, entries in enumerate(read(OUT / "live-1.json")["properties"]["qubits"]):
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
    ops = read(day1 / "t1-operations.json")
    check(
        "the jobs folder says the check was fitted, with no value",
        ops["status"] == "fitted"
        and ops["qubits"] == len(t1["qubits"])
        and set(ops) == {"status", "job_id", "qubits", "fit_quality", "quantum_seconds"},
        ops,
    )
else:
    check("day 1 fitted the check", False, "no t1-check.json in the sealed folder")

print("criterion 4: a later snapshot as the live document")
for label, folder, scored, name in (
    ("day 1", day1, s1, "live-1.json"),
    ("day 3", day3, s3, "live-3.json"),
):
    doc = read(OUT / name)
    state = read(folder / "sealed.json")
    sub = read(folder / "submission.json")
    saved = folder / "live-properties.json"
    check(
        f"{label}: the manifest names the saved document's hash",
        hashlib.sha256(saved.read_bytes()).hexdigest() == sub["live_properties_sha256"],
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
    print(
        f"  {label}: t_s {sub['t_s']}, live document stamped {doc['properties']['last_update_date']}"
    )
    rows_scored = tsv(scored / "arm-a.tsv")
    differ = sum(r["abs_err_reading"] != r["abs_err_reading_at_execution"] for r in rows_scored)
    check(
        f"{label}: the live state is new, so reading and the execution reading differ",
        differ > 0,
        f"{differ} of {len(rows_scored)} rows",
    )
check(
    "A1 and A2 are different comparisons here",
    a1["mean_d"] != a2["mean_d"],
    (a1["mean_d"], a2["mean_d"]),
)

# --- amendment 27: sealing on the real path --------------------------------------------------------
print("amendment 27: no score, count or fit outside the sealed folder before day 15")
needles: set[str] = set()
for scored in (s1, s3):
    for row in tsv(scored / "arm-a.tsv"):
        for key, value in row.items():
            if key == "p_hat" or key.startswith(("abs_err_", "log_score_")):
                needles.add(value)
            if key == "ones":
                needles.add(f'"ones": {value}')
    if (scored / "arm-b.json").exists():
        needles |= {repr(v) for v in floats(read(scored / "arm-b.json")["measured"])}
    summary = read(scored / "daily-summary.json")
    needles |= {repr(v) for v in floats(summary["arm_a"]) + floats(summary.get("arm_b"))}
t1_values = read(s1 / "t1-check.json")
for row in t1_values["qubits"]:
    needles |= {repr(row[k]) for k in ("t1_s", "stderr_s", "relative_se", "reduced_chi_squared")}
needles.add(repr(t1_values["median_relative_se"]))
needles -= TRIVIAL
encoded = sorted({n.encode() for n in needles})
in_sealed = b"".join(p.read_bytes() for p in SEALED.rglob("*") if p.is_file())
check(
    "every needle is in the sealed folder",
    all(n.startswith(b'"ones"') or holds(in_sealed, n) for n in encoded),
    f"{len(encoded)} needles",
)

outside = [
    p
    for p in JOBS.rglob("*")
    if p.is_file() and ".git" not in p.parts and "sealed" not in p.relative_to(JOBS).parts
]
outside += [*sorted(OUT.glob("morning-*.log")), OUT / "score-3.log", OUT / "report.log"]
leaks = [
    (str(p.relative_to(OUT)), n.decode())
    for p in outside
    for n in encoded
    if holds(p.read_bytes(), n)
]
logs = [p.name for p in outside if p.name.startswith("routine-")]
check(
    "no needle in any file outside the sealed folder, routine logs and stdout included",
    leaks == [],
    f"{len(outside)} files scanned, {len(logs)} routine logs and records; {leaks[:4]}",
)
for name in ("operations.json",):
    for folder in (day1, day3):
        ops = read(folder / name)
        check(
            f"{folder.name}: {name} holds operations only",
            ops["status"] == "scored"
            and set(ops)
            == {
                "status",
                "job_id",
                "job_number",
                "t_s",
                "t_execute",
                "queue_seconds",
                "quantum_seconds",
                "rows",
            },
            ops["rows"],
        )
report_log = (OUT / "report.log").read_text(encoding="utf-8").strip()
check(
    "report's stdout is its path only",
    report_log == f"report written: {SEALED / 'report.json'}",
    report_log[:120],
)

print("what each morning committed")
commits = git("log", "--reverse", "--format=%H %s").splitlines()
print("  commits:", [c.split(" ", 1)[1] for c in commits])
check("one commit per morning: days 1, 3 and 15", len(commits) == 3, len(commits))
for line in commits[:-1]:
    sha, subject = line.split(" ", 1)
    names = git("ls-tree", "-r", "--name-only", sha).split()
    scored_names = [
        n for n in names if n.rsplit("/", 1)[-1] in SCORED_NAMES or n.startswith("sealed/")
    ]
    check(f"{subject}: no scored file committed", scored_names == [], scored_names[:4])
    blobs = b"".join(
        subprocess.run(
            ["git", "-C", str(JOBS), "show", f"{sha}:{n}"], check=True, capture_output=True
        ).stdout
        for n in names
    )
    hits = [n.decode() for n in encoded if holds(blobs, n)]
    check(
        f"{subject}: no needle in any committed file", hits == [], f"{len(names)} files; {hits[:4]}"
    )
last_sha, last_subject = commits[-1].split(" ", 1)
names = git("ls-tree", "-r", "--name-only", last_sha).split()
committed_sealed = sorted(n.removeprefix("sealed/") for n in names if n.startswith("sealed/"))
on_disk = sorted(
    str(p.relative_to(SEALED)).replace("\\", "/") for p in SEALED.rglob("*") if p.is_file()
)
check(
    f"{last_subject}: the sealed folder is committed",
    committed_sealed == on_disk and bool(on_disk),
    f"{len(on_disk)} files",
)
same = all((JOBS / "sealed" / n).read_bytes() == (SEALED / n).read_bytes() for n in on_disk)
check("jobs/sealed equals the sealed folder byte for byte", same)

print("day 15")
final = read(SEALED / "report.json")
check("the day-15 report is complete", final["complete"] is True and final["interim_note"] is None)
check("it lists fourteen days", len(final["days"]) == 14, final["last_day"])
check(
    "days 1 and 3 scored, the other twelve empty",
    [d["status"] for d in final["days"]].count("scored") == 2
    and [d["status"] for d in final["days"]].count("empty") == 12,
)
record = sorted(JOBS.glob("routine-*.json"))[-1]
steps = [s["name"] for s in read(record)["steps"]]
check(
    "day 15's morning reported, unsealed and committed, and built nothing",
    steps[:2] == ["report", "unseal"] and "build" not in steps,
    (record.name, steps),
)

print()
print(f"{len(failures)} failures: {failures}" if failures else "all checks pass")
raise SystemExit(1 if failures else 0)
