"""Do the two files of each replayed day carry different calibration values?

    PYTHONPATH=<repo>/src python compare_readings.py <repo> <calibration-data commit> pairs.tsv

``archive_timing.py`` writes ``pairs.tsv``: per queue delay and day, the file a morning's scoring
would have read (``held``) and the file the whole archive names for the same instant (``tip``).
This script opens both with the predictors' own parser, ``scripts/hardware_test_predictors.py``
``_record``, so "a value differs" means the five quantities the hardware test's predictors read:
``T1``, ``T2``, ``readout_error``, ``prob_meas0_prep1`` and ``prob_meas1_prep0``.

Contract. Inputs: the repository (for ``scripts/`` and ``src/``), the pinned data commit, and the
TSV. Output: text on stdout. No side effects. A cell counts as changed when both files hold a
number and the numbers differ, or when one holds a number and the other does not.

It also checks, on every file it opens, that the time in the file's name equals the document's
``last_update_date``, which ``archive_timing.py`` assumes.
"""

from __future__ import annotations

import csv
import importlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

COHERENCE = ("T1", "T2")


def main() -> int:
    repo, sha, pairs = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3])
    sys.path.insert(0, str(repo / "scripts"))
    hp: Any = importlib.import_module("hardware_test_predictors")
    package = importlib.import_module("superconducted")
    inside = Path(str(package.__file__)).resolve().is_relative_to(repo / "src")
    print(f"superconducted imported from the repository's src: {inside}")
    blob = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD:scripts/hardware_test_predictors.py"],
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout.strip()
    print(f"scripts/hardware_test_predictors.py blob: {blob}")
    print(f"quantities: {', '.join(hp.QUANTITIES)}")

    records: dict[str, Any] = {}
    name_matches = 0

    def record(path: str) -> Any:
        nonlocal name_matches
        if path not in records:
            raw = subprocess.run(
                ["git", "-C", str(repo), "cat-file", "-p", f"{sha}:{path}"],
                capture_output=True,
                check=True,
            ).stdout
            records[path] = hp._record(path, json.loads(raw))
            name_matches += Path(path).name[:15] == records[path].time.strftime("%Y%m%dT%H%M%S")
        return records[path]

    def changed(held: Any, tip: Any) -> dict[str, tuple[int, int]]:
        """Per quantity: (cells changed, cells where both files hold a number)."""
        out: dict[str, tuple[int, int]] = {}
        for j, quantity in enumerate(hp.QUANTITIES):
            a, b = held.values[:, j], tip.values[:, j]
            both = np.isfinite(a) & np.isfinite(b)
            n = int((both & (a != b)).sum()) + int((np.isfinite(a) != np.isfinite(b)).sum())
            out[quantity] = (n, int(both.sum()))
        return out

    by_queue: dict[float, list[dict[str, str]]] = defaultdict(list)
    with pairs.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            by_queue[float(row["queue_h"])].append(row)

    for queue in sorted(by_queue):
        rows = by_queue[queue]
        same_state = coherence_days = readout_days = value_days = 0
        lines = []
        for row in rows:
            held, tip = record(row["held_path"]), record(row["tip_path"])
            if held.digest == tip.digest:
                same_state += 1
                lines.append(f"    {row['day']}: same device state (equal qubit digest)")
                continue
            cells = changed(held, tip)
            coherence = any(cells[q][0] for q in COHERENCE)
            readout = any(n for q, (n, _) in cells.items() if q not in COHERENCE)
            coherence_days += coherence
            readout_days += readout
            value_days += coherence or readout
            detail = ", ".join(f"{q} {n} of {both}" for q, (n, both) in cells.items())
            lines.append(f"    {row['day']}: {detail}")
        print(
            f"\nqueue {queue} h: a different file on {len(rows)} days; same device state on"
            f" {same_state}; one of the five quantities differs on {value_days}"
            f" (T1 or T2 on {coherence_days}, a readout quantity on {readout_days})"
        )
        print("\n".join(lines))

    print(f"\nfiles opened: {len(records)}; name time equal to last_update_date on {name_matches}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
