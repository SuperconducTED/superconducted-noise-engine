"""Tests for the NC-027 / NC-028 reproduction script.

The numbers themselves are reproduced against the real archive (see the
implementation doc); what is pinned here is the *sample rule*, because a
different rule silently gives a different R², and the R² arithmetic itself.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scripts import init_error_analysis as analysis


class TestSampleRule:
    def test_matches_the_recorded_selection_at_f0930b9(self) -> None:
        """225 post-cutover files → step 5 → indices 0, 5, ..., 195."""
        stems = [f"s{i:03d}" for i in range(225)]
        sample = analysis.select_sample(stems, 40)
        assert len(sample) == 40
        assert sample[0] == "s000"
        assert sample[-1] == "s195"
        assert sample == stems[::5][:40]

    def test_takes_everything_when_fewer_than_the_size(self) -> None:
        stems = [f"s{i:03d}" for i in range(10)]
        assert analysis.select_sample(stems, 40) == stems

    def test_sorts_before_stepping(self) -> None:
        """The rule is defined on stem order, whatever order git listed them in."""
        stems = [f"s{i:03d}" for i in range(80)]
        shuffled = stems[::-1]
        assert analysis.select_sample(shuffled, 40) == stems[::2][:40]

    def test_a_larger_archive_changes_the_sample(self) -> None:
        """Why the ref is pinned: one more file can move every pick."""
        base = [f"s{i:03d}" for i in range(225)]
        grown = base + [f"s{i:03d}" for i in range(225, 240)]
        assert analysis.select_sample(base, 40) != analysis.select_sample(grown, 40)


class TestOlsR2:
    def test_exact_linear_relation_scores_one(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.normal(size=(50, 3))
        y = 2.0 + x @ np.array([1.0, -3.0, 0.5])
        assert analysis.ols_r2(x, y, x, y) == pytest.approx(1.0)

    def test_a_relation_that_does_not_transport_scores_negative(self) -> None:
        """The NC-028 signature: worse than predicting the held-out mean."""
        x_train = np.linspace(0, 1, 50).reshape(-1, 1)
        y_train = 1.0 + 2.0 * x_train[:, 0]
        x_test = np.linspace(0, 1, 50).reshape(-1, 1)
        y_test = 5.0 - 2.0 * x_test[:, 0]
        assert analysis.ols_r2(x_train, y_train, x_test, y_test) < 0


def _qubit(init_error: float | None, **fields: float) -> list[dict[str, Any]]:
    entries = [{"name": name, "value": value} for name, value in fields.items()]
    if init_error is not None:
        entries.append({"name": "init_error", "value": init_error})
    return entries


def _snapshot(seed: int, *, missing_qubits: set[int]) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    qubits = []
    for q in range(4):
        fields = {name: float(rng.uniform(0.01, 0.1)) for name in analysis.PREDICTORS}
        init = None if q in missing_qubits else float(rng.uniform(0.001, 0.02))
        qubits.append(_qubit(init, **fields))
    return {"backend": "ibm_fez", "properties": {"qubits": qubits}}


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_end_to_end_reads_the_sample_from_a_git_ref(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reads through `git show` at a ref, applies the cutover, prints both claims."""
    repo = tmp_path / "archive"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "t@example.invalid"], check=True
    )
    subprocess.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True)
    folder = repo / "snapshots" / "2026-08" / "ibm_fez"
    folder.mkdir(parents=True)
    # One pre-cutover file (must be excluded) and three post-cutover files.
    # Qubit 3 never has init_error; qubit 2 sometimes does not.
    docs = {
        "20260803T231001000000Z": _snapshot(0, missing_qubits={0, 1, 2, 3}),
        "20260804T005230000000Z": _snapshot(1, missing_qubits={3}),
        "20260812T120000000000Z": _snapshot(2, missing_qubits={2, 3}),
        "20260824T080000000000Z": _snapshot(3, missing_qubits={3}),
    }
    for stem, doc in docs.items():
        (folder / f"{stem}.json").write_text(json.dumps(doc), encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "archive"], check=True)

    rc = analysis.main(["--repo", str(repo), "--ref", "HEAD"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "post-cutover snapshots available  : 3" in out
    assert "sampled snapshots                 : 3" in out
    assert "20260804T005230000000Z .. 20260824T080000000000Z" in out
    assert "snapshots where ALL 4 qubits have it : 0 of 3" in out
    assert "missing in EVERY sampled snapshot     : 1" in out
    assert "missing only SOMETIMES                : 1" in out
    assert "qubit-records with init_error and all predictors : 8" in out
    # Boundary split: snapshot 1 (3 rows) trains, snapshots 2 and 3 (2 + 3 rows) test.
    assert "cut at the snapshot boundary [NC-028] : train 20260804..20260804 (n=3)" in out
    assert "test 20260812..20260824 (n=5)" in out
    assert "cut at the row midpoint (original procedure)" in out
