# ruff: noqa: RUF001
"""Report section ``cihaz``: schedule, coverage, device-median change points, states, faults,
layout and layer fidelity (source ``06-device-time-topology.md`` and its Verification section).

Numbers come from ``results/device/*.json`` and ``results/verify/device/*.json``. Series that no
results file holds are recomputed from the field cache with the owner's own functions,
imported from ``analysis/device/`` (no re-implementation):

- round start times: ``schedule.rounds_table`` (15 min gap, a major round re-measures at
  least half of the entities; every ``lf`` event is a major round);
- device-median series and their PELT segments: ``changepoints.round_series``,
  ``changepoints.noise_sigma`` and ``changepoints.pelt`` with ``c = 8``;
- ``lf`` events, EPLG and the isolated-``cz`` prediction: the definitions of
  ``layer_fidelity.py`` with its ``Current`` class.

Every recomputed figure that a results file also holds is checked against it before the chart
is written (the checks are printed; a disagreement stops the script).

Writes ``results/report/cihaz.json``.
"""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "device"))

import changepoints as cp
import common as cm
import ddload
import device_common as dc
import layer_fidelity as lfm
import schedule as sch

SECTION = "cihaz"
C8 = 8.0
FAM = {f.name: f for f in dc.FAMILIES}


def check(label: str, got: Any, want: Any, tol: float = 0.0) -> None:
    if tol:
        ok = bool(np.allclose(np.asarray(got, float), np.asarray(want, float), rtol=tol, atol=0))
    else:
        ok = got == want
    print(f"{'ok  ' if ok else 'DIFF'} {label}: recomputed {got!r}, results {want!r}")
    if not ok:
        raise SystemExit(f"recomputed figure disagrees with the results file: {label}")


def hour_of_day(ms: float) -> float:
    s = cm.iso(ms)
    return int(s[11:13]) + int(s[14:16]) / 60.0 + int(s[17:19]) / 3600.0


def major_starts(dd: ddload.DD, name: str) -> np.ndarray:
    tab = sch.rounds_table(dd, FAM[name])
    need = 1 if name == "lf" else sch.MAJOR_SHARE * tab["n_entities"]
    return np.array(sorted(r["start"] for r in tab["rows"] if r["entities"] >= need))


def month_cats(months: list[str]) -> list[str]:
    out = [cm.MONTHS_TR[m[5:7]] for m in months]
    if months and months[-1] == "2026-10":
        out[-1] += " (5 gün)"
    return out


# ---------------------------------------------------------------------------------- schedule


def chart_clock(dd: ddload.DD, sched: dict[str, Any]) -> dict[str, Any]:
    names = ("T1", "cz", "rzz", "lf")
    series = []
    fams = sched["families"]
    for name in names:
        st = major_starts(dd, name)
        check(f"{name} major rounds", int(st.size), fams[name]["rounds_major"])
        gaps = np.diff(st) / ddload.MS_PER_HOUR
        daily = (gaps > sch.RESET_H) & (gaps < 30.0)
        check(
            f"{name} daily shift (h)",
            float(np.median(gaps[daily] - 24.0)),
            fams[name]["daily_shift_h_median"],
            tol=1e-5,
        )
        series.append(
            {
                "name": name,
                "style": "dots",
                "points": [[cm.iso(t), round(hour_of_day(t), 3)] for t in st],
            }
        )
    f = {k: fams[k] for k in ("T1", "sx", "cz", "rzz", "lf")}
    n_short = len(f["T1"]["short_gaps_below_20h"])
    return {
        "id": "cihaz-saat",
        "type": "line",
        "wide": True,
        "title": "Günlük döngü 24 saatten uzun: turlar her gün biraz daha geç başlıyor",
        "subtitle": (
            "Her ana turun başlangıç saati (UTC) tarihe karşı; `T1` "
            f"{f['T1']['rounds_major']}, `cz` {f['cz']['rounds_major']}, `rzz` "
            f"{f['rzz']['rounds_major']} ana tur ve {f['lf']['rounds_major']} arşiv içi `lf` olayı"
        ),
        "read": (
            f"Nokta dizileri her gün yukarı kayıyor ve 24'e varınca alttan yeniden başlıyor: "
            f"`T1` turları medyan {cm.tr(f['T1']['daily_shift_h_median'], 2)} saat, `sx` "
            f"{cm.tr(f['sx']['daily_shift_h_median'], 2)}, `cz` "
            f"{cm.tr(f['cz']['daily_shift_h_median'], 2)}, `rzz` "
            f"{cm.tr(f['rzz']['daily_shift_h_median'], 2)} saat daha geç başlıyor (medyan "
            f"aralık {cm.tr(f['T1']['gap_h_q'][3], 2)} ile {cm.tr(f['rzz']['gap_h_q'][3], 2)} "
            f"saat). Ani geri sıçramalar 20 saatten kısa aralıklar, yani yeniden başlatmalar "
            f"(`T1`'de {n_short}). `lf` kendi {cm.tr(f['lf']['gap_h_q'][3], 1)} saatlik "
            f"döngüsünde günde {cm.tr(f['lf']['daily_shift_h_median'], 2)} saat kayıyor. "
            "`sx` çizilmedi: `T1`'in hemen ardından geliyor."
        ),
        "caveat": (
            "Tur başlangıçlarının saat dağılımı düzgün değil (`T1` için ki-kare p = "
            f"{cm.tr(f['T1']['hour_of_day_chi2_p'], 4)}, 20 ile 23 UTC arasında yoğun). "
            "Yeniden başlatmaların döngüyü oraya taşıması en olası açıklama; bu bir yorum, "
            "test edilmedi. Takvim IBM'in hiçbir kaynağında tarif edilmiyor (06 §1.2, §3.1)."
        ),
        "source": "06 §0, §3.1; results/device/schedule.json; tur başlangıçları önbellekten",
        "x": {"label": "tarih", "scale": "time"},
        "y": {
            "label": "tur başlangıcı",
            "unit": "UTC saat",
            "scale": "linear",
            "min": 0,
            "max": 24,
        },
        "series": series,
    }


def chart_order(sched: dict[str, Any]) -> dict[str, Any]:
    order = sched["order_relative_to_T1"]
    group = {
        "readout": "günde birkaç tur",
        "init_error": "günde birkaç tur",
        "lf": "kendi döngüsü",
    }
    rows = []
    for name, o in sorted(order.items(), key=lambda kv: kv[1]["offset_h_q"][3]):
        q = o["offset_h_q"]
        rows.append(
            {
                "label": f"{name} (n = {o['anchors_matched']})",
                "est": round(q[3], 3),
                "lo": round(q[2], 3),
                "hi": round(q[4], 3),
                "group": group.get(name, "günde bir tur"),
            }
        )
    bm = sched["order_by_month"]
    o = {k: v["offset_h_q"][3] for k, v in order.items()}
    return {
        "id": "cihaz-sira",
        "type": "forest",
        "title": (
            "Bir döngüde sıra sabit: readout ve `measure_2`, `T1` ile `T2`, `sx`, sonra `cz` "
            "ve `rzz`"
        ),
        "subtitle": (
            "Her `T1` ana turuna (133 tur) en yakın ±12 saat içindeki ana turun farkı, saat; "
            "nokta medyan, çizgi %25 ile %75; n eşleşen `T1` turu"
        ),
        "read": (
            f"`init_error` {cm.tr(abs(o['init_error']), 2)}, readout "
            f"{cm.tr(abs(o['readout']), 2)}, `measure_2` {cm.tr(abs(o['measure_2']), 2)} saat "
            f"önce; `T2` 3 saniye sonra; `sx` {cm.tr(o['sx'], 2)}, `cz` {cm.tr(o['cz'], 2)}, "
            f"`rzz` {cm.tr(o['rzz'], 2)} saat sonra. Döngü uzadı: Mayıs'tan Eylül'e `cz` farkı "
            f"{cm.tr(bm['2026-05']['cz']['median_offset_h'], 2)}'dan "
            f"{cm.tr(bm['2026-09']['cz']['median_offset_h'], 2)} saate, `rzz` "
            f"{cm.tr(bm['2026-05']['rzz']['median_offset_h'], 2)}'den "
            f"{cm.tr(bm['2026-09']['rzz']['median_offset_h'], 2)} saate. `lf` döngüye kilitli "
            f"değil (%25 ile %75: {cm.tr(order['lf']['offset_h_q'][2], 2)} ile "
            f"+{cm.tr(order['lf']['offset_h_q'][4], 2)} saat)."
        ),
        "caveat": (
            "Bu bir takvim sırası. Kelly ve ark. 2018'in tarif ettiği türden bir kalibrasyon "
            "bağımlılık sırasına benziyor, ama IBM'in böyle bir grafik kullandığını göstermiyor. "
            'Readout ve `init_error` günde birkaç kez ölçüldüğü için "en yakın tur" onlarda '
            "gevşek bir eşleşme (06 §3.2)."
        ),
        "source": "06 §0, §3.2; 00 §3; results/device/schedule.json (order_relative_to_T1)",
        "x": {"label": "T1 turuna göre fark", "unit": "saat", "scale": "linear"},
        "rows": rows,
        "ref": 0,
    }


def chart_coverage(docs: dict[str, Any], v6: dict[str, Any]) -> dict[str, Any]:
    bm = docs["cadence"]["by_month"]
    vr = docs["visible_rounds"]
    months = sorted(bm)
    ro = [vr["readout"][m]["per_day"] for m in months]
    g15 = v6["gap15"]
    return {
        "id": "cihaz-kapsam",
        "type": "bar",
        "title": "Belge sayısı arttı, görünen readout turu azaldı: günde 5,62'den 3,67'ye",
        "subtitle": (
            "Ay başına, günde ortalama: arşivlenen belge, readout ana turu, `T1` ana turu ve "
            "`rzz` ana turu; ana tur kübitlerin ya da kuplörlerin en az yarısını yeniden ölçen tur"
        ),
        "read": (
            f"Belge/gün {cm.tr(bm['2026-05']['files_per_day'], 2)} (Mayıs) ile "
            f"{cm.tr(bm['2026-09']['files_per_day'], 2)} (Eylül) arasında arttı, readout "
            f"turu/gün {cm.tr(ro[0], 2)}'den {cm.tr(ro[4], 2)}'ye düştü. `T1` her ay günde "
            "yaklaşık bir tur. `rzz` Ağustos'ta günde 0,48'e iniyor: 19 ile 31 Ağustos arası "
            "279,8 saat cihaz genelinde yeniden ölçülmedi, öteki aileler ölçülürken."
        ),
        "caveat": (
            "Doğrulayıcı düşüşü 15, 60 ve 180 dakikalık tur aralıklarında ve yalnızca canlı "
            f"belgeli Mayıs, Haziran, Temmuz'da da buldu ({cm.tr(g15['2026-05']['per_day'], 2)}; "
            f"{cm.tr(g15['2026-06']['per_day'], 2)}; {cm.tr(g15['2026-07']['per_day'], 2)}). "
            "Kayıp belge bir sayımı yalnızca düşürebileceği için düşüş en azından kısmen IBM'in "
            "ne çalıştırdığı ya da yayımladığındaki bir değişim (yorum). Aylar arası her olay hızı "
            "karşılaştırması bu iki etkiyi taşıyor."
        ),
        "source": (
            "06 §3.4, Verification; results/device/documents.json (visible_rounds, cadence), "
            "results/verify/device/v6_readout_cadence.json"
        ),
        "x": {"label": "ay", "scale": "band"},
        "y": {"label": "günde", "scale": "linear"},
        "categories": month_cats(months),
        "series": [
            {"name": "belge / gün", "values": [cm.r4(bm[m]["files_per_day"]) for m in months]},
            {"name": "readout turu / gün", "values": [cm.r4(x) for x in ro]},
            {"name": "T1 turu / gün", "values": [cm.r4(vr["T1"][m]["per_day"]) for m in months]},
            {"name": "rzz turu / gün", "values": [cm.r4(vr["rzz"][m]["per_day"]) for m in months]},
        ],
    }


# ---------------------------------------------------------------------------- change points


def median_series(
    dd: ddload.DD, name: str, cps: dict[str, Any]
) -> tuple[list[list[Any]], list[list[Any]], list[int]]:
    """Points of the device-median series and of its PELT (c = 8) segment medians."""
    x, t = cp.round_series(dd, FAM[name])
    sig = cp.noise_sigma(x)
    check(f"{name} rounds in series", int(x.size), cps["series"][name]["n"])
    check(f"{name} noise sigma", sig, cps["series"][name]["noise_sigma"], tol=1e-5)
    pts = cp.pelt(x, C8 * sig * sig * np.log(x.size))
    bounds = [0, *pts, x.size]
    meds = [float(np.median(x[bounds[k] : bounds[k + 1]])) for k in range(len(bounds) - 1)]
    check(
        f"{name} c=8 segment medians",
        meds,
        cps["series"][name]["c8"]["segment_medians_log10"],
        tol=1e-5,
    )
    raw = [[cm.iso(tt), cm.r4(10.0**xx)] for tt, xx in zip(t, x, strict=True)]
    step: list[list[Any]] = []
    for k, m in enumerate(meds):
        step.append([cm.iso(t[bounds[k]]), cm.r4(10.0**m)])
        step.append([cm.iso(t[bounds[k + 1] - 1]), cm.r4(10.0**m)])
    return raw, step, pts


def cp_rows(cps: dict[str, Any], name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = cps["series"][name]["c8"]["pelt_points"]
    return out


def shift_tr(x: float) -> str:
    return ("+" if x > 0 else "") + cm.tr(x, 3)


def chart_readout(dd: ddload.DD, cps: dict[str, Any], v5: dict[str, Any]) -> dict[str, Any]:
    ro_raw, ro_step, _ = median_series(dd, "readout", cps)
    in_raw, in_step, _ = median_series(dd, "init_error", cps)
    every = [p[1] for p in ro_raw + in_raw]
    ylo, yhi = cm.r4(0.9 * min(every)), cm.r4(1.1 * max(every))
    rp = cp_rows(cps, "readout")
    ip = cp_rows(cps, "init_error")
    summ = cps["summary_value_series"]["c8"]
    r = v5["readout"]
    pts_tr = "; ".join(f"{cm.date_tr(p['at'])} {shift_tr(p['shift_log10'])}" for p in rp)
    return {
        "id": "cihaz-medyan-okuma",
        "type": "line",
        "wide": True,
        "title": (
            "Readout medyanı Mayıs ve Haziran'da düştü; değişim noktaları bilinen olaylarla "
            "şans düzeyinde örtüşüyor"
        ),
        "subtitle": (
            f"Ana tur başına, yeniden ölçülen kübitlerin medyanı ({len(ro_raw)} readout, "
            f"{len(in_raw)} `init_error` turu) ve PELT segment medyanları (en tutucu ceza, c = 8); "
            "log ölçek"
        ),
        "read": (
            f"Readout'ta c = 8 noktaları (dekad, log10): {pts_tr}. Düşüşün çoğu Mayıs ve "
            f"Haziran'da. `init_error` {cm.date_tr(ip[0]['at'])} günü "
            f"{cm.tr(abs(ip[0]['shift_log10']), 3)} dekad yükseliyor, "
            f"{cm.date_tr(ip[2]['at'])} günü {cm.tr(abs(ip[2]['shift_log10']), 3)} dekad "
            "düşüyor; bilinen bir olay yok. Dokuz serideki "
            f"{summ['detected']} noktanın {summ['matched']}'i bilinen bir olaya 36 saat içinde; "
            f"şansla beklenen {cm.tr(summ['expected_by_chance'], 2)}."
        ),
        "caveat": (
            "8 Haziran düşüşü (uzunluk 1.560'tan 1.700 ns'ye geçtikten 2,6 saat sonra, PELT ile "
            f"−0,138 dekad) yeniden üretiliyor (pencere medyanlarıyla "
            f"{cm.tr(r['len1_k5_post_minus_pre_median_decades'], 3)} ile "
            f"{cm.tr(r['len1_k20_post_minus_pre_median_decades'], 3)}) ve `T1`, `T2`, `sx`'te "
            'aynı yerde adım yok. Ama "tek açık istisna" denemez: readout\'un en büyük '
            f"10 turluk düşüşü 17 Mayıs'ta ({cm.tr(r['largest_drops_k10'][0][0], 2)} dekad), "
            "bilinen bir olay olmadan; 8 ile 9 Haziran aynı zamanda bir takvim yeniden "
            "başlatması; aynı belgede `measure.threshold` ilk kez çıkıyor; 30 Temmuz'daki ikinci "
            "uzunluk değişimi hiçbir yanıt vermiyor. Tek olay (n = 1), atfedilemez (06 Doğrulama)."
        ),
        "source": (
            "06 §0, §3.5, Verification; 00 §4.6; results/device/changepoints.json, "
            "results/verify/device/v5_changepoint.json; seriler önbellekten"
        ),
        "x": {"label": "tarih", "scale": "time"},
        "y": {"label": "cihaz medyanı", "scale": "log", "min": ylo, "max": yhi},
        "markers": [
            {"axis": "x", "value": "2026-06-08T18:56:28Z", "label": "1.700 ns, eşik"},
            {"axis": "x", "value": "2026-07-30T21:09:17Z", "label": "1.660 ns"},
        ],
        "series": [
            {"name": "readout_error", "style": "dots", "points": ro_raw},
            {"name": "readout_error, PELT segmenti", "style": "line", "points": ro_step},
            {"name": "init_error", "style": "dots", "points": in_raw},
            {"name": "init_error, PELT segmenti", "style": "line", "points": in_step},
        ],
    }


def chart_coherence(dd: ddload.DD, cps: dict[str, Any], coh: dict[str, Any]) -> dict[str, Any]:
    t1m = coh["T1"]["rounds"]["device_median_value_by_month"]
    t1_raw, t1_step, _ = median_series(dd, "T1", cps)
    t2_raw, t2_step, _ = median_series(dd, "T2", cps)
    p1 = cp_rows(cps, "T1")
    p2 = cp_rows(cps, "T2")

    def pts(rows: list[dict[str, Any]]) -> str:
        return "; ".join(f"{cm.date_tr(p['at'])} {shift_tr(p['shift_log10'])}" for p in rows)

    return {
        "id": "cihaz-medyan-koherans",
        "type": "line",
        "wide": True,
        "title": (
            "`T1` ve `T2` medyanlarının büyük adımları Mayıs'ta, takvimin en sık yeniden "
            "başlatıldığı haftalarda"
        ),
        "subtitle": (
            f"Ana tur başına, yeniden ölçülen kübitlerin medyanı, µs ({len(t1_raw)} `T1` ve "
            f"{len(t2_raw)} `T2` turu) ve PELT segment medyanları (c = 8)"
        ),
        "read": (
            f"c = 8 noktaları (dekad): `T1` {pts(p1)}; `T2` {pts(p2)}. `T1`'in aylık cihaz "
            f"medyanı Mayıs'ta {cm.tr(t1m['2026-05'], 1)} µs, Haziran'da "
            f"{cm.tr(t1m['2026-06'], 1)} µs, sonra {cm.tr(t1m['2026-08'], 1)} ile "
            f"{cm.tr(t1m['2026-07'], 1)} µs arasında (02 §3.1). 28 Mayıs noktası `xslow`'un "
            'kaybolmasından 34,7 saat önce ve eşleşme kuralına göre "eşleşmiş" sayılıyor.'
        ),
        "caveat": (
            "Mayıs noktalarının takvimin en sık yeniden başlatıldığı haftalara denk gelmesi "
            "zamanda bir çakışma, gösterilmiş bir neden değil (06 §3.5). 02 aynı `T1` adımını "
            "başka bir yöntemle 15 Mayıs 05 UTC turuna tarihliyor; arşiv cihazın ortamının mı "
            "yoksa değerlerin üretim biçiminin mi değiştiğini ayıramıyor (02 §3.2, 00 §4.2)."
        ),
        "source": (
            "06 §3.5; 02 §3.2; 00 §4.2; results/device/changepoints.json; seriler önbellekten"
        ),
        "x": {"label": "tarih", "scale": "time"},
        "y": {"label": "cihaz medyanı", "unit": "µs", "scale": "linear"},
        "markers": [
            {"axis": "x", "value": "2026-05-29T16:46:42Z", "label": "xslow kayboluyor"},
        ],
        "series": [
            {"name": "T1", "style": "dots", "points": t1_raw},
            {"name": "T1, PELT segmenti", "style": "line", "points": t1_step},
            {"name": "T2", "style": "dots", "points": t2_raw},
            {"name": "T2, PELT segmenti", "style": "line", "points": t2_step},
        ],
    }


# ------------------------------------------------------------------------------------ states


def chart_states(dd: ddload.DD, st: dict[str, Any]) -> dict[str, Any]:
    sid = dd.file("state_id")
    counts = np.bincount(sid[sid >= 0])
    counts = counts[counts > 0]
    check("distinct states", int(counts.size), st["distinct_states"])
    check("single-file states", int(np.sum(counts == 1)), st["states_with_one_file"])
    check("largest state (files)", int(counts.max()), st["max_files_per_state"])
    labels = {
        "g2.cz.gate_error": "cz",
        "g1.sx.gate_error": "sx",
        "g1.measure.threshold": "measure.threshold",
        "gen.zz": "zz",
        "g2.rzz.gate_error": "rzz",
        "gen.lf": "lf",
        "g1.xslow.gate_error": "xslow",
        "g1.measure_2.gate_error": "measure_2",
    }
    by = st["same_state_pairs_with_change_by_field"]
    order = sorted(by, key=lambda k: -by[k])
    fm = st["flag_mismatch"]
    return {
        "id": "cihaz-durum",
        "type": "bar",
        "orient": "h",
        "title": (
            '760 "durum" yalnızca kübit kayıtlarını ayırıyor; kapı yeniden kalibrasyonları '
            "görünmüyor"
        ),
        "subtitle": (
            f"Aynı durumdaki {st['consecutive_pairs_same_state']} ardışık belge çiftinden, "
            "alana göre değeri değişen çift sayısı"
        ),
        "read": (
            "Durum özeti (`health/state-index.tsv`) yalnızca `properties.qubits` kayıtlarını, "
            f"tarihleri atılmış olarak kapsıyor. Aynı durumdaki çiftlerin "
            f"{st['same_state_pairs_with_any_listed_change']}'ünde bir kapı, `lf`, `zz` ya da eşik "
            f"değeri değişiyor; en çok `cz` ({by['g2.cz.gate_error']}) ve `sx` "
            f"({by['g1.sx.gate_error']}). Durum başına medyan "
            f"{int(st['files_per_state_q'][3])} belge, {st['states_with_one_file']} durum tek "
            f"belgelik, en büyüğü {st['max_files_per_state']} belge. Yani 760 bir kalibrasyon "
            "sayısı değil."
        ),
        "caveat": (
            "Aynı durumdaki çiftlerde kübit değeri hiç değişmiyor (0/998): özet kübit "
            "değerlerinden yapıldığı için bu neredeyse totolojik; bilgi veren kısım kapı "
            f"değişimleri (06 Doğrulama). `is_new_state` belge zamanını değil dosyalama sırasını "
            f"işaretliyor: {fm['states_where_flag_is_not_on_first_file_in_time']} durumda bayrak "
            "zamanca ilk belgede değil, hepsinde ilk belge tarihsel."
        ),
        "source": "06 §2.4, §6.2 madde 3, §7.1, Verification; 01 §6; results/device/states.json",
        "x": {"label": "aynı durumda değişen çift", "scale": "linear"},
        "y": {"label": "", "scale": "band"},
        "categories": [labels[k] for k in order],
        "series": [{"name": "çift", "values": [by[k] for k in order]}],
    }


# ---------------------------------------------------------------------------- faults, layout


def chart_faults(dd: ddload.DD, lay: dict[str, Any], v4: dict[str, Any]) -> dict[str, Any]:
    _, und = dc.undirected_columns(dd)
    keys = [f"{a}-{b}" for a, b in und]
    share = dict.fromkeys(keys, 0.0)
    for fam in ("cz", "rzz"):
        for e in lay["faults"][fam]["entities"]:
            share[e["entity"]] = max(share[e["entity"]], float(e["share_of_present_files"]))
    perm = sorted(
        set(lay["faults"]["cz"]["entities_always"]) | set(lay["faults"]["rzz"]["entities_always"])
    )
    check(
        "permanent couplers",
        perm,
        sorted("-".join(map(str, e)) for e in v4["permanent_couplers"]),
    )
    eflags = dict.fromkeys(perm, "kalici")
    for e in lay["faults"]["zz_zero"]["entities"]:
        if e["entity"] not in eflags:
            eflags[e["entity"]] = "zz0"
    nflags = {"72": "q72", "17": "q17"}
    clus = lay["clustering"][0]
    return {
        "id": "cihaz-ariza",
        "type": "map",
        "title": "Altı kalıcı arızalı kuplörden ikisi `q72`'de, ikisi `q99`'da birleşiyor",
        "subtitle": (
            "Kuplör rengi: `cz` ya da `rzz` hatasının yer tutucu (`gate_error >= 1`) olduğu "
            "belge payı, iki kapıdan büyüğü; 1.760 belge, 176 kuplör. Vurgulu çizgi: kalıcı "
            "arıza ya da `zz` = 0; vurgulu çerçeve: arızalı kübit"
        ),
        "read": (
            "Her belgede yer tutucu: `cz` için 27-28, 32-33, 71-72, 72-73; `rzz` için 32-33, "
            "71-72, 72-73, 95-99, 99-115. Altı rastgele kuplörde beklenen bitişik çift "
            f"{cm.tr(clus['adjacent_pairs_null_mean'], 2)}, gözlenen "
            f"{clus['adjacent_pairs_observed']} "
            f"(p = {cm.tr(clus['p_value_at_least_observed'], 3)}). "
            "`q72`'nin `sx`'i her belgede yer tutucu, `T2`'si hiçbir belgede yok. 102-103'ün "
            "`cz`'si belgelerin %88,8'inde yer tutucu, 29 Eylül'den beri gerçek değer. `zz` "
            "32-33'te hep 0; 13-14, 39-53 ve 109-118'de 10 Temmuz'a kadar 0."
        ),
        "caveat": (
            'Bitişiklik sonucu (p = 0,018) doğrulandı. "Uzamsal olarak yoğunlaşmış" ise yalnızca '
            "düşündürücü: 10 kübitlik ayak izinin ortalama sekme mesafesi "
            f"({cm.tr(v4['footprint_mean_hop_couplers_only'], 2)}) rastgele kübitlerle "
            "karşılaştırılmıştı; arızalar kuplör olduğundan doğru karşılaştırma rastgele "
            f"kuplörler: p = {cm.tr(v4['null_b_random_couplers']['p_le_obs'], 3)} (tek test, "
            "düzeltmesiz), bitişik çiftler verildiğinde p = "
            f"{cm.tr(v4['null_c_random_couplers_with_ge2_adjacent']['p_le_obs'], 2)} "
            "(06 Doğrulama). 6 ile 16 varlıkla testlerin gücü düşük."
        ),
        "source": (
            "06 §0, §5.2, §6.1, Verification; 01 §5; results/device/layout_faults.json, "
            "results/verify/device/v4_faults.json"
        ),
        "scale": "seq",
        "domain": [0, 1],
        "edge_values": {k: cm.r4(v) for k, v in share.items()},
        "edge_flags": eflags,
        "node_flags": nflags,
        "flags": {
            "kalici": "kalıcı arıza: her belgede yer tutucu",
            "zz0": "zz = 0 (eksik değer işareti)",
            "q72": "q72: sx her belgede yer tutucu, T2 hiç yok",
            "q17": "q17: `sx` belgelerin %11,9'unda yer tutucu, 13 Temmuz'a kadar",
        },
        "edge_label": "yer tutucu belge payı",
    }


def chart_degree(lay: dict[str, Any]) -> dict[str, Any]:
    lg = lay["layout"]
    deg = lg["degree_by_qubit"]
    dcount = lg["degree_counts"]
    return {
        "id": "cihaz-derece",
        "type": "map",
        "title": "Yerleşim heavy-hex: 100 kübit derece 2, 48 kübit derece 3, 8 kübit derece 1",
        "subtitle": (
            "Kübit rengi: kübitin kuplör sayısı (derece); 156 kübit, 176 kuplör, tek bir yerleşim"
        ),
        "read": (
            f"Graf iki parçalı ({lg['bipartition_sizes'][0]} ve {lg['bipartition_sizes'][1]} "
            f"kübit; derece-3 kübitlerin {dcount['3']}'i de {lg['bipartition_sizes'][1]}'lük "
            f"sınıfta), en kısa çevre {lg['girth']}, bağımsız çevre sayısı {lg['cycle_rank']}, "
            f"çap {lg['diameter']} sekme, ortalama sekme mesafesi {cm.tr(lg['mean_distance'], 2)}. "
            "Derece-3 kübitlerin hepsi 16 kübitlik sıralarda; aradaki 4 kübitlik sıralar köprü. "
            'Readout\'un "dama tahtası" deseni büyük ölçüde bu derece sınıflarından geliyor '
            "(03 Doğrulama). `sx` hatası derece-3 kübitlerde daha düşük (04 §5); doğrulayıcıya "
            "göre `T1` de aynı deseni gösteriyor, bu bir ipucu, bulgu değil (04 Doğrulama)."
        ),
        "caveat": (
            "Bütün uzamsal ifadeler indeks farkı değil, bu graf üzerindeki sekme mesafesi "
            "kullanmalı. Önbellekte kübit ya da rezonatör frekansı yok; derece etkisinin fiziksel "
            "kökeni bu yüzden test edilemiyor (00 §4.4)."
        ),
        "source": "06 §5.1; 00 §4.4; results/device/layout_faults.json (layout)",
        "scale": "seq",
        "domain": [1, 3],
        "node_values": {str(q): int(d) for q, d in enumerate(deg)},
        "node_label": "derece",
    }


# ------------------------------------------------------------------------------ layer fidelity


class LF:
    """``lf`` events, EPLG and the isolated-``cz`` prediction, as in ``layer_fidelity.py``."""

    def __init__(self, dd: ddload.DD) -> None:
        self.names = list(dd.meta["lf_names"])
        self.nq = np.array([int(n.split("_")[1]) for n in self.names])
        self.chains = dd.meta["lf_chains"]
        v = np.array(dd.v("gen.lf"))
        stamp = np.array(dd.d("gen.lf"))[:, 0]
        cid = np.array(np.load(dd.path / "gen.lf_chain__v.npy"))
        ev = [0] + [i for i in range(1, dd.n_files) if stamp[i] != stamp[i - 1]]
        self.ev = np.array(ev)
        self.t = stamp[self.ev]
        self.lf = v[self.ev]
        self.cid = cid[self.ev]
        self.inside = self.t >= float(dd.file_ms[0])
        self.eplg_avg = 0.8 * (1.0 - self.lf ** (1.0 / (self.nq - 1.0)))
        cols, und = dc.undirected_columns(dd)
        col_of = {e: c for c, e in zip(cols, und, strict=True)}
        cz = lfm.Current(dd, "g2.cz.gate_error", cols)
        pred = np.full(self.lf.shape, np.nan)
        for k in range(self.ev.size):
            tk = float(self.t[k])
            for j in range(len(self.names)):
                c = self.chains[int(self.cid[k, j])]
                es = [col_of[(min(a, b), max(a, b))] for a, b in pairwise(c)]
                errs = np.array([cz.at(e, tk)[0] for e in es])
                if np.all(np.isfinite(errs)):
                    pred[k, j] = float(np.sum(np.log1p(-1.25 * errs)))
        self.ln_pred = pred
        self.ratio = np.log(self.lf) / pred

    def col(self, n: int) -> int:
        return self.names.index(f"lf_{n}")


def chart_eplg(
    lf: LF, lfj: dict[str, Any], cps: dict[str, Any], v1: dict[str, Any]
) -> dict[str, Any]:
    vals = lfj["values"]
    check("lf events", int(lf.ev.size), lfj["cadence"]["events"])
    check(
        "EPLG(100) per event",
        [float(f"{x:.6g}") for x in lf.eplg_avg[:, lf.col(100)]],
        vals["eplg100_avg_by_event"],
        tol=1e-5,
    )
    ins = lf.inside
    series = []
    for n in (100, 50, 10):
        y = lf.eplg_avg[ins, lf.col(n)]
        series.append(
            {
                "name": f"EPLG({n})",
                "style": "line+dots",
                "points": [[cm.iso(t), cm.r4(v)] for t, v in zip(lf.t[ins], y, strict=True)],
            }
        )
    sp = v1["eplg_spearman_in_archive"]
    pn = vals["per_N"]
    pelt = cps["series"]["lf_eplg100"]["c8"]["pelt_points"][0]
    return {
        "id": "cihaz-eplg",
        "type": "line",
        "wide": True,
        "title": (
            "100 kübitlik zincirde katman başına hata zamanla artıyor "
            f"(Spearman {cm.tr(sp['rho'], 3)})"
        ),
        "subtitle": (
            f"Arşiv içi {int(ins.sum())} `lf` olayında EPLG(N), IBM'in ortalama kapı hatası "
            "biçimi 4/5 (1 − lf_N^(1/(N−1))); N = 100, 50, 10"
        ),
        "read": (
            f"`lf_100` medyanı {cm.tr(pn['100']['lf_q'][3], 3)} (aralık "
            f"{cm.tr(pn['100']['lf_q'][0], 3)} ile {cm.tr(pn['100']['lf_q'][6], 3)}), EPLG(100) "
            f"medyanı {cm.tr(pn['100']['eplg_avg_q'][3], 5)}. EPLG N ile büyüyor (medyan "
            f"{cm.tr(pn['10']['eplg_avg_q'][3], 5)}, {cm.tr(pn['50']['eplg_avg_q'][3], 5)}, "
            f"{cm.tr(pn['100']['eplg_avg_q'][3], 5)}; N = 10, 50, 100): en iyi kısa zincirler "
            "kötü kapılardan kaçınabiliyor, uzunlar kaçınamıyor (yorum). EPLG(100) zamanla "
            f"artıyor: Spearman {cm.tr(sp['rho'], 3)} (p = {cm.sci(sp['p'])}, n = {sp['n']}); PELT "
            f"c = 8'de tek adım {cm.date_tr(pelt['at'])} (+{cm.tr(pelt['shift_log10'], 3)} dekad)."
        ),
        "caveat": (
            "İlk `lf` değeri 10 Mayıs damgalı ve 1 Temmuz'a kadar taşınıyor; burada dışarıda. "
            "`lf` damgası 217 belgede `last_update_date`'ten sonra, bu yüzden `lf` saat ölçeğinde "
            "öteki alanlarla sıralanmamalı (06 §6.2 madde 1)."
        ),
        "source": (
            "06 §2.5, §3.7, Verification; results/device/layer_fidelity.json, changepoints.json, "
            "results/verify/device/v1_basics.json; seriler önbellekten"
        ),
        "x": {"label": "lf damgası", "scale": "time"},
        "y": {"label": "EPLG, ortalama kapı hatası biçimi", "scale": "linear"},
        "markers": [{"axis": "x", "value": pelt["at"], "label": "PELT adımı"}],
        "series": series,
    }


def chart_ratio(lf: LF, lfj: dict[str, Any], v3: dict[str, Any]) -> dict[str, Any]:
    med = np.nanmedian(lf.ratio, axis=0)
    check(
        "median ratio by N",
        [float(f"{x:.6g}") for x in med],
        lfj["link"]["median_ratio_by_N"],
        tol=1e-5,
    )
    q25 = np.nanquantile(lf.ratio, 0.25, axis=0)
    q75 = np.nanquantile(lf.ratio, 0.75, axis=0)
    g = lfj["link"]["ratio_lnlf_over_lnpred_cz_q_by_N_group"]
    order = np.argsort(lf.nq)
    pts = [[int(lf.nq[j]), cm.r4(med[j])] for j in order]
    band = [[int(lf.nq[j]), cm.r4(q25[j]), cm.r4(q75[j])] for j in order]
    grp = ", ".join(f"{cm.tr(g[k][3], 2)} ({k.replace('-', ' ile ')})" for k in g)
    return {
        "id": "cihaz-katman-oran",
        "type": "line",
        "title": (
            "Katmanlı zincirin hatası izole `cz` tahmininin yaklaşık 1,4 katı ve zincir "
            "uzunluğundan bağımsız"
        ),
        "subtitle": (
            "Her N için 83 olay üzerinden `ln(lf_N) / ln(pred_N)`, `pred_N` zincirin N − 1 "
            "kuplöründe Π(1 − 5/4 · `cz`), `cz` lf damgasından önceki son değer; çizgi medyan, "
            "gölge %25 ile %75"
        ),
        "read": (
            f"Medyan oran N gruplarında {grp}; doğrulayıcının bağımsız hesabı N = 10, 50, 100 için "
            f"{cm.tr(v3['ratio_lf10']['median'], 2)}, {cm.tr(v3['ratio_lf50']['median'], 2)}, "
            f"{cm.tr(v3['ratio_lf100']['median'], 2)}. Birinci dereceden (−ln(1 − e) ≈ e), bir "
            "katmandaki kapı izole benchmark'ının öngördüğünden yaklaşık 1,4 kat sık hata yapıyor."
        ),
        "caveat": (
            "Neden açık: katman içi crosstalk, zincir uçlarındaki boşta bekleme, katmanlı ve izole "
            "fitlerin farkı ve izole `cz` değerinin lf damgasındaki medyan 10,9 saatlik yaşı "
            'ayrılamıyor (06 §7.2). "1,4 kat sık" bir yorum. Oranın N\'den bağımsız olması '
            "hafifçe beklenmedik: alt zincirler üzerinden maksimum, kısa N'de oranı düşürmeliydi."
        ),
        "source": (
            "06 §7.2, Verification; 00 §4.5; results/device/layer_fidelity.json (link), "
            "results/verify/device/v3_lf_ratio.json; yüzdelikler önbellekten"
        ),
        "x": {"label": "zincir uzunluğu N", "unit": "kübit", "scale": "linear"},
        "y": {
            "label": "ln(lf_N) / ln(pred_N)",
            "scale": "linear",
            "min": 0.9,
            "max": max(1.7, float(np.ceil(np.nanmax(q75) * 10.0) / 10.0)),
        },
        "markers": [{"axis": "y", "value": 1, "label": "izole tahmin"}],
        "series": [{"name": "medyan oran", "style": "line", "points": pts, "band": band}],
    }


def chart_pred(lf: LF, lfj: dict[str, Any]) -> dict[str, Any]:
    k = lf.col(100)
    ln_lf = np.log(lf.lf[:, k])
    ok = np.isfinite(lf.ln_pred[:, k])
    r = stats.spearmanr(ln_lf[ok], lf.ln_pred[ok, k])
    ref = lfj["link"]["spearman_events_lnlf100_vs_lnpred_cz"]
    check("lf_100 events with a prediction", int(ok.sum()), ref["n"])
    check("Spearman ln lf_100 vs ln pred", float(r.statistic), ref["rho"], tol=1e-5)
    rq = lfj["link"]["ratio_lf100_cz_q"]
    nxt = lfj["link"]["spearman_events_lnlf100_vs_lnpred_next_cz"]
    pts = [
        [cm.r4(float(np.exp(lf.ln_pred[i, k]))), cm.r4(float(lf.lf[i, k])), cm.iso(lf.t[i])[:10]]
        for i in np.flatnonzero(ok)
    ]
    below = sum(1 for x, y, _ in pts if y < x)
    return {
        "id": "cihaz-lf-tahmin",
        "type": "scatter",
        "title": (
            "Olay bazında `lf_100` izole tahmini yalnızca zayıf izliyor "
            f"(Spearman {cm.tr(ref['rho'], 3)})"
        ),
        "subtitle": (
            f"Her `lf` olayında ölçülen `lf_100` ile aynı zincirin izole `cz` tahmini "
            f"Π(1 − 5/4 · `cz`); {ref['n']} olay (83 olayın {83 - ref['n']}'sinde zincir yer "
            "tutucu durumdaki 102-103'ü kullanıyor, tahmin yok)"
        ),
        "read": (
            f"{len(pts)} olayın {below}'inde nokta y = x çizgisinin altında: ölçülen katman "
            f"fidelity'si izole tahminden düşük. `ln` oranının medyanı {cm.tr(rq[3], 2)} "
            "(%25 ile %75: "
            f"{cm.tr(rq[2], 2)} ile {cm.tr(rq[4], 2)}). İki değer olaydan olaya yalnızca zayıf "
            f"birlikte oynuyor: Spearman {cm.tr(ref['rho'], 3)} (p = {cm.tr(ref['p'], 3)}); lf "
            f"damgasından sonraki ilk `cz` turu kullanılırsa {cm.tr(nxt['rho'], 3)} "
            f"(n = {nxt['n']})."
        ),
        "caveat": (
            "Zincir neredeyse her olayda yeniden seçiliyor, bu yüzden noktalar aynı kapı kümesinin "
            "tekrarları değil. İzole `cz` değeri lf damgasında medyan 10,9 saat yaşlı."
        ),
        "source": (
            "06 §7.2, Verification; results/device/layer_fidelity.json (link); noktalar önbellekten"
        ),
        "x": {"label": "izole cz tahmini", "scale": "linear"},
        "y": {"label": "ölçülen lf_100", "scale": "linear"},
        "diag": True,
        "series": [{"name": "lf olayı", "points": pts}],
    }


def chart_chains(lfj: dict[str, Any], v3: dict[str, Any]) -> dict[str, Any]:
    ch = lfj["chains"]
    link = lfj["link"]
    share = ch["lf100_inclusion_share_by_qubit"]
    never = ch["qubits_never_in_lf100_chain"]
    jq = ch["lf100_chain_jaccard_consecutive_q"]
    return {
        "id": "cihaz-zincir",
        "type": "map",
        "title": (
            "`lf_100` zinciri olaydan olaya yeniden seçiliyor: 83 olayda "
            f"{ch['distinct_lf100_chains']} farklı zincir"
        ),
        "subtitle": (
            "Kübit rengi: 83 `lf` olayının kaçında kübitin `lf_100` zincirinde yer aldığı (pay); "
            "vurgulu çerçeve: hiç kullanılmayan kübit"
        ),
        "read": (
            "Sabit bir zincir her kübite 0 ya da 1 verirdi; çoğu kübit arada. Derece-3 kübitler "
            f"medyan {cm.tr(ch['inclusion_median_degree3'], 3)}, derece-2 "
            f"{cm.tr(ch['inclusion_median_degree2'], 3)} (Mann-Whitney p = "
            f"{cm.sci(ch['inclusion_by_degree_mannwhitney_p'])}), derece-1 "
            f"{cm.tr(ch['inclusion_median_degree1'], 3)} (yol ancak orada bitebilir). "
            f"{', '.join(f'`q{q}`' for q in never)} hiç kullanılmıyor: üçü kalıcı arızalı "
            "kuplörlerde, `q64` için yer tutucu verisinde bir neden görünmüyor. Ardışık "
            f"zincirlerin kübit örtüşmesi (Jaccard) medyan {cm.tr(jq[3], 3)}; "
            f"{link['consecutive_pairs_same_lf100_chain']} ardışık çift aynı zincir."
        ),
        "caveat": (
            "Zincir değişiminin `lf`'nin kalıcı olmayan bileşenine katkısı yalnızca düşündürücü: "
            "`ln(lf_100)`'ün olaydan olaya değişiminin robust standart sapması zincir "
            f"değiştiğinde {cm.tr(link['mad_sd_change_lnlf100_chain_changed'], 3)} (doğrulayıcı "
            f"{cm.tr(v3['robust_sd_dln_diff'], 3)}), değişmediğinde "
            f"{cm.tr(link['mad_sd_change_lnlf100_same_chain'], 3)}; aynı zincirli yalnızca "
            f"{v3['consecutive_pairs_in_archive']['same']} çift, permütasyon p = "
            f"{cm.tr(v3['perm_p_sd_diff_ge_same'], 3)}, Levene p = {cm.tr(v3['levene_p'], 3)} "
            "(06 Doğrulama). Bileşenin kendisi ne tahmin hatasına ne gerçek dalgalanmaya "
            "atfedilebiliyor (06 §4)."
        ),
        "source": "06 §4, §5.3, §7.1, Verification; results/device/layer_fidelity.json (chains)",
        "scale": "seq",
        "domain": [0, 1],
        "node_values": {str(q): cm.r4(s) for q, s in enumerate(share)},
        "node_flags": {str(q): "never" for q in never},
        "flags": {"never": "hiçbir lf_100 zincirinde değil"},
        "node_label": "lf_100 zincirinde olma payı",
    }


def main() -> int:
    dd = ddload.DD()
    sched = cm.load("device/schedule.json")
    docs = cm.load("device/documents.json")
    cps = cm.load("device/changepoints.json")
    st = cm.load("device/states.json")
    lay = cm.load("device/layout_faults.json")
    lfj = cm.load("device/layer_fidelity.json")
    v1 = cm.load("verify/device/v1_basics.json")
    v3 = cm.load("verify/device/v3_lf_ratio.json")
    v4 = cm.load("verify/device/v4_faults.json")
    v5 = cm.load("verify/device/v5_changepoint.json")
    v6 = cm.load("verify/device/v6_readout_cadence.json")
    lf = LF(dd)
    charts = [
        chart_clock(dd, sched),
        chart_order(sched),
        chart_coverage(docs, v6),
        chart_readout(dd, cps, v5),
        chart_coherence(dd, cps, cm.load("coherence/temporal.json")),
        chart_states(dd, st),
        chart_faults(dd, lay, v4),
        chart_degree(lay),
        chart_eplg(lf, lfj, cps, v1),
        chart_ratio(lf, lfj, v3),
        chart_pred(lf, lfj),
        chart_chains(lfj, v3),
    ]
    fams = sched["families"]
    summ = cps["summary_value_series"]["c8"]
    payload = {
        "section": SECTION,
        "title_tr": (
            "Cihaz ve zaman: takvim, değişim noktaları, arızalar, yerleşim ve layer fidelity"
        ),
        "intro_tr": [
            (
                "Bu bölüm belgelerin kendisini, IBM'in kalibrasyon takvimini, cihaz geneli "
                "değişimleri, arıza haritasını, heavy-hex yerleşimini ve layer fidelity'yi "
                "(`lf_N`) inceliyor (06). Takvim IBM'in hiçbir kaynağında tarif edilmiyor; "
                "aşağıdaki takvim ifadelerinin hepsi kayıt damgalarından çıkarım."
            ),
            (
                "Günlük döngü 24 saatten biraz uzun (24,7 ile 25,3 saat) ve saatin etrafında "
                "dolaşıyor; yeniden başlatmalar onu geri çekiyor. Bir döngü içinde sıra sabit: "
                "readout ve `measure_2`, saniyeler arayla `T1` ve `T2`, yaklaşık bir saat sonra "
                "`sx`, saatler sonra `cz` ve `rzz`. `lf` kendi 26,5 saatlik döngüsünde."
            ),
            (
                "Cihaz medyanlarındaki değişim noktaları bilinen olaylarla ancak şans düzeyinde "
                "örtüşüyor. Kalıcı arızalı kuplörler iki kübit çevresinde birleşiyor (`q72`, "
                "`q99`). Katmanlı zincirlerde ölçülen hata, "
                "aynı zincirin izole `cz` değerlerinden beklenenin yaklaşık 1,4 katı; nedeni açık."
            ),
        ],
        "bullets_tr": [
            (
                f"**Döngü**: `T1` için {fams['T1']['rounds_major']} ana tur, medyan aralık "
                f"{cm.tr(fams['T1']['gap_h_q'][3], 2)} saat, her gün "
                f"{cm.tr(fams['T1']['daily_shift_h_median'], 2)} saat daha geç; `cz` "
                f"{cm.tr(fams['cz']['daily_shift_h_median'], 2)}, `rzz` "
                f"{cm.tr(fams['rzz']['daily_shift_h_median'], 2)}, `lf` "
                f"{cm.tr(fams['lf']['daily_shift_h_median'], 2)} saat (06 §3.1)."
            ),
            (
                "**Bir tur birkaç saniyelik damga grubu**: `sx`, `T2` ve `xslow` gruplarında hiç "
                "komşu kübit çifti yok (`sx` için 0, rastgele beklenti 5.657); readout ve `T1` "
                "grupları kübit indeks sırasını izliyor (06 §3.3). Damgalar ölçüm değil yazım "
                "zamanı gibi davranıyor (yorum)."
            ),
            (
                "**Kapsam ve kadans**: belge/gün 9,25'ten 22,77'ye çıkarken görünen readout "
                "turu/gün 5,62'den 3,67'ye indi; düşüş yalnızca canlı belgeli aylarda da var "
                "(06 §3.4, Doğrulama)."
            ),
            (
                f"**Değişim noktaları**: en tutucu cezada {summ['detected']} noktanın "
                f"{summ['matched']}'i bilinen bir olaya 36 saat içinde, şansla beklenen "
                f"{cm.tr(summ['expected_by_chance'], 2)}. 8 Haziran readout düşüşü (−0,138 dekad) "
                "tek olay ve atfedilemiyor; en büyük düşüş 17 Mayıs'ta, bilinen olay yok (06 §3.5, "
                "Doğrulama)."
            ),
            (
                "**Açıklanmamış bölüm**: `init_error` 21 Ağustos'ta 0,225 dekad yükselip 31 "
                "Ağustos'ta 0,300 dekad düşüyor; aynı tarihlerde readout noktaları var, bilinen "
                "olay yok (06 §3.5)."
            ),
            (
                f"**Durumlar**: {st['distinct_states']} ayrık durum kübit kaydı durumu; aynı "
                f"durumdaki {st['consecutive_pairs_same_state']} ardışık çiftin "
                f"{st['same_state_pairs_with_any_listed_change']}'ünde bir kapı, `lf`, `zz` ya da "
                "eşik değişiyor (06 §2.4, §7.1)."
            ),
            (
                "**Arızalar**: 6 kalıcı arızalı kuplörden 2 bitişik çift `q72` ve `q99` "
                'üzerinden (p = 0,018); "uzamsal yoğunlaşma" yalnızca düşündürücü (p = 0,042; '
                "0,16) (06 §5.2, Doğrulama)."
            ),
            (
                "**Layer fidelity**: `lf_100` medyanı 0,545, EPLG(100) 0,00489 ve zamanla artıyor; "
                "katmanlı hata izole `cz` tahmininin 1,36 ile 1,41 katı, N'den bağımsız; 83 olayda "
                "59 farklı `lf_100` zinciri (06 §2.5, §7.1, §7.2)."
            ),
        ],
        "charts": charts,
    }
    path = cm.write_section(SECTION, payload)
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
