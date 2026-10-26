"""Task N0 of the pattern detector: count the rows the protocol in ``README.md`` defines.

Nothing here is scored against the labels. The script reports what README section 6's decision
tree needs (events, rows, positives, days, censoring, per-qubit counts) and the null's parameters
(pooled lag-1 autocorrelation of training increments, ``q``, the per-qubit robust scale), at both
the protocol's ``delta`` and its fallback.

Run from the repository root with the pinned interpreter (Windows ``PYTHONPATH`` uses ``;``)::

    PYTHONPATH=src;. python docs/evidence/pattern-detector/count_events.py \
        --repo . --ref <calibration-data sha> --out docs/evidence/pattern-detector \
        --cache <scratch>/collection.pkl

``--selftest`` runs the label logic on a synthetic archive and exits; it touches no git ref.

Outputs: ``counts.json`` (every figure section 8 quotes), ``counts.tsv`` (the same, one row per
figure) and ``rows.tsv.gz`` (the labelled rows at the protocol's ``delta``: N1's input).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import pickle
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
from scripts.canonical_snapshot_digest import qubit_digest
from scripts.init_error_analysis import _git, list_snapshots, read_snapshot

from superconducted.calibration.loader import parse_snapshot

BACKEND = "ibm_fez"
CUT = "2026-09-01T00:00:00+00:00"
DELTA = 0.37
DELTA_FALLBACK = 0.25
K = 5
WINDOW_D = 30.0
MIN_WINDOW_STATES = 5
MIN_WINDOW_DISTINCT = 3
RECAL_FRACTION = 0.20
FLOOR_TRAIN_FULL = 150
FLOOR_TRAIN_CORE = 60
FLOOR_TEST_POS = 30
FLOOR_TEST_DAYS = 30
DAY = 86400.0


@dataclass(frozen=True)
class FileRecord:
    path: str
    time: float  # epoch seconds of properties.last_update_date
    digest: str
    log_t1: np.ndarray  # (n_qubits,) log T1 in seconds, NaN where missing
    t1_dates: tuple[str | None, ...]


def _epoch(stamp: str) -> float:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(UTC).timestamp()


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).isoformat()


def _day(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).date().isoformat()


# ------------------------------------------------------------------------------- loading


def record_of(path: str, doc: dict[str, Any]) -> FileRecord:
    props = doc["properties"]
    parsed = parse_snapshot(doc, source=path)
    log_t1 = np.array(
        [
            math.log(q.t1_seconds) if q.t1_seconds is not None and q.t1_seconds > 0 else math.nan
            for q in parsed.qubits
        ],
        dtype=np.float64,
    )
    t1_dates = tuple(
        next((p.get("date") for p in params if p.get("name") == "T1"), None)
        for params in props["qubits"]
    )
    return FileRecord(path, _epoch(props["last_update_date"]), qubit_digest(doc), log_t1, t1_dates)


def load_files(repo: Path, ref: str) -> list[FileRecord]:
    paths = [p for p in list_snapshots(repo, ref, "snapshots") if f"/{BACKEND}/" in p]
    records: list[FileRecord] = []
    for i, path in enumerate(paths):
        records.append(record_of(path, read_snapshot(repo, ref, path)))
        if (i + 1) % 250 == 0:
            print(f"  read {i + 1}/{len(paths)} files", file=sys.stderr)
    records.sort(key=lambda r: (r.time, r.path))
    return records


def distinct_states(files: list[FileRecord]) -> list[int]:
    """Indices (into the time-sorted file list) of the first file of each distinct state."""
    seen: set[str] = set()
    out: list[int] = []
    for i, rec in enumerate(files):
        if rec.digest not in seen:
            seen.add(rec.digest)
            out.append(i)
    return out


def index_new_state_count(repo: Path, ref: str) -> int:
    text = _git(repo, "show", f"{ref}:health/state-index.tsv").decode("utf-8")
    rows = [line.split("\t") for line in text.splitlines()[1:] if line.strip()]
    return sum(1 for r in rows if r[3].strip() == "1")


def recal_times(files: list[FileRecord]) -> list[float]:
    """Chip-wide T1 sweeps: >= RECAL_FRACTION of comparable qubits carry a new T1 date."""
    out: list[float] = []
    for prev, cur in pairwise(files):
        pairs = [
            (a, b)
            for a, b in zip(prev.t1_dates, cur.t1_dates, strict=False)
            if a is not None and b is not None
        ]
        if pairs and sum(1 for a, b in pairs if a != b) / len(pairs) >= RECAL_FRACTION:
            out.append(cur.time)
    return out


# ------------------------------------------------------------------------------- protocol


@dataclass(frozen=True)
class Event:
    qubit: int
    file_index: int
    time: float
    value: float  # log T1 at the event (the reading)
    increment: float  # value minus the previous event's value


@dataclass
class Row:
    qubit: int
    time: float
    reading: float
    level: float
    d: float
    n_window_states: int
    n_window_distinct: int
    y: int | None  # None when censored
    crosses_cut: bool


def events_of(files: list[FileRecord], qubit: int) -> list[Event]:
    """Re-measurement events: value changes of log T1 between consecutive files."""
    out: list[Event] = []
    prev: float | None = None
    for f, rec in enumerate(files):
        v = float(rec.log_t1[qubit]) if qubit < rec.log_t1.size else math.nan
        if not math.isfinite(v):
            continue
        if prev is not None and v != prev:
            out.append(Event(qubit, f, rec.time, v, v - prev))
        prev = v
    return out


def level_at(
    files: list[FileRecord], state_times: np.ndarray, states: list[int], qubit: int, t: float
) -> tuple[float, int, int] | None:
    """State-weighted geometric mean over distinct states strictly before t, inside 30 days."""
    lo = int(np.searchsorted(state_times, t - WINDOW_D * DAY, side="right"))
    hi = int(np.searchsorted(state_times, t, side="left"))  # strictly before t
    vals = np.array([files[states[i]].log_t1[qubit] for i in range(lo, hi)], dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    n_states = int(vals.size)
    n_distinct = int(np.unique(vals).size)
    if n_states < MIN_WINDOW_STATES or n_distinct < MIN_WINDOW_DISTINCT:
        return None
    return float(np.mean(vals)), n_states, n_distinct


def label(events: list[Event], i: int, reading: float, level: float, k: int) -> int | None:
    succ = events[i + 1 : i + 1 + k]
    if len(succ) < k:
        return None
    m = float(np.median([e.value for e in succ]))
    return int(abs(m - reading) < abs(m - level))


def build_rows(
    files: list[FileRecord], states: list[int], delta: float, k: int, cut: float
) -> tuple[list[Row], list[list[Event]]]:
    state_times = np.array([files[s].time for s in states])
    n_q = int(max(r.log_t1.size for r in files))
    rows: list[Row] = []
    all_events: list[list[Event]] = []
    for q in range(n_q):
        ev = events_of(files, q)
        all_events.append(ev)
        for i, e in enumerate(ev):
            lvl = level_at(files, state_times, states, q, e.time)
            if lvl is None:
                continue
            level, n_states, n_distinct = lvl
            d = e.value - level
            if abs(d) < delta:
                continue
            y = label(ev, i, e.value, level, k)
            succ = ev[i + 1 : i + 1 + k]
            crosses = e.time < cut and any(s.time >= cut for s in succ)
            rows.append(Row(q, e.time, e.value, level, d, n_states, n_distinct, y, crosses))
    return rows, all_events


# ------------------------------------------------------------------------------- null parameters


def pooled_rho(all_events: list[list[Event]], cut: float) -> tuple[float, int]:
    """Lag-1 autocorrelation of consecutive training increments, pooled over qubits."""
    pairs = [
        (a.increment, b.increment) for ev in all_events for a, b in pairwise(ev) if b.time < cut
    ]
    if len(pairs) < 3:
        return math.nan, len(pairs)
    arr = np.array(pairs)
    return float(np.corrcoef(arr[:, 0], arr[:, 1])[0, 1]), len(pairs)


def q_of(rho: float) -> float:
    if not math.isfinite(rho) or rho >= 0.0:
        return math.nan
    return max(0.0, -1.0 / rho - 2.0)


def robust_sigma(all_events: list[list[Event]], cut: float) -> np.ndarray:
    """Per-qubit sigma_q = 1.4826 * MAD(training increments) / sqrt(2); NaN below 20 increments."""
    out = []
    for ev in all_events:
        inc = np.array([e.increment for e in ev if e.time < cut])
        if inc.size < 20:
            out.append(math.nan)
            continue
        mad = float(np.median(np.abs(inc - np.median(inc))))
        out.append(1.4826 * mad / math.sqrt(2.0))
    return np.array(out)


# ------------------------------------------------------------------------------- counting


def count(rows: list[Row], cut: float) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split in ("train", "test"):
        sel = [r for r in rows if (r.time < cut) == (split == "train")]
        labelled = [r for r in sel if r.y is not None]
        out[f"{split}_rows_incl_censored"] = len(sel)
        out[f"{split}_censored"] = len(sel) - len(labelled)
        out[f"{split}_rows"] = len(labelled)
        out[f"{split}_positives"] = sum(r.y for r in labelled if r.y is not None)
        out[f"{split}_days_with_row"] = len({_day(r.time) for r in labelled})
        out[f"{split}_days_with_positive"] = len({_day(r.time) for r in labelled if r.y == 1})
        for sign, name in ((-1, "below"), (1, "above")):
            s = [r for r in labelled if (r.d < 0) == (sign < 0)]
            out[f"{split}_rows_{name}"] = len(s)
            out[f"{split}_positives_{name}"] = sum(r.y for r in s if r.y is not None)
        if split == "train":
            out["train_rows_crossing_cut"] = sum(1 for r in labelled if r.crosses_cut)
        per_q: dict[int, int] = {}
        for r in labelled:
            per_q[r.qubit] = per_q.get(r.qubit, 0) + 1
        counts = np.array(sorted(per_q.values())) if per_q else np.array([0])
        out[f"{split}_qubits_with_row"] = len(per_q)
        out[f"{split}_rows_per_qubit_min"] = int(counts.min())
        out[f"{split}_rows_per_qubit_median"] = float(np.median(counts))
        out[f"{split}_rows_per_qubit_max"] = int(counts.max())
        out[f"{split}_base_rate"] = (
            out[f"{split}_positives"] / out[f"{split}_rows"] if out[f"{split}_rows"] else math.nan
        )
    return out


def branch(c: dict[str, Any]) -> str:
    """README section 6's decision tree, applied to one delta's counts."""
    test_ok = c["test_positives"] >= FLOOR_TEST_POS and c["test_days_with_row"] >= FLOOR_TEST_DAYS
    if c["train_positives"] >= FLOOR_TRAIN_FULL and test_ok:
        return "1: full 14-feature list"
    if c["train_positives"] >= FLOOR_TRAIN_CORE and test_ok:
        return "2: core 5-feature list"
    return "3: below the floors at this delta"


def summarise(
    files: list[FileRecord], states: list[int], cut: float, ref: str
) -> tuple[dict[str, Any], list[Row]]:
    summary: dict[str, Any] = {
        "ref": ref,
        "backend": BACKEND,
        "files": len(files),
        "distinct_states": len(states),
        "first_file": _iso(files[0].time),
        "last_file": _iso(files[-1].time),
        "cut": CUT,
        "k": K,
        "window_days": WINDOW_D,
        "min_window_states": MIN_WINDOW_STATES,
        "min_window_distinct": MIN_WINDOW_DISTINCT,
        "chipwide_t1_sweeps": len(recal_times(files)),
    }
    rows_main: list[Row] = []
    for delta in (DELTA, DELTA_FALLBACK):
        rows, all_events = build_rows(files, states, delta, K, cut)
        c = count(rows, cut)
        c["branch"] = branch(c)
        summary[f"delta_{delta}"] = c
        if delta == DELTA:
            rows_main = rows
            summary["events_total"] = sum(len(ev) for ev in all_events)
            summary["events_train"] = sum(1 for ev in all_events for e in ev if e.time < cut)
            summary["events_test"] = summary["events_total"] - summary["events_train"]
            rho, n_pairs = pooled_rho(all_events, cut)
            sig = robust_sigma(all_events, cut)
            fin = sig[np.isfinite(sig)]
            summary["null"] = {
                "rho_train_pooled": rho,
                "rho_pairs": n_pairs,
                "q": q_of(rho),
                "sigma_q_qubits": int(fin.size),
                "sigma_q_min": float(fin.min()) if fin.size else math.nan,
                "sigma_q_p10": float(np.quantile(fin, 0.10)) if fin.size else math.nan,
                "sigma_q_median": float(np.median(fin)) if fin.size else math.nan,
                "sigma_q_p90": float(np.quantile(fin, 0.90)) if fin.size else math.nan,
                "sigma_q_max": float(fin.max()) if fin.size else math.nan,
            }
    first = summary[f"delta_{DELTA}"]["branch"]
    if first.startswith("3"):
        second = summary[f"delta_{DELTA_FALLBACK}"]["branch"]
        summary["branch_taken"] = (
            f"3 then {second} at delta {DELTA_FALLBACK}"
            if not second.startswith("3")
            else "4: stop, insufficient rows at both deltas"
        )
    else:
        summary["branch_taken"] = f"{first} at delta {DELTA}"
    return summary, rows_main


def write_outputs(out: Path, summary: dict[str, Any], rows: list[Row]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "counts.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    flat: list[tuple[str, Any]] = []

    def walk(prefix: str, node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
        else:
            flat.append((prefix, node))

    walk("", summary)
    with (out / "counts.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["figure", "value"])
        w.writerows(flat)
    with gzip.open(out / "rows.tsv.gz", "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(
            [
                "qubit",
                "time",
                "split",
                "reading_log",
                "level_log",
                "d",
                "n_window_states",
                "n_window_distinct",
                "y",
                "crosses_cut",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r.qubit,
                    _iso(r.time),
                    "train" if r.time < _epoch(CUT) else "test",
                    f"{r.reading:.6f}",
                    f"{r.level:.6f}",
                    f"{r.d:.6f}",
                    r.n_window_states,
                    r.n_window_distinct,
                    "" if r.y is None else r.y,
                    int(r.crosses_cut),
                ]
            )


# ------------------------------------------------------------------------------- self-test


def _synthetic() -> list[FileRecord]:
    """Two qubits, hourly files for 60 days, one shift and one transient, built by hand."""
    base = _epoch("2026-06-01T00:00:00+00:00")
    files: list[FileRecord] = []
    v = np.array([math.log(100e-6), math.log(100e-6)])
    for h in range(60 * 24):
        t = base + h * 3600.0
        day, hour = divmod(h, 24)
        if hour == 0 and day > 0:
            # one re-measurement a day; five distinct wobbles so every 30-day window
            # holds at least MIN_WINDOW_DISTINCT values
            wobble = 0.01 * ((day % 5) - 2)
            v = np.array([math.log(100e-6) + wobble, math.log(100e-6) + wobble])
            if day == 40:  # qubit 0 shifts and stays; qubit 1 dips and returns
                v = v + np.array([0.6, -0.9])
            if 40 < day <= 46:
                v[0] = math.log(100e-6) + 0.6 + wobble  # qubit 0 stays near the new value
        dates = (f"d{day}", f"d{day}")
        files.append(FileRecord(f"f{h}", t, f"digest{h}", v.copy(), dates))
    return files


def selftest() -> None:
    files = _synthetic()
    states = distinct_states(files)
    cut = _epoch("2026-07-25T00:00:00+00:00")
    rows, all_events = build_rows(files, states, DELTA, K, cut)
    by_q: dict[int, Row] = {}
    for r in sorted(rows, key=lambda r: r.time):
        if abs(r.d) > 0.5 and r.qubit not in by_q:
            by_q[r.qubit] = r  # the first large disagreement of each qubit
    assert 0 in by_q and 1 in by_q, f"expected a row for each qubit, got {by_q.keys()}"
    assert by_q[0].y == 1, f"qubit 0 shifted and stayed: expected y=1, got {by_q[0].y}"
    assert by_q[1].y == 0, f"qubit 1 dipped and returned: expected y=0, got {by_q[1].y}"
    assert by_q[0].d > 0.5 and by_q[1].d < -0.8
    # mutation: a label computed against the reading as reference must differ
    ev0 = all_events[0]
    idx = next(i for i, e in enumerate(ev0) if e.time == by_q[0].time)
    assert label(ev0, idx, by_q[0].reading, by_q[0].level, K) == 1
    assert label(ev0, idx, by_q[0].level, by_q[0].reading, K) == 0
    # censoring: the last events have fewer than K successors
    tail = [r for r in rows if r.y is None]
    assert all(r.time > files[-1].time - (K + 1) * DAY for r in tail)
    c = count(rows, cut)
    assert c["train_rows"] + c["test_rows"] + c["train_censored"] + c["test_censored"] == len(rows)
    rho, n = pooled_rho(all_events, cut)
    assert math.isfinite(rho) and n > 10
    print(f"selftest ok: rows={len(rows)} y0={by_q[0].y} y1={by_q[1].y} rho={rho:.3f}")


# ------------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--ref", type=str)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--cache", type=Path, help="pickle of the collected files, written if absent")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.ref or not args.out:
        ap.error("--ref and --out are required")
    if args.cache and args.cache.exists():
        files = pickle.loads(args.cache.read_bytes())
        print(f"loaded {len(files)} files from cache", file=sys.stderr)
    else:
        files = load_files(args.repo, args.ref)
        if args.cache:
            args.cache.parent.mkdir(parents=True, exist_ok=True)
            args.cache.write_bytes(pickle.dumps(files))
    states = distinct_states(files)
    indexed = index_new_state_count(args.repo, args.ref)
    if len(states) != indexed:
        raise SystemExit(
            f"reproduction guard: {len(states)} distinct states against "
            f"{indexed} is_new_state rows in health/state-index.tsv at {args.ref}"
        )
    summary, rows = summarise(files, states, _epoch(CUT), args.ref)
    write_outputs(args.out, summary, rows)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
