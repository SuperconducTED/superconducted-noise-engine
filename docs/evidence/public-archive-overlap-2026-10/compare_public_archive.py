"""Cross-check the public ``qiskit-calibration-drift`` parquet against this project's archive.

Two measurements, both for ``ibm_fez`` only, both read-only:

1. **Overlap.** Every calibration event this project archived (a ``(property, qubits,
   calibrated_time)`` triple with its value) is looked up in the public table. Equal, equal
   only after a unit rescale, different, or absent, per property.
2. **Distinct device states.** The public table is replayed *as of* ``calibrated_time`` (the
   latest event per key with ``calibrated_time <= t``), and the resulting qubit block is
   digested the way ``scripts/canonical_snapshot_digest.qubit_digest`` digests ours, after
   checking that this projection partitions our own files exactly as the official digest
   does. States are counted at hourly and half-hourly marks before our first snapshot (what
   adoption would add) and inside our window (what a 30-minute poll would have caught).

**Completeness rule (added 2026-10-26 on review).** A replayed state is counted only when
every non-excluded qubit holds a value for each of the five ``COMPLETE`` properties (T1, T2,
``readout_error``, ``prob_meas0_prep1``, ``prob_meas1_prep0``), the fields the training set
reads. The table's first ``readout_error`` event for ``ibm_fez`` is at 2026-01-31T13:19:17Z,
so the marks before it hold T1 and T2 only: a startup artefact of the replay, not a state IBM
ever published. ``readout_length`` and ``init_error`` are not required: the builder does not
read them and ``init_error`` has no event before 2026-08-01 in the table or in our documents.
Incomplete marks are excluded from the counts and reported per mark grid. This is an
initialisation check, not the training-admissibility check (ADR-029's plausibility guard).

Three public-table defects are handled by rule and reported, never silently:

- T1 and T2 rows observed live before 2026-05-07 hold seconds under the label ``us``; a value
  below ``SECONDS_MISLABEL_MAX`` is multiplied by 1e6 (no physical T1 or T2 is below 0.01 us).
- IBM omits qubit 72's T1 and T2 from live documents; an event table cannot express omission,
  so the replay would carry a stale value forever. Those two keys are dropped on both sides.
- The public table keeps the first value seen per ``(key, calibrated_time)``; IBM sometimes
  republishes a different value under the same stamp (``readout_length`` 1560 vs 1700 ns).
  The replay is **not** modified for this: it carries the public table's value, and the
  validation against our documents classifies every differing key by comparing the two
  sides' ``calibrated_time`` stamps (same-stamp conflict, public table lacks our event, we
  lack theirs, key held on one side only) and names the documents with a same-stamp conflict.

Run with an isolated interpreter and the exact out-of-pins readers named in the README::

    python -X utf8 -I compare_public_archive.py --parquet <file> --ours <dir> --repo <root>
        --pylib <dir> --out <dir>

``<dir>`` for ``--ours`` holds ``snapshots/`` and ``health/`` as exported from a pinned
``calibration-data`` ref. Keep ``<dir>`` short: Windows refuses paths over 260 characters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND = "ibm_fez"
ALL7 = (
    "T1",
    "T2",
    "readout_error",
    "prob_meas0_prep1",
    "prob_meas1_prep0",
    "readout_length",
    "init_error",
)
CORE5 = ("T1", "T2", "readout_error", "prob_meas0_prep1", "prob_meas1_prep0")
COMPLETE = CORE5
EXCLUDE = frozenset({(72, "T1"), (72, "T2")})
SECONDS_MISLABEL_MAX = 0.01
PUBLIC_START = "2026-01-31T00:00:00+00:00"
HALF_HOUR = 1800
HOUR = 3600

Key = tuple[int, str]
Event = tuple[int, str, int, float]  # (calibrated_time epoch, property, qubit, value)


def _epoch(stamp: str) -> int:
    return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UTC).timestamp())


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).isoformat()


def _digest(entries: dict[Key, float]) -> str:
    body = json.dumps(sorted((q, n, v) for (q, n), v in entries.items()), separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def _project(entries: dict[Key, float], names: tuple[str, ...]) -> dict[Key, float]:
    return {k: v for k, v in entries.items() if k[1] in names}


class Replay:
    """Their qubit-scope events replayed as of ``calibrated_time``, in mark order."""

    def __init__(self, events: list[Event]) -> None:
        self._events = events  # sorted by calibrated_time
        self._i = 0
        self.state: dict[Key, float] = {}
        self.stamp: dict[Key, int] = {}

    def advance(self, mark: int) -> dict[Key, float]:
        while self._i < len(self._events) and self._events[self._i][0] <= mark:
            cal, prop, qubit, value = self._events[self._i]
            self.state[(qubit, prop)] = value
            self.stamp[(qubit, prop)] = cal
            self._i += 1
        return self.state


def _digests_at(
    events: list[Event], marks: list[int], names: tuple[str, ...], required: frozenset[Key]
) -> list[str | None]:
    """Digest per mark, or ``None`` where the replayed state is incomplete."""
    replay = Replay([e for e in events if e[1] in names])
    out: list[str | None] = []
    for m in marks:
        state = replay.advance(m)
        out.append(_digest(state) if required <= state.keys() else None)
    return out


def _grid(marks: list[int], digests: list[str | None]) -> tuple[set[str], dict[str, Any]]:
    kept = {d for d in digests if d is not None}
    first = next((m for m, d in zip(marks, digests, strict=True) if d is not None), None)
    info = {
        "marks": len(marks),
        "marks_incomplete_excluded": sum(1 for d in digests if d is None),
        "first_complete_mark": _iso(first) if first is not None else None,
    }
    return kept, info


def _classify(ours_stamp: int, theirs_stamp: int) -> str:
    if ours_stamp == theirs_stamp:
        return "same_stamp_conflict"
    if ours_stamp > theirs_stamp:
        return "public_lacks_event"
    return "ours_lacks_event"


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--parquet", required=True, type=Path)
    ap.add_argument("--ours", required=True, type=Path)
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--pylib", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    sys.path.insert(0, str(args.pylib))
    sys.path.insert(0, str(args.repo))
    import duckdb
    import pyarrow as pa
    from scripts.canonical_snapshot_digest import qubit_digest

    args.out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "backend": BACKEND,
        "exclusion": sorted(EXCLUDE),
        "seconds_mislabel_max": SECONDS_MISLABEL_MAX,
    }

    # ------------------------------------------------------------------ our archive
    files = sorted(f for f in (args.ours / "snapshots").rglob("*.json") if f.parent.name == BACKEND)
    docs: list[tuple[int, str, dict[Key, float], dict[Key, int], str]] = []
    our_events: set[tuple[str, int, int, int, float, str]] = set()
    n_qubits = 0
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        props = doc["properties"]
        entries: dict[Key, float] = {}
        dates: dict[Key, int] = {}
        n_qubits = max(n_qubits, len(props["qubits"]))
        for qi, params in enumerate(props["qubits"]):
            for p in params:
                cal = _epoch(p["date"])
                our_events.add((p["name"], qi, -1, cal, float(p["value"]), p.get("unit", "")))
                if (qi, p["name"]) not in EXCLUDE:
                    entries[(qi, p["name"])] = float(p["value"])
                    dates[(qi, p["name"])] = cal
        for g in props["gates"]:
            qs = g["qubits"]
            qa, qb = qs[0], (qs[1] if len(qs) > 1 else -1)
            for p in g["parameters"]:
                name = f"{g['gate']}_{p['name']}"
                our_events.add(
                    (name, qa, qb, _epoch(p["date"]), float(p["value"]), p.get("unit", ""))
                )
        docs.append((_epoch(props["last_update_date"]), f.name, entries, dates, qubit_digest(doc)))
    docs.sort()
    first_l, last_l = docs[0][0], docs[-1][0]
    required = frozenset((q, p) for q in range(n_qubits) for p in COMPLETE if (q, p) not in EXCLUDE)
    report["completeness"] = {
        "required_properties": list(COMPLETE),
        "qubits": n_qubits,
        "required_keys": len(required),
    }

    official = {d for _, _, _, _, d in docs}
    index_rows = (
        (args.ours / "health" / "state-index.tsv").read_text(encoding="utf-8").splitlines()[1:]
    )
    index = {r.split("\t")[2] for r in index_rows}
    # the projection must partition our files exactly as the official digest does; qubit 72's
    # excluded keys can only merge files, so the pair count is the check
    pairs = Counter((d, _digest(e)) for _, _, e, _, d in docs)
    report["ours"] = {
        "files": len(files),
        "window": [_iso(first_l), _iso(last_l)],
        "distinct_official_qubit_digest": len(official),
        "distinct_in_state_index_tsv": len(index),
        "recomputed_equals_index": official == index,
        "distinct_projected_all7_with_exclusion": len({p for _, p in pairs}),
        "official_to_projected_pairs": len(pairs),
        "unique_events_all_scopes": len(our_events),
    }

    # ------------------------------------------------------------------ their table
    con = duckdb.connect()
    con.execute("set TimeZone='UTC'")
    cols = list(zip(*sorted(our_events), strict=True))
    con.register(
        "ours",
        pa.table(
            {
                "property": pa.array(cols[0]),
                "qa": pa.array(cols[1], pa.int64()),
                "qb": pa.array(cols[2], pa.int64()),
                "epoch": pa.array(cols[3], pa.int64()),
                "value": pa.array(cols[4], pa.float64()),
                "unit": pa.array(cols[5]),
            }
        ),
    )
    con.execute(
        f"""
        create table theirs as
        select property, qubit_a as qa, coalesce(cast(qubit_b as bigint), -1) as qb,
               cast(epoch(calibrated_time) as bigint) as epoch, value, unit, scope,
               cast(epoch(observed_time) as bigint) as obs
        from '{args.parquet.as_posix()}' where backend = '{BACKEND}'
        """
    )
    per_prop = con.execute(
        """
        with t as (select distinct property, qa, qb, epoch, value, unit from theirs),
        j as (select o.property, o.value ov, t.value tv, o.unit ou, t.unit tu
              from ours o left join t using (property, qa, qb, epoch))
        select property, count(*) ours_total,
               sum(case when tv is null then 1 else 0 end) ours_only,
               sum(case when tv = ov then 1 else 0 end) equal,
               sum(case when tv is not null and tv <> ov
                        and abs(tv * 1e6 - ov) <= 1e-9 * abs(ov) then 1 else 0 end) equal_after_1e6,
               sum(case when tv is not null and tv <> ov
                        and not abs(tv * 1e6 - ov) <= 1e-9 * abs(ov) then 1 else 0 end) differ,
               sum(case when tv is not null and tu <> ou then 1 else 0 end) unit_label_differs
        from j group by 1 order by 1
        """
    ).fetchall()
    head = (
        "property",
        "ours_total",
        "ours_only",
        "equal",
        "equal_after_1e6",
        "differ",
        "unit_label_differs",
    )
    report["overlap_by_property"] = [dict(zip(head, r, strict=True)) for r in per_prop]
    report["overlap_totals"] = {
        k: sum(int(r[k]) for r in report["overlap_by_property"]) for k in head[1:]
    }
    report["theirs_only_in_window_training_fields"] = con.execute(
        f"""
        with t as (select distinct property, qa, qb, epoch from theirs
                   where property in ('T1', 'T2', 'readout_error',
                                      'sx_gate_error', 'sx_gate_length')
                     and epoch between {first_l} and {last_l})
        select property, count(*) from t left join ours o using (property, qa, qb, epoch)
        where o.property is null group by 1 order by 1
        """
    ).fetchall()
    coh = "property in ('T1', 'T2')"
    below = f"value < {SECONDS_MISLABEL_MAX}"
    report["unit_defect"] = {
        "t1_t2_rows_below_threshold": con.execute(
            f"select property, count(*) from theirs where {coh} and {below} group by 1 order by 1"
        ).fetchall(),
        "t1_t2_rows_in_ambiguous_zone_0_01_to_1": con.execute(
            f"select count(*) from theirs where {coh} and not {below} and value < 1"
        ).fetchone()[0],
        "t1_t2_keys_with_two_values": con.execute(
            f"""select count(*) from (select property, qa, epoch from theirs where {coh}
                group by 1, 2, 3 having count(distinct value) > 1)"""
        ).fetchone()[0],
        "last_seconds_row_observed": _iso(
            con.execute(
                f"select max(obs) from theirs where property = 'T1' and {below}"
            ).fetchone()[0]
        ),
    }

    # ------------------------------------------------------------------ replay
    rows = con.execute(
        f"""
        select cast(epoch(calibrated_time) as bigint) cal, property, qubit_a,
               case when {coh} and {below} then value * 1e6 else value end
        from '{args.parquet.as_posix()}'
        where backend = '{BACKEND}' and scope = 'qubit' order by 1, epoch(observed_time)
        """
    ).fetchall()
    events: list[Event] = [
        (int(c), p, int(q), float(v)) for c, p, q, v in rows if (int(q), p) not in EXCLUDE
    ]
    report["their_qubit_scope_events_after_exclusion"] = len(events)
    report["their_first_event_per_required_property"] = {
        p: _iso(min(c for c, pp, _, _ in events if pp == p)) for p in COMPLETE
    }

    pre_hour = list(range(_epoch(PUBLIC_START), first_l, HOUR))
    pre_half = list(range(_epoch(PUBLIC_START), first_l, HALF_HOUR))
    win_half = list(range(first_l, last_l + 1, HALF_HOUR))
    for label, names in (("all7", ALL7), ("core5", CORE5)):
        ours_set = {_digest(_project(e, names)) for _, _, e, _, _ in docs}
        at_l = _digests_at(events, [lud for lud, _, _, _, _ in docs], names, required)
        equal = sum(
            1
            for (_, _, e, _, _), t in zip(docs, at_l, strict=True)
            if _digest(_project(e, names)) == t
        )
        causes: Counter[str] = Counter()
        doc_kinds: Counter[str] = Counter()
        conflict_docs: list[str] = []
        replay = Replay([e for e in events if e[1] in names])
        for (lud, name, e, dates, _), t in zip(docs, at_l, strict=True):
            state = replay.advance(lud)
            o = _project(e, names)
            if _digest(o) != t:
                kinds: set[str] = set()
                for k in set(o) | set(state):
                    if o.get(k) != state.get(k):
                        if k not in state:
                            kind = "public_lacks_key"
                        elif k not in o:
                            kind = "ours_lacks_key"
                        else:
                            kind = _classify(dates[k], replay.stamp[k])
                        causes[f"{k[1]}:{kind}"] += 1
                        kinds.add(kind)
                doc_kinds["+".join(sorted(kinds))] += 1
                if "same_stamp_conflict" in kinds:
                    conflict_docs.append(name)
        s_pre_hour, g_pre_hour = _grid(pre_hour, _digests_at(events, pre_hour, names, required))
        s_pre_half, g_pre_half = _grid(pre_half, _digests_at(events, pre_half, names, required))
        s_win_half, g_win_half = _grid(win_half, _digests_at(events, win_half, names, required))
        report[label] = {
            "ours_distinct": len(ours_set),
            "validation_docs_equal": equal,
            "validation_docs_total": len(docs),
            "mismatch_causes": dict(causes.most_common(12)),
            "mismatch_docs_by_kind_set": dict(doc_kinds.most_common()),
            "mismatch_docs_with_same_stamp_conflict": conflict_docs,
            "pre_window_hourly": g_pre_hour,
            "pre_window_half_hourly": g_pre_half,
            "in_window_half_hourly": g_win_half,
            "pre_window_hourly_marks": len(pre_hour),
            "pre_window_distinct_hourly": len(s_pre_hour),
            "pre_window_distinct_half_hourly": len(s_pre_half),
            "pre_window_already_in_ours": len(s_pre_half & ours_set),
            "union_ours_plus_pre_window_hourly": len(ours_set | s_pre_hour),
            "union_ours_plus_pre_window_half_hourly": len(ours_set | s_pre_half),
            "in_window_distinct_half_hourly": len(s_win_half),
            "in_window_shared_with_ours": len(s_win_half & ours_set),
            "in_window_not_in_ours": len(s_win_half - ours_set),
            "ours_not_on_half_hour_marks": len(ours_set - s_win_half),
            "union_ours_plus_all_half_hourly": len(ours_set | s_pre_half | s_win_half),
        }

    (args.out / "summary.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    with (args.out / "overlap-by-property.tsv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(head) + "\n")
        for r in report["overlap_by_property"]:
            fh.write("\t".join(str(r[k]) for k in head) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "overlap_by_property"}, indent=2, default=str
        )
    )


if __name__ == "__main__":
    main()
