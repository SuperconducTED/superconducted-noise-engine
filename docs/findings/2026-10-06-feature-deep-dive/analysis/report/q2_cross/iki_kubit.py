"""Report section "iki-kubit": two-qubit gates and couplings (05) for the advisor page.

Writes ``results/report/iki-kubit.json`` (format: ``analysis/report/spec_check.py``). Every
headline number is read from ``results/gates_2q/*.json``; the per-coupler and per-event
series that no results file holds (scatters, histograms, device maps) are recomputed from the
cache with the owner's own definitions, imported from ``analysis/gates_2q`` (canonical coupler
``a < b``, measured-rule events with placeholders masked, ``limit_2q``), and each is checked
against the owner's figure before it is used (``q2common.check``).

Loads ``g2.cz.*``, ``g2.rzz.*``, ``gen.zz``, ``q.T1`` and ``q.T2`` and the configuration
coordinates. Not charted here on purpose: variograms and the correlation of couplers that share
a qubit (the root section owns them).
"""

# Turkish text uses the dotless i, which RUF001 flags as ambiguous; it is intended. The section
# text is long Turkish prose in f-strings that ruff format does not split, hence E501.
# ruff: noqa: RUF001, E501

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gates_2q"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common2q as c2
import ddload
import q2common as rc
from link_qubits import limit_2q

KHZ = 1e6
ODD_LENGTH = ("102-103", "146-147", "68-69", "80-81", "106-107")
FROZEN_ZZ = ("13-14", "39-53", "109-118")


def gantt_rows(prof: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for gate in ("cz", "rzz"):
        for cpl in prof[gate]["placeholders"]["couplers"]:
            if cpl["runs"] > cpl["runs_listed_cap"]:
                raise ValueError(f"{gate} {cpl['coupler']}: runs truncated in profile.json")
            spans = [
                [rc.stem_iso(r["first_file"]), rc.stem_iso(r["last_file"])] for r in cpl["run_list"]
            ]
            rows.append({"label": f"{gate} {cpl['coupler']}", "spans": spans, "group": gate})
    return rows


def main() -> int:
    prof = rc.load("gates_2q/profile.json")
    rel = rc.load("gates_2q/cz_vs_rzz.json")
    temp = rc.load("gates_2q/temporal.json")
    spat = rc.load("gates_2q/spatial.json")
    zzj = rc.load("gates_2q/zz.json")
    link = rc.load("gates_2q/link.json")

    dd = ddload.DD()
    pairs, fwd, _ = c2.canonical(dd)
    lab = [c2.label(p) for p in pairs]
    at = {name: i for i, name in enumerate(lab)}
    ser = {g: c2.gate_series(dd, g, fwd) for g in c2.GATES}
    evmed = {
        g: np.array(
            [np.median(np.log10(ser[g][col].y)) if col in ser[g] else np.nan for col in fwd]
        )
        for g in c2.GATES
    }
    recs = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for g in c2.GATES:
            v = np.array(dd.v(f"g2.{g}.gate_error"))[:, fwd]
            recs[g] = np.where(v < 1.0, v, np.nan)
        recmed = {g: np.nanmedian(recs[g], axis=0) for g in c2.GATES}
    charts: list[dict[str, Any]] = []

    # ---- 1. cz against rzz, per-coupler event medians
    both = np.isfinite(evmed["cz"]) & np.isfinite(evmed["rzz"])
    rho = float(stats.spearmanr(evmed["cz"][both], evmed["rzz"][both]).statistic)
    ratio = 10.0 ** (evmed["rzz"][both] - evmed["cz"][both])
    lv = rel["levels"]
    rc.check("cz-rzz couplers", int(both.sum()), rel["couplers_with_both_series"], 0)
    rc.check("cz-rzz Spearman", rho, lv["between_coupler_spearman_of_log_medians"]["rho"], 5e-4)
    rc.check(
        "rzz/cz median ratio",
        float(np.median(ratio)),
        lv["per_coupler_median_ratio_rzz_over_cz_q"][4],
        5e-4,
    )
    named = {"31-32", "148-149", "149-150", "102-103"}
    pts: list[list[Any]] = []
    for i in np.flatnonzero(both):
        p: list[Any] = [rc.r4(10 ** evmed["cz"][i]), rc.r4(10 ** evmed["rzz"][i])]
        if lab[i] in named:
            p.append(lab[i])
        pts.append(p)
    ext = {e["coupler"]: e["rzz_over_cz"] for e in lv["extremes"]}
    hi3 = sorted(ext[k] for k in ("148-149", "149-150", "102-103"))
    charts.append(
        {
            "id": "cz-rzz-kuplor-medyanlari",
            "type": "scatter",
            "title": "`cz` ve `rzz` aynı kuplörün kalitesini ölçer, ama biri ötekinin kopyası değildir",
            "subtitle": (
                f"Kuplör başına olay medyanı: x `cz` hatası, y `rzz` hatası (log-log; "
                f"{int(both.sum())} kuplör; yer tutucular maskeli). Çizgi y = x."
            ),
            "read": (
                f"Noktalar köşegen çevresinde dar bir bantta: kuplör medyanları arasında Spearman "
                f"{rc.dec(rho)}, `rzz/cz` oranının medyanı {rc.dec(float(np.median(ratio)))} "
                f"(`rzz` medyanı daha düşük olan kuplörlerin payı "
                f"{rc.pct(lv['share_couplers_rzz_median_below_cz'])}). Uçlar: 31-32'de `rzz`, `cz`'nin {rc.dec(ext['31-32'])} katı; 148-149, "
                f"149-150 ve 102-103'te {rc.dec(hi3[0], 2)} ile {rc.dec(hi3[-1], 2)} katı. Aynı "
                f"dosyada ikisinin de geçerli olduğu {rc.intk(lv['same_file_records_both_valid'])} "
                f"kaydın hiçbirinde iki değer eşit değil."
            ),
            "source": "05 §1.1, §7.1; results/gates_2q/cz_vs_rzz.json (levels)",
            "x": {"label": "`cz` hatası (kuplör medyanı)", "scale": "log"},
            "y": {"label": "`rzz` hatası (kuplör medyanı)", "scale": "log"},
            "diag": True,
            "series": [{"name": "kuplör", "points": pts}],
        }
    )

    # ---- 2. cz levels on the device
    sc = spat["cz"]
    always_cz = set(prof["cz"]["placeholders"]["couplers_always_placeholder"])
    share_102 = next(
        x["share_of_files"]
        for x in prof["cz"]["placeholders"]["couplers"]
        if x["coupler"] == "102-103"
    )
    edge_cz = {lab[i]: rc.r4(10 ** evmed["cz"][i]) for i in range(len(lab))}
    flags_cz = dict.fromkeys(sorted(always_cz), "hep-yer-tutucu")
    flags_cz["102-103"] = "cogunlukla-yer-tutucu"
    charts.append(
        {
            "id": "cz-cihaz-haritasi",
            "type": "map",
            "title": "Kötü `cz` kuplörleri cihazda öbeklenir",
            "subtitle": (
                f"Kuplör başına `cz` olay medyanı (log renk ölçeği; {sc['couplers']} kuplör). İşaretli "
                f"kenarlar: her dosyada yer tutucuda olan {len(always_cz)} kuplör (değer yok) ve "
                f"2026-09-29'a kadar çoğunlukla yer tutucuda kalan 102-103."
            ),
            "read": (
                f"Bir kübit paylaşan kuplörler benzer seviyededir: Moran's I "
                f"{rc.dec(sc['morans_i_log']['I'])} (permütasyon p {rc.dec(sc['morans_i_log']['p_one_sided'], 4)}; "
                f"sıfır dağılımının %97,5 noktası {rc.dec(sc['morans_i_log']['null_q_2p5_50_97p5'][2], 2)}). "
                f"`rzz` için aynı ölçü {rc.dec(spat['rzz']['morans_i_log']['I'])} "
                f"(p {rc.dec(spat['rzz']['morans_i_log']['p_one_sided'], 4)}). İki kapıda da yönelim, satır ya da "
                f"merkezden uzaklık etkilerinin hiçbiri 21 test için Bonferroni düzeltmesinden sonra kalmaz."
            ),
            "caveat": (
                "Moran's I seviyelerin öbeklendiğini gösterir, nedenini göstermez. 05'in doğrulayıcısına "
                "göre bu öbeklenme, bir kübit paylaşan kuplörlerin ortak sapmasıyla büyük olasılıkla aynı "
                "olgudur (yorum)."
            ),
            "source": "05 §5.2, §6.1 and Verification; results/gates_2q/spatial.json, profile.json",
            "scale": "seqlog",
            "node_values": {},
            "edge_values": edge_cz,
            "edge_flags": flags_cz,
            "flags": {
                "hep-yer-tutucu": "Her dosyada yer tutucu (1): ölçülmüş değer yok",
                "cogunlukla-yer-tutucu": (
                    f"Yer tutucuda geçen dosya payı {rc.pct(share_102)}; 2026-09-29'dan beri ölçülüyor"
                ),
            },
            "edge_label": "`cz` hatası",
        }
    )

    # ---- 3. placeholder episodes
    rows = gantt_rows(prof)
    runs = [
        r for g in ("cz", "rzz") for x in prof[g]["placeholders"]["couplers"] for r in x["run_list"]
    ]
    finite_runs = [r["hours"] for r in runs if not (r["open_at_start"] and r["open_at_end"])]
    pc, pr = prof["cz"]["placeholders"], prof["rzz"]["placeholders"]
    rec_102 = next(
        x["record_median_error"]
        for x in prof["cz"]["lengths"]["non_68ns_couplers"]
        if x["coupler"] == "102-103"
    )
    shared = next(r for x in pr["couplers"] if x["coupler"] == "38-49" for r in x["run_list"])
    charts.append(
        {
            "id": "yer-tutucu-donemleri",
            "type": "gantt",
            "title": "Arızalar tek tek kötü değerler değil, günlerden aylara süren durumlardır",
            "subtitle": (
                f"Kuplör ve kapı başına yer tutucu (1) dönemleri, dönemin ilk dosyasından son yer "
                f"tutucu dosyasına; {pc['couplers_ever_placeholder']} `cz` ve "
                f"{pr['couplers_ever_placeholder']} `rzz` kuplörü, 1.760 dosya."
            ),
            "read": (
                f"`cz`'de {len(pc['couplers_always_placeholder'])}, `rzz`'de "
                f"{len(pr['couplers_always_placeholder'])} kuplör her dosyada yer tutucudadır; diğer "
                f"dönemler {rc.dec(min(finite_runs), 1)} saatten {rc.intk(max(finite_runs))} saate uzanır "
                f"(girişler: `cz` {pc['entries_into_placeholder']}, `rzz` {pr['entries_into_placeholder']}). "
                f"`cz` 102-103 dosyaların {rc.pct(share_102)}'inde yer tutucudaydı ve 2026-09-29'da çıktı; "
                f"o tarihten beri kayıt medyanı {rc.sci(rec_102)}. 2026-09-03'te dört kuplörde (38-49, "
                f"49-50, 148-149, 149-150) aynı anda başlayan {rc.dec(shared['hours'], 1)} saatlik `rzz` "
                f"dönemi, dört bağımsız arızadan çok kalibrasyon tarafında tek bir olaya benzer (yorum)."
            ),
            "caveat": "Arşivin ilk dosyasında zaten açık olan dönemlerin süresi bir alt sınırdır.",
            "source": "05 §6.1; results/gates_2q/profile.json (placeholders.couplers.run_list)",
            "x": {
                "label": "Tarih (UTC)",
                "scale": "time",
                "min": "2026-05-13T12:13:22Z",
                "max": "2026-10-06T02:57:42Z",
            },
            "markers": [
                {
                    "axis": "x",
                    "value": rc.stem_iso(shared["first_file"]),
                    "label": "Dört kuplörde ortak `rzz` dönemi",
                },
                {
                    "axis": "x",
                    "value": "2026-09-29T02:26:26Z",
                    "label": "102-103 `cz` yer tutucudan çıkar",
                },
            ],
            "rows": rows,
        }
    )

    # ---- 4. coherence limit over reported error, per event
    t1 = np.array(dd.v("q.T1"))
    t2 = np.array(dd.v("q.T2"))
    ratios: dict[str, np.ndarray] = {}
    for g in c2.GATES:
        glen = np.array(dd.v(f"g2.{g}.gate_length"))
        parts = []
        for i, col in enumerate(fwd):
            if col not in ser[g]:
                continue
            s = ser[g][col]
            a, b = pairs[i]
            f = s.file_idx
            parts.append(limit_2q(t1[f, a], t2[f, a], t1[f, b], t2[f, b], glen[f, col]) / s.y)
        ratios[g] = np.concatenate(parts)
        rc.check(
            f"{g} limit/error median",
            float(np.nanmedian(ratios[g])),
            link[g]["limit_over_error_q"][4],
            5e-4,
        )
        rc.check(f"{g} events", ratios[g].size, link[g]["events"], 0)
    edges = rc.log_edges(-2.4, 0.6)
    series_h = []
    for g in c2.GATES:
        e, k = rc.hist(ratios[g], edges)
        series_h.append({"name": f"{g} ({rc.intk(ratios[g].size)} olay)", "edges": e, "counts": k})
    ref = link["reference_limits"]
    lc = link["cz"]
    charts.append(
        {
            "id": "koherans-siniri-orani",
            "type": "hist",
            "title": "Koherans sınırı, raporlanan iki kübit hatasının medyanda yaklaşık üçte biridir",
            "subtitle": (
                "Olay başına koherans sınırı / raporlanan hata (log eksen). Sınır: o dosyada geçerli "
                "`T1`, `T2` ve kapı süresiyle, iki kübitte bağımsız genlik ve faz sönümünün verdiği "
                "ortalama kapı hatası."
            ),
            "read": (
                f"Oranın medyanı {rc.dec(lc['limit_over_error_q'][4])} (`cz`) ve "
                f"{rc.dec(link['rzz']['limit_over_error_q'][4])} (`rzz`); `cz` için %10 ile %90 arası "
                f"{rc.dec(lc['limit_over_error_q'][2])} ile {rc.dec(lc['limit_over_error_q'][6])}. Medyan "
                f"`T1` ({rc.dec(ref['median_T1_us_all_records'], 1)} µs) ve `T2` "
                f"({rc.dec(ref['median_T2_us_all_records'], 2)} µs) ile 68 ns'lik bir kapının sınırı "
                f"{rc.sci(ref['limit_at_median_T1_T2']['68'])}; medyan `cz` hatası bunun "
                f"{rc.dec(lc['event_median_error_over_68ns_limit_at_median_T1_T2'], 2)} katı. Sınırın "
                f"hatayı aştığı olayların payı {rc.pct(lc['share_events_limit_above_error'])} (`cz`) ve "
                f"{rc.pct(link['rzz']['share_events_limit_above_error'])} (`rzz`)."
            ),
            "caveat": (
                f"Sınır bir vekildir, kesin bir alt sınır değildir: kullanılan `T1` ve `T2`, kapı "
                f"damgasından medyanda {rc.dec(lc['abs_hours_gate_stamp_to_T1_T2_stamps_q'][4], 1)} saat "
                f"uzakta ölçülmüştür."
            ),
            "source": "05 §7.2; results/gates_2q/link.json (reference_limits, *.limit_over_error_q)",
            "x": {"label": "Koherans sınırı / raporlanan hata", "scale": "log"},
            "y": {"label": "Olay sayısı", "scale": "linear"},
            "markers": [{"axis": "x", "value": 1, "label": "sınır = hata"}],
            "series": series_h,
        }
    )

    # ---- 5. what goes with a coupler's level: sx, coherence limit, readout (from link.json)
    cats = [
        "hata ~ koherans sınırı",
        "hata ~ sx_a + sx_b",
        "hata ~ okuma toplamı",
        "hata ~ sx | sınır (kısmi)",
        "hata ~ sınır | sx (kısmi)",
        "hata ~ okuma | sınır, sx (kısmi)",
    ]
    keys = [
        ("spearman_err_vs_limit", "rho"),
        ("spearman_err_vs_sx_sum", "rho"),
        ("spearman_err_vs_readout_sum", "rho"),
        ("partial_err_sx_given_limit", "rho"),
        ("partial_err_limit_given_sx", "rho"),
        ("partial_err_readout_given_limit_sx", "rho"),
    ]
    bc = {g: link[g]["between_coupler"] for g in c2.GATES}
    wc = link["cz"]["within_coupler_changes"]
    charts.append(
        {
            "id": "kuplor-hatasi-iliskileri",
            "type": "bar",
            "orient": "h",
            "title": "Kötü kuplörler, koherans sınırından çok kübitlerinin `sx` hatasıyla birlikte gider",
            "subtitle": (
                f"Kuplör medyanları arasında Spearman ve kısmi sıra korelasyonları (`cz` "
                f"{bc['cz']['couplers']}, `rzz` {bc['rzz']['couplers']} kuplör). Okuma: iki kübitin okuma "
                f"hatası toplamı; ortak değişkenler kapı olayının dosyasındaki güncel değerler."
            ),
            "read": (
                f"`cz` hatası `sx_a + sx_b` ile {rc.dec(bc['cz']['spearman_err_vs_sx_sum']['rho'])}, koherans "
                f"sınırıyla {rc.dec(bc['cz']['spearman_err_vs_limit']['rho'])} korelasyonludur. Kısmi "
                f"korelasyonlar: sınır sabitken `sx` için {rc.dec(bc['cz']['partial_err_sx_given_limit']['rho'])}, "
                f"`sx` sabitken sınır için {rc.dec(bc['cz']['partial_err_limit_given_sx']['rho'])}, ikisi "
                f"sabitken okuma hatası için {rc.dec(bc['cz']['partial_err_readout_given_limit_sx']['rho'])}. Bir kuplör zamanla değişirken kübitlerinin değerleri neredeyse eşlik etmez "
                f"(ardışık değişimlerde `sx` toplamıyla {rc.dec(wc['spearman_dlog_err_vs_dlog_sx_sum']['rho'])})."
            ),
            "caveat": (
                'Doğrulayıcı "`sx` koheransten fazla açıklar" ifadesini zayıflattı: bu bir sıra '
                "korelasyonudur. Sınır, saatler uzakta damgalanmış `T1` ve `T2`'den kurulan gürültülü bir "
                "vekildir (doğrulayıcının kendi kübit düzeyi indirgemesi 0,318 verir). IBM'e göre 2Q "
                "benchmark tek kübitli Clifford dizileriyle iki kübitli kapıları dönüşümlü uygular; bu da "
                "fiziksel bir bağ olmadan aynı deseni üretebilir."
            ),
            "source": "05 §7.3 and Verification; results/gates_2q/link.json (*.between_coupler)",
            "x": {
                "label": "Spearman (kısmi: sıra korelasyonu)",
                "scale": "linear",
                "min": -0.1,
                "max": 0.7,
            },
            "categories": cats,
            "series": [
                {"name": g, "values": [rc.r4(bc[g][k][f]) for k, f in keys]} for g in c2.GATES
            ],
        }
    )

    # ---- 6. device-wide level per round: no material change in five months
    line_series = []
    for g in c2.GATES:
        d = temp[g]
        if len(d["device_round_start_series"]) != len(d["device_round_median_log10_series"]):
            raise ValueError(f"{g}: device round series lengths differ")
        line_series.append(
            {
                "name": f"{g} ({d['device_rounds_ge_half']} tur)",
                "style": "line+dots",
                "points": [
                    [t, rc.r4(10**z)]
                    for t, z in zip(
                        d["device_round_start_series"],
                        d["device_round_median_log10_series"],
                        strict=True,
                    )
                ],
            }
        )
    tc, tz = temp["cz"], temp["rzz"]
    pcc, pcr = tc["per_coupler_change_points"], tz["per_coupler_change_points"]
    charts.append(
        {
            "id": "cihaz-seviyesi-zaman",
            "type": "line",
            "title": "Cihaz çapındaki iki kübit hata seviyesi beş ayda belirgin değişmedi",
            "subtitle": (
                "Tur başına cihaz medyanı hata (kuplörlerin en az yarısını kapsayan turlar; 15 dakikadan "
                "uzun boşlukla ayrılan damgalar bir tur). Tarih turun başlangıcı, UTC. Tur sayısı her serinin ilk "
                "(arşiv öncesi damgalı) olayını içerir; bu yüzden `cz` için 131, 06'daki 130'dan bir fazla."
            ),
            "read": (
                f"Tur medyanı `cz` için {rc.sci(tc['device_round_median_q'][0])} ile "
                f"{rc.sci(tc['device_round_median_q'][-1])}, `rzz` için {rc.sci(tz['device_round_median_q'][0])} "
                f"ile {rc.sci(tz['device_round_median_q'][-1])} arasında kalır. 30 günlük Theil-Sen eğimi "
                f"`log10` cinsinden `cz` {rc.dec(tc['device_trend_log10_per_30d_theil_sen'], 5)} (%95 aralığı "
                f"{rc.dec(tc['device_trend_theil_sen_95ci_per_30d'][0], 4)} ile "
                f"{rc.dec(tc['device_trend_theil_sen_95ci_per_30d'][1], 4)}), `rzz` "
                f"{rc.dec(tz['device_trend_log10_per_30d_theil_sen'], 5)}; iki aralık da sıfırı içerir. "
                f"Kuplör düzeyinde ise seviye yer yer kayar: {pcc['couplers_tested_ge_30_events']} `cz` "
                f"kuplöründen {pcc['discoveries_bh_5pct']} tanesinde, {pcr['couplers_tested_ge_30_events']} "
                f"`rzz` kuplöründen {pcr['discoveries_bh_5pct']} tanesinde haftalarca süren bir seviye "
                f"değişimi var (Benjamini-Hochberg, %5)."
            ),
            "caveat": (
                "`rzz` serisindeki büyük boşluk 2026-08-19 ile 08-31 arasındaki 279,8 saatlik cihaz çapı "
                "duraklamadır (bu sürede `cz` turları sürdü). Doğrulayıcıya göre kapsam bölünmesinden "
                "sonraki `rzz` olay hızı düşüşünün çoğu bu tek duraklamadır: duraklama hariç 0,729, "
                "öncesinde 0,809 olay/kuplör/gün."
            ),
            "source": "05 §2.3, §3.2 and Verification; results/gates_2q/temporal.json (device_round_*)",
            "x": {"label": "Tur başlangıcı (UTC)", "scale": "time"},
            "y": {"label": "Cihaz medyanı hata", "scale": "linear"},
            "markers": [
                {
                    "axis": "x",
                    "value": prof["coverage_split"]["split_utc"],
                    "label": "Kapsam bölünmesi",
                }
            ],
            "series": line_series,
        }
    )

    # ---- 7. zz bursts: device-wide refresh about every 5 h
    gcol = c2.gen_columns(dd, pairs)
    zz = np.array(dd.v("gen.zz"))[:, gcol] * KHZ
    changed = np.diff(zz, axis=0) != 0
    per_file = changed.sum(axis=1)
    burst = np.flatnonzero(per_file > 0) + 1
    bgap = np.diff(dd.file_ms[burst]) / ddload.MS_PER_HOUR
    zb = zzj["bursts"]
    rc.check("zz bursts", burst.size, zb["files_with_any_change"], 0)
    rc.check("zz median burst gap", float(np.median(bgap)), zb["gap_between_bursts_h_q"][4], 5e-3)
    e, k = rc.hist(bgap, rc.log_edges(-0.4, 2.0))
    al = zzj["alignment_with_gate_rounds"]["cz"]
    cz_gap = prof["cz"]["values"]["rounds"]["gap_between_round_starts_h_q"][4]
    charts.append(
        {
            "id": "zz-patlama-araliklari",
            "type": "hist",
            "title": "`zz` tüm cihazda yaklaşık 5 saatte bir yeniden belirlenir; günlük kapı turlarına belirgin bağlı görünmüyor",
            "subtitle": (
                f"Ardışık `zz` değişim patlamaları (en az bir kuplörün değeri değişen dosyalar) arasındaki "
                f"süre, saat (log eksen; {burst.size} patlama, {bgap.size} aralık)."
            ),
            "read": (
                f"Medyan aralık {rc.dec(zb['gap_between_bursts_h_q'][4], 2)} saat (çeyrekler "
                f"{rc.dec(zb['gap_between_bursts_h_q'][3], 2)} ve {rc.dec(zb['gap_between_bursts_h_q'][5], 2)}); "
                f"`cz` turları arasındaki medyan {rc.dec(cz_gap, 1)} saatin yaklaşık beşte biri. "
                f"{zb['files_with_any_change']} patlamanın {zb['bursts_with_ge_170_couplers']} tanesi 176 "
                f"kuplörün en az 170'ini birlikte değiştirir. `cz` olayı içeren {al['files_with_events']} "
                f"dosyada patlama payı {rc.pct(al['event_files_that_are_bursts'])}, tüm dosyalarda "
                f"{rc.pct(al['share_of_all_files_that_are_bursts'])}: patlamalar kapı turlarına belirgin biçimde bağlı görünmüyor. "
                f"Değişimler kalıcı değildir (gecikme-1 öz-korelasyonu {rc.dec(zzj['lag1_autocorr_dlog_abs_zz'])})."
            ),
            "caveat": (
                "`zz` tarihi her kayıtta dosyanın oluşturulma zamanıdır; zamanlama yalnızca değerin "
                "değiştiği ilk dosyadan okunur. IBM'in `zz` değerini doğrudan bir ZZ deneyiyle mi ölçtüğü, "
                "yoksa başka sık ölçülen büyüklüklerden mi hesapladığı belgeden karar verilemez."
            ),
            "source": "05 §1.4; results/gates_2q/zz.json (bursts, alignment_with_gate_rounds)",
            "x": {"label": "Patlamalar arası süre", "scale": "log", "unit": "saat"},
            "y": {"label": "Aralık sayısı", "scale": "linear"},
            "markers": [
                {"axis": "x", "value": rc.r4(zb["gap_between_bursts_h_q"][4]), "label": "medyan"},
                {"axis": "x", "value": rc.r4(cz_gap), "label": "`cz` turu medyanı"},
            ],
            "series": [{"name": "patlamalar arası süre", "edges": e, "counts": k}],
        }
    )

    # ---- 8. zz per-coupler level by orientation
    coords = np.array(next(iter(dd.meta["config_values"]["coords"].values()))["value"], dtype=float)
    a_ = np.array([p[0] for p in pairs])
    b_ = np.array([p[1] for p in pairs])
    horizontal = coords[a_, 1] == coords[b_, 1]
    absmed = np.median(np.abs(zz), axis=0)
    nz = absmed > 0
    zs = spat["abs_zz"]
    rc.check(
        "zz horizontal median",
        float(np.median(absmed[nz & horizontal])),
        zs["horizontal_median"] * KHZ,
        5e-3,
    )
    rc.check(
        "zz bridge median",
        float(np.median(absmed[nz & ~horizontal])),
        zs["bridge_median"] * KHZ,
        5e-3,
    )
    edges_zz = rc.log_edges(-0.1, 1.5)
    e_h, k_h = rc.hist(absmed[nz & horizontal], edges_zz)
    _, k_b = rc.hist(absmed[nz & ~horizontal], edges_zz)
    rq = zzj["record_khz_q"]
    charts.append(
        {
            "id": "zz-kuplor-dagilimi",
            "type": "hist",
            "title": "Statik ZZ birkaç kHz düzeyindedir ve köprü kuplörlerde daha büyüktür",
            "subtitle": (
                f"Kuplör başına dosyalar üzerinden medyan `|zz|`, kHz (log eksen): "
                f"{int((nz & horizontal).sum())} yatay kuplör (iki kübit aynı uzun satırda) ve "
                f"{int((nz & ~horizontal).sum())} köprü kuplör. Her dosyada 0 olan 32-33 dışarıda."
            ),
            "read": (
                f"Köprü kuplörlerin medyanı {rc.dec(zs['bridge_median'] * KHZ, 2)} kHz, yatayların "
                f"{rc.dec(zs['horizontal_median'] * KHZ, 2)} kHz: oran {rc.dec(zs['bridge_over_horizontal'], 2)} "
                f"(Mann-Whitney p {rc.dec(zs['mannwhitney_p'], 4)}). Tüm kayıtların medyanı "
                f"{rc.dec(rq[4], 2)} kHz, %10 ile %90 arası {rc.dec(rq[2], 2)} ile {rc.dec(rq[6], 1)} kHz. "
                f"Komşu kuplörler arasında kümelenme saptanmadı (Moran's I {rc.dec(zs['morans_i_log']['I'])}, "
                f"p {rc.dec(zs['morans_i_log']['p_one_sided'], 2)}); sütun boyunca bir eğim var "
                f"(Spearman {rc.dec(zs['spearman_vs_column_x']['rho'], 2)})."
            ),
            "caveat": (
                "Yönelim etkisinin sabit tasarım parametrelerinden (detuning, kuplör tasarımı) geldiği bir "
                "yorumdur; ikinci bir Heron r2 cihazında yönelim etkisi görülmezse yanlışlanır."
            ),
            "source": "05 §1.2, §5.2, §6.3; results/gates_2q/spatial.json (abs_zz), zz.json (record_khz_q)",
            "x": {"label": "Kuplör medyanı `|zz|`", "scale": "log", "unit": "kHz"},
            "y": {"label": "Kuplör sayısı", "scale": "linear"},
            "series": [
                {"name": "yatay", "edges": e_h, "counts": k_h},
                {"name": "köprü", "edges": e_h, "counts": k_b},
            ],
        }
    )

    # ---- 9. zz against cz error, between couplers
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        gmed = np.nanmedian(np.log10(recs["cz"]), axis=0)
    okc = np.isfinite(gmed) & nz
    rho_z = float(stats.spearmanr(gmed[okc], np.log10(absmed[okc])).statistic)
    rz = zzj["relations"]
    rc.check(
        "zz-cz couplers",
        int(okc.sum()),
        rz["cz"]["between_coupler_spearman_median_log_err_vs_median_abs_zz"]["n"],
        0,
    )
    rc.check(
        "zz-cz Spearman",
        rho_z,
        rz["cz"]["between_coupler_spearman_median_log_err_vs_median_abs_zz"]["rho"],
        5e-4,
    )
    odd = np.array([x in ODD_LENGTH for x in lab])
    nl = zzj["non_68ns_length_vs_abs_zz"]
    charts.append(
        {
            "id": "zz-cz-iliskisiz",
            "type": "scatter",
            "title": "Statik ZZ ile bir kuplörün `cz` hatası arasında ilişki saptanmadı",
            "subtitle": (
                f"Kuplör başına dosyalar üzerinden medyan `|zz|` (kHz, x) ve medyan `cz` hatası (y), log-log; "
                f"{int(okc.sum())} kuplör. İkinci seri: kapı süresi 88 ya da 116 ns olan beş kuplör."
            ),
            "read": (
                f"Kuplörler arası Spearman {rc.dec(rho_z)} "
                f"(p {rc.dec(rz['cz']['between_coupler_spearman_median_log_err_vs_median_abs_zz']['p'], 2)}); "
                f"`rzz` için {rc.dec(rz['rzz']['between_coupler_spearman_median_log_err_vs_median_abs_zz']['rho'])}. "
                f"Kuplör içinde de her kapı olayındaki güncel `|zz|` ile hata "
                f"{rc.dec(rz['cz']['within_coupler_spearman_demeaned']['rho'])} düzeyinde birlikte hareket eder. "
                f"Beş uzun kapılı kuplörün `|zz|` medyanları {rc.dec(min(nl['abs_median_khz']), 2)} ile "
                f"{rc.dec(max(nl['abs_median_khz']), 2)} kHz arasında, diğer {nl['rest_n']} kuplörün medyanı "
                f"{rc.dec(nl['rest_abs_median_khz_median'], 2)} kHz (Mann-Whitney p {rc.sci(nl['mannwhitney_less_p'], 1)})."
            ),
            "caveat": (
                "Uzun kapı ile düşük `|zz|` ilişkisi sıralara bakılarak bulundu; p değeri önceden konmuş bir "
                "hipotezin testi değildir, yalnızca hipotez üretir. Başka bir Heron r2 arşivinde fark "
                "görülmezse yanlışlanır."
            ),
            "source": "05 §7.4 and Verification; results/gates_2q/zz.json (relations, non_68ns_length_vs_abs_zz)",
            "x": {"label": "Kuplör medyanı `|zz|`", "scale": "log", "unit": "kHz"},
            "y": {"label": "Kuplör medyanı `cz` hatası", "scale": "log"},
            "series": [
                {
                    "name": "68 ns kuplörler",
                    "points": [
                        [rc.r4(absmed[i]), rc.r4(10 ** gmed[i])] for i in np.flatnonzero(okc & ~odd)
                    ],
                },
                {
                    "name": "88 ya da 116 ns kuplörler",
                    "points": [
                        [rc.r4(absmed[i]), rc.r4(10 ** gmed[i]), lab[i]]
                        for i in np.flatnonzero(okc & odd)
                    ],
                },
            ],
        }
    )

    # ---- 10. zz on the device, with the frozen, zero and negative couplers flagged
    frozen = {x["coupler"]: x for x in zzj["couplers_with_at_most_one_value_change"]}
    neg_all = [x["coupler"] for x in zzj["negative_couplers"] if x["negative_files"] == 1760]
    flags_zz = dict.fromkeys(FROZEN_ZZ, "donuk")
    flags_zz["32-33"] = "hep-sifir"
    for k in neg_all:
        flags_zz[k] = "hep-negatif"
    fv = [rc.dec(frozen[k]["distinct_values_khz"][-1], 3) for k in FROZEN_ZZ]
    neg68 = next(x for x in zzj["negative_couplers"] if x["coupler"] == "68-69")
    k73 = next(x for x in zzj["negative_couplers"] if x["coupler"] == "72-73")
    charts.append(
        {
            "id": "zz-cihaz-haritasi",
            "type": "map",
            "title": "`|zz|` cihazda öbeklenmesi saptanmadı; üç kuplörün değeri Temmuz'dan beri donuk",
            "subtitle": (
                f"Kuplör başına dosyalar üzerinden medyan `|zz|`, kHz (log renk ölçeği; {int(nz.sum())} "
                f"kuplör). İşaretler: 2026-07-10'dan beri tek değerde kalan üç kuplör, her dosyada 0 olan "
                f"32-33 ve her dosyada negatif olan 68-69."
            ),
            "read": (
                f"13-14, 39-53 ve 109-118 ilk 429 dosyada tam 0 idi; 2026-07-10'da birer değer aldılar "
                f"({fv[0]}; {fv[1]}; {fv[2]} kHz) ve bir daha değişmediler. Kuplör başına medyan değişim "
                f"sayısı {round(zb['value_changes_per_coupler_q'][4])}: 5 saatlik yenileme bu üç kuplöre "
                f"ulaşmıyor. 68-69 her dosyada negatif (medyan {rc.dec(neg68['median_khz'], 2)} kHz, işaret "
                f"değişimi yok). Ölü kübit 72'nin kuplörlerinde değer işaret değiştirerek salınır: 72-73'te "
                f"{rc.dec(k73['min_khz'], 0)} ile +{rc.dec(k73['max_khz'], 0)} kHz arasında "
                f"{k73['sign_changes']} işaret değişimi."
            ),
            "caveat": "`zz` kullanan bir model bu üç kuplörü yenilenmemiş saymalı, kararlı değil.",
            "source": "05 §1.4, §6.3; results/gates_2q/zz.json (couplers_with_at_most_one_value_change, negative_couplers)",
            "scale": "seqlog",
            "node_values": {},
            "edge_values": {lab[i]: (rc.r4(absmed[i]) if nz[i] else None) for i in range(len(lab))},
            "edge_flags": flags_zz,
            "flags": {
                "donuk": "2026-07-10'dan beri tek değerde donuk (öncesinde 0)",
                "hep-sifir": "Her dosyada tam 0: eksik değer işareti, iki kapı da kalıcı arızalı",
                "hep-negatif": "Her dosyada negatif; haritada mutlak değer",
            },
            "edge_label": "`|zz|` (kHz)",
        }
    )

    # ---- section text
    vc, vr = prof["cz"]["values"], prof["rzz"]["values"]
    q32 = link["faulty_coupler_qubits"]
    ref68 = prof["cz"]["lengths"]["record_median_error_at_68ns"]
    for g in c2.GATES:
        for x in prof[g]["lengths"]["non_68ns_couplers"]:
            if x["record_median_error"] is not None:
                want = x["record_median_error"]
                rc.check(
                    f"{g} {x['coupler']} record median",
                    recmed[g][at[x["coupler"]]],
                    want,
                    5e-4 * want,
                )
    pcts = [
        q32[q][k]
        for q in ("32", "33")
        for k in ("sx_percentile", "T1_percentile", "T2_percentile", "readout_percentile")
    ]
    section = {
        "section": "iki-kubit",
        "title_tr": "İki kübitli kapılar ve kuplörler: `cz`, `rzz`, `jq`, `zz`",
        "intro_tr": [
            (
                f"Bu bölüm 176 kuplörün iki kübitli alanlarını inceler: {rc.intk(vc['events_total'])} `cz` ve "
                f"{rc.intk(vr['events_total'])} `rzz` yeniden ölçüm olayı (yer tutucular olaylar kurulmadan "
                f"önce maskelenmiş) ve 83.440 `|zz|` değer olayı. Bir kuplörün iki yönü, yer tutucular "
                f"dışında değer ve tarih olarak birebir aynıdır (309.760 karşılaştırmanın hepsinde); bu "
                f"yüzden her kuplör için tek bir sütun (`a < b`) kullanılır."
            ),
            (
                "IBM'in belgelerine göre kuplör başına 2Q hata, aralarında en az iki kübit bulunan kenarlardan "
                'oluşan "izolasyon" gruplarında randomize benchmarking (RB) ile ölçülür; `rzz` hatası RZZ '
                "açıları üzerinden ortalanır ve keyfi üniterler için bir RB çeşidiyle ölçülür; 1 değeri, "
                'benchmarking birkaç gün başarılı olmadığında yazılan bayat değerdir (IBM "View backend '
                "details\", 2026-10-06'da okundu). Arşivdeki `gate_error` değerinin tam olarak bu büyüklük "
                "olduğu bir çıkarımdır. `jq` ve `zz` hiçbir IBM kaynağında tanımlanmamış."
            ),
            (
                "Her değer tek bir sayıdır ve belirsizlik taşımaz. Değerlerin bir turdan ötekine kalıcı "
                "olmayan büyük bir bileşeni vardır; bunun ne olduğu bu verilerle ayrıştırılamaz, bu yüzden "
                "burada ölçüm ya da kestirim gürültüsü diye adlandırılmaz."
            ),
        ],
        "bullets_tr": [
            (
                f"**`cz` ve `rzz` ayrı kalibrasyonlardır.** Aynı dosyada ikisinin de geçerli olduğu "
                f"{rc.intk(lv['same_file_records_both_valid'])} kaydın hiçbirinde değerler eşit değil; `rzz` "
                f"olayı `cz` olayını medyanda {rc.dec(rel['timing']['offset_nearest_rzz_minus_cz_h_q'][4], 2)} "
                f"saat sonra izler. Yine de aynı kuplörün kalitesini ölçerler: kuplör medyanları arasında "
                f"Spearman {rc.dec(lv['between_coupler_spearman_of_log_medians']['rho'])} (170 kuplör)."
            ),
            (
                f"**Seviyeler.** Olay medyanı {rc.sci(vc['event_weighted_q'][4])} (`cz`) ve "
                f"{rc.sci(vr['event_weighted_q'][4])} (`rzz`); kuplör medyanları en iyiden en kötüye "
                f"{rc.dec(vc['best_to_worst_coupler_median_ratio'], 1)} (`cz`) ve "
                f"{rc.dec(vr['best_to_worst_coupler_median_ratio'], 1)} (`rzz`) kat açılır. Cihaz düzeyindeki "
                f"iki kübit hata seviyesi beş ayda belirgin değişmedi (30 günlük Theil-Sen eğiminin %95 "
                f"aralığı sıfırı içerir)."
            ),
            (
                f"**Arızalar birer durumdur.** `cz`'de {pc['couplers_ever_placeholder']} kuplör en az bir kez "
                f"yer tutucuda (her zaman: {len(pc['couplers_always_placeholder'])}; giriş: "
                f"{pc['entries_into_placeholder']}), `rzz`'de {pr['couplers_ever_placeholder']} (her zaman: "
                f"{len(pr['couplers_always_placeholder'])}; giriş: {pr['entries_into_placeholder']}). "
                f"32-33 iki kapıda da kalıcı arızalı, oysa iki kübitinin raporlanan medyanlarının hiçbiri uç "
                f"değil (yüzdelik {int(100 * min(pcts) + 0.5)} ile {int(100 * max(pcts) + 0.5)} arası)."
            ),
            (
                f"**Koherans sınırı hatanın yaklaşık üçte biri.** Olay başına sınır/hata oranının medyanı "
                f"{rc.dec(lc['limit_over_error_q'][4])} (`cz`) ve {rc.dec(link['rzz']['limit_over_error_q'][4])} "
                f"(`rzz`); sınır, saatler uzakta ölçülmüş `T1` ve `T2`'den kurulan bir vekildir."
            ),
            (
                f"**Kuplörün seviyesi en çok kübitlerinin `sx` hatasıyla birlikte gider.** Kuplörler arası "
                f"Spearman: `sx_a + sx_b` ile {rc.dec(bc['cz']['spearman_err_vs_sx_sum']['rho'])}, koherans "
                f"sınırıyla {rc.dec(bc['cz']['spearman_err_vs_limit']['rho'])}; okuma, ikisi verildiğinde "
                f"{rc.dec(bc['cz']['partial_err_readout_given_limit_sx']['rho'])} ekler. Bu bir korelasyondur, "
                f'"açıklar" denemez.'
            ),
            (
                f"**`jq` bilgi taşımaz:** {rc.intk(prof['jq']['records'])} kaydın hepsinde 0. **Kapı süreleri "
                f"yapılandırma değeridir:** kuplörlerin çoğunda 68 ns; 102-103 ve 146-147'de 88 ns; üç "
                f"kuplörde `rzz` 116 ns; 71-72 ve 72-73'te, her dosyada yer tutucudayken, 2026-09-05'ten "
                f"beri 84 ns. Süre hatayı tek başına belirlemez: 88 ns'lik 146-147'nin `cz` kayıt medyanı "
                f"{rc.sci(recmed['cz'][at['146-147']])} (68 ns kayıtlarında {rc.sci(ref68)}), "
                f"102-103'ünkü {rc.sci(recmed['cz'][at['102-103']])}."
            ),
            (
                f"**`zz` statik ZZ'dir (birimi GHz; kayıt medyanı {rc.dec(rq[4], 2)} kHz) ve tüm cihazda "
                f"yaklaşık 5 saatte bir yenilenir.** {zb['files_with_any_change']} patlamanın "
                f"{zb['bursts_with_ge_170_couplers']} tanesi en az 170 kuplörü değiştirir, aralık medyanı "
                f"{rc.dec(zb['gap_between_bursts_h_q'][4], 2)} saat. `cz` ve `rzz` hatasıyla ilişki saptanmadı "
                f"({rc.dec(rz['cz']['between_coupler_spearman_median_log_err_vs_median_abs_zz']['rho'])} ve "
                f"{rc.dec(rz['rzz']['between_coupler_spearman_median_log_err_vs_median_abs_zz']['rho'])}); "
                f"köprü kuplörlerde {rc.dec(zs['bridge_over_horizontal'], 2)} kat büyüktür; üç kuplör "
                f"2026-07-10'dan beri donuk."
            ),
            (
                f"**Uzayda öbeklenme.** Kuplör seviyeleri grafikte öbeklenir: Moran's I `cz` için "
                f"{rc.dec(sc['morans_i_log']['I'])}, `rzz` için {rc.dec(spat['rzz']['morans_i_log']['I'])}; "
                f"`|zz|` için öbeklenme saptanmadı ({rc.dec(zs['morans_i_log']['I'])})."
            ),
        ],
        "charts": charts,
    }
    path = rc.write_section("iki-kubit", section)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
