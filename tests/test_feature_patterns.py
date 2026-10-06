"""Tests for the feature-pattern script (Issue #110, decision A9).

The figures themselves come from the real archive and are recorded, provisionally, in
``docs/roadmap/2026-10-05-feature-patterns-and-method.md``. What is pinned here is the
machinery those figures rest on: the event rule and its placeholder mask, the duplicate
checks, the local-level algebra, the coherence-limit formula, and the blob reader that
deadlocked on its first full run.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scripts import feature_patterns as fp

_HAS_GIT = shutil.which("git") is not None


def _series_arrays(values: list[float], dates: list[float]) -> tuple[fp.FloatArray, fp.FloatArray]:
    return np.array(values, dtype=np.float64)[:, None], np.array(dates, dtype=np.float64)[:, None]


class TestEventRule:
    def test_an_event_needs_both_a_new_value_and_a_new_date(self) -> None:
        v, d = _series_arrays([0.1, 0.1, 0.2, 0.3, 0.3], [1, 2, 2, 3, 4])
        series, counts = fp.events(v, d, mask_placeholder=False)
        assert len(series) == 1
        # file 0 starts the series; only file 3 changes both value and date
        assert series[0].y.tolist() == [0.1, 0.3]
        assert series[0].file_idx.tolist() == [0, 3]
        assert counts == {
            "value_moved_date_kept": 1,
            "date_moved_value_kept": 2,
            "date_regressed": 0,
        }

    def test_placeholders_are_masked_before_events_are_counted(self) -> None:
        """A re-stamped placeholder would otherwise count as an event in every file."""
        v, d = _series_arrays([0.01, 1.0, 1.0, 1.0, 0.02], [1, 5, 6, 7, 8])
        masked, _ = fp.events(v, d, mask_placeholder=True)
        unmasked, _ = fp.events(v, d, mask_placeholder=False)
        assert masked[0].y.tolist() == [0.01, 0.02]
        assert len(unmasked[0].y) == 3

    def test_an_all_placeholder_column_yields_no_series(self) -> None:
        v, d = _series_arrays([1.0, 1.0], [1, 2])
        series, _ = fp.events(v, d, mask_placeholder=True)
        assert series == []


class TestLocalLevel:
    @pytest.mark.parametrize("q", [0.01, 0.2, 1.0, 5.0])
    def test_q_round_trips_through_the_lag1_autocorrelation(self, q: float) -> None:
        rho = -1.0 / (q + 2.0)
        assert fp.local_level_q(rho)["q"] == pytest.approx(q, abs=1e-4)

    def test_the_gain_solves_the_steady_state_riccati_equation(self) -> None:
        """alpha^2 = q (1 - alpha) is the scalar steady-state Kalman condition."""
        q = 0.2326
        alpha = fp.local_level_q(-1.0 / (q + 2.0))["alpha_opt"]
        assert alpha**2 == pytest.approx(q * (1 - alpha), abs=1e-3)

    @pytest.mark.parametrize("rho", [-0.5, -0.6, 0.0, 0.1])
    def test_outside_the_open_interval_q_is_undefined(self, rho: float) -> None:
        assert math.isnan(fp.local_level_q(rho)["q"])

    def test_simulated_local_level_recovers_its_q(self) -> None:
        rng = np.random.default_rng(7)
        q_true = 0.25
        series = []
        for e in range(200):
            level = np.cumsum(rng.normal(scale=math.sqrt(q_true), size=150))
            z = level + rng.normal(size=150)
            series.append(
                fp.Series(
                    entity=e,
                    t_ms=np.arange(150, dtype=np.float64) * 8.64e7,
                    file_idx=np.arange(150, dtype=np.int64),
                    y=10.0**z,
                )
            )
        m = fp.memory(series)
        assert m["scored_events"] > 0
        assert fp.local_level_q(m["lag1_autocorr_of_change"])["q"] == pytest.approx(
            q_true, abs=0.05
        )

    def test_noise_around_a_level_favours_the_mean_and_a_random_walk_favours_persistence(
        self,
    ) -> None:
        rng = np.random.default_rng(3)

        def build(walk: bool) -> list[fp.Series]:
            out = []
            for e in range(50):
                steps = rng.normal(size=120)
                z = np.cumsum(steps) if walk else steps
                out.append(
                    fp.Series(
                        entity=e,
                        t_ms=np.arange(120, dtype=np.float64),
                        file_idx=np.arange(120, dtype=np.int64),
                        y=10.0 ** (0.1 * z - 3.0),
                    )
                )
            return out

        noise = fp.memory(build(walk=False))
        walk = fp.memory(build(walk=True))
        assert noise["lag1_autocorr_of_change"] == pytest.approx(-0.5, abs=0.05)
        assert noise["skill_vs_persistence"]["expanding_mean"] < 0.85
        assert walk["lag1_autocorr_of_change"] == pytest.approx(0.0, abs=0.05)
        assert walk["skill_vs_persistence"]["expanding_mean"] > 1.5


class TestCoherenceLimit:
    def test_zero_length_and_infinite_coherence_give_zero_error(self) -> None:
        one = np.array([1.0])
        assert fp.coherence_limit_1q(one * 100.0, one * 80.0, one * 0.0)[0] == pytest.approx(0.0)
        assert fp.coherence_limit_1q(one * 1e12, one * 1e12, one * 24.0)[0] == pytest.approx(
            0.0, abs=1e-12
        )

    def test_short_gate_matches_the_first_order_expansion(self) -> None:
        """1 - F ~ t/(6 T1) + t/(3 T2) for t << T1, T2."""
        t1, t2, t_ns = 120.0, 90.0, 24.0
        t_us = t_ns * 1e-3
        exact = fp.coherence_limit_1q(np.array([t1]), np.array([t2]), np.array([t_ns]))[0]
        assert exact == pytest.approx(t_us / (6 * t1) + t_us / (3 * t2), rel=1e-3)

    def test_average_and_process_fidelity_agree_for_one_qubit(self) -> None:
        """F_avg = (2 F_pro + 1) / 3 for d = 2."""
        t1, t2, t = np.array([50.0]), np.array([40.0]), np.array([500.0])
        f_pro = fp.process_fidelity_1q(t1, t2, t)[0]
        assert 1.0 - (2 * f_pro + 1) / 3 == pytest.approx(fp.coherence_limit_1q(t1, t2, t)[0])


def _gate(kind: str, qubits: list[int], error: float, date: str, length: float) -> dict[str, Any]:
    return {
        "gate": kind,
        "name": f"{kind}{'_'.join(map(str, qubits))}",
        "qubits": qubits,
        "parameters": [
            {"date": date, "name": "gate_error", "unit": "", "value": error},
            {"date": date, "name": "gate_length", "unit": "ns", "value": length},
        ],
    }


def _doc(stamp: str, sx0: float, cz01: float, cz10: float) -> dict[str, Any]:
    qubit = [
        {"date": stamp, "name": "T1", "unit": "us", "value": 100.0},
        {"date": stamp, "name": "T2", "unit": "us", "value": 80.0},
        {"date": stamp, "name": "readout_error", "unit": "", "value": 0.0125},
        {"date": stamp, "name": "prob_meas0_prep1", "unit": "", "value": 0.015625},
        {"date": stamp, "name": "prob_meas1_prep0", "unit": "", "value": 0.009375},
    ]
    gates = [
        _gate("sx", [0], sx0, stamp, 24),
        _gate("x", [0], sx0, stamp, 24),
        _gate("rx", [0], sx0, stamp, 24),
        _gate("sx", [1], 3e-4, stamp, 24),
        _gate("cz", [0, 1], cz01, stamp, 68),
        _gate("cz", [1, 0], cz10, stamp, 68),
    ]
    return {
        "backend": "ibm_fez",
        "properties": {
            "last_update_date": stamp,
            "qubits": [qubit, qubit],
            "gates": gates,
            "general": [],
        },
    }


def _init_fake_archive(root: Path, docs: list[dict[str, Any]]) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }

    def run(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, env=env
        )

    root.mkdir(parents=True, exist_ok=True)
    run("init", "-q")
    for doc in docs:
        stamp = doc["properties"]["last_update_date"]
        stem = stamp[:19].replace("-", "").replace(":", "") + "000000Z"
        path = root / "snapshots" / "2026-09" / "ibm_fez" / f"{stem}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc), encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "fixture")
    return run("rev-parse", "HEAD").stdout.decode().strip()


@pytest.mark.skipif(not _HAS_GIT, reason="git is not available")
class TestExtract:
    def test_aliases_and_directions_are_checked_then_collapsed(self, tmp_path: Path) -> None:
        docs = [
            _doc("2026-09-01T01:00:00+00:00", 2e-4, 3e-3, 3e-3),
            _doc("2026-09-02T01:00:00+00:00", 2.5e-4, 1.0, 1.0),
            _doc("2026-09-03T01:00:00+00:00", 2.5e-4, 4e-3, 5e-3),
        ]
        ref = _init_fake_archive(tmp_path / "repo", docs)
        cache = fp.extract(tmp_path / "repo", ref, "ibm_fez")

        assert cache.edges == [(0, 1)]
        assert cache.values["sx"][:, 0].tolist() == [2e-4, 2.5e-4, 2.5e-4]
        assert cache.checks["alias_compared"] == 6
        assert cache.checks["alias_value_mismatch"] == 0
        assert cache.checks["edge_direction_compared"] == 3
        # the third file disagrees across directions, and that is counted, not hidden
        assert cache.checks["edge_direction_value_mismatch"] == 1
        series, _ = fp.events(cache.values["cz"], cache.dates["cz"], mask_placeholder=True)
        assert len(series) == 1
        assert series[0].file_idx.tolist() == [0, 2]

    def test_the_cache_round_trips(self, tmp_path: Path) -> None:
        ref = _init_fake_archive(
            tmp_path / "repo", [_doc("2026-09-01T01:00:00+00:00", 2e-4, 3e-3, 3e-3)]
        )
        cache = fp.extract(tmp_path / "repo", ref, "ibm_fez")
        fp.save_cache(cache, tmp_path / "c.npz", ref)
        loaded, loaded_ref = fp.load_cache(tmp_path / "c.npz")
        assert loaded_ref == ref
        assert loaded.stems == cache.stems
        assert loaded.edges == cache.edges
        np.testing.assert_array_equal(loaded.values["sx"], cache.values["sx"])
        np.testing.assert_array_equal(loaded.dates["cz"], cache.dates["cz"])


@pytest.mark.skipif(not _HAS_GIT, reason="git is not available")
def test_the_blob_reader_does_not_deadlock_on_a_large_request_list(tmp_path: Path) -> None:
    """The first full run hung: all requests were written before any answer was read.

    2,000 requests are about 82 kB of input and 4 MB of output, more than either pipe
    buffer holds, which is the condition that deadlocked the write-everything-first reader.
    """
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    blob = root / "b.bin"
    blob.write_bytes(bytes(range(256)) * 8)
    sha = (
        subprocess.run(
            ["git", "-C", str(root), "hash-object", "-w", str(blob)],
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .strip()
    )
    sizes: list[int] = []

    def read() -> None:
        sizes.extend(len(b) for b in fp.iter_blobs(root, [sha] * 2000))

    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    worker.join(timeout=120)
    assert not worker.is_alive(), "iter_blobs deadlocked"
    assert sizes == [2048] * 2000
