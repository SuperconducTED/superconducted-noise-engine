# ruff: noqa: E501
"""Criterion 5: remove each guard and confirm a test fails. Restores from a backup; never via git.

    python mutate_submit.py <repo root>

Each mutant asserts its pattern is found exactly once, so a mutant that changes nothing cannot pass
as caught. Every run uses only the fast tests, except the batching mutant.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = "scripts/hardware_submit.py"
TESTS = "tests/test_hardware_submit.py"

MUTANTS = [
    ("HEAD check", "if head != frozen_at:", "if False:"),
    ("clean tree check", 'if _git(repo, "status", "--porcelain").strip():', "if False:"),
    ("Frozen status check", "if not FROZEN_STATUS.search(text):", "if False:"),
    (
        "status check reads the word only",
        'FROZEN_STATUS = re.compile(r"\\*\\*Status\\*\\*:\\s*\\*\\*Frozen\\b")',
        'FROZEN_STATUS = re.compile(r"Frozen at")',
    ),
    (
        "a commit without the pre-registration",
        '    except subprocess.CalledProcessError as exc:\n        raise RefusedError(f"{prereg} is not in the frozen commit") from exc\n',
        '    except KeyError as exc:\n        raise RefusedError(f"{prereg} is not in the frozen commit") from exc\n',
    ),
    ("hash named check", "if named is None:", "if False:"),
    ("hash equals check", "if named.group(1) != controls_sha:", "if named is None:"),
    ("both arguments needed", "if not frozen_at or prereg is None:", "if False:"),
    (
        "guard runs in main",
        "            check_frozen(args.repo, args.frozen_at, args.prereg, controls_sha)\n",
        "            pass\n",
    ),
    (
        "second job refused",
        'if (job_dir / "job_id.txt").exists():\n        raise RefusedError(f"a job was already',
        'if False:\n        raise RefusedError(f"a job was already',
    ),
    ("window close refused", "        if t_s >= closes:\n", "        if False:\n"),
    ("window open refused", "        if t_s < opens:\n", "        if False:\n"),
    (
        "missed day recorded",
        '        job_dir / "missed.json",\n',
        '        job_dir / "not-missed.json",\n',
    ),
    (
        "window checked again at submission",
        "if enforce_window and (at_submit := now()) >= closes:",
        "if False and (at_submit := now()) >= closes:",
    ),
    (
        "rehearsal keeps its execution time",
        'running = stored["running"]',
        "running = self._execute_at.isoformat()",
    ),
    (
        "registers joined in the circuit's order",
        "pub.join_data(names)",
        "pub.join_data(names[::-1])",
    ),
    ("no register refused", "        if not names:\n", "        if False:\n"),
    ("rep_delay range checked", "if not low <= rep_delay <= high:", "if False:"),
    (
        "rep_delay checked before capture",
        "    check_rep_delay(REP_DELAY_S, device.rep_delay_range())\n",
        "    pass\n",
    ),
    (
        "decoupling off",
        '"dynamical_decoupling": {"enable": False}',
        '"dynamical_decoupling": {"enable": True}',
    ),
    ("gate twirling off", '"enable_gates": False', '"enable_gates": True'),
    ("init_qubits on", '"init_qubits": True', '"init_qubits": False'),
    ("rep_delay is 500 us", "REP_DELAY_S = 500e-6", "REP_DELAY_S = 250e-6"),
    ("job 1 is Arm A only", 'return "A" if job_number == 1 else "AB"', 'return "AB"'),
    (
        "arm B shots",
        "shots += [ARM_B_SHOTS] * len(job.arm_b)",
        "shots += [ARM_A_SHOTS] * len(job.arm_b)",
    ),
    (
        "live reading used",
        "rows = predictor_rows(collected, at=t_s, live=live)",
        "rows = predictor_rows(collected, at=t_s, live=None)",
    ),
    (
        "sealed before submit",
        '    write_json_lf(job_dir / "sealed.json", job_to_state(job))\n    write_circuits(job_dir / "circuits.qpy", job.arm_a + job.arm_b)\n',
        "    pass\n",
    ),
    (
        "job id written",
        '(job_dir / "job_id.txt").write_text(job_id + "\\n", encoding="utf-8", newline="\\n")',
        '(job_dir / "other.txt").write_text(job_id + "\\n", encoding="utf-8", newline="\\n")',
    ),
    ("sealed hash checked", "if _sha256(job_dir / name) != submission[key]:", "if False:"),
    ("queued left alone", "if now() < next_submission(t_s):", "if False:"),
    ("still queued cancelled", "        device.cancel(job_id)\n", "        pass\n"),
    (
        "running not cancelled",
        'WAITING = frozenset({"INITIALIZING", "QUEUED", "VALIDATING"})',
        'WAITING = frozenset({"INITIALIZING", "QUEUED", "VALIDATING", "RUNNING"})',
    ),
    (
        "failed day recorded",
        'job_dir / "failed.json", {"reason": "the job did not finish", "status": status}',
        'job_dir / "other.json", {"reason": "the job did not finish", "status": status}',
    ),
    ("shot count checked", "if sum(circuit_counts.values()) != expected:", "if False:"),
    (
        "archive past t_execute",
        "if not any(f.time > t_execute for f in collected.files):",
        "if False:",
    ),
    (
        "control added",
        "job = with_execution(job, execution_rows(collected, at=t_execute, live=None))",
        "job = with_execution(job, [])",
    ),
    (
        "cross-check failure tolerated",
        "    except Exception as exc:  # an unscored cross-check must not cost the day's scores\n",
        "    except KeyError as exc:\n",
    ),
    ("each circuit's own register", "getattr(pub.data, names[0])", 'getattr(pub.data, "c")'),
    ("token needed", "    if not token:\n", "    if False:\n"),
    (
        "span reaches the bootstrap",
        "list(diffs), list(dates), block_days=BLOCK_DAYS, seed=seed, span=span\n",
        "list(diffs), list(dates), block_days=BLOCK_DAYS, seed=seed\n",
    ),
    (
        "span widens the axis",
        "first, n_days = _calendar_axis(dates if span is None else [*dates, *span])",
        "first, n_days = _calendar_axis(dates)",
        "scripts/hardware_reading_vs_level.py",
    ),
    ("three day blocks", "BLOCK_DAYS = 3", "BLOCK_DAYS = 1"),
    ("fourteen days", "N_JOBS = 14", "N_JOBS = 15"),
    ("nominal is 80 percent", "BAND_NOMINAL = 0.80", "BAND_NOMINAL = 0.70"),
    (
        "a calendar within a block has no interval",
        "if (span[1] - span[0]).days + 1 <= BLOCK_DAYS:",
        "if False:",
    ),
    (
        "the block itself is within",
        "if (span[1] - span[0]).days + 1 <= BLOCK_DAYS:",
        "if (span[1] - span[0]).days + 1 < BLOCK_DAYS:",
    ),
    ("interval lower end decides", '"passes": low > 0.0,', '"passes": high > 0.0,'),
    (
        "A1 and A2 draw differently",
        'a2 = _beats(discriminating, "reading_at_execution", span=span, seed=int(state[1]))',
        'a2 = _beats(discriminating, "reading_at_execution", span=span, seed=int(state[0]))',
    ),
    (
        "A2 compares the execution reading",
        'a2 = _beats(discriminating, "reading_at_execution", span=span,',
        'a2 = _beats(discriminating, "reading", span=span,',
    ),
    ("A3 is strict and positive", "is not None and gap > 0.0", "is not None and gap >= -1.0"),
    (
        "A3 covers both readings",
        'for name in ("reading", "reading_at_execution")\n    )\n    covered',
        'for name in ("reading",)\n    )\n    covered',
    ),
    ("A3 reads the controls", "_gaps(control, name)", "_gaps(discriminating, name)"),
    (
        "A4 reads the widened coverage",
        "a4 = coverage_widened is not None and coverage_widened >= BAND_NOMINAL",
        "a4 = coverage is not None and coverage >= BAND_NOMINAL",
    ),
    (
        "A4 leaves out rows with no band",
        'for r in discriminating\n        if int(r["band_covered_widened"]) >= 0\n',
        "for r in discriminating\n",
    ),
    (
        "A1 to A3 pair the rows",
        'if math.isfinite(float(r[f"abs_err_{other}"])) and math.isfinite(float(r["abs_err_level"]))\n',
        "",
    ),
    (
        "S1 needs every condition",
        'elif a1["passes"] and a2["passes"] and a3 and a4:',
        'elif a1["passes"]:',
    ),
    (
        "S1 fails on a tie",
        "elif execution_gap is not None and execution_gap <= 0.0:",
        "elif execution_gap is not None and execution_gap < 0.0:",
    ),
    ("staleness named", 'elif a1["passes"] and not a2["passes"]:', "elif False:"),
    ("band ranks by midpoint", "(float(a) + float(b)) / 2.0", "float(a)"),
    (
        "missing band end not a prediction",
        "None if a is None or b is None else ",
        "0.0 if a is None or b is None else ",
    ),
    (
        "one predictor meets both",
        'any(ranks(n) and picks(n) for n in ("level", "band"))',
        'any(ranks(n) for n in ("level", "band"))',
    ),
    (
        "each condition by either",
        '"each_condition_by_either": any(ranks(n) for n in ("level", "band"))\n        and any(picks(n) for n in ("level", "band")),',
        '"each_condition_by_either": True,',
    ),
    (
        "B1 at least as well",
        "ours is not None and theirs is not None and ours >= theirs",
        "ours is not None and theirs is not None",
    ),
    ("B2 at least as often", 'return hits[name] >= hits["reading"]', "return True"),
    (
        "declared first day",
        "    outside = sorted(d.isoformat()",
        "    first_day = min(named, default=first_day)\n    outside = sorted(d.isoformat()",
    ),
    ("outside folders refused", "if outside:\n", "if False:\n"),
    ("complete only after day 14", "complete = today > final", "complete = today >= final"),
    ("axis stops at today", "last = min(today, final)", "last = final"),
    (
        "empty day kept",
        '"status": _day_status(named[d]) if d in named else "empty"',
        '"status": _day_status(named[d]) if d in named else "scored"',
    ),
    (
        "failed before missed",
        'if (job_dir / "failed.json").exists():\n        return "failed"\n',
        "",
    ),
    ("missed named", 'if (job_dir / "missed.json").exists():\n        return "missed"\n', ""),
    ("Arm A rows read", 'rows.extend(_read_rows(folder / "arm-a.tsv", day))', "pass"),
    ("Arm B jobs read", 'arm_b_jobs.append(_read_json(folder / "arm-b.json"))', "pass"),
    (
        "refused exits cleanly",
        '        except RefusedError as exc:\n            print(f"refused: {exc}", file=sys.stderr)\n            return EXIT_REFUSED\n        write_json_lf(args.jobs_dir / "report.json", outcome)\n',
        '        except KeyError as exc:\n            print(f"refused: {exc}", file=sys.stderr)\n            return EXIT_REFUSED\n        write_json_lf(args.jobs_dir / "report.json", outcome)\n',
    ),
    (
        "rehearsal runs circuits alone",
        '        for circuit, n_shots, seed in zip(circuits, shots, seeds, strict=True):\n            sampler = SamplerV2(mode=simulator, options={"simulator": {"seed_simulator": seed}})\n            result = sampler.run([(circuit, None, n_shots)]).result()\n            counts.extend(_counts_from_pubs(result, [circuit]))\n',
        '        sampler = SamplerV2(mode=simulator, options={"simulator": {"seed_simulator": seeds[0]}})\n        result = sampler.run([(c, None, s) for c, s in zip(circuits, shots, strict=True)]).result()\n        counts.extend(_counts_from_pubs(result, circuits))\n',
    ),
]


def main(root: str) -> int:
    repo = Path(root)
    path = repo / SCRIPT
    original = path.read_bytes()
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([".", "src"]), "PYTHONIOENCODING": "utf-8"}
    survivors: list[str] = []
    try:
        for name, old, new, *where in MUTANTS:
            target = repo / where[0] if where else path
            before = target.read_bytes()
            source = before.decode("utf-8")
            count = source.count(old)
            if count != 1:
                print(f"PATTERN NOT FOUND ONCE ({count}): {name}", flush=True)
                survivors.append(f"{name} (pattern)")
                continue
            target.write_text(source.replace(old, new), encoding="utf-8", newline="\n")
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    TESTS,
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
            caught = run.returncode != 0
            lines = run.stdout.splitlines()
            last = [ln for ln in lines if "FAILED" in ln or "ERROR" in ln]
            why = last[0] if last else (f"NO TEST NAMED: {lines[-1]}" if lines else "NO OUTPUT")
            print(f"{'caught  ' if caught else 'SURVIVED'} {name:38s} {why[:90]}", flush=True)
            if not caught:
                survivors.append(name)
            target.write_bytes(before)
    finally:
        path.write_bytes(original)
    print(f"\n{len(MUTANTS)} mutants, {len(survivors)} survivors: {survivors}", flush=True)
    return 1 if survivors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
