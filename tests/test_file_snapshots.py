"""End-to-end test of ``scripts/file_snapshots.sh`` — real branch switch included.

PR #50's review found the filing step calling
``scripts/canonical_snapshot_digest.py`` *after* ``git checkout -B
calibration-data`` had removed ``scripts/`` from the working tree: Python
exited 2 (file not found) and every genuine duplicate would have been recorded
as ``collision-unreadable``. The unit tests could not see it because they
exercised the digest and the shell separately, and the pre-deployment
simulation ran the shell without the branch switch.

So this test does the switch for real. It builds a bare "origin" holding a
``calibration-data`` branch with archived snapshots, a source repository
holding the two scripts, a staging directory with a duplicate, a collision and
a new payload, and runs the script under bash. The assertions are on what
reached origin, because that is the only thing the poller's consumers see.

Requires ``git`` and ``bash`` (Git for Windows ships both); skipped otherwise.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "file_snapshots.sh"
DIGEST = REPO_ROOT / "scripts" / "canonical_snapshot_digest.py"

# A is re-observed unchanged (bytes differ, document does not); B is re-observed
# with a changed value; C is a June stamp polled in September, so it must file
# under 2026-06 rather than the poll month.
STEM_A = "20260828T031723000000Z"
STEM_B = "20260828T061614000000Z"
STEM_C = "20260630T065221000000Z"
POLL_TIME = "2026-09-01T12:00:00Z"

OPS_LEGACY = [
    {"name": "measure_2", "qargs": [0]},
    {"name": "cz", "qargs": [0, 1]},
    {"name": "sx", "qargs": [1]},
]
OPS_SORTED = sorted(OPS_LEGACY, key=lambda e: (e["name"], tuple(e["qargs"])))


def _doc(operations: list[dict[str, Any]], stamp: str, t1: float = 100.0) -> dict[str, Any]:
    return {
        "backend": "ibm_fez",
        "timestamp": stamp,
        "schema_version": "1.0.0",
        "properties": {"qubits": [[{"name": "T1", "unit": "us", "value": t1}]]},
        "target": {"num_qubits": 2, "physical_qubits": [0, 1], "operations": operations},
        "configuration": None,
    }


def _legacy(stem: str, t1: float = 100.0) -> bytes:
    """A pre-#46 archived file: unsorted operations, indented."""
    return json.dumps(_doc(OPS_LEGACY, stem, t1), indent=2).encode()


def _fresh(stem: str, t1: float = 100.0) -> bytes:
    """A post-#46 payload: sorted operations, canonical separators."""
    return json.dumps(_doc(OPS_SORTED, stem, t1), sort_keys=True, separators=(",", ":")).encode()


def _live(stem: str, t1: float = 100.0) -> bytes:
    """A snapshot as a LIVE poll archived it: full `configuration`, live `target`."""
    doc = _doc(OPS_LEGACY, stem, t1)
    doc["configuration"] = {"backend_name": "ibm_fez", "n_qubits": 156, "simulator": False}
    return json.dumps(doc, indent=2).encode()


def _historical(stem: str, t1: float = 100.0) -> bytes:
    """The same document as a HISTORICAL fetch produces it.

    `fetch_snapshot(historical_at=...)` leaves `configuration` as None and
    sources `target` from `target_history`, so a backfill re-reading an
    archived stamp is never byte-equal to the live copy even when every
    measurement matches.
    """
    doc = _doc([], stem, t1)
    doc["configuration"] = None
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()


def _find_bash() -> str | None:
    """Prefer the bash that ships with Git on Windows over the WSL launcher."""
    candidates: list[Path] = []
    if sys.platform == "win32":
        git = shutil.which("git")
        if git:
            for root in Path(git).resolve().parents[1:3]:
                candidates += [root / "bin" / "bash.exe", root / "usr" / "bin" / "bash.exe"]
    found = shutil.which("bash")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            probe = subprocess.run(
                [str(candidate), "-c", "echo ok"], capture_output=True, text=True, timeout=30
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0 and probe.stdout.strip() == "ok":
            return str(candidate)
    return None


BASH = _find_bash()
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(BASH is None or GIT is None, reason="needs git and bash")


def _git(*args: str, cwd: Path) -> str:
    assert GIT is not None
    return subprocess.run(
        [GIT, *args], cwd=cwd, capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def _git_bytes(*args: str, cwd: Path) -> bytes:
    assert GIT is not None
    return subprocess.run([GIT, *args], cwd=cwd, capture_output=True, check=True).stdout


def _identity(repo: Path) -> None:
    _git("config", "user.name", "test", cwd=repo)
    _git("config", "user.email", "test@example.invalid", cwd=repo)
    # Hermetic: a contributor's global signing setup must not reach the sandbox.
    _git("config", "commit.gpgsign", "false", cwd=repo)


@pytest.fixture
def sandbox(tmp_path: Path) -> dict[str, Path]:
    """A bare origin with an archive on ``calibration-data``, and a source clone."""
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "--initial-branch=main", str(origin), cwd=tmp_path)

    seed = tmp_path / "seed"
    _git("init", "-q", "--initial-branch=calibration-data", str(seed), cwd=tmp_path)
    _identity(seed)
    archive = seed / "snapshots" / "2026-08" / "ibm_fez"
    archive.mkdir(parents=True)
    (archive / f"{STEM_A}.json").write_bytes(_legacy(STEM_A))
    (archive / f"{STEM_B}.json").write_bytes(_legacy(STEM_B))
    (seed / "README.md").write_text("# Calibration Data\n", encoding="utf-8")
    _git("add", "-A", cwd=seed)
    _git("commit", "-q", "-m", "seed archive", cwd=seed)
    _git("remote", "add", "origin", str(origin), cwd=seed)
    _git("push", "-q", "origin", "calibration-data", cwd=seed)

    src = tmp_path / "src"
    _git("init", "-q", "--initial-branch=main", str(src), cwd=tmp_path)
    _identity(src)
    (src / "scripts").mkdir()
    shutil.copy(SCRIPT, src / "scripts" / SCRIPT.name)
    shutil.copy(DIGEST, src / "scripts" / DIGEST.name)
    _git("add", "-A", cwd=src)
    _git("commit", "-q", "-m", "source tree", cwd=src)
    _git("remote", "add", "origin", str(origin), cwd=src)
    return {"origin": origin, "src": src, "tmp": tmp_path}


def _stage(tmp: Path, name: str, payloads: dict[str, bytes]) -> Path:
    staging = tmp / name
    (staging / "ibm_fez").mkdir(parents=True)
    for stem, data in payloads.items():
        (staging / "ibm_fez" / f"{stem}.json").write_bytes(data)
    return staging


def _run(
    sandbox: dict[str, Path], staging: Path, worktree: Path, poll_time: str = POLL_TIME
) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    env = dict(os.environ)
    env.update(
        {
            "STAGING_DIR": staging.as_posix(),
            "DATA_WORKTREE": worktree.as_posix(),
            "POLL_TIME": poll_time,
            "PYTHON": Path(sys.executable).as_posix(),
            "BACKEND": "ibm_fez",
        }
    )
    return subprocess.run(
        [BASH, (sandbox["src"] / "scripts" / SCRIPT.name).as_posix()],
        cwd=sandbox["src"],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )


def _ledger(origin: Path, month: str) -> dict[str, str]:
    """``{last_update_date: decision}`` from the pushed ledger."""
    text = _git("show", f"calibration-data:ledger/{month}.tsv", cwd=origin)
    header, *rows = text.strip("\n").split("\n")
    assert header.split("\t") == ["poll_time_utc", "backend", "last_update_date", "decision"]
    decisions: dict[str, str] = {}
    for row in rows:
        _, backend, stem, decision = row.split("\t")
        assert backend == "ibm_fez"
        decisions[stem] = decision
    return decisions


def _tree(origin: Path) -> set[str]:
    return set(_git("ls-tree", "-r", "--name-only", "calibration-data", cwd=origin).split())


def _subject(origin: Path) -> str:
    return _git("log", "-1", "--format=%s", "calibration-data", cwd=origin).strip()


class TestFileSnapshots:
    def test_duplicate_collision_and_new_through_a_real_branch_switch(
        self, sandbox: dict[str, Path]
    ) -> None:
        """The blocker from PR #50's review, end to end.

        With the data branch checked out in place, ``scripts/`` vanished and A
        came back ``collision-unreadable``. Through a worktree the digest is
        still there, so A is ``duplicate``, B is ``collision`` and C is ``new``.
        """
        staging = _stage(
            sandbox["tmp"],
            "staging",
            {STEM_A: _fresh(STEM_A), STEM_B: _fresh(STEM_B, t1=999.0), STEM_C: _fresh(STEM_C)},
        )
        result = _run(sandbox, staging, sandbox["tmp"] / "wt")
        assert result.returncode == 0, result.stdout + result.stderr

        origin = sandbox["origin"]
        assert _ledger(origin, "2026-09") == {
            STEM_A: "duplicate",
            STEM_B: "collision",
            STEM_C: "new",
        }
        assert _subject(origin) == f"calibration: {POLL_TIME} ibm_fez (+1)"

        tree = _tree(origin)
        assert f"snapshots/2026-06/ibm_fez/{STEM_C}.json" in tree  # payload month, not poll month
        assert not any(p.startswith("snapshots/2026-09/") for p in tree)
        collisions = sorted(p for p in tree if p.startswith("collisions/"))
        assert len(collisions) == 1
        assert collisions[0].startswith(f"collisions/2026-08/ibm_fez/{STEM_B}.")
        assert collisions[0].endswith(".json")

        # Never overwritten: both archived copies are byte-for-byte the seed's.
        for stem in (STEM_A, STEM_B):
            archived = _git_bytes(
                "show", f"calibration-data:snapshots/2026-08/ibm_fez/{stem}.json", cwd=origin
            )
            assert archived == _legacy(stem)

        # The source checkout is untouched: still on main, scripts still present.
        assert _git("branch", "--show-current", cwd=sandbox["src"]).strip() == "main"
        assert (sandbox["src"] / "scripts" / DIGEST.name).exists()
        # New and colliding payloads were moved out; the duplicate is simply
        # left behind in the (ephemeral) staging directory, as before.
        assert [p.name for p in (staging / "ibm_fez").iterdir()] == [f"{STEM_A}.json"]

    def test_a_poll_that_observes_nothing_new_is_still_recorded(
        self, sandbox: dict[str, Path]
    ) -> None:
        """ADR-025: the ledger row is the evidence a quiet poll used to discard."""
        staging = _stage(sandbox["tmp"], "staging", {STEM_A: _fresh(STEM_A)})
        result = _run(sandbox, staging, sandbox["tmp"] / "wt")
        assert result.returncode == 0, result.stdout + result.stderr

        origin = sandbox["origin"]
        assert _ledger(origin, "2026-09") == {STEM_A: "duplicate"}
        assert _subject(origin) == f"poll: {POLL_TIME} ibm_fez (no new document)"
        assert not any(p.startswith("collisions/") for p in _tree(origin))

    def test_ledger_appends_across_polls_in_the_same_month(self, sandbox: dict[str, Path]) -> None:
        first = _stage(sandbox["tmp"], "staging1", {STEM_A: _fresh(STEM_A)})
        result = _run(sandbox, first, sandbox["tmp"] / "wt1", "2026-09-01T12:00:00Z")
        assert result.returncode == 0, result.stdout + result.stderr
        # A fresh runner starts without the worktree; emulate that.
        _git(
            "worktree", "remove", "--force", (sandbox["tmp"] / "wt1").as_posix(), cwd=sandbox["src"]
        )

        second = _stage(sandbox["tmp"], "staging2", {STEM_C: _fresh(STEM_C)})
        result = _run(sandbox, second, sandbox["tmp"] / "wt2", "2026-09-01T16:00:00Z")
        assert result.returncode == 0, result.stdout + result.stderr

        origin = sandbox["origin"]
        text = _git("show", "calibration-data:ledger/2026-09.tsv", cwd=origin)
        assert text.count("poll_time_utc") == 1  # header written once
        assert _ledger(origin, "2026-09") == {STEM_A: "duplicate", STEM_C: "new"}
        assert _subject(origin) == "calibration: 2026-09-01T16:00:00Z ibm_fez (+1)"

    def test_a_backfilled_re_read_is_not_a_collision(self, sandbox: dict[str, Path]) -> None:
        """The defect the first production backfill exposed.

        A sweep re-reads stamps we already hold, and a historical fetch is
        structurally less complete than the live poll that archived them. Under
        a whole-document comparison every such re-read was filed as a
        `collision` — 7 of them on the first run, every one with a
        byte-identical `properties` block. It must be `duplicate-partial`:
        recorded in the ledger, archived copy untouched, nothing written to
        `collisions/`.
        """
        staging = _stage(sandbox["tmp"], "staging", {STEM_A: _historical(STEM_A)})
        result = _run(sandbox, staging, sandbox["tmp"] / "wt")
        assert result.returncode == 0, result.stdout + result.stderr

        origin = sandbox["origin"]
        assert _ledger(origin, "2026-09") == {STEM_A: "duplicate-partial"}
        assert not any(p.startswith("collisions/") for p in _tree(origin))
        assert _subject(origin) == f"poll: {POLL_TIME} ibm_fez (no new document)"
        # The archived copy is the more complete of the two and is kept as-is.
        archived = _git_bytes(
            "show", f"calibration-data:snapshots/2026-08/ibm_fez/{STEM_A}.json", cwd=origin
        )
        assert archived == _legacy(STEM_A)

    def test_a_changed_measurement_is_still_a_collision_across_fetch_paths(
        self, sandbox: dict[str, Path]
    ) -> None:
        """The protection must survive the fix.

        Same provenance difference as above, but a T1 that actually moved. This
        is #46 §3c's failure mode and it must still reach `collisions/`.
        """
        staging = _stage(sandbox["tmp"], "staging", {STEM_A: _historical(STEM_A, t1=999.0)})
        result = _run(sandbox, staging, sandbox["tmp"] / "wt")
        assert result.returncode == 0, result.stdout + result.stderr

        origin = sandbox["origin"]
        assert _ledger(origin, "2026-09") == {STEM_A: "collision"}
        collisions = [p for p in _tree(origin) if p.startswith("collisions/")]
        assert len(collisions) == 1
        assert "CALIBRATION PAYLOAD" in result.stdout + result.stderr

    def test_a_missing_digest_refuses_to_file_anything(self, sandbox: dict[str, Path]) -> None:
        """Without a comparator the script must stop, not guess."""
        (sandbox["src"] / "scripts" / DIGEST.name).unlink()
        staging = _stage(sandbox["tmp"], "staging", {STEM_A: _fresh(STEM_A)})
        result = _run(sandbox, staging, sandbox["tmp"] / "wt")
        assert result.returncode == 1
        assert "missing" in result.stdout + result.stderr
        assert not any(p.startswith("ledger/") for p in _tree(sandbox["origin"]))
