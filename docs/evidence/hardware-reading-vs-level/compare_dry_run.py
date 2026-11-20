"""Compare two output folders of the #125 dry run (`scripts/hardware_reading_vs_level.py`).

    python docs/evidence/hardware-reading-vs-level/compare_dry_run.py <reference> <new>

Two tiers, as `docs/implementations/2026-10-28-hardware-test-offline-half.md` sets them out:

- MUST MATCH decides the exit code: the selection and circuit keys of `manifest.json`, and the five
  verdicts under each truth in the new folder's `criteria.json`.
- REPORTED never fails the run: whether the sampled outputs are identical, which holds on one
  machine and has not been checked across platforms. Line endings are normalised before comparing.

Exit 0 when everything in MUST MATCH holds, 1 otherwise. Reads only; writes nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

MANIFEST_KEYS = ("discriminating", "controls", "slots_dt", "layouts", "selection_log")
VERDICTS = ("1_sampling", "2_offset", "3_direction", "4_arm_b", "5_timing")
TRUTHS = ("truth1", "truth2")
REPORTED_FILES = (
    "arm-a-truth1.tsv",
    "arm-a-truth2.tsv",
    "arm-b-truth1.tsv",
    "arm-b-truth2.tsv",
    "criteria.json",
    "selection.json",
)


def _load(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _lines(path: Path) -> list[bytes]:
    return path.read_bytes().replace(b"\r\n", b"\n").split(b"\n")


def _differing_keys(reference: dict[str, Any], new: dict[str, Any]) -> list[str]:
    return sorted(k for k in set(reference) | set(new) if reference.get(k) != new.get(k))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    reference, new = Path(argv[0]), Path(argv[1])
    ref_manifest, new_manifest = _load(reference / "manifest.json"), _load(new / "manifest.json")
    criteria = _load(new / "criteria.json")
    failures = 0

    print("MUST MATCH")
    for key in MANIFEST_KEYS:
        same = ref_manifest.get(key) == new_manifest.get(key)
        failures += not same
        print(f"  manifest.{key}: {'same' if same else 'DIFFERENT'}")
    for truth in TRUTHS:
        for verdict in VERDICTS:
            passed = bool(criteria[truth][verdict]["pass"])
            failures += not passed
            print(f"  {truth}.{verdict}: {'pass' if passed else 'FAIL'}")

    print("REPORTED")
    for name in REPORTED_FILES:
        old_lines, new_lines = _lines(reference / name), _lines(new / name)
        if old_lines == new_lines:
            print(f"  {name}: identical")
        else:
            changed = sum(a != b for a, b in zip(old_lines, new_lines, strict=False))
            extra = abs(len(old_lines) - len(new_lines))
            print(f"  {name}: differs, {changed} lines changed, {extra} lines added or removed")
    print(f"  manifest keys that differ: {_differing_keys(ref_manifest, new_manifest)}")
    print(
        "  controls.json keys that differ: "
        f"{_differing_keys(_load(reference / 'controls.json'), _load(new / 'controls.json'))}"
    )

    print(f"RESULT: {'all must-match rows hold' if not failures else f'{failures} rows failed'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
