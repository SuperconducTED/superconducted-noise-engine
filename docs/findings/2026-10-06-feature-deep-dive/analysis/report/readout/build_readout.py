# ruff: noqa: RUF001
"""Build the "readout" section of the advisor report page (``results/report/readout.json``).

Source document: ``03-readout-measurement.md`` with its appended Verification section. Where the
verifier weakened a claim, the Turkish text below uses the corrected reading and the chart
carries a caveat. (RUF001 is silenced for this file because the Turkish dotless i is a letter,
not a confusable.)

Data: fields of ``results/readout/*.json`` and ``results/verify/readout/*.json`` where a chart
needs only those; series that no results file holds (device median per session, per-qubit
window medians, per-qubit medians for the scatters and the map, the placebo distributions, the
stale-record spans) are recomputed from the field cache through ``ddload`` with the owner's own
helpers (``analysis/readout/rocommon.py``, ``length_changes.py``, ``sessions.py``,
``spatial_temporal.py``) or, for the asymmetry placebo, a copy of the verifier's definition in
``analysis/verify/readout/v_extra.py`` (that module runs on import, so it is not imported). Every
recomputed figure that the document also states is printed against it; a mismatch is reported,
and the text quotes the document's figure.

Output contract: ``analysis/report/spec_check.py``.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ddload

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "readout"))
import length_changes as lc
import rocommon as rc
import sessions as rs
import spatial_temporal as stp

DEEP = Path(__file__).resolve().parents[3]
RES = DEEP / "results"
OUT = RES / "report" / "readout.json"
H = 3.6e6
DAY = 24 * H
CHECKS: list[tuple[str, float, float, float]] = []


def check(name: str, got: float, doc: float, tol: float) -> None:
    CHECKS.append((name, float(got), float(doc), tol))


def g4(v: float) -> float:
    return float(f"{v:.4g}")


def load(rel: str) -> dict[str, Any]:
    out: dict[str, Any] = json.loads((RES / rel).read_text(encoding="utf-8"))
    return out


def iso_min(ms: float) -> str:
    """ISO time to the minute (keeps the long line series light)."""
    return rc.iso(ms)[:16] + "Z"


def stem_iso(stem: str) -> str:
    return f"{stem[0:4]}-{stem[4:6]}-{stem[6:8]}T{stem[9:11]}:{stem[11:13]}:{stem[13:15]}Z"


def degrees(dd: ddload.DD) -> np.ndarray:
    edges = sorted({(min(a, b), max(a, b)) for a, b in dd.meta["coupling_map"]})
    deg = np.zeros(156, dtype=np.int64)
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    return deg


# ---------------------------------------------------------------- computations


MERGE_GAP_H = 48.0


def stale_spans(dd: ddload.DD, c: dict[str, np.ndarray]) -> tuple[list[dict[str, Any]], Any]:
    """Per qubit with at least 100 stale records: periods of files whose P(0|1) is stale.

    A run is a maximal set of consecutive files with a stale P(0|1); it ends at the next file
    (whose P(0|1) is fresh again). Runs separated by less than ``MERGE_GAP_H`` are merged for
    display: at page width a gap of a few hours (the daily refresh) is below one pixel. The
    quantiles of the unmerged gaps are returned so the text can state them.
    """
    st = c["stale_p0g1"]
    fm = dd.file_ms
    rows, gaps = [], []
    for q in np.flatnonzero(st.sum(axis=0) >= 100):
        idx = np.flatnonzero(st[:, q])
        br = np.flatnonzero(np.diff(idx) > 1)
        starts = np.concatenate([[idx[0]], idx[br + 1]])
        ends = np.concatenate([idx[br], [idx[-1]]])
        runs = [(fm[a], fm[min(b + 1, fm.size - 1)]) for a, b in zip(starts, ends, strict=True)]
        merged = [list(runs[0])]
        for a, b in runs[1:]:
            gaps.append((a - merged[-1][1]) / H)
            if a - merged[-1][1] < MERGE_GAP_H * H:
                merged[-1][1] = b
            else:
                merged.append([a, b])
        spans = [[rc.iso(a), rc.iso(b)] for a, b in merged]
        rows.append({"q": int(q), "res": int(q % 17), "runs": len(runs), "spans": spans})
    order = {10: 0, 9: 1, 16: 2}
    rows.sort(key=lambda r: (order.get(r["res"], 9), r["q"]))
    return rows, np.quantile(np.array(gaps), [0.5, 0.9])


def session_t1_distance(dd: ddload.DD, s: rc.Sessions) -> np.ndarray:
    """Hours from each session start to the nearest ``T1`` round (as ``sessions.py``)."""
    t1_rounds = rs.stamp_rounds(dd, "q.T1")
    i = np.searchsorted(t1_rounds, s.start_ms)
    prev_gap = np.where(i > 0, (s.start_ms - t1_rounds[np.clip(i - 1, 0, None)]) / H, np.inf)
    next_gap = np.where(
        i < t1_rounds.size,
        (t1_rounds[np.clip(i, None, t1_rounds.size - 1)] - s.start_ms) / H,
        np.inf,
    )
    out: np.ndarray = np.minimum(prev_gap, next_gap)
    return out


def device_medians(s: rc.Sessions, ns: dict[str, rc.NoiseSeries]) -> dict[str, Any]:
    """Device median per session (median over qubits of log10), as ``spatial_temporal.py``."""
    big = np.flatnonzero(s.kind != "small")
    out: dict[str, Any] = {}
    for name in ("ro", "p0g1_fresh", "p1g0"):
        mat = np.full((s.start_ms.size, 156), np.nan)
        for x in ns[name].series:
            y = np.asarray(x.y)
            si = s.index(x.t_ms)
            ok = (si >= 0) & np.isfinite(y) & (y > 0)
            mat[si[ok], x.entity] = np.log10(y[ok])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            dev = np.nanmedian(mat[big], axis=1)
        ok = np.isfinite(dev)
        out[name] = (s.start_ms[big][ok], dev[ok])
    return out


def length_experiment(dd: ddload.DD, ns: dict[str, rc.NoiseSeries]) -> dict[str, Any]:
    """Per-qubit 7-day window medians of RO and the RO placebo, with ``length_changes.py``."""
    data = lc.per_qubit(ns["ro"], ("even", "mixed"))
    w = 24.0 * 7
    t_lo = float(dd.file_ms[0]) / H
    t_hi = float(dd.file_ms[-1]) / H
    avoid = [rc.iso_ms(cg[0]) / H for cg in lc.CHANGES]
    out: dict[str, Any] = {}
    for stamp, _, _ in lc.CHANGES:
        t0 = rc.iso_ms(stamp) / H
        before = lc.window_medians(data, t0 - w, t0 - lc.GUARD_H)
        after = lc.window_medians(data, t0 + lc.GUARD_H, t0 + w)
        out[stamp] = (before, after)
    out["placebo"] = lc.placebo(data, t_lo, t_hi, w, avoid)
    return out


def asym_placebo(dd: ddload.DD, r: rc.Readout) -> dict[str, Any]:
    """The verifier's A placebo (``v_extra.py`` probe 3), copied so it is not re-run on import."""
    ro, a, b, dro, da, db = r.ro, r.p0g1, r.p1g0, r.d_ro, r.d_p0g1, r.d_p1g0
    win = 10 * 60e3
    present = np.isfinite(ro) & np.isfinite(a) & np.isfinite(b)
    both = present & (np.abs(dro - da) <= win) & (np.abs(dro - db) <= win)
    asym = np.where(both, a - b, np.nan)
    rl = np.array(dd.v("q.readout_length"), dtype=np.float64)
    ch = np.flatnonzero(np.diff(np.nanmedian(rl, axis=1)) != 0) + 1

    def stamp_idx(e: int) -> np.ndarray:
        ok = np.flatnonzero(np.isfinite(ro[:, e]) & np.isfinite(dro[:, e]))
        x = dro[ok, e]
        out: np.ndarray = ok[np.concatenate([[True], x[1:] != x[:-1]])]
        return out

    t_ev, a_ev = [], []
    for e in range(156):
        i = stamp_idx(e)
        t_ev.append(dro[i, e])
        a_ev.append(asym[i, e])

    def dstat(tc: float, guard: float = 6.0) -> float | None:
        res = []
        for t, y in zip(t_ev, a_ev, strict=True):
            m = np.isfinite(y)
            t, y = t[m], y[m]
            bef = y[(t >= tc - 7 * DAY - guard * H) & (t < tc - guard * H)]
            aft = y[(t > tc + guard * H) & (t <= tc + 7 * DAY + guard * H)]
            if bef.size >= 3 and aft.size >= 3:
                res.append(np.median(aft) - np.median(bef))
        return float(np.median(res)) if len(res) >= 100 else None

    tc1, tc2 = float(dd.file_ms[ch[0]]), float(dd.file_ms[ch[1]])
    obs = dstat(tc1)
    first, last = float(np.nanmin(dro)), float(np.nanmax(dro))
    pl = []
    tc = first + 8 * DAY
    while tc < last - 8 * DAY:
        if abs(tc - tc1) > 15 * DAY and abs(tc - tc2) > 15 * DAY:
            v = dstat(tc)
            if v is not None:
                pl.append(v)
        tc += DAY
    return {"obs": obs, "placebo": np.array(pl)}


def asym_vs_decay(dd: ddload.DD, ns: dict[str, rc.NoiseSeries]) -> dict[str, np.ndarray]:
    """Per-qubit medians of A and of ``1 - exp(-t_ro/T1)``, exactly as ``t1_link.py``."""
    t1 = np.array(dd.v("q.T1"), dtype=np.float64)
    t_ro = np.array(dd.v("q.readout_length"), dtype=np.float64)
    q_, p0_, p1_, ro_, t1_, tro_ = [], [], [], [], [], []
    for a, b, x in zip(ns["p0g1_fresh"].series, ns["p1g0"].series, ns["ro"].series, strict=True):
        y0, y1 = np.asarray(a.y), np.asarray(b.y)
        ok = np.isfinite(y0) & np.isfinite(y1)
        f = a.file_idx[ok]
        q_.append(np.full(f.size, a.entity))
        p0_.append(y0[ok])
        p1_.append(y1[ok])
        ro_.append(np.asarray(x.y)[ok])
        t1_.append(t1[f, a.entity])
        tro_.append(t_ro[f, a.entity])
    q, p0, p1 = np.concatenate(q_), np.concatenate(p0_), np.concatenate(p1_)
    ro, tt1, tro = np.concatenate(ro_), np.concatenate(t1_), np.concatenate(tro_)
    good = np.isfinite(tt1) & (tt1 > 0)
    q, p0, p1, ro, tt1, tro = q[good], p0[good], p1[good], ro[good], tt1[good], tro[good]
    d_full = 1.0 - np.exp(-tro * 1e-3 / tt1)
    asym = p0 - p1
    qs = np.unique(q)
    return {
        "q": qs,
        "asym": np.array([np.median(asym[q == k]) for k in qs]),
        "d_full": np.array([np.median(d_full[q == k]) for k in qs]),
        "p0": np.array([np.median(p0[q == k]) for k in qs]),
        "ro": np.array([np.median(ro[q == k]) for k in qs]),
        "events": np.array([int(good.sum())]),
    }


def init_vs_p1g0(dd: ddload.DD, r: rc.Readout) -> dict[str, np.ndarray]:
    """Per-qubit lifetime medians of ``init_error`` and P(1|0), as ``thresholds_m2_init.py``."""
    v = np.array(dd.v("q.init_error"), dtype=np.float64)
    life = np.isfinite(v).any(axis=1)
    first = int(np.flatnonzero(life)[0])
    ok = np.isfinite(v)
    vm = np.where(ok & (v < 1e-6), np.nan, v)
    rows = np.zeros(v.shape[0], dtype=bool)
    rows[first:] = True
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        med_init = np.nanmedian(vm[first:], axis=0)
        med_p1 = np.nanmedian(np.where(rows[:, None], r.p1g0, np.nan), axis=0)
        med_ro = np.nanmedian(np.where(rows[:, None], r.ro, np.nan), axis=0)
    return {"init": med_init, "p1": med_p1, "ro": med_ro}


def m2_vs_ro(dd: ddload.DD, r: rc.Readout) -> dict[str, np.ndarray]:
    """Per-qubit medians of ``measure_2`` error and RO in its lifetime (placeholders masked)."""
    v = np.array(dd.v("g1.measure_2.gate_error"), dtype=np.float64)
    vm = np.where(v >= 1.0, np.nan, v)
    life = np.isfinite(v).any(axis=1)
    return {
        "m2": np.nanmedian(vm, axis=0),
        "ro": np.nanmedian(np.where(life[:, None], r.ro, np.nan), axis=0),
    }


# ---------------------------------------------------------------- text helpers


def pct(x: float, nd: int = 1) -> str:
    return f"%{x * 100:.{nd}f}".replace(".", ",")


def tr(x: float, fmt: str) -> str:
    """Number in Turkish prose form (decimal comma)."""
    return format(x, fmt).replace(".", ",")


def th(n: float) -> str:
    """Integer with a dot for thousands (Turkish)."""
    return f"{n:,.0f}".replace(",", ".")


# ---------------------------------------------------------------- charts


def build() -> dict[str, Any]:
    dd = ddload.DD()
    r = rc.load(dd)
    c = rc.record_classes(r)
    s = rc.sessions(r, c)
    ns = rc.noise_series(r, c, s)
    deg = degrees(dd)

    j_ses = load("readout/sessions.json")
    j_len = load("readout/length_changes.json")
    j_st = load("readout/spatial_temporal.json")
    j_t1 = load("readout/t1_link.json")
    j_thr = load("readout/thresholds_m2_init.json")
    j_x = load("verify/readout/extra_check.json")
    j_ll = load("verify/readout/length_link_check.json")
    j_rec = load("verify/readout/records_check.json")

    charts: list[dict[str, Any]] = []

    # 1. Stamp classes and the mean rule.
    rcl = j_ses["record_classes"]
    keys = ("same3", "staggered", "stale_p0g1", "other")
    check("same3 records", float(c["same3"].sum()), rcl["same3"]["records"], 0)
    check("staggered records", float(c["staggered"].sum()), rcl["staggered"]["records"], 0)
    check("stale records", float(c["stale_p0g1"].sum()), rcl["stale_p0g1"]["records"], 0)
    charts.append(
        {
            "id": "ro-stamp-classes",
            "type": "bar",
            "orient": "h",
            "title": (
                "RO, üç değeri aynı oturumdan gelen her kayıtta P(0|1) ile P(1|0)'ın ortalaması"
            ),
            "subtitle": (
                "274.560 kübit kaydı, `readout_error`, `prob_meas0_prep1` ve "
                "`prob_meas1_prep0` damgalarının ilişkisine göre dört sınıf; ikinci seri "
                "RO = (P(0|1) + P(1|0)) / 2 kuralının tuttuğu kayıtlar"
            ),
            "read": (
                "Özdeş damgalı 188.100 (%68,51) ve aynı oturumda kademeli damgalı 72.900 "
                "(%26,55) kaydın hepsinde kural tutar; kademelide P(0|1) RO'dan medyan 81 s, "
                "P(1|0) 41 s önce damgalanır. Kuralın bozulduğu 11.263 kaydın 11.258'i (%99,956) "
                "P(0|1)'i RO'dan medyan 11,57 saat eski olan bayat kayıtlardır."
            ),
            "source": (
                "03 §0 item 1, §1.3; results/readout/sessions.json: record_classes, stagger, "
                "stale_p0g1; reproduced in results/verify/readout/records_check.json"
            ),
            "x": {"label": "Kayıt sayısı", "scale": "linear"},
            "categories": [
                "Özdeş damgalar",
                "Kademeli (aynı oturum)",
                "Bayat P(0|1)",
                "Diğer",
            ],
            "series": [
                {"name": "Kayıt", "values": [rcl[k]["records"] for k in keys]},
                {
                    "name": "Ortalama kuralı tutan",
                    "values": [rcl[k]["mean_rule_holds"] for k in keys],
                },
            ],
        }
    )

    # 2. The rotating stale group.
    rows, gap_q = stale_spans(dd, c)
    groups = j_ses["stale_p0g1"]["groups_by_qubit_mod_17"]
    check("stale qubits >= 100", len(rows), j_ses["stale_p0g1"]["qubits_stale_ge_100_records"], 0)
    for res in (9, 10, 16):
        got = sorted(row["q"] for row in rows if row["res"] == res)
        check(f"group {res} matches", float(got == sorted(groups[str(res)]["qubits"])), 1.0, 0)
    glabel = {
        10: "kalan 10 (2026-05-13 ile 07-25)",
        9: "kalan 9 (2026-07-25 ile 08-25)",
        16: "kalan 16 (2026-08-25'ten beri)",
    }
    max_spans = max(len(row["spans"]) for row in rows)
    runs = sum(row["runs"] for row in rows)
    print(f"stale gantt: {len(rows)} rows, {runs} runs, at most {max_spans} merged spans in a row")
    print(f"  unmerged gaps between runs, median and 90%: {gap_q[0]:.2f} h, {gap_q[1]:.2f} h")
    fr = j_ses["stale_p0g1"]["group_qubit_p0g1_fresh_by_session_kind"]
    charts.append(
        {
            "id": "ro-stale-group",
            "type": "gantt",
            "title": (
                "P(0|1)'i gün içinde yenilenmeyen 9 kübitlik grup döner: indis mod 17 kalanı "
                "10, sonra 9, sonra 16"
            ),
            "subtitle": (
                "P(0|1)'in RO'dan 10 dakikadan eski olduğu dönemler; en az 100 bayat kaydı olan "
                "27 kübit, kalan sınıfına göre gruplu (toplam 11.515 bayat kayıt, 35 kübit). "
                f"Aralarında {MERGE_GAP_H:.0f} saatten kısa boşluk olan bayat dönemler "
                f"birleştirildi (boşlukların medyanı {tr(gap_q[0], '.1f')} saat)"
            ),
            "read": (
                "Her grup aynı 17 kalanındaki 9 kübittir ve geçişler 2026-07-25 ile 2026-08-25'te "
                "olur. Birleştirilen boşluklar P(0|1)'in yeniden taze olduğu kısa aralardır ve "
                f"neredeyse hepsi günlük oturumlardan gelir: grubun P(0|1)'i günlük oturumlarda "
                f"{th(fr['even']['events'])} olayın "
                f"{th(fr['even']['fresh'])}'sında taze, gün içi oturumlarda "
                f"{th(fr['mixed']['events'])} olayın yalnızca {fr['mixed']['fresh']}'unda. "
                "`meas_map` 156 kübitin tek grubudur, gruplamayı açıklamaz."
            ),
            "caveat": (
                "Mekanizma bir çıkarımdır. `2 RO - P(1|0)` değerinin 1/4096 ızgarasına düşmesi "
                "kanıt sayılmaz: RO 1/8192, P(1|0) 1/4096 ızgarasında olduğu için test aritmetik "
                "olarak başarısız olamaz (karıştırılmış P(0|1) ile de %100). Veri yalnızca örtük "
                "değerin bayat değerle tutarlı olduğunu gösterir (medyan oran 1,01). Taze/bayat "
                "sayımı doğrulamada yeniden üretilmedi."
            ),
            "source": (
                "03 §0 item 2, §6, Verification; results/readout/sessions.json: stale_p0g1; "
                "results/verify/readout/records_check.json"
            ),
            "x": {"label": "Tarih (UTC)", "scale": "time"},
            "markers": [
                {
                    "axis": "x",
                    "value": stem_iso(groups["9"]["first_file"]),
                    "label": "10 -> 9",
                },
                {
                    "axis": "x",
                    "value": stem_iso(groups["16"]["first_file"]),
                    "label": "9 -> 16",
                },
            ],
            "rows": [
                {"label": f"q{row['q']}", "group": glabel[row["res"]], "spans": row["spans"]}
                for row in rows
            ],
        }
    )
    check(
        "records_check median ratio",
        j_rec["recovered_vs_published_stale_median_ratio"],
        1.01,
        0.001,
    )

    # 3. Session parity.
    big = s.kind != "small"
    es = s.even_share[big]
    edges = [round(0.4 + 0.025 * k, 3) for k in range(26)]
    counts = np.histogram(es, bins=edges)[0]
    check("sessions >= 100 qubits", float(big.sum()), 589, 0)
    check("even sessions", float(np.sum(s.kind == "even")), 123, 0)
    check("last parity bin = 123", float(counts[-1]), 123, 0)
    check(
        "mixed even share median", float(np.median(s.even_share[s.kind == "mixed"])), 0.498, 0.001
    )
    charts.append(
        {
            "id": "ro-session-parity",
            "type": "hist",
            "title": (
                "İki tür okuma oturumu var: 123 oturumda yayımlanan her sayım çift, 466 oturumda "
                "yaklaşık yarısı"
            ),
            "subtitle": (
                "En az 100 kübitli 589 oturumun her birinde yayımlanan sayımların (4096 x p, "
                "P(0|1) ve P(1|0)) çift olan payı; 0,025 genişlikli kutular"
            ),
            "read": (
                "Sağ uçtaki çubuk (pay tam 1, bütün değerler 1/2048 ızgarasında) 123 oturumdur; "
                "kalan 466 oturum 0,5 çevresinde toplanır (medyan 0,498). Rastgele bir binom "
                "sayımın çift olma olasılığı yaklaşık yarıdır."
            ),
            "caveat": (
                "Çift oturumların durum başına 2.048 atış kullandığı ızgaranın doğal okumasıdır, "
                "ama iki varyans testi bunu çözmüyor; günlük oturumların atış sayısı açık. "
                "Belgedeki 2^-312 şans olasılığı bağımsız ve adil parite varsayar; küçük sayımlar "
                "ve sıfırlar adil değildir (doğrulama)."
            ),
            "source": (
                "03 §0 item 3, §1.3, §4.5, Verification; results/readout/sessions.json: sessions"
            ),
            "x": {"label": "Çift sayımların payı", "scale": "linear", "min": 0.4, "max": 1.025},
            "y": {"label": "Oturum", "scale": "linear"},
            "series": [{"name": "Oturumlar", "edges": edges, "counts": counts.tolist()}],
        }
    )

    # 4. Distance of sessions to T1 rounds.
    near = session_t1_distance(dd, s)
    ev_mask, mx_mask = s.kind == "even", s.kind == "mixed"
    share_e = float(np.mean(near[ev_mask] <= 3.0))
    share_m = float(np.mean(near[mx_mask] <= 3.0))
    check(
        "even within 3h of T1",
        share_e,
        j_ses["sessions"]["share_within_3h_of_t1_round"]["even"],
        1e-4,
    )
    check(
        "mixed within 3h of T1",
        share_m,
        j_ses["sessions"]["share_within_3h_of_t1_round"]["mixed"],
        1e-4,
    )
    t_edges = list(range(26))
    eh = j_ses["sessions"]["start_hour_utc_counts"]["even"]
    check("even sessions starting 18-23 UTC", float(sum(eh[18:24])), 61, 0)
    charts.append(
        {
            "id": "ro-session-t1",
            "type": "hist",
            "title": (
                "Çift oturumlar günlük `T1` turunun hemen yanında, karışık oturumlar gün boyuna "
                "yayılıyor"
            ),
            "subtitle": (
                "Oturum başlangıcından en yakın `T1` turuna (133 tur) saat; 123 çift ve 466 "
                "karışık oturum, 1 saatlik kutular"
            ),
            "read": (
                f"Çift oturumların {pct(share_e)}'ı bir `T1` turuna 3 saatten yakın başlar, "
                f"karışıkların {pct(share_m)}'si. Çift oturumların 61'i UTC 18:00 ile 23:59 "
                "arasında başlar ve günde yaklaşık bir tane görülür (aya göre 0,71 ile 1,08). "
                "Bu, çift oturumların günlük `T1`, `T2` ve `measure_2` turunun parçası, "
                "karışıkların gün içi yeniden ölçüm olduğu okumasıyla uyumludur."
            ),
            "caveat": (
                "Hangi IBM işinin hangi alanı yazdığı belgelenmemiştir; oturum türlerinin "
                "günlük tur ve gün içi izleme olarak okunması verilerden çıkarımdır."
            ),
            "source": "03 §0 item 3, §1.3; results/readout/sessions.json: sessions",
            "x": {"label": "En yakın T1 turuna uzaklık", "scale": "linear", "unit": "saat"},
            "y": {"label": "Oturum", "scale": "linear"},
            "series": [
                {
                    "name": "Çift (günlük) oturumlar",
                    "edges": t_edges,
                    "counts": np.histogram(near[ev_mask], bins=t_edges)[0].tolist(),
                },
                {
                    "name": "Karışık (gün içi) oturumlar",
                    "edges": t_edges,
                    "counts": np.histogram(near[mx_mask], bins=t_edges)[0].tolist(),
                },
            ],
        }
    )

    # 5. Device median per session over time.
    dm = device_medians(s, ns)
    t_ro, v_ro = dm["ro"]
    q_doc = j_st["temporal"]["ro_device_median_per_session"]["q"]
    check("device sessions", float(t_ro.size), 589, 0)
    check("device RO min", 10 ** float(v_ro.min()), q_doc[0], 2e-6)
    check("device RO median", 10 ** float(np.median(v_ro)), q_doc[2], 2e-6)
    check("device RO max", 10 ** float(v_ro.max()), q_doc[4], 2e-6)
    cps = stp.binseg(v_ro, min_seg=15)
    cps_doc = [
        cp["session_start"]
        for cp in j_st["temporal"]["ro_device_median_per_session"]["change_points"]
    ]
    check("binseg change points equal", float([rc.iso(t_ro[k]) for k in cps] == cps_doc), 1.0, 0)
    bounds = [0, *cps, v_ro.size]
    step = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        lvl = g4(10 ** float(np.median(v_ro[a:b])))
        step.append([iso_min(t_ro[a]), lvl])
        step.append([iso_min(t_ro[b - 1] if b == v_ro.size else t_ro[b]), lvl])

    def pts(name: str) -> list[list[Any]]:
        t, v = dm[name]
        return [[iso_min(tt), g4(10 ** float(vv))] for tt, vv in zip(t, v, strict=True)]

    charts.append(
        {
            "id": "ro-device-timeline",
            "type": "line",
            "title": (
                "Cihaz düzeyindeki okuma hatasının çoğu haziran ortasından önce düştü, sonra "
                "yavaşça kaydı"
            ),
            "subtitle": (
                "Oturum başına cihaz medyanı (kübitler üzerinden medyan), en az 100 kübitli 589 "
                "oturum; RO için ikili bölütleme segment düzeyleri; log ölçek"
            ),
            "read": (
                "RO oturum medyanı 0,00775 ile 0,0237 arasında (medyan 0,00946). İkili bölütleme "
                "RO'da altı kırılma bulur; 2026-06-08 uzunluk değişikliğinden sonraki ilk "
                "oturumda RO düzeyi 0,0120'den 0,00876'ya, P(1|0) düzeyi 0,00903'ten 0,00488'e "
                "iner. 2026-07-30 değişikliğinde kırılma yok."
            ),
            "caveat": (
                "Kırılma noktaları betimseldir (ceza ve en kısa segment birer seçimdir). "
                "06-08 düşüşü 'tek açık istisna' değildir: en büyük düşüş 2026-05-17'de "
                "(10 turluk pencerede -0,20 dekad) bilinen bir olay olmadan görülür ve 06-08/09 "
                "aynı zamanda günlük takvimin yeniden başladığı bir tarihtir (06 doğrulaması)."
            ),
            "source": (
                "03 §3.1; 06 §3.5 and Verification; 00 §4.6; "
                "results/readout/spatial_temporal.json: temporal"
            ),
            "x": {"label": "Oturum başlangıcı (UTC)", "scale": "time"},
            "y": {"label": "Hata olasılığı", "scale": "log"},
            "markers": [
                {"axis": "x", "value": "2026-05-17T13:53:44Z", "label": "05-17: bilinen olay yok"},
                {"axis": "x", "value": rc.CHANGE_1, "label": "t_ro 1.560 -> 1.700 ns"},
                {"axis": "x", "value": rc.CHANGE_2, "label": "t_ro 1.700 -> 1.660 ns"},
            ],
            "series": [
                {"name": "RO", "points": pts("ro"), "style": "dots"},
                {"name": "P(0|1)", "points": pts("p0g1_fresh"), "style": "dots"},
                {"name": "P(1|0)", "points": pts("p1g0"), "style": "dots"},
                {"name": "RO segment düzeyi", "points": step, "style": "line"},
            ],
        }
    )

    # 6. Per-qubit before and after each length change.
    le = length_experiment(dd, ns)
    w1 = j_len["changes"][0]["windows"]["7d"]["ro_all_sessions"]
    w2 = j_len["changes"][1]["windows"]["7d"]["ro_all_sessions"]
    series6 = []
    for (stamp, lo_ns, hi_ns), doc in zip(lc.CHANGES, (w1, w2), strict=True):
        before, after = le[stamp]
        ok = np.isfinite(before) & np.isfinite(after) & (before > 0) & (after > 0)
        d = np.log10(after[ok] / before[ok])
        check(
            f"{stamp[:10]} median log10",
            float(np.median(d)),
            doc["median_log10_after_over_before"],
            6e-5,
        )
        check(f"{stamp[:10]} share up", float(np.mean(d > 0)), doc["share_qubits_up"], 6e-5)
        check(
            f"{stamp[:10]} device before",
            float(np.median(before[ok])),
            doc["device_median_before"],
            1e-6,
        )
        check(
            f"{stamp[:10]} device after",
            float(np.median(after[ok])),
            doc["device_median_after"],
            1e-6,
        )
        series6.append(
            {
                "name": f"{stamp[:10]} ({th(lo_ns)} -> {th(hi_ns)} ns)",
                "points": [[g4(before[q]), g4(after[q]), f"q{q}"] for q in np.flatnonzero(ok)],
            }
        )
    charts.append(
        {
            "id": "ro-length-before-after",
            "type": "scatter",
            "title": (
                "2026-06-08'de kübitlerin %98'inde RO düştü; 2026-07-30'da noktalar köşegende kaldı"
            ),
            "subtitle": (
                "Kübit başına medyan RO, değişiklikten önceki ve sonraki 7 günlük pencere (6 saat "
                "koruma payı), 156 kübit, her değişiklik bir seri; log-log, çizgi y = x"
            ),
            "read": (
                "06-08'de (1.560 -> 1.700 ns) medyan değişim -0,137 dekad, yalnızca 3 kübit "
                "(%1,9) yükseldi ve cihaz medyanı 0,0114'ten 0,00806'ya indi (Wilcoxon p = "
                "9,4e-26). 07-30'da (1.700 -> 1.660 ns) medyan değişim +0,003 dekad, kübitlerin "
                "%53,9'u yükseldi (p = 0,14)."
            ),
            "caveat": (
                "`measure.threshold` alanı ilk kez 06-08 değişikliğiyle aynı dosyada görünür ve "
                "sıfırlama süresi de t_ro ile birlikte değişti: uzunluk ile ayırt etme "
                "prosedürünün daha geniş bir değişikliği arşivde ayrılamaz."
            ),
            "source": "03 §0 items 7 and 8, §7.4; results/readout/length_changes.json: changes",
            "x": {"label": "Önceki 7 gün, medyan RO", "scale": "log"},
            "y": {"label": "Sonraki 7 gün, medyan RO", "scale": "log"},
            "diag": True,
            "series": series6,
        }
    )

    # 7. RO placebo distribution.
    pl = le["placebo"]
    pq = np.quantile(pl, [0.05, 0.5, 0.95])
    check("placebo days", float(pl.size), w1["placebo_days"], 0)
    for k, v in enumerate(w1["placebo_q05_q50_q95"]):
        check(f"placebo q{k}", float(pq[k]), v, 6e-5)
    p_edges = [round(-0.15 + 0.01 * k, 2) for k in range(22)]
    p_counts = np.histogram(np.clip(pl, -0.1499, 0.0599), bins=p_edges)[0]
    check("placebo inside hist range", float(pl.min() > -0.15 and pl.max() < 0.06), 1.0, 0)
    pl_min, pl_max = float(pl.min()), float(pl.max())
    charts.append(
        {
            "id": "ro-length-placebo",
            "type": "hist",
            "title": (
                "06-08 düşüşüne 104 plasebo gününün hiçbiri ulaşmıyor; 07-30 değişimi sıradan "
                "günlerin arasında"
            ),
            "subtitle": (
                "Aynı istatistik (kübitler üzerinden medyan log10(sonra/önce), 7 günlük "
                "pencereler) arşivin diğer her gününde: değişikliklere bir pencereden yakın "
                "günler hariç 104 plasebo günü, 0,01 dekadlık kutular"
            ),
            "read": (
                "Plasebo günlerinin %5 ile %95 aralığı -0,039 ile +0,030 dekad, uçları "
                f"{tr(pl_min, '+.3f')} ve {tr(pl_max, '+.3f')}. 06-08'de gözlenen -0,137, hiçbir "
                "plasebo günü bu büyüklüğe ulaşmıyor; 07-30'da gözlenen +0,003."
            ),
            "caveat": (
                "Doğrulayıcının daha sıkı dışlamasıyla (70 gün) plasebo en küçüğü -0,084; RO "
                "düşüşü yine dışarıda. Plasebo arşivin ilk haftasını kapsayamaz: 2026-05-17'deki "
                "daha büyük düşüş (farklı bir pencere istatistiğiyle -0,20 dekad) bu dağılımda yok."
            ),
            "source": (
                "03 §7.4 and Verification; results/readout/length_changes.json; "
                "results/verify/readout/length_link_check.json: placebo7; 06 Verification"
            ),
            "x": {"label": "Medyan log10(sonra/önce)", "scale": "linear", "unit": "dekad"},
            "y": {"label": "Plasebo günü", "scale": "linear"},
            "markers": [
                {
                    "axis": "x",
                    "value": w1["median_log10_after_over_before"],
                    "label": "06-08: -0,137",
                },
                {
                    "axis": "x",
                    "value": w2["median_log10_after_over_before"],
                    "label": "07-30: +0,003",
                },
            ],
            "series": [{"name": "Plasebo günleri", "edges": p_edges, "counts": p_counts.tolist()}],
        }
    )
    check("verifier placebo min", j_ll["placebo7"]["min"], -0.084, 1e-9)

    # 8. Forest of the two experiments with placebo ranges.
    ch1, ch2 = (j_len["changes"][k]["windows"]["7d"] for k in (0, 1))
    frows = []
    for label, key in (
        ("RO", "ro_all_sessions"),
        ("P(0|1)", "p0g1_fresh_all_sessions"),
        ("P(1|0)", "p1g0_all_sessions"),
    ):
        q05, q50, q95 = ch1[key]["placebo_q05_q50_q95"]
        frows += [
            {
                "label": f"{label} · 06-08",
                "est": ch1[key]["median_log10_after_over_before"],
                "group": "2026-06-08",
            },
            {
                "label": f"{label} · 07-30",
                "est": ch2[key]["median_log10_after_over_before"],
                "group": "2026-07-30",
            },
            {
                "label": f"{label} · plasebo",
                "est": q50,
                "lo": q05,
                "hi": q95,
                "group": "Plasebo (%5, medyan, %95)",
            },
        ]
    t1q = ch1["t1_control"]["placebo_q05_q50_q95"]
    frows += [
        {
            "label": "T1 · 06-08",
            "est": ch1["t1_control"]["median_log10_after_over_before"],
            "group": "2026-06-08",
        },
        {
            "label": "T1 · 07-30",
            "est": ch2["t1_control"]["median_log10_after_over_before"],
            "group": "2026-07-30",
        },
        {
            "label": "T1 · plasebo",
            "est": t1q[1],
            "lo": t1q[0],
            "hi": t1q[2],
            "group": "Plasebo (%5, medyan, %95)",
        },
    ]
    charts.append(
        {
            "id": "ro-length-forest",
            "type": "forest",
            "title": "06-08'de P(1|0) P(0|1)'den üç kat fazla düştü; `T1` yerinden oynamadı",
            "subtitle": (
                "Kübitler üzerinden medyan log10(sonra/önce), 7 günlük pencereler, 156 kübit "
                "(`T1` için 153 ile 155); plasebo satırı diğer günlerin %5, medyan ve %95 değeri"
            ),
            "read": (
                "06-08'de RO -0,137, P(0|1) -0,079, P(1|0) -0,269 dekad; üçü de plasebo "
                "aralığının dışında (P(0|1) sınıra en yakın). `T1` -0,017 ile kendi plasebo "
                "aralığında (-0,051 ile +0,108). 07-30'da dört değişimin hepsi sıfıra yakın ve "
                "plasebo aralığında."
            ),
            "caveat": (
                "Daha uzun entegrasyonun iki bulutu daha iyi ayırması bir okumadır; aynı tarihteki "
                "prosedür değişikliği de verilerle aynı ölçüde tutarlıdır."
            ),
            "source": "03 §7.4; results/readout/length_changes.json: changes[*].windows.7d",
            "x": {"label": "Medyan log10(sonra/önce)", "scale": "linear", "unit": "dekad"},
            "ref": 0,
            "rows": frows,
        }
    )

    # 9. Asymmetry placebo (verifier's definition).
    ap = asym_placebo(dd, r)
    apl = ap["placebo"]
    xa = j_x["A_placebo_7d"]
    check("A obs (verifier)", ap["obs"], j_x["A_change_at_first_length_change_7d"], 6e-6)
    check("A placebo days", float(apl.size), xa["days"], 0)
    check("A placebo q05", float(np.quantile(apl, 0.05)), xa["q05"], 6e-6)
    check("A placebo q95", float(np.quantile(apl, 0.95)), xa["q95"], 6e-6)
    check("A placebo max", float(apl.max()), xa["max"], 6e-6)
    a_edges = [round(-0.0025 + 0.00025 * k, 5) for k in range(19)]
    check("A placebo inside range", float(apl.min() > -0.0025 and apl.max() < 0.002), 1.0, 0)
    charts.append(
        {
            "id": "ro-asym-placebo",
            "type": "hist",
            "title": "06-08'de asimetrinin artışı sıradan günlerin aralığından çıkmıyor",
            "subtitle": (
                "A = P(0|1) - P(1|0) için kübitler üzerinden medyan (sonra - önce), 7 günlük "
                "pencereler; doğrulayıcının tanımıyla 70 plasebo günü, gözlenen değer ve "
                "yalnız uzunluktan beklenen bozunma artışı"
            ),
            "read": (
                "Gözlenen +0,00146; plasebo %5 ile %95 aralığı -0,00146 ile +0,00129, en büyük "
                "plasebo +0,00153. `T1` sabit tutulunca tam pencere +0,00093, yarım pencere "
                "+0,00047 artış öngörür; gözlenen bunların 1,6 ve 3,1 katıdır."
            ),
            "caveat": (
                "Belgenin 'A öngörülen düzeyde arttı' okuması doğrulamada zayıfladı: sahip "
                "betiğinin Wilcoxon p değeri (7,5e-16, artış +0,0016) bir uzunluk etkisi "
                "göstermez, çünkü aynı istatistik sıradan günlerde de bu kadar oynar."
            ),
            "source": (
                "03 §7.2, §7.4 and Verification; results/verify/readout/extra_check.json; "
                "results/readout/length_changes.json: asymmetry_p0g1_minus_p1g0"
            ),
            "x": {"label": "Medyan A değişimi (sonra - önce)", "scale": "linear"},
            "y": {"label": "Plasebo günü", "scale": "linear"},
            "markers": [
                {
                    "axis": "x",
                    "value": j_x["predicted_dA_half_window_median"],
                    "label": "yarım pencere",
                },
                {
                    "axis": "x",
                    "value": j_x["predicted_dA_full_window_median"],
                    "label": "tam pencere",
                },
                {
                    "axis": "x",
                    "value": j_x["A_change_at_first_length_change_7d"],
                    "label": "gözlenen",
                },
            ],
            "series": [
                {
                    "name": "Plasebo günleri",
                    "edges": a_edges,
                    "counts": np.histogram(apl, bins=a_edges)[0].tolist(),
                }
            ],
        }
    )

    # 10. A against decay across qubits.
    ad = asym_vs_decay(dd, ns)
    bq = j_t1["between_qubits"]
    rho = stats.spearmanr(ad["asym"], ad["d_full"]).statistic
    ts = stats.theilslopes(ad["asym"], ad["d_full"])
    check("A vs decay spearman", float(rho), bq["spearman_asymmetry_vs_decay"]["rho"], 6e-5)
    check(
        "P01 vs decay spearman",
        float(stats.spearmanr(ad["p0"], ad["d_full"]).statistic),
        bq["spearman_p0g1_vs_decay"]["rho"],
        6e-5,
    )
    check(
        "Theil-Sen slope", float(ts.slope), bq["theil_sen_asymmetry_on_decay_full"]["slope"], 6e-5
    )
    check("t1 link events", float(ad["events"][0]), j_t1["events"], 0)
    shown = ad["q"] != 72  # q72 (decay 0.179, A 0.274) would compress the other 155 points
    check("q72 is the largest-decay qubit", float(ad["q"][np.argmax(ad["d_full"])]), 72, 0)
    lo_x, hi_x = float(ad["d_full"][shown].min()), float(ad["d_full"][shown].max())
    q72_x = float(ad["d_full"][~shown][0])
    q72_y = float(ad["asym"][~shown][0])
    a_lo, a_hi = float(ad["asym"][shown].min()), float(ad["asym"][shown].max())
    print(f"A shown {a_lo:.4g}..{a_hi:.4g}; x {lo_x:.4g}..{hi_x:.4g}")
    slope = bq["theil_sen_asymmetry_on_decay_full"]["slope"]
    icpt = bq["theil_sen_asymmetry_on_decay_full"]["intercept"]
    charts.append(
        {
            "id": "ro-asym-vs-decay",
            "type": "scatter",
            "title": (
                "Okuma sırasındaki bozunma kübitler arasında asimetride görünüyor, P(0|1)'in "
                "kendisinde görünmüyor"
            ),
            "subtitle": (
                "Kübit başına medyan A = P(0|1) - P(1|0) ile beklenen bozunma 1 - exp(-t_ro/`T1`) "
                "(aynı dosyadaki `T1` ve t_ro), 91.710 oturum olayı; 155 kübit gösteriliyor, "
                f"q72 (bozunma {tr(q72_x, '.3f')}, A {tr(q72_y, '.3f')}) ölçeği sıkıştıracağı "
                "için dışarıda; koyu çizgi Theil-Sen uyumu, ince çizgi y = x (tam pencere)"
            ),
            "read": (
                "156 kübitin hepsiyle Spearman 0,423 (p = 3,9e-8), Theil-Sen eğimi 0,310 (%95 "
                "GA 0,209 ile 0,437); A kübitlerin %96,2'sinde tam pencere bozunmasının altında, "
                "medyan A/bozunma oranı 0,464. Aynı karşılaştırma P(0|1) için 0,016: P(0|1) ile "
                "P(1|0) büyük bir ortak örtüşme hatasını paylaşır (kübitler arası 0,908) ve fark "
                "almak onu siler."
            ),
            "caveat": (
                "Etkin bozunma süresinin pencerenin yarısı olduğu okuması desteklenmez: uzunluk "
                "deneyi tam pencere tahmininin 1,6, yarım pencerenin 3,1 katını verir, ve artık "
                "uyarılmış nüfus A'yı düşürdüğü için 0,46 oranı etkin süreyi belirlemez. Düşük "
                "hatalı yarıda (80 kübit) ilişki zayıflar (0,159, p = 0,16). Kübit içinde günlük "
                "`T1` değişimleri P(0|1)'i oynatmaz (-0,014)."
            ),
            "source": (
                "03 §0 item 9, §7.2 and Verification; results/readout/t1_link.json: "
                "between_qubits, within_qubits_even_sessions; results/verify/readout/"
                "extra_check.json"
            ),
            "x": {"label": "Beklenen bozunma 1 - exp(-t_ro/T1)", "scale": "linear"},
            "y": {"label": "Medyan A = P(0|1) - P(1|0)", "scale": "linear"},
            "diag": True,
            "fit": [[g4(lo_x), g4(icpt + slope * lo_x)], [g4(hi_x), g4(icpt + slope * hi_x)]],
            "series": [
                {
                    "name": "Kübitler",
                    "points": [
                        [g4(x), g4(y), f"q{q}"]
                        for q, x, y in zip(ad["q"], ad["d_full"], ad["asym"], strict=True)
                        if q != 72
                    ],
                }
            ],
        }
    )

    # 11. init_error against P(1|0).
    iv = init_vs_p1g0(dd, r)
    ok = np.isfinite(iv["init"]) & np.isfinite(iv["p1"]) & (iv["p1"] > 0)
    ji = j_thr["init_error"]
    check("init qubits", float(ok.sum()), 116, 0)
    check(
        "init vs p1g0 spearman",
        float(stats.spearmanr(iv["init"][ok], iv["p1"][ok]).statistic),
        ji["between_qubit_spearman_medians"]["init_vs_p1g0"]["rho"],
        6e-5,
    )
    never = ~np.isfinite(iv["init"])
    check(
        "never-present RO median",
        float(np.median(iv["ro"][never])),
        ji["never_present_vs_others_median_ro"][0],
        1e-6,
    )
    charts.append(
        {
            "id": "ro-init-vs-p1g0",
            "type": "scatter",
            "title": (
                "`init_error` kübitler arasında P(1|0)'ı izliyor; P(1|0) tipik olarak onun iki katı"
            ),
            "subtitle": (
                "Kübit başına medyan, 2026-08-04'ten itibaren; `init_error` taşıyan 116 kübit "
                "(1e-6 altındaki 540 dejenere değer maskeli); log-log, çizgi y = x"
            ),
            "read": (
                "Spearman 0,822; aynı oturumdaki kayıtlarda kübit içinde 0,722 (109 kübit, 4.938 "
                "kayıt). P(1|0)/`init_error` medyanı 1,95 ve kayıtların %14,8'inde P(1|0) daha "
                "küçük. Hiç `init_error` taşımayan 40 kübitin medyan RO'su 0,0331, diğerlerinin "
                "0,0071 (p = 1,3e-20)."
            ),
            "caveat": (
                "IBM tanımı 'önceki deney kübiti |1> durumunda hazırladıysa' koşulunu da içerir; "
                "artık |1> nüfusunun P(1|0)'a doğrudan eklendiği okuması çıkarımdır. 40 kübit "
                "karşılaştırması doğrulayıcının medyan tanımıyla 0,0314'e karşı 0,0076."
            ),
            "source": (
                "03 §0 item 10, §7.1, §7.3, Verification; results/readout/thresholds_m2_init.json: "
                "init_error"
            ),
            "x": {"label": "Medyan init_error", "scale": "log"},
            "y": {"label": "Medyan P(1|0)", "scale": "log"},
            "diag": True,
            "series": [
                {
                    "name": "Kübitler",
                    "points": [
                        [g4(iv["init"][q]), g4(iv["p1"][q]), f"q{q}"] for q in np.flatnonzero(ok)
                    ],
                }
            ],
        }
    )

    # 12. measure_2 against RO.
    mv = m2_vs_ro(dd, r)
    jm = j_thr["measure_2"]
    check(
        "m2 vs ro spearman",
        float(stats.spearmanr(mv["m2"], mv["ro"]).statistic),
        jm["spearman_per_qubit_medians_m2_vs_ro"]["rho"],
        6e-5,
    )
    check(
        "m2 above ro share",
        float(np.mean(mv["m2"] > mv["ro"])),
        jm["share_qubits_m2_above_ro"],
        6e-5,
    )
    charts.append(
        {
            "id": "ro-m2-vs-ro",
            "type": "scatter",
            "title": "`measure_2` hatası RO'yu izliyor ama kübitlerin %60'ında daha kötü",
            "subtitle": (
                "Kübit başına medyan `measure_2` hatası (1.340 ns, orta-devre ölçüm komutu) ile "
                "aynı dosyalardaki medyan RO, 156 kübit, 2026-08-07'den itibaren (yer tutucu "
                "dosyalar maskeli); log-log, çizgi y = x"
            ),
            "read": (
                "Spearman 0,852; `measure_2`/RO oranının medyanı 1,25 (%10: 0,79, %90: 2,87) ve "
                "kübitlerin %60,3'ü köşegenin üstünde. Kübit içinde ilişki daha zayıf (0,382, "
                "8.112 olay). `measure_2` günde bir kez ölçülür: 52 turun %90,4'ü bir çift "
                "oturuma 1 saatten yakın."
            ),
            "source": "03 §0 item 11, §7.1; results/readout/thresholds_m2_init.json: measure_2",
            "x": {"label": "Medyan RO (measure)", "scale": "log"},
            "y": {"label": "Medyan measure_2 hatası", "scale": "log"},
            "diag": True,
            "series": [
                {
                    "name": "Kübitler",
                    "points": [[g4(mv["ro"][q]), g4(mv["m2"][q]), f"q{q}"] for q in range(156)],
                }
            ],
        }
    )

    # 13. Thresholds against session kinds.
    sk = j_thr["thresholds"]["sessions_whose_interval_file_changes_threshold"]
    mt = j_thr["thresholds"]["g1.measure.threshold"]
    thv = np.array(dd.v("g1.measure.threshold"), dtype=np.float64)
    both = np.isfinite(thv[1:]) & np.isfinite(thv[:-1])
    n_chg = np.sum((thv[1:] != thv[:-1]) & both, axis=1)
    n_chg = n_chg[both.any(axis=1)]
    check("threshold change files", float(np.sum(n_chg > 0)), mt["change_files"], 0)
    check("threshold partial files", float(np.sum((n_chg > 0) & (n_chg < 156))), 0, 0)
    charts.append(
        {
            "id": "ro-threshold-sessions",
            "type": "stack",
            "title": (
                "Eşikler cihaz çapında hep birlikte güncelleniyor ve çoğunlukla gün içi "
                "oturumlarla geliyor"
            ),
            "subtitle": (
                "`measure.threshold` ömrü boyunca (2026-06-08'den itibaren) oturumlar, oturumun "
                "düştüğü dosya aralığında eşiğin değişip değişmediğine göre; 343 gün içi ve 97 "
                "günlük oturum"
            ),
            "read": (
                f"Gün içi oturumların {sk['mixed']['with_change']}'i "
                f"({pct(sk['mixed']['with_change'] / sk['mixed']['sessions'])}), günlük "
                f"oturumların {sk['even']['with_change']}'si "
                f"({pct(sk['even']['with_change'] / sk['even']['sessions'])}) eşiği değiştiren "
                "bir dosyaya düşer. 327 değişiklik dosyasının her birinde 156 kübitin hepsi "
                "değişir; `measure` ve `measure_reset` eşikleri ortak 127.452 kaydın hepsinde "
                "aynıdır."
            ),
            "caveat": (
                "Eşik alanı montaj damgalıdır: bir değişiklik yalnızca iki ardışık dosya arasına "
                "yerleştirilebilir ve 99 değişiklik dosyasının aralığında hiç okuma oturumu "
                "yoktur. Eşik, IBM'in her kalibrasyonda yeniden tanımladığı bir izdüşüm boyunca "
                "konumdur; kendi başına kararlı bir fiziksel düzey değildir (değerlerin %84,6'sı "
                "negatif, 147 kübitte işaret değiştirir)."
            ),
            "source": (
                "03 §0 item 12, §7.1, §6; results/readout/thresholds_m2_init.json: thresholds"
            ),
            "x": {"label": "Oturum türü", "scale": "band"},
            "y": {"label": "Oturum", "scale": "linear"},
            "categories": ["Gün içi (karışık) oturumlar", "Günlük (çift) oturumlar"],
            "series": [
                {
                    "name": "Eşiği değiştiren dosyaya düşen",
                    "values": [sk["mixed"]["with_change"], sk["even"]["with_change"]],
                },
                {
                    "name": "Eşik değişmeyen",
                    "values": [
                        sk["mixed"]["sessions"] - sk["mixed"]["with_change"],
                        sk["even"]["sessions"] - sk["even"]["with_change"],
                    ],
                },
            ],
        }
    )

    # 14. Device map of median RO with degree-3 flags.
    med = stp.per_qubit_median(ns["ro"])
    check(
        "map median of medians",
        10 ** float(np.median(med)),
        j_st["spatial"]["ro"]["median_of_medians"],
        1e-6,
    )
    check(
        "degree counts 8/100/48",
        float([int(np.sum(deg == k)) for k in (1, 2, 3)] == [8, 100, 48]),
        1.0,
        0,
    )
    charts.append(
        {
            "id": "ro-device-map",
            "type": "map",
            "title": (
                "Kübit başına medyan RO: komşular arasındaki zıtlık büyük ölçüde derece "
                "sınıfından geliyor"
            ),
            "subtitle": (
                "Kübit başına medyan RO (bütün okuma oturumu olayları), 156 kübit; kırmızı "
                "çerçeve derece 3 kübitler (48), çerçevesizler derece 2 (100) ve derece 1 (8); "
                "log renk ölçeği"
            ),
            "read": (
                "Medyanların medyanı 0,00903 (%10: 0,00562, %90: 0,0412); en kötüler q72 (0,350), "
                "q83 (0,126), q43, q131, q113. Ham Moran's I -0,196 (p = 0,007); her derece "
                "sınıfının medyanı çıkarılınca -0,047 (p = 0,59). Satır veya sütun eğilimi yok "
                "ve sıralama kararlı (haziran ile eylül, Spearman 0,926)."
            ),
            "caveat": (
                "Belgenin 'dama tahtası' bulgusu ve frekans tahsisi okuması doğrulamada "
                "zayıfladı: heavy-hex örgüde derece 3 ve derece 2 kübitler sırayla dizildiği için "
                "komşu zıtlığı büyük ölçüde derece etkisidir. `measure_2` için (Moran's I -0,430) "
                "derece testi yapılmadı."
            ),
            "source": (
                "03 §0 item 14, §5, Verification; results/readout/spatial_temporal.json: spatial; "
                "results/verify/readout/extra_check.json"
            ),
            "scale": "seqlog",
            "node_label": "medyan RO",
            "node_values": {str(q): g4(10 ** float(med[q])) for q in range(156)},
            "node_flags": {str(q): "d3" for q in np.flatnonzero(deg == 3)},
            "flags": {"d3": "derece 3 kübit (üç komşu)"},
        }
    )

    # 15. Median RO by degree class (verifier's figures).
    bd = j_x["median_ro_by_degree"]
    charts.append(
        {
            "id": "ro-degree-class",
            "type": "bar",
            "title": (
                "Derece 2 kübitlerin okuma hatası derece 1 ve 3 kübitlerden belirgin biçimde düşük"
            ),
            "subtitle": (
                "Derece sınıfına göre kübit başına medyan RO'ların medyanı (doğrulayıcının tanımı: "
                "bütün damga olayları); 8, 100 ve 48 kübit"
            ),
            "read": (
                "Derece 2: 0,00757; derece 1: 0,01196; derece 3: 0,01428 (Kruskal-Wallis p = "
                "3,5e-7). Bu sınıf farkı çıkarılınca kalan uzamsal özilinti anlamlı değildir "
                "(Moran's I -0,047, p = 0,59)."
            ),
            "caveat": (
                "Derece sınıfı rakamları doğrulayıcının tek bir hesabıdır. Fiziksel nedeni "
                "(frekans tahsisi, rezonatör tasarımı) test edilemez: önbellekte kübit ve "
                "rezonatör frekansları yok."
            ),
            "source": "03 Verification; 00 §4.4; results/verify/readout/extra_check.json",
            "x": {"label": "Derece sınıfı", "scale": "band"},
            "y": {"label": "Medyan RO", "scale": "linear"},
            "orient": "v",
            "categories": ["Derece 1 (8 kübit)", "Derece 2 (100 kübit)", "Derece 3 (48 kübit)"],
            "series": [{"name": "Medyan RO", "values": [bd["1"], bd["2"], bd["3"]]}],
        }
    )

    # 16. Monthly device level.
    mo = j_st["temporal"]["monthly_device_median_of_qubit_medians"]
    months = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    mlabels = ["Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim"]
    charts.append(
        {
            "id": "ro-monthly-level",
            "type": "bar",
            "title": "Aylık cihaz düzeyi: mayıstan hazirana büyük düşüş, sonra hafif yukarı kayma",
            "subtitle": (
                "Her kübitin aylık medyanının kübitler üzerinden medyanı (kübit başına en az 5 "
                "olay); mayıs 18,5 gün, ekim 5,1 gün kapsar"
            ),
            "read": (
                "RO 0,01416 (mayıs), 0,00854 (haziran), 0,00812, 0,00836, 0,00854 ve 0,00928 "
                "(ekim). P(1|0) mayıstan hazirana yarıya iner (0,01001'den 0,00500'e) ve sonra "
                "0,0042 ile 0,0049 arasında kalır. Değerlerde günün saatine veya haftanın gününe "
                "bağlı pratik büyüklükte bir mevsimsellik yok (epsilon-kare en çok 0,00042)."
            ),
            "caveat": (
                "Görünür oturum sıklığı aya göre değişir (günde 5,68'den 3,07'ye); bunun IBM'in "
                "daha seyrek ölçmesinden mi, arşivin ara belgeleri daha az görmesinden mi "
                "geldiği arşivden ayrılamaz."
            ),
            "source": (
                "03 §0 item 15, §2.3, §3.1; results/readout/spatial_temporal.json: "
                "temporal.monthly_device_median_of_qubit_medians; sessions.json: by_month"
            ),
            "x": {"label": "Ay (2026)", "scale": "band"},
            "y": {"label": "Hata olasılığı", "scale": "linear"},
            "orient": "v",
            "categories": mlabels,
            "series": [
                {"name": "RO", "values": [g4(mo["ro"][m]) for m in months]},
                {"name": "P(0|1)", "values": [g4(mo["p0g1_fresh"][m]) for m in months]},
                {"name": "P(1|0)", "values": [g4(mo["p1g0"][m]) for m in months]},
            ],
        }
    )

    return {
        "section": "readout",
        "title_tr": "Okuma ve ölçüm: atama hataları, oturumlar, okuma süresi deneyi, eşikler",
        "intro_tr": INTRO,
        "bullets_tr": BULLETS,
        "charts": charts,
    }


INTRO = [
    (
        "Bu bölüm `ibm_fez`'in okuma alanlarını ele alır: P(0|1) (`prob_meas0_prep1`, |1> "
        "hazırlanıp 0 okunması), P(1|0) (`prob_meas1_prep0`), atama hatası RO "
        "(`readout_error`, `measure` hatasıyla kayıt kayıt aynı), asimetri A = P(0|1) - P(1|0), "
        "okuma süresi t_ro, `init_error`, `measure_2` ve ayırt etme eşikleri. Temel: 1.760 "
        "anlık görüntü dosyası, 156 kübit, 598 okuma oturumunda 91.896 RO damga olayı."
    ),
    (
        "Okuma, değerleri bir sayımdan geldiği için binom atış gürültüsü hesaplanabilen tek "
        "ailedir. Atış gürültüsü, onun ötesindeki kalıcı olmayan bileşen ve variogramlar ana "
        "bölümde ele alınır; burada alanların nasıl üretildiği, iki doğal deney, `T1` "
        "bozunmasıyla bağ, ilgili alanlar ve uzamsal yapı var."
    ),
    (
        "Yedi sahip betiğinin hepsi doğrulamada alan alan yeniden üretildi. Dört iddia "
        "zayıfladı (bayat P(0|1) için ızgara testi, 'dama tahtası', yarım pencere bozunması, "
        "2^-312 parite olasılığı), biri ikiye ayrıldı (06-08 RO düşüşü ayakta, A kısmı zayıf), "
        "hiçbiri çürütülmedi. Aşağıdaki metin ve grafikler düzeltilmiş okumaları kullanır."
    ),
]

BULLETS = [
    (
        "**RO, P(0|1) ile P(1|0)'ın ortalamasıdır**, üç değer aynı oturumdan geldiğinde: "
        "188.100 özdeş ve 72.900 kademeli damgalı kaydın hepsinde tutar; bozulduğu 11.263 "
        "kaydın %99,956'sı P(0|1)'i medyan 11,57 saat eski olan kayıtlardır."
    ),
    (
        "**Dönen 9 kübitlik grup:** P(0|1)'i gün içinde yenilenmeyen grup hep aynı mod 17 "
        "kalanındaki 9 kübittir (10, 2026-07-25'te 9, 2026-08-25'te 16). Mekanizma çıkarımdır; "
        "örtük değerin 1/4096 ızgarasına düşmesi aritmetik olarak kaçınılmazdır ve kanıt sayılmaz."
    ),
    (
        "**İki oturum türü:** en az 100 kübitli 589 oturumun 123'ünde her sayım çift, 466'sında "
        "yaklaşık yarısı. Çift oturumların %87,0'ı bir `T1` turuna 3 saatten yakın (karışıklarda "
        "%15,7); bu oturumların 2.048 atış kullanıp kullanmadığı açık. Eşik değişiklikleri "
        "çoğunlukla gün içi oturumlarla gelir (343'ün 208'i, günlüklerde 97'nin 20'si) ve her "
        "biri 156 kübitin hepsini birlikte değiştirir (327 dosya)."
    ),
    (
        "**2026-06-08 (t_ro 1.560 -> 1.700 ns) güçlü bir doğal deneydir:** kübit başına RO "
        "medyan -0,137 dekad, kübitlerin yalnızca %1,9'u yükseldi, 104 plasebo gününün hiçbiri "
        "bu büyüklüğe ulaşmadı; P(1|0) -0,269, P(0|1) -0,079, `T1` plasebo aralığında kaldı. "
        "Ancak eşik alanı aynı dosyada başlar (uzunluk ile prosedür ayrılamaz) ve bu düşüş tek "
        "açık istisna değildir: okumanın en büyük düşüşü 2026-05-17'de bilinen bir olay "
        "olmadan görülür (10 turluk pencerede -0,20 dekad)."
    ),
    (
        "**2026-07-30 (1.700 -> 1.660 ns) saptanabilir bir şey oynatmadı:** RO +0,003 dekad, "
        "plasebo aralığında (-0,039 ile +0,030); öngörülen bozunma değişimi (-0,0003) verinin "
        "çözebileceğinin altında. Aylık cihaz RO'su mayısta 0,01416, haziranda 0,00854, "
        "ekimde 0,00928: düşüşün çoğu haziran ortasından önce."
    ),
    (
        "**Okuma sırasındaki bozunma kübitler arasında görünür:** A, 1 - exp(-t_ro/`T1`) ile "
        "Spearman 0,423 (eğim 0,310), P(0|1) tek başına 0,016. Yarım pencere okuması "
        "desteklenmez ve 06-08'deki A artışı (+0,00146) plasebo aralığında (en büyük +0,00153). "
        "Kübit içinde günlük `T1` değişimleri P(0|1)'i oynatmaz (-0,014)."
    ),
    (
        "**İlgili alanlar okuma kalitesini izler:** `init_error` P(1|0) ile kübitler arasında "
        "0,822, aynı oturumda kübit içinde 0,722; hiç taşımayan 40 kübitin medyan RO'su 0,0331, "
        "diğerlerinin 0,0071. `measure_2` hatası RO'nun medyan 1,25 katı (Spearman 0,852, "
        "kübitlerin %60,3'ünde daha kötü)."
    ),
    (
        "**Uzamsal yapı büyük ölçüde derece sınıfıdır:** medyan RO derece 2'de 0,00757, derece "
        "1'de 0,01196, derece 3'te 0,01428 (p = 3,5e-7); ham Moran's I -0,196, sınıf medyanları "
        "çıkarılınca -0,047 (p = 0,59). Frekans okuması test edilemez; kübit sıralaması kararlı "
        "(haziran ile eylül 0,926)."
    ),
]


def main() -> None:
    sec = build()
    print("\nchecks (name: recomputed / document, tolerance):")
    bad = 0
    for name, got, doc, tol in CHECKS:
        ok = abs(got - doc) <= tol
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {name}: {got:.6g} / {doc:.6g} (tol {tol:g})")
    print(f"{len(CHECKS)} checks, {bad} mismatches")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(sec, ensure_ascii=False, indent=1) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(text.encode('utf-8')):,} bytes, {len(sec['charts'])} charts)")


if __name__ == "__main__":
    main()
