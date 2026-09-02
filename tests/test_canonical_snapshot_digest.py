"""Tests for the order-insensitive snapshot digest.

This is the comparison the poll workflow uses to decide `duplicate` vs
`collision`. The property that matters is asymmetric: reordering
`target.operations` must NOT change the digest (or every duplicate poll against
the pre-fix archive is misfiled as a collision, putting routine churn on the
channel ADR-025 reserves for real divergence), while any change to actual
calibration values MUST change it (or real divergence is silently dropped).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest
from scripts.canonical_snapshot_digest import canonical_digest, main


def _doc(operations: list[dict[str, Any]], t1: float = 100.0) -> dict[str, Any]:
    return {
        "backend": "ibm_fez",
        "timestamp": "2026-08-28T03:17:23+00:00",
        "schema_version": "1.0.0",
        "properties": {"qubits": [[{"name": "T1", "unit": "us", "value": t1}]]},
        "target": {"num_qubits": 2, "physical_qubits": [0, 1], "operations": operations},
        "configuration": None,
    }


def _write(tmp_path: pathlib.Path, name: str, doc: dict[str, Any], **kw: Any) -> pathlib.Path:
    p = tmp_path / name
    p.write_text(json.dumps(doc, **kw), encoding="utf-8")
    return p


OPS_A = [
    {"name": "measure_2", "qargs": [0]},
    {"name": "cz", "qargs": [0, 1]},
    {"name": "sx", "qargs": [1]},
]
OPS_SHUFFLED = [
    {"name": "cz", "qargs": [0, 1]},
    {"name": "sx", "qargs": [1]},
    {"name": "measure_2", "qargs": [0]},
]


class TestCanonicalDigest:
    def test_operations_order_does_not_change_the_digest(self, tmp_path: pathlib.Path) -> None:
        """The pre-fix archive vs a post-fix payload: same document, same digest."""
        legacy = _write(tmp_path, "legacy.json", _doc(OPS_A), indent=2)
        resorted = _write(tmp_path, "resorted.json", _doc(OPS_SHUFFLED), indent=2, sort_keys=True)

        assert legacy.read_bytes() != resorted.read_bytes()  # bytewise `cmp` would differ
        assert canonical_digest(legacy) == canonical_digest(resorted)

    def test_a_changed_calibration_value_changes_the_digest(self, tmp_path: pathlib.Path) -> None:
        """Real divergence must survive canonicalisation, or it gets dropped."""
        a = _write(tmp_path, "a.json", _doc(OPS_A, t1=100.0))
        b = _write(tmp_path, "b.json", _doc(OPS_SHUFFLED, t1=999.0))
        assert canonical_digest(a) != canonical_digest(b)

    def test_indentation_and_key_order_do_not_matter(self, tmp_path: pathlib.Path) -> None:
        a = _write(tmp_path, "a.json", _doc(OPS_A), indent=2, sort_keys=True)
        b = _write(tmp_path, "b.json", _doc(OPS_A), separators=(",", ":"))
        assert canonical_digest(a) == canonical_digest(b)

    def test_missing_target_is_still_digestible(self, tmp_path: pathlib.Path) -> None:
        doc = _doc(OPS_A)
        doc["target"] = None
        p = _write(tmp_path, "no_target.json", doc)
        assert len(canonical_digest(p)) == 64

    def test_malformed_operation_entries_do_not_raise(self, tmp_path: pathlib.Path) -> None:
        """A digest that refuses to compute is worse than one over an odd document."""
        doc = _doc([{"name": "cz"}, {"qargs": [0]}, "not-a-dict"])  # type: ignore[list-item]
        p = _write(tmp_path, "odd.json", doc)
        assert len(canonical_digest(p)) == 64


class TestCli:
    def test_compare_same_document_exits_zero(self, tmp_path: pathlib.Path) -> None:
        a = _write(tmp_path, "a.json", _doc(OPS_A), indent=2)
        b = _write(tmp_path, "b.json", _doc(OPS_SHUFFLED), sort_keys=True)
        assert main(["--compare", str(a), str(b)]) == 0

    def test_compare_different_documents_exits_one(self, tmp_path: pathlib.Path) -> None:
        a = _write(tmp_path, "a.json", _doc(OPS_A, t1=100.0))
        b = _write(tmp_path, "b.json", _doc(OPS_A, t1=999.0))
        assert main(["--compare", str(a), str(b)]) == 1

    def test_unreadable_file_exits_two_not_one(self, tmp_path: pathlib.Path) -> None:
        """`cannot tell` must be distinguishable from `they differ`.

        The workflow preserves the payload either way, but records a different
        decision, so the ledger does not claim a divergence it never observed.
        """
        a = _write(tmp_path, "a.json", _doc(OPS_A))
        assert main(["--compare", str(a), str(tmp_path / "missing.json")]) == 2

    def test_non_utf8_file_exits_two_not_one(self, tmp_path: pathlib.Path) -> None:
        """A byte sequence that is not UTF-8 must be "cannot tell", not "differs".

        `UnicodeDecodeError` is raised by the *read*, before JSON parsing, so it
        is neither `OSError` nor `JSONDecodeError`. Left uncaught it escaped as a
        traceback and the process exited 1 — which the workflow reads as
        genuinely different, recording `collision` and warning that the payload
        differs from the archived copy when it was never compared.
        """
        a = _write(tmp_path, "a.json", _doc(OPS_A))
        bad = tmp_path / "bad.json"
        bad.write_bytes(b"\xff\xfe{")
        assert main(["--compare", str(a), str(bad)]) == 2

    def test_invalid_json_exits_two(self, tmp_path: pathlib.Path) -> None:
        a = _write(tmp_path, "a.json", _doc(OPS_A))
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert main(["--compare", str(a), str(bad)]) == 2

    def test_compare_requires_exactly_two_paths(self, tmp_path: pathlib.Path) -> None:
        a = _write(tmp_path, "a.json", _doc(OPS_A))
        with pytest.raises(SystemExit):
            main(["--compare", str(a)])

    def test_prints_one_digest_per_path(
        self, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        a = _write(tmp_path, "a.json", _doc(OPS_A))
        b = _write(tmp_path, "b.json", _doc(OPS_A, t1=1.0))
        assert main([str(a), str(b)]) == 0
        lines = capsys.readouterr().out.strip().split("\n")
        assert len(lines) == 2
        assert all(len(line.split("  ")[0]) == 64 for line in lines)
