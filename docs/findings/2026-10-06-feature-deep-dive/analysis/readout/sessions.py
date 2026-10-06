"""Readout stamps, record classes, the stale P(0|1) groups, and readout sessions.

Writes ``results/readout/sessions.json``:

- how the three readout stamps relate in every record, and where ``ro = (P(0|1) + P(1|0))/2``
  holds or fails;
- the qubits whose published P(0|1) lags ``ro`` by hours, with their date ranges, and the
  implied fresh value ``2 ro - P(1|0)``;
- readout sessions (clusters of readout stamps), their kind by count parity, their hour of
  day, their alignment with ``T1`` rounds, and the visible session cadence by month.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import rocommon as rc


def stamp_rounds(dd: ddload.DD, field: str) -> np.ndarray:
    """Start times of device-wide rounds of ``field`` (stamp events clustered, gap > 15 min)."""
    ev = rc.stamp_events(np.array(dd.v(field)), np.array(dd.d(field)))
    t = np.sort(np.concatenate([s.t_ms[1:] for s in ev if s.t_ms.size > 1]))
    br = np.flatnonzero(np.diff(t) > rc.SESSION_GAP_MS)
    starts = np.concatenate([[0], br + 1])
    sizes = np.diff(np.concatenate([starts, [t.size]]))
    out: np.ndarray = t[starts][sizes >= rc.MIN_SESSION_QUBITS / 2]
    return out


def main() -> None:
    dd = ddload.DD()
    r = rc.load(dd)
    c = rc.record_classes(r)
    n_present = int(c["present"].sum())
    gap_s = np.maximum(np.abs(r.d_ro - r.d_p0g1), np.abs(r.d_ro - r.d_p1g0)) / 1000.0
    not3 = c["present"] & ~c["same3"]

    classes: dict[str, Any] = {}
    for name in ("same3", "staggered", "stale_p0g1", "other"):
        m = c[name]
        classes[name] = {
            "records": int(m.sum()),
            "share": round(float(m.sum()) / n_present, 4),
            "mean_rule_holds": int((m & c["mean_ok"]).sum()),
        }
    sens = {f"le_{s}_s": int((not3 & (gap_s <= s)).sum()) for s in (60, 120, 300, 600, 1800, 3600)}
    stag = c["staggered"]
    stagger: dict[str, Any] = {
        "ro_minus_p0g1_s_q": rc.quantiles(((r.d_ro - r.d_p0g1) / 1000.0)[stag]),
        "ro_minus_p1g0_s_q": rc.quantiles(((r.d_ro - r.d_p1g0) / 1000.0)[stag]),
        "not_same3_records_by_max_gap": sens,
    }
    per_file_same3 = c["same3"].sum(axis=1) / np.maximum(c["present"].sum(axis=1), 1)
    stagger["files_with_no_same3_record"] = int(np.sum(per_file_same3 == 0))
    stagger["per_file_same3_share_q"] = rc.quantiles(per_file_same3)
    hist = ~np.array(dd.file("has_configuration")).astype(bool)
    stagger["files_with_no_same3_record_historical"] = int(np.sum((per_file_same3 == 0) & hist))

    # The stale P(0|1) records: which qubits, when, by how much.
    st = c["stale_p0g1"]
    lag_h = (r.d_ro - r.d_p0g1) / 3.6e6
    stale_q = np.flatnonzero(st.sum(axis=0) > 0)
    rows = []
    for q in stale_q:
        f = np.flatnonzero(st[:, q])
        rows.append(
            {
                "qubit": int(q),
                "qubit_mod_17": int(q % 17),
                "stale_records": int(f.size),
                "first_file": dd.stems[f[0]][:15],
                "last_file": dd.stems[f[-1]][:15],
            }
        )
    major = [row for row in rows if row["stale_records"] >= 100]
    groups: dict[int, dict[str, Any]] = {}
    for row in major:
        g = groups.setdefault(
            row["qubit_mod_17"],
            {"qubits": [], "first_file": row["first_file"], "last_file": row["last_file"]},
        )
        g["qubits"].append(row["qubit"])
        g["first_file"] = min(g["first_file"], row["first_file"])
        g["last_file"] = max(g["last_file"], row["last_file"])
    imp_ok = st & c["p1g0_fresh"]
    imp = 2.0 * r.ro - r.p1g0
    k = imp[imp_ok] * rc.SHOTS
    stale: dict[str, Any] = {
        "records": int(st.sum()),
        "share_of_mean_rule_failures": round(
            float((st & ~c["mean_ok"]).sum()) / max(int((~c["mean_ok"] & c["present"]).sum()), 1),
            5,
        ),
        "mean_rule_failures_total": int((~c["mean_ok"] & c["present"]).sum()),
        "mean_rule_failures_not_stale": int((~c["mean_ok"] & c["present"] & ~st).sum()),
        "lag_h_q": rc.quantiles(lag_h[st]),
        "qubits_ever_stale": int(stale_q.size),
        "qubits_stale_ge_100_records": len(major),
        "groups_by_qubit_mod_17": {str(kk): v for kk, v in sorted(groups.items())},
        "minor_qubits": [row for row in rows if row["stale_records"] < 100],
        "implied_p0g1_records": int(imp_ok.sum()),
        "implied_p0g1_on_1_over_4096_grid": round(
            float(np.mean(np.abs(k - np.round(k)) < 1e-6)), 6
        ),
        "implied_p0g1_q": rc.quantiles(imp[imp_ok]),
        "implied_minus_published_p0g1_q": rc.quantiles((imp - r.p0g1)[imp_ok]),
        "meas_map_groups": [
            len(g) for g in next(iter(dd.meta["config_values"]["meas_map"].values()))["value"]
        ],
    }

    # Sessions.
    s = rc.sessions(r, c)
    big = s.kind != "small"
    hours = np.array([datetime.fromtimestamp(x / 1000, UTC).hour for x in s.start_ms])
    wday = np.array([datetime.fromtimestamp(x / 1000, UTC).weekday() for x in s.start_ms])
    months = np.array([rc.iso(x)[:7] for x in s.start_ms])
    sess: dict[str, Any] = {
        "rule": "readout_error stamp events of all qubits, sorted, split at gaps > 15 min",
        "n_sessions": int(s.start_ms.size),
        "kinds": {kk: int(np.sum(s.kind == kk)) for kk in ("even", "mixed", "small")},
        "even_share_histogram_big": {
            "edges": [0, 0.4, 0.45, 0.55, 0.6, 0.9, 0.99, 1.0, 1.01],
            "counts": np.histogram(
                s.even_share[big], bins=[0, 0.4, 0.45, 0.55, 0.6, 0.9, 0.99, 0.999999, 1.01]
            )[0].tolist(),
        },
        "mixed_even_share_q": rc.quantiles(s.even_share[s.kind == "mixed"]),
        "counts_per_session_q": {
            kk: rc.quantiles(s.n_counts[s.kind == kk]) for kk in ("even", "mixed")
        },
        "qubits_per_session_q": {
            kk: rc.quantiles(s.n_qubits[s.kind == kk]) for kk in ("even", "mixed", "small")
        },
        "duration_min_q": {
            kk: rc.quantiles((s.end_ms - s.start_ms)[s.kind == kk] / 6e4)
            for kk in ("even", "mixed")
        },
        "small_sessions": [
            {"start": rc.iso(s.start_ms[i]), "qubits": int(s.n_qubits[i])}
            for i in np.flatnonzero(s.kind == "small")
        ],
        "first_even": rc.iso(s.start_ms[s.kind == "even"][0]),
        "last_even": rc.iso(s.start_ms[s.kind == "even"][-1]),
        "start_hour_utc_counts": {
            kk: np.bincount(hours[s.kind == kk], minlength=24).tolist() for kk in ("even", "mixed")
        },
        "start_weekday_counts_mon0": {
            kk: np.bincount(wday[s.kind == kk], minlength=7).tolist() for kk in ("even", "mixed")
        },
    }
    # Visible cadence by month (coverage depends on the archive's polling in each period).
    by_month = {}
    for mo in sorted(set(months[big])):
        sel = big & (months == mo)
        st_ms = s.start_ms[sel]
        first_day = datetime.fromisoformat(mo + "-01T00:00:00+00:00").timestamp() * 1000
        nxt = (int(mo[:4]) + (mo[5:] == "12"), int(mo[5:]) % 12 + 1)
        last_day = datetime(nxt[0], nxt[1], 1, tzinfo=UTC).timestamp() * 1000
        span_lo = max(first_day, float(dd.file_ms[0]))
        span_hi = min(last_day, float(dd.file_ms[-1]))
        days = (span_hi - span_lo) / 8.64e7
        fsel = (dd.file_ms >= first_day) & (dd.file_ms < last_day)
        by_month[mo] = {
            "sessions": int(sel.sum()),
            "even": int(np.sum(sel & (s.kind == "even"))),
            "days_covered": round(days, 2),
            "sessions_per_day": round(float(sel.sum()) / days, 3),
            "even_per_day": round(float(np.sum(sel & (s.kind == "even"))) / days, 3),
            "gap_between_sessions_h_q": rc.quantiles(np.diff(st_ms) / 3.6e6),
            "files": int(fsel.sum()),
            "historical_files": int(np.sum(fsel & hist)),
        }
    sess["by_month"] = by_month

    # Alignment with T1 rounds (assigned cross-family link: T1 is loaded for this only).
    t1_rounds = stamp_rounds(dd, "q.T1")
    t1_idx = np.searchsorted(t1_rounds, s.start_ms)
    prev_gap = np.where(
        t1_idx > 0, (s.start_ms - t1_rounds[np.clip(t1_idx - 1, 0, None)]) / 3.6e6, np.inf
    )
    next_gap = np.where(
        t1_idx < t1_rounds.size,
        (t1_rounds[np.clip(t1_idx, None, t1_rounds.size - 1)] - s.start_ms) / 3.6e6,
        np.inf,
    )
    nearest = np.minimum(prev_gap, next_gap)
    sess["t1_rounds"] = int(t1_rounds.size)
    sess["hours_to_nearest_t1_round_q"] = {
        kk: rc.quantiles(nearest[s.kind == kk]) for kk in ("even", "mixed")
    }
    sess["share_within_3h_of_t1_round"] = {
        kk: round(float(np.mean(nearest[s.kind == kk] <= 3.0)), 4) for kk in ("even", "mixed")
    }

    # In which session kind does a stale-group qubit's P(0|1) get refreshed?
    ev = rc.stamp_events(r.ro, r.d_ro)
    fresh_by_kind: dict[str, list[int]] = {"even": [0, 0], "mixed": [0, 0]}
    all_by_kind: dict[str, list[int]] = {"even": [0, 0], "mixed": [0, 0]}
    for e in ev:
        q = e.entity
        si = s.index(e.t_ms)
        kinds = np.where(si >= 0, s.kind[np.clip(si, 0, None)], "none")
        in_group = st[:, q].sum() >= 100
        if in_group:
            first = np.flatnonzero(st[:, q])[0]
            last = np.flatnonzero(st[:, q])[-1]
            within = (e.file_idx >= first) & (e.file_idx <= last)
        else:
            within = np.zeros(e.file_idx.size, dtype=bool)
        fr = c["p0g1_fresh"][e.file_idx, q]
        for kk in ("even", "mixed"):
            m = (kinds == kk) & within
            fresh_by_kind[kk][0] += int((m & fr).sum())
            fresh_by_kind[kk][1] += int(m.sum())
            m2 = (kinds == kk) & ~in_group
            all_by_kind[kk][0] += int((m2 & fr).sum())
            all_by_kind[kk][1] += int(m2.sum())
    stale["group_qubit_p0g1_fresh_by_session_kind"] = {
        kk: {"fresh": v[0], "events": v[1]} for kk, v in fresh_by_kind.items()
    }
    stale["other_qubit_p0g1_fresh_by_session_kind"] = {
        kk: {"fresh": v[0], "events": v[1]} for kk, v in all_by_kind.items()
    }

    rc.write(
        "sessions.json",
        "sessions.py",
        {
            "n_files": dd.n_files,
            "records": n_present,
            "record_classes": classes,
            "stagger": stagger,
            "stale_p0g1": stale,
            "sessions": sess,
        },
    )


if __name__ == "__main__":
    main()
