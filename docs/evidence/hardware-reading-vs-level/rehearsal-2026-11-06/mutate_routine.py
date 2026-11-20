# ruff: noqa: E501
"""Criterion 5 for the morning routine and the T1 check. Restores from memory; never via git.

    python mutate_routine.py <repo root>

Run with the T1 check's interpreter so the tests that need Qiskit Experiments run too. Each mutant
asserts its pattern is found exactly once, so a mutant that changes nothing cannot pass as caught.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DAILY = "scripts/hardware_daily.py"
CHECK = "scripts/hardware_t1_check.py"
DAILY_TESTS = "tests/test_hardware_daily.py"
CHECK_TESTS = "tests/test_hardware_t1_check.py"

MUTANTS = [
    # --- the routine
    (
        DAILY,
        "the run's calendar",
        "return (day - first_day).days + 1",
        "return (day - first_day).days",
    ),
    (
        DAILY,
        "before the run nothing",
        "if number < 1 or number > N_JOBS + 1:",
        "if number > N_JOBS + 1:",
    ),
    (DAILY, "after the run nothing", "if number < 1 or number > N_JOBS + 1:", "if number < 1:"),
    (DAILY, "day 15 submits nothing", "    if number <= N_JOBS:\n", "    if True:\n"),
    (
        DAILY,
        "check on first and last only",
        "T1_JOBS = frozenset({1, N_JOBS})",
        "T1_JOBS = frozenset(range(1, N_JOBS + 1))",
    ),
    (
        DAILY,
        "no check after a refused build",
        "if built == 0 and number in T1_JOBS:",
        "if number in T1_JOBS:",
    ),
    (
        DAILY,
        "today is never scored",
        "if p.is_dir() and DAY_FOLDER.fullmatch(p.name) and p.name < today.isoformat()",
        "if p.is_dir() and DAY_FOLDER.fullmatch(p.name)",
    ),
    (
        DAILY,
        "only day folders are scored",
        "if p.is_dir() and DAY_FOLDER.fullmatch(p.name) and p.name < today.isoformat()",
        "if p.is_dir() and p.name < today.isoformat()",
    ),
    (
        DAILY,
        "a scored day is not scored again",
        '        and not (job_dir / "arm-a.tsv").exists()\n',
        "",
    ),
    (
        DAILY,
        "a failed day is not scored again",
        '        and not (job_dir / "failed.json").exists()\n',
        "",
    ),
    (
        DAILY,
        "an empty day is not scored",
        '        (job_dir / "job_id.txt").exists()\n',
        "        True\n",
    ),
    (
        DAILY,
        "a fitted check is not refitted",
        '        and not (job_dir / "t1-check.json").exists()\n',
        "",
    ),
    (
        DAILY,
        "a failed check is not refitted",
        '        and not (job_dir / "t1-failed.json").exists()\n',
        "",
    ),
    (
        DAILY,
        "a refused build is a failure",
        "# no job today, and whoever reads the task's last result should see that.\nALLOWED = {\n",
        '# no job today, and whoever reads the task\'s last result should see that.\nALLOWED = {\n    "build": {0, EXIT_REFUSED},\n',
    ),
    (
        DAILY,
        "not ready to score is no failure",
        '    "score": {0, EXIT_NOT_YET},\n',
        '    "score": {0},\n',
    ),
    (DAILY, "the exit reports failures", "return 0 if allowed_all else 1", "return 0"),
    (
        DAILY,
        "the time limit is applied",
        "return process.wait(timeout=limit_s)",
        "return process.wait()",
    ),
    (
        DAILY,
        "the limit reports itself",
        "            _kill_tree(process)\n            return EXIT_TIMED_OUT\n",
        "            _kill_tree(process)\n            return 0\n",
    ),
    (
        DAILY,
        "the step's children die too",
        '            ["taskkill", "/T", "/F", "/PID", str(process.pid)],\n',
        '            ["taskkill", "/F", "/PID", str(process.pid)],\n',
    ),
    (
        DAILY,
        "output goes to the log",
        "            stdout=handle,\n",
        "            stdout=subprocess.PIPE,\n",
    ),
    (
        DAILY,
        "each step appends",
        'with log.open("ab") as handle:',
        'with log.open("wb") as handle:',
    ),
    (DAILY, "waits for the window", "    if 0.0 < wait <= limit_s:\n", "    if False:\n"),
    (DAILY, "does not wait long", "    if 0.0 < wait <= limit_s:\n", "    if 0.0 < wait:\n"),
    (
        DAILY,
        "a rehearsal never waits",
        "    if morning.rehearsal is None:\n        _wait_for_window",
        "    if True:\n        _wait_for_window",
    ),
    (
        DAILY,
        "the freeze flags reach build",
        '    if morning.rehearsal is not None:\n        return []\n    return ["--frozen-at"',
        '    return ["--frozen-at"',
    ),
    (DAILY, "nothing committed unless asked", "    if morning.commit_data:\n", "    if True:\n"),
    (DAILY, "nothing pushed unless asked", "        if morning.push_data:\n", "        if True:\n"),
    (
        DAILY,
        "a real morning needs the freeze",
        '    elif not args.frozen_at or args.prereg is None:\n        parser.error("a real morning needs --frozen-at and --prereg")\n',
        "",
    ),
    (
        DAILY,
        "a rehearsal comes whole",
        "if any(v is not None for v in flags) and any(v is None for v in flags):",
        "if False:",
    ),
    (DAILY, "pushing needs committing", "if args.push_data and not args.commit_data:", "if False:"),
    (DAILY, "the machine stays awake", "    _stay_awake()\n", ""),
    (DAILY, "the awake flags", "es_continuous | es_system_required", "es_system_required"),
    # --- the check
    (CHECK, "the first delay", "FIRST_DELAY_S = 1e-6", "FIRST_DELAY_S = 2e-6"),
    (CHECK, "the delay span", "DELAY_SPAN_IN_T1 = 3.0", "DELAY_SPAN_IN_T1 = 2.0"),
    (CHECK, "eight delays", "N_DELAYS = 8", "N_DELAYS = 7"),
    (CHECK, "1024 shots", "T1_SHOTS = 1024", "T1_SHOTS = 512"),
    (
        CHECK,
        "a bad expectation refused",
        "if not np.isfinite(expected_t1_s) or expected_t1_s * DELAY_SPAN_IN_T1 <= FIRST_DELAY_S:",
        "if False:",
    ),
    (CHECK, "first and last jobs only", "    if number not in T1_JOBS:\n", "    if False:\n"),
    (
        CHECK,
        "needs a main job",
        '    if not (job_dir / "job_id.txt").exists():\n',
        "    if False:\n",
    ),
    (
        CHECK,
        "a real check needs a real job",
        'if not local and main_id.startswith("local-"):',
        "if False:",
    ),
    (CHECK, "submitted once", '    if (job_dir / "t1-job_id.txt").exists():\n', "    if False:\n"),
    (
        CHECK,
        "rep_delay checked",
        "    check_rep_delay(REP_DELAY_S, device.rep_delay_range())\n",
        "",
    ),
    (CHECK, "circuits validated", "    validate_isa_circuits(circuits, device.target)\n", ""),
    (
        CHECK,
        "the delays come from level",
        'level = state["sources"]["level"]',
        'level = state["sources"]["reading"]',
    ),
    (
        CHECK,
        "the circuits are sealed",
        '    write_circuits(job_dir / "t1-circuits.qpy", circuits)\n',
        '    write_circuits(job_dir / "other.qpy", circuits)\n',
    ),
    (
        CHECK,
        "the seal is written first",
        '    write_json_lf(job_dir / "t1-sealed.json", sealed)\n    job_id = device.submit(circuits, [T1_SHOTS] * len(circuits), options)\n',
        '    job_id = device.submit(circuits, [T1_SHOTS] * len(circuits), options)\n    write_json_lf(job_dir / "t1-sealed.json", sealed)\n',
    ),
    (
        CHECK,
        "the job id is written",
        '(job_dir / "t1-job_id.txt").write_text(job_id',
        '(job_dir / "other.txt").write_text(job_id',
    ),
    (
        CHECK,
        "the pinned options",
        'options = pinned_options(f"issue-125-t1-{number:02d}")',
        'options = {"environment": {"job_tags": [f"issue-125-t1-{number:02d}"]}}',
    ),
    (
        CHECK,
        "score needs a check",
        '    if not (job_dir / "t1-job_id.txt").exists():\n',
        "    if False:\n",
    ),
    (
        CHECK,
        "the seal's hash checked",
        'if _sha256(job_dir / "t1-circuits.qpy") != sealed["circuits_sha256"]:',
        "if False:",
    ),
    (
        CHECK,
        "not yet is left alone",
        'if status in WAITING or status == "RUNNING":',
        "if status in WAITING:",
    ),
    (
        CHECK,
        "queued is left alone",
        'if status in WAITING or status == "RUNNING":',
        'if status == "RUNNING":',
    ),
    (
        CHECK,
        "failure recorded",
        'job_dir / "t1-failed.json", {"reason": "the check did not finish", "status": status}',
        'job_dir / "other.json", {"reason": "the check did not finish", "status": status}',
    ),
    (
        CHECK,
        "shots checked",
        "        if sum(counts.values()) != expected:\n",
        "        if False:\n",
    ),
    (
        CHECK,
        "raw counts first",
        '    write_json_lf(job_dir / "t1-results.json", {"job_id": job_id, "counts": fetched.counts})\n',
        "",
    ),
    (CHECK, "the fit's qubits named", "    if set(out) != set(delays):\n", "    if False:\n"),
    (
        CHECK,
        "the guard runs for a real check",
        'if args.mode == "submit" and not local:',
        "if False:",
    ),
    (
        CHECK,
        "the check reads the frozen hash",
        'args.repo, args.frozen_at, args.prereg, str(submission["controls_file_sha256"])',
        'args.repo, args.frozen_at, args.prereg, "0" * 64',
    ),
    (
        CHECK,
        "reading beside the fit",
        '"reading_t1_s": float(state["sources"]["reading"][str(q)][0])',
        '"reading_t1_s": float(state["sources"]["level"][str(q)][0])',
    ),
    (
        CHECK,
        "the median is the median",
        'statistics.median(r["relative_se"] for r in per_qubit)',
        'max(r["relative_se"] for r in per_qubit)',
    ),
]


def main(root: str) -> int:
    repo = Path(root)
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([".", "src"]), "PYTHONIOENCODING": "utf-8"}
    survivors: list[str] = []
    for where, name, old, new in MUTANTS:
        path = repo / where
        original = path.read_bytes()
        text = original.decode("utf-8")
        count = text.count(old)
        if count != 1:
            print(f"PATTERN NOT FOUND ONCE ({count}): {name}", flush=True)
            survivors.append(f"{name} (pattern)")
            continue
        tests = DAILY_TESTS if where == DAILY else CHECK_TESTS
        try:
            path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    tests,
                    "-q",
                    "-x",
                    "-m",
                    "not slow",
                    "-o",
                    "addopts=",
                    "-p",
                    "no:cacheprovider",
                    "--tb=no",
                ],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        finally:
            path.write_bytes(original)
        caught = run.returncode != 0
        lines = run.stdout.splitlines()
        last = [ln for ln in lines if "FAILED" in ln or "ERROR" in ln]
        why = last[0] if last else (f"NO TEST NAMED: {lines[-1]}" if lines else "NO OUTPUT")
        print(f"{'caught  ' if caught else 'SURVIVED'} {name:38s} {why[:90]}", flush=True)
        if not caught:
            survivors.append(name)
    print(f"\n{len(MUTANTS)} mutants, {len(survivors)} survivors: {survivors}", flush=True)
    return 1 if survivors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
