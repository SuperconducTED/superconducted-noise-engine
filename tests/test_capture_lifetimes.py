"""Issue #104, amendment 2: ``capture_lifetimes.py --exclude-day`` on a synthetic record.

Baha's review 5927517413 on PR #156: a day of E whose covering sweep was skipped stayed in E as long
as any of its documents was captured, so P1 failed on a day the protocol removes. The record here
is the one the reproduction used: 2026-11-16 to 2026-11-24, two documents a day at 06:00 and 18:00,
all captured except 2026-11-21 06:00, which was missed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "evidence" / "capture-rate-2026-11" / "capture_lifetimes.py"
HEADER = "day\tlast_update_date\tserved\theld\tretrieved\tstatus\tstep_hours\trun_id"
SKIPPED = date(2026, 11, 21)


@pytest.fixture(scope="module")
def record(tmp_path_factory: pytest.TempPathFactory) -> Path:
    repo = tmp_path_factory.mktemp("capture")
    rows = [HEADER]
    for k in range(9):
        day = date(2026, 11, 16) + timedelta(days=k)
        for hour in ("06", "18"):
            missed = day == SKIPPED and hour == "06"
            flags = ("yes", "no", "no", "MISSED") if missed else ("yes", "yes", "yes", "captured")
            stem = f"{day:%Y%m%d}T{hour}0000000000Z"
            rows.append("\t".join([day.isoformat(), stem, *flags, "0.25", "1"]))
    (repo / "health").mkdir()
    (repo / "health" / "capture.tsv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8", newline="\n"
    )
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "-c", "core.autocrlf=false", "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "synthetic record"], check=True)
    return repo


def _run(repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}
    command = [sys.executable, str(SCRIPT), "--ref", "HEAD"]
    command += ["--from", "2026-11-16", "--to", "2026-11-24", *extra]
    return subprocess.run(
        command, cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8"
    )


def test_without_the_flag_the_skipped_day_stays_and_fails_p1(record: Path) -> None:
    """The finding, as reproduced on the code before the change."""
    done = _run(record)
    assert done.returncode == 0, done.stderr
    assert "selected documents stamped 2026-11-16 to 2026-11-24: 18" in done.stdout
    assert "of 0.5 h or more: 1 of 17" in done.stdout
    assert "2026-W47   7 (2026-11-16..2026-11-22)" in done.stdout
    assert "excluded days" not in done.stdout


def test_an_excluded_day_leaves_the_selection_and_the_week(record: Path) -> None:
    done = _run(record, "--exclude-day", str(SKIPPED))
    assert done.returncode == 0, done.stderr
    assert "selected documents stamped 2026-11-16 to 2026-11-24: 16" in done.stdout
    assert "of 0.5 h or more: 0 of 15" in done.stdout
    assert "the D+1 sweep skipped): 2026-11-21; recorded days left: 8" in done.stdout
    assert "2026-W47   6 (2026-11-16..2026-11-22)     12 /   12" in done.stdout


def test_both_ends_can_be_excluded_and_are_listed_in_date_order(record: Path) -> None:
    done = _run(record, "--exclude-day", "2026-11-24", "--exclude-day", "2026-11-16")
    assert done.returncode == 0, done.stderr
    assert "the D+1 sweep skipped): 2026-11-16, 2026-11-24; recorded days left: 7" in done.stdout


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (
            ("--exclude-day", "2026-11-25"),
            "--exclude-day outside 2026-11-16 to 2026-11-24: 2026-11-25",
        ),
        (
            ("--exclude-day", "2026-11-15"),
            "--exclude-day outside 2026-11-16 to 2026-11-24: 2026-11-15",
        ),
        (("--exclude-day", "2026-11-21", "--exclude-day", "2026-11-21"), "given twice"),
    ],
)
def test_an_exclusion_outside_the_selection_or_given_twice_is_refused(
    record: Path, extra: tuple[str, ...], message: str
) -> None:
    done = _run(record, *extra)
    assert done.returncode != 0
    assert message in done.stderr
    assert "selected documents" not in done.stdout
