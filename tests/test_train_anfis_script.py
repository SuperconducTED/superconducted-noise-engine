"""Regression coverage for the synthetic ANFIS training CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "train_anfis.py"


@pytest.mark.parametrize("extra_args, interval_type2", [([], False), (["--it2"], True)])
def test_train_anfis_script_recovers_planted_model(
    extra_args: list[str], interval_type2: bool
) -> None:
    completed = subprocess.run(
        [sys.executable, str(_SCRIPT), "--rows", "96", "--seed", "7", *extra_args],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert report["data_source"] == "planted_tsk_synthetic"
    assert report["interval_type2"] is interval_type2
    assert report["rows"] == 96
    assert report["train_rmse"][0] < 1e-10
