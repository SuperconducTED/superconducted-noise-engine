"""Document cadence, provenance, configuration and target evolution, and stamp semantics.

Covers the file-level arrays (``file.*``) and the ``meta.json`` structure:

- files per day by month, live (with ``configuration``) against historical (without);
- consecutive-file gaps by month and every gap above 12 h, dated;
- the ledger (poll rows from 2026-09-02): decisions by month, polls per day, poll latency;
- visible re-measurement rounds per day by month for readout and the daily families, and the
  readout gap distribution by month (what coverage does to event rates);
- configuration keys that change, the key that appears mid-archive, target operation sets by
  provenance, record counts per file, backend and schema version;
- the device-wide length changes as dated value events;
- what ``last_update_date`` is consistent with: the newest measured stamp in the file, the
  placeholder stamp, the ``zz`` stamp and the ``measure.threshold`` stamp.

Writes ``results/device/documents.json``.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload
import device_common as dc

LONG_FILE_GAP_H = 12.0
READOUT_SLOW_GAP_H = 6.5
MEASURED_FIELDS = (
    "q.T1",
    "q.T2",
    "q.readout_error",
    "q.prob_meas0_prep1",
    "q.prob_meas1_prep0",
    "q.init_error",
    "g1.sx.gate_error",
    "g1.x.gate_error",
    "g1.id.gate_error",
    "g1.rx.gate_error",
    "g1.xslow.gate_error",
    "g1.measure_2.gate_error",
    "g2.cz.gate_error",
    "g2.rzz.gate_error",
)


def month(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000.0, UTC).strftime("%Y-%m")


def to_ms(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000.0


def stem_ms(stem: str) -> float:
    return datetime.strptime(stem[:15], "%Y%m%dT%H%M%S").replace(tzinfo=UTC).timestamp() * 1000.0


def days_covered(fms: np.ndarray, mo: str) -> float:
    """Days of month ``mo`` between the first and last file of the archive."""
    y, m = int(mo[:4]), int(mo[5:])
    start = datetime(y, m, 1, tzinfo=UTC).timestamp() * 1000.0
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=UTC).timestamp() * 1000.0
    lo, hi = max(start, float(fms[0])), min(end, float(fms[-1]))
    return max(hi - lo, 0.0) / dc.MS_PER_DAY


def cadence(dd: ddload.DD) -> dict[str, Any]:
    fms = dd.file_ms
    live = dd.file("has_configuration").astype(bool)
    months = np.array([month(x) for x in fms])
    gaps = np.diff(fms) / ddload.MS_PER_HOUR
    out: dict[str, Any] = {"by_month": {}}
    for mo in sorted(set(months)):
        sel = months == mo
        g = gaps[sel[1:]]
        days = days_covered(fms, mo)
        out["by_month"][mo] = {
            "files": int(sel.sum()),
            "live": int(np.sum(sel & live)),
            "historical": int(np.sum(sel & ~live)),
            "days_covered": dc.r6(days),
            "files_per_day": dc.r6(sel.sum() / days) if days else None,
            "gap_h_q": dc.quantiles(g),
        }
    out["gap_h_q_all"] = dc.quantiles(gaps)
    out["gap_h_q_live_to_live"] = dc.quantiles(gaps[live[1:] & live[:-1]])
    out["gaps_above_12h_count"] = int(np.sum(gaps > LONG_FILE_GAP_H))
    out["gaps_above_12h"] = [
        {
            "after": dd.stems[k],
            "before": dd.stems[k + 1],
            "hours": dc.r6(gaps[k]),
            "live_live": bool(live[k] and live[k + 1]),
        }
        for k in np.flatnonzero(gaps > LONG_FILE_GAP_H)
    ]
    out["first_historical_file"] = dd.stems[int(np.flatnonzero(~live)[0])]
    out["timestamp_equals_last_update_all_files"] = bool(
        np.all(dd.file("timestamp_ms") == dd.file("last_update_ms"))
    )
    return out


def ledger(dd: ddload.DD) -> dict[str, Any]:
    rows = dd.meta["ledger"]
    live = dd.file("has_configuration").astype(bool)
    by_stem = {s.removesuffix(".json"): i for i, s in enumerate(dd.stems)}
    dec = Counter((r["poll_time_utc"][:7], r["decision"]) for r in rows)
    polls = sorted({r["poll_time_utc"] for r in rows})
    pms = np.array([to_ms(p) for p in polls])
    per_day = Counter(p[:10] for p in polls)
    days = sorted(per_day)
    lat_live, lat_hist = [], []
    seen_first: dict[str, float] = {}
    for r in rows:
        if r["decision"] != "new":
            continue
        key = r["last_update_date"]
        seen_first.setdefault(key, to_ms(r["poll_time_utc"]))
    for key, pt in seen_first.items():
        i = by_stem.get(key)
        if i is None:
            continue
        lag = (pt - float(dd.file_ms[i])) / ddload.MS_PER_HOUR
        (lat_live if live[i] else lat_hist).append(lag)
    files_after = [i for i, s in enumerate(dd.stems) if stem_ms(s) >= to_ms(polls[0])]
    no_new_row = [
        dd.stems[i] for i in files_after if dd.stems[i].removesuffix(".json") not in seen_first
    ]
    return {
        "rows": len(rows),
        "first_poll": polls[0],
        "last_poll": polls[-1],
        "distinct_poll_times": len(polls),
        "decisions_by_month": {f"{m} {d}": c for (m, d), c in sorted(dec.items())},
        "polls_per_day_q": dc.quantiles([per_day[d] for d in days[1:-1]]),
        "poll_interval_h_q": dc.quantiles(np.diff(pms) / ddload.MS_PER_HOUR),
        "new_rows_matched_to_files": len(lat_live) + len(lat_hist),
        "first_poll_minus_last_update_h_q_live": dc.quantiles(lat_live),
        "first_poll_minus_last_update_h_q_historical": dc.quantiles(lat_hist),
        "files_after_first_poll": len(files_after),
        "files_after_first_poll_without_new_row": len(no_new_row),
        "examples_without_new_row": no_new_row[:5],
    }


def visible_rounds(dd: ddload.DD) -> dict[str, Any]:
    fms = dd.file_ms
    out: dict[str, Any] = {}
    for fam in dc.FAMILIES:
        if fam.name in ("lf", "xslow"):
            continue
        ev = dc.family_events(dd, fam)
        lab = dc.split_rounds(ev.t_ms)
        starts, sizes = [], []
        for r in np.unique(lab):
            m = lab == r
            starts.append(float(ev.t_ms[m].min()))
            sizes.append(int(np.unique(ev.entity[m]).size))
        st = np.array(starts)
        major = np.array(sizes) >= 0.5 * ev.n_entities
        st = np.sort(st[major])
        by: dict[str, Any] = {}
        for mo in sorted({month(x) for x in st}):
            sel = np.array([month(x) == mo for x in st])
            days = days_covered(fms, mo)
            g = np.diff(st[sel]) / ddload.MS_PER_HOUR
            row: dict[str, Any] = {
                "major_rounds": int(sel.sum()),
                "per_day": dc.r6(sel.sum() / days) if days else None,
            }
            if fam.name in ("readout", "init_error"):
                row["gap_h_q"] = dc.quantiles(g)
                row["share_gaps_above_6p5h"] = (
                    dc.r6(np.mean(g > READOUT_SLOW_GAP_H)) if g.size else None
                )
            by[mo] = row
        out[fam.name] = by
    return out


def configuration(dd: ddload.DD) -> dict[str, Any]:
    live = dd.file("has_configuration").astype(bool)
    store = dd.meta["config_values"]
    changing = {}
    absent_in_live = {}
    for key, values in store.items():
        ids = dd.file(f"config.{key}")
        missing = int(np.sum((ids < 0) & live))
        if missing:
            idx = np.flatnonzero((ids >= 0) & live)
            absent_in_live[key] = {
                "live_files_without_key": missing,
                "first_live_file_with_key": dd.stems[int(idx[0])],
                "value": next(iter(values.values()))["value"],
            }
        if len(values) > 1:
            changing[key] = [
                {
                    "id": e["id"],
                    "first": e["first"],
                    "last": e["last"],
                    "files": e["files"],
                    "chars": e["chars"],
                }
                for e in values.values()
            ]
    clops_v = [
        {"first": e["first"], "files": e["files"], "json": "string" if e["chars"] == 6 else "null"}
        for e in store["clops_v"].values()
    ]
    basis = [
        {"first": e["first"], "last": e["last"], "value": e["value"]}
        for e in store["basis_gates"].values()
    ]
    sig_desc = []
    for e in store["instruction_signatures"].values():
        val = e["value"] or []
        sig_desc.append(
            {
                "first": e["first"],
                "names": sorted({str(x.get("name")) for x in val if isinstance(x, dict)}),
            }
        )
    tid = dd.file("target_ops_id")
    targets = []
    for t in dd.meta["target_sets"]:
        row: dict[str, Any] = {"id": t["id"], "n_ops": t["n_ops"]}
        for lab, sel in (("live", live), ("historical", ~live)):
            idx = np.flatnonzero((tid == t["id"]) & sel)
            row[lab] = (
                {"files": int(idx.size), "first": dd.stems[idx[0]], "last": dd.stems[idx[-1]]}
                if idx.size
                else {"files": 0}
            )
        targets.append(row)
    first_live_t3 = float(dd.file_ms[np.flatnonzero((tid == 3) & live)[0]])
    early_hist_t3 = np.flatnonzero((tid == 3) & ~live & (dd.file_ms < first_live_t3))
    xs = np.array(dd.v("g1.xslow.gate_error"))
    rec_counts = {}
    for name in ("n_qubit_records", "n_gate_records", "n_general_records", "n_target_ops"):
        arr = dd.file(name)
        rec_counts[name] = [
            {
                "value": int(v),
                "files": int(np.sum(arr == v)),
                "first": dd.stems[int(np.flatnonzero(arr == v)[0])],
                "last": dd.stems[int(np.flatnonzero(arr == v)[-1])],
            }
            for v in np.unique(arr)
        ]
    return {
        "keys": len(store),
        "keys_changing": changing,
        "keys_absent_from_some_live_files": absent_in_live,
        "clops_v": clops_v,
        "basis_gates": basis,
        "instruction_signature_names": sig_desc,
        "target_sets_by_provenance": targets,
        "historical_files_with_2224_ops_before_first_live_2224": int(early_hist_t3.size),
        "those_files_range": [dd.stems[early_hist_t3[0]], dd.stems[early_hist_t3[-1]]]
        if early_hist_t3.size
        else None,
        "those_files_with_any_xslow_record": int(
            np.sum(np.isfinite(xs[early_hist_t3]).any(axis=1))
        ),
        "those_files_without_any_xslow_record": int(
            np.sum(~np.isfinite(xs[early_hist_t3]).any(axis=1))
        ),
        "record_counts": rec_counts,
        "backend_versions": dd.meta["backend_versions"],
        "backend_version_id_distinct": int(np.unique(dd.file("backend_version_id")).size),
        "schema_versions": dd.meta["schema_versions"],
    }


def length_events(dd: ddload.DD) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in ("q.readout_length", "g1.reset.gate_length", "g2.cz.gate_length"):
        v = np.array(dd.v(field))
        rows = []
        for i in range(1, dd.n_files):
            both = np.isfinite(v[i]) & np.isfinite(v[i - 1])
            ch = np.flatnonzero(both & (v[i] != v[i - 1]))
            if ch.size:
                ent = dd.entities(field)
                rows.append(
                    {
                        "file": dd.stems[i],
                        "entities_changed": int(ch.size),
                        "from_to": sorted({(float(v[i - 1, c]), float(v[i, c])) for c in ch}),
                        "examples": [ent[int(c)] for c in ch[:4]],
                    }
                )
        out[field] = rows
    return out


def stamp_semantics(dd: ddload.DD) -> dict[str, Any]:
    fms = dd.file_ms
    newest = np.full(dd.n_files, -np.inf)
    for field in MEASURED_FIELDS:
        v = np.array(dd.v(field))
        d = np.array(dd.d(field))
        if field.endswith("gate_error"):
            d[v >= 1.0] = np.nan
        newest = np.fmax(newest, np.nanmax(np.where(np.isfinite(d), d, -np.inf), axis=1))
    ph = np.array(dd.d("g1.sx.gate_error"))[:, 72]
    zz = np.array(dd.d("gen.zz"))
    thr = np.array(dd.d("g1.measure.threshold"))
    thr_rows = np.isfinite(thr).any(axis=1)
    thr_eq = np.all((thr == fms[:, None]) | ~np.isfinite(thr), axis=1)
    live = dd.file("has_configuration").astype(bool)
    gap = (fms - newest) / ddload.MS_PER_HOUR
    return {
        "measured_fields_used": list(MEASURED_FIELDS),
        "share_last_update_equals_newest_measured_stamp": dc.r6(np.mean(gap == 0)),
        "files_last_update_before_newest_measured_stamp": int(np.sum(gap < 0)),
        "last_update_minus_newest_measured_h_q": dc.quantiles(gap),
        "share_placeholder_stamp_after_last_update": dc.r6(np.mean(ph > fms)),
        "placeholder_minus_last_update_h_q_live": dc.quantiles(
            (ph - fms)[live] / ddload.MS_PER_HOUR
        ),
        "placeholder_minus_last_update_h_q_historical": dc.quantiles(
            (ph - fms)[~live] / ddload.MS_PER_HOUR
        ),
        "share_files_all_zz_stamps_equal_last_update": dc.r6(
            np.mean(np.all((zz == fms[:, None]) | ~np.isfinite(zz), axis=1))
        ),
        "share_threshold_files_all_stamps_equal_last_update": dc.r6(np.mean(thr_eq[thr_rows])),
        "threshold_files": int(thr_rows.sum()),
    }


def main() -> int:
    dd = ddload.DD()
    payload = {
        **dc.header("documents.py"),
        "n_files": dd.n_files,
        "cadence": cadence(dd),
        "ledger": ledger(dd),
        "visible_rounds": visible_rounds(dd),
        "configuration": configuration(dd),
        "length_events": length_events(dd),
        "stamp_semantics": stamp_semantics(dd),
    }
    ddload.write_json(dc.RESULTS / "documents.json", payload)
    print("wrote", dc.RESULTS / "documents.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
