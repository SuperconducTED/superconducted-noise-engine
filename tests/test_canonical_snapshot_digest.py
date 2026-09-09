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
from scripts.canonical_snapshot_digest import canonical_digest, is_lossy_reread, main, qubit_digest


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

    def test_qubit_scope_ignores_gate_data_but_not_t1(self, tmp_path: pathlib.Path) -> None:
        first = _doc(OPS_A, t1=100.0)
        second = _doc(OPS_SHUFFLED, t1=100.0)
        second["properties"]["gates"] = [{"gate": "x", "value": 99}]
        changed = _doc(OPS_A, t1=101.0)
        a, b, c = (
            _write(tmp_path, name, doc)
            for name, doc in (("a.json", first), ("b.json", second), ("c.json", changed))
        )
        assert canonical_digest(a, scope="qubits") == canonical_digest(b, scope="qubits")
        assert canonical_digest(a, scope="qubits") != canonical_digest(c, scope="qubits")
        assert qubit_digest(first) == canonical_digest(a, scope="qubits")

    def test_qubit_scope_rejects_missing_or_malformed_qubits(self, tmp_path: pathlib.Path) -> None:
        missing = _doc(OPS_A)
        missing["properties"] = {}
        malformed = _doc(OPS_A)
        malformed["properties"] = None
        for name, document in (("missing.json", missing), ("malformed.json", malformed)):
            with pytest.raises(ValueError, match=r"properties\.qubits"):
                canonical_digest(_write(tmp_path, name, document), scope="qubits")


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

    def test_qubit_scope_compares_qubit_blocks(self, tmp_path: pathlib.Path) -> None:
        a = _write(tmp_path, "a.json", _doc(OPS_A))
        b = _write(tmp_path, "b.json", _doc(OPS_SHUFFLED))
        assert main(["--compare", "--scope", "qubits", str(a), str(b)]) == 0


def _historical(operations: list[dict[str, Any]], t1: float = 100.0) -> dict[str, Any]:
    """A snapshot as a HISTORICAL fetch produces it.

    `fetch_snapshot(historical_at=...)` leaves `configuration` as None and
    sources `target` from `target_history` rather than the live backend, so the
    same document fetched historically is not byte-equal to the archived live
    copy even when every measurement matches.
    """
    doc = _doc(operations, t1)
    doc["configuration"] = None
    doc["target"] = {"num_qubits": 2, "physical_qubits": [0, 1], "operations": []}
    return doc


# The pair that reproduced the parameter-date defect: backfill run 34058863047
# re-read `ibm_fez` 20260813T220506000000Z, a stamp `calibration-data` already
# held. Same `last_update_date`, same 156/1952/449 shape, `qubits` and
# `general` exactly equal -- and 26 gate entries differing in nothing but a
# per-parameter `date` about 11 minutes apart. Those 26 were exactly the 26
# entries carrying the `gate_error = 1` placeholder that means "not
# calibrated"; no measured entry differed.
HIST_DATE = "2026-08-13T22:14:31+00:00"  # what the history endpoint stamped
LIVE_DATE = "2026-08-13T22:25:32+00:00"  # what the archived live poll stamped


def _dated_properties(
    date: str,
    *,
    t1: float = 100.0,
    t1_unit: str = "us",
    gate_length: float = 24,
    last_update_date: str = "2026-08-13T22:05:06+00:00",
) -> dict[str, Any]:
    """A `properties` block with a parameter record in all three real places.

    `qubits[][]`, `gates[].parameters[]` and `general[]` each hold records of
    shape `{date, name, unit, value}` -- verified to be every place a `date`
    appears inside `properties`. `last_update_date` sits beside them on a dict
    with no `value`, which is what keeps it out of the normalisation.
    """
    return {
        "backend_name": "ibm_fez",
        "last_update_date": last_update_date,
        "qubits": [[{"date": date, "name": "T1", "unit": t1_unit, "value": t1}]],
        "gates": [
            {
                "gate": "id",
                "name": "id72",
                "qubits": [72],
                "parameters": [
                    {"date": date, "name": "gate_error", "unit": "", "value": 1},
                    {"date": date, "name": "gate_length", "unit": "ns", "value": gate_length},
                ],
            }
        ],
        "general": [{"date": date, "name": "jq_7273", "unit": "GHz", "value": 0}],
    }


def _live_dated(date: str, **kw: Any) -> dict[str, Any]:
    """The archived side: a LIVE poll, so it carries a `configuration`."""
    doc = _doc(OPS_A)
    doc["properties"] = _dated_properties(date, **kw)
    doc["configuration"] = {"n_qubits": 156}
    return doc


def _historical_dated(date: str, **kw: Any) -> dict[str, Any]:
    """The incoming side: a HISTORICAL re-read, so `configuration` is None."""
    doc = _historical(OPS_SHUFFLED)
    doc["properties"] = _dated_properties(date, **kw)
    return doc


class TestPayloadOnlyDigest:
    """The comparison a backfill needs.

    A sweep re-reads stamps the archive already holds — a query inside a gap is
    answered with the document at the gap's opening. Compared in full, a
    historical re-read of an archived stamp ALWAYS differs, and the first
    backfill run duly filed 7 such pairs into `collisions/` with byte-identical
    `properties` blocks. Comparing the calibration payload is what tells
    "different fetch path" from "different measurements".
    """

    def test_configuration_and_target_do_not_affect_the_payload_digest(
        self, tmp_path: pathlib.Path
    ) -> None:
        live = _write(tmp_path, "live.json", _doc(OPS_A))
        hist = _write(tmp_path, "hist.json", _historical(OPS_SHUFFLED))
        assert canonical_digest(live) != canonical_digest(hist)  # full: differs
        assert canonical_digest(live, payload_only=True) == canonical_digest(
            hist, payload_only=True
        )

    def test_a_changed_calibration_value_still_differs(self, tmp_path: pathlib.Path) -> None:
        """The protection ADR-025 reserves collisions/ for must survive.

        #46 §3c lost five gate-level versions under one stamp, and gate data
        lives inside `properties` — so payload-only must still catch it.
        """
        live = _write(tmp_path, "live.json", _doc(OPS_A, t1=100.0))
        hist = _write(tmp_path, "hist.json", _historical(OPS_A, t1=999.0))
        assert canonical_digest(live, payload_only=True) != canonical_digest(
            hist, payload_only=True
        )

    def test_missing_properties_is_still_digestible(self, tmp_path: pathlib.Path) -> None:
        doc = _doc(OPS_A)
        del doc["properties"]
        p = _write(tmp_path, "no_props.json", doc)
        assert len(canonical_digest(p, payload_only=True)) == 64

    def test_two_documents_without_properties_are_equal(self, tmp_path: pathlib.Path) -> None:
        """Degenerate, but it must not raise — refusing to compare is worse."""
        a_doc, b_doc = _doc(OPS_A), _doc(OPS_SHUFFLED, t1=1.0)
        del a_doc["properties"], b_doc["properties"]
        a = _write(tmp_path, "a.json", a_doc)
        b = _write(tmp_path, "b.json", b_doc)
        assert canonical_digest(a, payload_only=True) == canonical_digest(b, payload_only=True)

    def test_a_parameter_date_difference_is_not_a_divergence(self, tmp_path: pathlib.Path) -> None:
        """The reproduction, at the digest level.

        The history endpoint re-stamps the entries it synthesises, so a
        backfilled re-read of an archived document differs in those stamps
        while every measurement matches. Hashing them made run 34058863047
        write a `collisions/` file for a document already held -- violating
        issue #53's "collisions/ still empty" criterion by getting the
        comparison wrong, not because IBM republished.
        """
        live = _write(tmp_path, "live.json", _live_dated(LIVE_DATE))
        hist = _write(tmp_path, "hist.json", _historical_dated(HIST_DATE))
        assert canonical_digest(live, payload_only=True) == canonical_digest(
            hist, payload_only=True
        )

    def test_a_value_change_still_differs_when_the_date_moved_too(
        self, tmp_path: pathlib.Path
    ) -> None:
        """The direction that matters most.

        A real republication arrives with new dates AND new numbers. Dropping
        `date` must not drag the value change through with it, or #46 s3c's
        five lost gate-level versions become losable again.
        """
        live = _write(tmp_path, "live.json", _live_dated(LIVE_DATE, t1=100.0))
        hist = _write(tmp_path, "hist.json", _historical_dated(HIST_DATE, t1=100.5))
        assert canonical_digest(live, payload_only=True) != canonical_digest(
            hist, payload_only=True
        )

    def test_a_unit_change_still_differs(self, tmp_path: pathlib.Path) -> None:
        """Why `date` is dropped rather than everything but `value`.

        The rejected alternative -- compare values only -- would call a T1 of
        100 in `us` equal to a T1 of 100 in `ns`. `name` and `unit` are
        measurement; only `date` is decided by which endpoint answered.
        """
        live = _write(tmp_path, "live.json", _live_dated(LIVE_DATE, t1_unit="us"))
        hist = _write(tmp_path, "hist.json", _historical_dated(HIST_DATE, t1_unit="ns"))
        assert canonical_digest(live, payload_only=True) != canonical_digest(
            hist, payload_only=True
        )

    def test_last_update_date_still_changes_the_payload_digest(
        self, tmp_path: pathlib.Path
    ) -> None:
        """The normalisation is scoped to parameter records, not to `date`-ness.

        `last_update_date` is the document's own identity -- the value the
        archive filename is derived from -- and must keep participating.
        """
        live = _write(tmp_path, "live.json", _live_dated(LIVE_DATE))
        hist = _write(
            tmp_path,
            "hist.json",
            _historical_dated(HIST_DATE, last_update_date="2026-08-13T22:06:06+00:00"),
        )
        assert canonical_digest(live, payload_only=True) != canonical_digest(
            hist, payload_only=True
        )

    def test_the_full_digest_still_sees_parameter_dates(self, tmp_path: pathlib.Path) -> None:
        """Live-vs-live stays strict.

        `--compare` decides `duplicate` vs `collision` for two live polls,
        where the safe answer is `collision` and any difference belongs in
        front of a human. Only the cross-fetch-path comparison normalises.
        """
        a = _write(tmp_path, "a.json", _live_dated(LIVE_DATE))
        b = _write(tmp_path, "b.json", _live_dated(HIST_DATE))
        assert canonical_digest(a) != canonical_digest(b)

    def test_digesting_leaves_the_document_intact(self, tmp_path: pathlib.Path) -> None:
        """The dates are real data: the caller still writes them out.

        `file_snapshots.sh` preserves the payload it just compared, so the
        normalisation has to build new containers rather than mutate.
        """
        p = _write(tmp_path, "live.json", _live_dated(LIVE_DATE))
        canonical_digest(p, payload_only=True)
        reread = json.loads(p.read_text(encoding="utf-8"))
        assert reread["properties"]["general"][0]["date"] == LIVE_DATE
        assert reread["properties"]["gates"][0]["parameters"][0]["date"] == LIVE_DATE


class TestPayloadOnlyCli:
    def test_compare_payload_only_exits_zero_across_fetch_paths(
        self, tmp_path: pathlib.Path
    ) -> None:
        live = _write(tmp_path, "live.json", _doc(OPS_A))
        hist = _write(tmp_path, "hist.json", _historical(OPS_SHUFFLED))
        assert main(["--compare", str(live), str(hist)]) == 1  # full comparison
        assert main(["--compare", "--payload-only", str(live), str(hist)]) == 0

    def test_compare_payload_only_exits_one_on_changed_measurements(
        self, tmp_path: pathlib.Path
    ) -> None:
        live = _write(tmp_path, "live.json", _doc(OPS_A, t1=100.0))
        hist = _write(tmp_path, "hist.json", _historical(OPS_A, t1=999.0))
        assert main(["--compare", "--payload-only", str(live), str(hist)]) == 1

    def test_unreadable_still_exits_two_under_payload_only(self, tmp_path: pathlib.Path) -> None:
        a = _write(tmp_path, "a.json", _doc(OPS_A))
        assert main(["--compare", "--payload-only", str(a), str(tmp_path / "missing.json")]) == 2

    def test_payload_only_and_compare_reread_agree_on_a_date_only_pair(
        self, tmp_path: pathlib.Path
    ) -> None:
        """The two modes answer the same question and must not diverge.

        They were two copies of one `json.dumps` line, which is how the
        per-parameter `date` came to be normalised in neither.
        """
        live = _write(tmp_path, "live.json", _live_dated(LIVE_DATE))
        hist = _write(tmp_path, "hist.json", _historical_dated(HIST_DATE))
        assert main(["--compare", str(hist), str(live)]) == 1  # full: still differs
        assert main(["--compare", "--payload-only", str(hist), str(live)]) == 0
        assert main(["--compare-reread", str(hist), str(live)]) == 0


class TestIsLossyReread:
    """The directional guard that keeps `--payload-only` from being a blanket rule.

    PR #55's review showed the first attempt reduced to comparing the payload
    alone: full equality implies payload equality, so `F or (not F and P)` is
    just `P`. The narrow comparison therefore has to be gated on evidence that
    the incoming payload really is a lossy historical re-read, not merely that
    its payload happens to match.
    """

    def test_historical_over_live_is_a_reread(self) -> None:
        assert is_lossy_reread({"configuration": None}, {"configuration": {"n_qubits": 156}})

    def test_live_over_live_is_not(self) -> None:
        assert not is_lossy_reread({"configuration": {"a": 1}}, {"configuration": {"a": 1}})

    def test_live_over_historical_is_not(self) -> None:
        """Directional: a MORE complete payload is never explained away."""
        assert not is_lossy_reread({"configuration": {"a": 1}}, {"configuration": None})

    def test_historical_over_historical_is_not(self) -> None:
        assert not is_lossy_reread({"configuration": None}, {"configuration": None})


class TestCompareRereadCli:
    def test_lossy_reread_with_matching_payload_exits_zero(self, tmp_path: pathlib.Path) -> None:
        archived = _doc(OPS_A)
        archived["configuration"] = {"n_qubits": 156}
        a = _write(tmp_path, "archived.json", archived)
        b = _write(tmp_path, "hist.json", _historical(OPS_SHUFFLED))
        assert main(["--compare-reread", str(b), str(a)]) == 0

    def test_two_live_payloads_exit_one_even_when_the_payload_matches(
        self, tmp_path: pathlib.Path
    ) -> None:
        """The P1 regression, at the CLI boundary."""
        archived = _doc(OPS_A)
        archived["configuration"] = {"n_qubits": 156}
        incoming = _doc([op for op in OPS_A if op["name"] != "cz"])
        incoming["configuration"] = {"n_qubits": 156}
        a = _write(tmp_path, "archived.json", archived)
        b = _write(tmp_path, "incoming.json", incoming)
        assert main(["--compare-reread", str(b), str(a)]) == 1

    def test_lossy_reread_with_changed_measurements_exits_one(self, tmp_path: pathlib.Path) -> None:
        archived = _doc(OPS_A, t1=100.0)
        archived["configuration"] = {"n_qubits": 156}
        a = _write(tmp_path, "archived.json", archived)
        b = _write(tmp_path, "hist.json", _historical(OPS_A, t1=999.0))
        assert main(["--compare-reread", str(b), str(a)]) == 1

    def test_a_date_only_reread_exits_zero(self, tmp_path: pathlib.Path) -> None:
        """Run 34058863047's collision, at the boundary the workflow calls.

        Exit 0 is what `file_snapshots.sh` reads as `duplicate-partial`, so
        this pair no longer writes a file into `collisions/`.
        """
        live = _write(tmp_path, "live.json", _live_dated(LIVE_DATE))
        hist = _write(tmp_path, "hist.json", _historical_dated(HIST_DATE))
        assert main(["--compare-reread", str(hist), str(live)]) == 0

    def test_two_live_payloads_differing_only_in_date_still_exit_one(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Normalising `date` must not become a blanket rule.

        The P1 gate is what keeps the narrow comparison narrow: two live polls
        both carry a `configuration`, never reach it, and their difference
        stays a collision however small it is.
        """
        a = _write(tmp_path, "a.json", _live_dated(LIVE_DATE))
        b = _write(tmp_path, "b.json", _live_dated(HIST_DATE))
        assert main(["--compare-reread", str(b), str(a)]) == 1

    def test_a_reread_whose_values_moved_with_the_date_exits_one(
        self, tmp_path: pathlib.Path
    ) -> None:
        """A genuine value difference is still a collision, dates notwithstanding."""
        live = _write(tmp_path, "live.json", _live_dated(LIVE_DATE, gate_length=24))
        hist = _write(tmp_path, "hist.json", _historical_dated(HIST_DATE, gate_length=25))
        assert main(["--compare-reread", str(hist), str(live)]) == 1

    def test_unreadable_exits_two(self, tmp_path: pathlib.Path) -> None:
        a = _write(tmp_path, "a.json", _doc(OPS_A))
        assert main(["--compare-reread", str(a), str(tmp_path / "missing.json")]) == 2

    def test_compare_and_compare_reread_are_mutually_exclusive(
        self, tmp_path: pathlib.Path
    ) -> None:
        a = _write(tmp_path, "a.json", _doc(OPS_A))
        b = _write(tmp_path, "b.json", _doc(OPS_A))
        with pytest.raises(SystemExit):
            main(["--compare", "--compare-reread", str(a), str(b)])
