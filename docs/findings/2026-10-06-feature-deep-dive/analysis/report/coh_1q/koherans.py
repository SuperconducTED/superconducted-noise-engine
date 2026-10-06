"""Report section ``koherans``: the findings of ``02-coherence.md`` as Turkish text and charts.

Writes ``results/report/koherans.json`` (format: ``analysis/report/spec_check.py``).

Figures come from ``results/coherence/*.json`` where a results file holds them. Series that
no results file holds (event histograms, one qubit's time series, the dip scatter, the stale
spans) are recomputed from the field cache with the owner's definitions, imported from
``analysis/coherence/cohlib.py``; every recomputed headline is checked against the figure the
document states before anything is written. Variograms are not charted here (another section
owns them). Wording follows the document's Verification section wherever it weakened a claim.
"""

# The section text is Turkish: the dotless i (U+0131) is intended, not a confusable.
# ruff: noqa: RUF001

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ddload

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "coherence"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from typing import Any

import cohlib
import numpy as np
from _common import check, fit_hist_x, iso, load, log_hist, runs, sig, write_section
from scipy import stats

DIP = float(np.log10(2.0))  # dips.py: a dip is at least a factor of two below the level
STALE_H = 72.0  # profile.py: a value older than 72 h was carried past at least three rounds
EXAMPLE_QUBIT = 6  # one of the two most dip-prone qubits (11 dips each, dips.json)
STALE_ROWS = (("q.T1", 72), ("q.T1", 11), ("q.T1", 17), ("q.T1", 103), ("q.T2", 149))


def chart_distributions(dd: ddload.DD) -> dict[str, Any]:
    s1 = cohlib.events(dd, "q.T1")
    s2 = cohlib.events(dd, "q.T2")
    t1 = np.concatenate([s.y for s in s1])
    t2 = np.concatenate([s.y for s in s2])
    check("T1 events", t1.size, 20063, 0)
    check("T2 events", t2.size, 20626, 0)
    check("T1 median us", float(np.median(t1)), 125.971, 0.01)
    check("T2 median us", float(np.median(t2)), 92.9247, 0.01)
    return {
        "id": "koh-dagilim",
        "type": "hist",
        "title": "`T1` ve `T2` dağılımları düşük değerlere doğru uzanıyor",
        "subtitle": (
            "Olay başına `T1` (20.063 olay, 156 kübit) ve `T2` (20.626 olay, 155 kübit), µs; "
            "log10 ekseninde 0,05 dekadlık kutular"
        ),
        "read": (
            "`T1` medyanı 126 µs; medyan yüzde 1'lik dilimin (39,5 µs) 3,19 katı, yüzde 99'luk "
            "dilim (261 µs) medyanın yalnız 2,07 katı. Bu asimetrik alt kuyruk `T1` dipleridir. "
            "`T2` (medyan 92,9 µs, yüzde 1'lik dilim 6,46 µs) gövdesinde de çarpık: güçlü faz "
            "kaybı yaşayan bir kübit grubu geri kalanların çok altında."
        ),
        "source": "02 §0, §2.1; results/coherence/profile.json (events.T1/T2.distribution)",
        "x": {"label": "Değer", "scale": "log", "unit": "µs"},
        "y": {"label": "Olay sayısı", "scale": "linear"},
        "markers": [
            {"axis": "x", "value": 125.971, "label": "T1: 126"},
            {"axis": "x", "value": 92.9247, "label": "T2: 92,9"},
        ],
        "series": [
            {"name": "T1", **log_hist(t1, 0.0, 2.7)},
            {"name": "T2", **log_hist(t2, 0.0, 2.7)},
        ],
    }


def chart_variance_share(profile: dict[str, Any], sx_profile: dict[str, Any]) -> dict[str, Any]:
    ev, der = profile["events"], profile["derived"]
    between = [
        ev["T1"]["variance_split"]["between_share"],
        ev["T2"]["variance_split"]["between_share"],
        der["variance_split_gamma_phi"]["between_share"],
        der["variance_split_s"]["between_share"],
        sx_profile["distribution"]["between_share"],
    ]
    for label, got, want in zip(
        ("T1", "T2", "Gamma_phi", "s", "sx"),
        between,
        (0.386, 0.817, 0.882, 0.897, 0.744),
        strict=True,
    ):
        check(f"between share {label}", got, want, 0.0006)
    return {
        "id": "koh-varyans-payi",
        "type": "stack",
        "title": "`T1` çoğunlukla kübit içinde, `T2` çoğunlukla kübitler arasında değişiyor",
        "subtitle": (
            "log10 değerlerin toplam varyansının kübit ortalamaları arasındaki ve kübit içindeki "
            "payı; olay başına, bütün kübitler (`sx` satırı 04'ten, karşılaştırma için)"
        ),
        "read": (
            "Kübitler arası pay `T1` için 0,386, `T2` için 0,817, `Gamma_phi` için 0,882, "
            "`s = T2/(2 T1)` için 0,897; `sx` hatası 0,744. Hangi kübit olduğunu bilmek `T2`'yi "
            "büyük ölçüde belirliyor, `T1`'in ise yarıdan azını: `T1`'in varyansının çoğu aynı "
            "kübitte turdan tura değişim."
        ),
        "source": (
            "02 §2.1; results/coherence/profile.json (variance_split); 04 §2; "
            "results/gates_1q/sx_profile.json (distribution.between_share)"
        ),
        "x": {"label": "Alan", "scale": "band"},
        "y": {"label": "Varyans payı", "scale": "linear", "min": 0, "max": 1},
        "categories": ["T1", "T2", "Gamma_phi", "s = T2/(2 T1)", "sx hatası (04)"],
        "series": [
            {"name": "Kübitler arası", "values": [round(v, 3) for v in between]},
            {"name": "Kübit içi", "values": [round(1.0 - v, 3) for v in between]},
        ],
    }


def chart_t1_map(spatial: dict[str, Any]) -> dict[str, Any]:
    tab = spatial["per_qubit_table"]
    moran = spatial["per_qubit_stats"]["T1"]["moran"]
    check("Moran I T1", moran["morans_i"], -0.017, 0.0005)
    check("Moran p T1", moran["perm_p_two_sided"], 0.86, 0.005)
    return {
        "id": "koh-t1-harita",
        "type": "map",
        "title": "Kübit medyanı `T1`'de komşu yapısı görülmüyor",
        "subtitle": (
            "Her kübitin `T1` olaylarının medyanı (µs; her kübitin ilk olayı hariç), heavy-hex "
            "yerleşiminde; 156 kübit"
        ),
        "read": (
            "Bağlantı grafiğinde Moran's I -0,017 (p = 0,86, 9.999 permütasyon): bağlı komşular "
            "rastgele çiftlerden daha benzer değil, yarı varyans 1 adımdan 5+ adıma kadar düz. "
            "En düşük `q72` 9,8 µs, `q149` 48,7, `q0` 51,0; en yüksek `q15` 256,7, `q13` 236,3, "
            "`q9` 204,9."
        ),
        "caveat": (
            'Test 156 birimle yalnız büyük etkileri yakalar; "yapı yok", "tespit edilmedi" '
            "demektir (02 Doğrulama). Merkezden uzaklıkla Spearman +0,254: p = 0,001386, 36 "
            "testlik Bonferroni eşiğinin (0,001389) kıl payı altında; derece etkisinin p'si "
            '(0,0028) eşiğin altına inmiyor. "Kenardaki kübitlerin `T1`\'i daha uzun" '
            "tekrarlanması gereken bir aday, bulgu değil."
        ),
        "source": (
            "02 §5; results/coherence/spatial.json (per_qubit_table, per_qubit_stats.T1.moran, "
            "lowest_T1_qubits, highest_T1_qubits)"
        ),
        "scale": "seqlog",
        "node_label": "medyan T1 (µs)",
        "node_values": {str(r["q"]): r["T1_us"] for r in tab},
        "node_flags": {"72": "q72", "11": "bayat", "17": "bayat"},
        "flags": {
            "q72": "T1 seyrek ölçülüyor ve 1.126 dosyada 72 saatten eski; T2 hiç yok",
            "bayat": "T1 uzun süre yeniden ölçülmeden taşındı (gizli eskime)",
        },
    }


def chart_t2_map(spatial: dict[str, Any]) -> dict[str, Any]:
    tab = spatial["per_qubit_table"]
    moran = spatial["per_qubit_stats"]["T2"]["moran"]
    check("Moran I T2", moran["morans_i"], 0.116, 0.0005)
    check("Moran p T2", moran["perm_p_two_sided"], 0.10, 0.005)
    t2 = sorted((r["T2_us"], r["q"]) for r in tab if r["T2_us"] is not None)
    check("T2 median lowest q149", t2[0][0], 5.18, 0.005)
    check("T2 median highest q1", t2[-1][0], 206.3, 0.05)
    check("T1-T2 across qubits", spatial["across_qubits"]["T1_vs_T2"]["spearman"], 0.30, 0.005)
    return {
        "id": "koh-t2-harita",
        "type": "map",
        "title": (
            "Kübit medyanı `T2` 5 ile 206 µs arasında; komşular arasında benzerlik saptanmadı"
        ),
        "subtitle": (
            "Her kübitin `T2` olaylarının medyanı (µs; ilk olay hariç), heavy-hex yerleşiminde, "
            "log renk ölçeği; 155 kübit (`q72` için `T2` hiç raporlanmıyor)"
        ),
        "read": (
            "En düşük `q149` 5,2 µs ve `q150` 5,6 µs, en yüksek `q1` 206,3 µs. Moran's I 0,116 "
            "(p = 0,10). Kübit medyanlarında `T2` ile `T1` arasında Spearman yalnız 0,30, `T2` "
            "ile `Gamma_phi` arasında -0,96: bir kübitin `T2`'sini `T1`'i değil, faz kaybı "
            "belirliyor."
        ),
        "source": (
            "02 §5, §7; results/coherence/spatial.json (per_qubit_table, per_qubit_stats.T2, "
            "across_qubits)"
        ),
        "scale": "seqlog",
        "node_label": "medyan T2 (µs)",
        "node_values": {str(r["q"]): r["T2_us"] for r in tab},
        "node_flags": {"72": "yok", "149": "bayat"},
        "flags": {
            "yok": "T2 hiçbir dosyada yok",
            "bayat": "T2 351 dosyada 72 saatten eski",
        },
    }


def dip_series(dd: ddload.DD) -> dict[int, dict[str, Any]]:
    """dips.py's per-qubit series: first event dropped, at least 20 events, 14-event level."""
    per: dict[int, dict[str, Any]] = {}
    for s in cohlib.events(dd, "q.T1"):
        z = np.log10(s.y[1:])
        t = s.t_ms[1:]
        if z.size < 20:
            continue
        per[s.entity] = {"z": z, "t": t, "level": cohlib.rolling_level(z)}
    return per


def chart_dip_example(per: dict[int, dict[str, Any]], dips: dict[str, Any]) -> dict[str, Any]:
    n_dips, n_events, lens = 0, 0, []
    for d in per.values():
        dev = d["z"] - d["level"]
        ok = np.isfinite(dev)
        flag = ok & (dev <= -DIP)
        n_dips += int(flag.sum())
        n_events += int(ok.sum())
        lens += [b - a + 1 for a, b in runs(flag.tolist())]
    check("dip events", n_dips, 630, 0)
    check("events with a level", n_events, 19595, 0)
    check("episodes", len(lens), 602, 0)
    check("single-event episodes", sum(n == 1 for n in lens), 574, 0)
    f2 = dips["dips"]["factor_2"]
    check("recovery median h", f2["episode_duration_to_recovery_h_quantiles"][4], 25.0, 0.05)
    pers = dips["persistence"]["all"]
    check("consecutive dip pairs", pers["observed_consecutive_dip_pairs"], 28, 0)
    check("shuffled mean", pers["shuffled_mean"], 21.6, 0.05)
    check("shuffled 5%", pers["shuffled_quantiles_5_50_95"][0], 15, 0)
    check("shuffled 95%", pers["shuffled_quantiles_5_50_95"][2], 29, 0)
    check("persistence p", pers["p_shuffled_ge_observed"], 0.10, 0.001)
    d = per[EXAMPLE_QUBIT]
    dev = d["z"] - d["level"]
    flag = np.isfinite(dev) & (dev <= -DIP)
    check("example qubit dips", int(flag.sum()), 11, 0)
    t = [iso(ms) for ms in d["t"]]
    val = 10.0 ** d["z"]
    lvl = 10.0 ** d["level"]
    return {
        "id": "koh-dip-ornek",
        "type": "line",
        "title": "Bir `T1` dipi çoğunlukla tek turda kalıyor: `q6` örneği",
        "subtitle": (
            f"`q6`'nın {d['z'].size} `T1` olayı (µs, log ekseni), kayan seviyesi (komşu 14 "
            "olayın medyanı, olayın kendisi hariç) ve seviyenin en az 2 kat altındaki olaylar"
        ),
        "read": (
            "`q6` 11 dip ile en çok dip gösteren iki kübitten biri. Cihaz genelinde 19.595 "
            "olayın 630'u (%3,2; 151 kübit) dip; 602 epizodun 574'ü tek olay, 28'i iki olay. "
            "Dip, medyan 25,0 saat sonra, yani bir sonraki turda sona eriyor."
        ),
        "caveat": (
            'Doğrulayıcı "dipler bir tur sürer, şanstan fazla sürmez" ifadesini zayıflattı: '
            "art arda dip çifti 28; olayların sırası karıştırıldığında ortalama 21,6 (yüzde 5 ile "
            "95: 15 ile 29), p = 0,10. Bu yaklaşık %30 fazla ve test 28 çifte dayanıyor. 25 "
            "saatlik örneklemede birkaç saatlik bir bekleme "
            "art arda dip üretemez. Tek turluk dipler veriyle tutarlı, kanıtlanmış değil."
        ),
        "source": (
            "02 §0, §4.2 ve Doğrulama; results/coherence/dips.json (dips.factor_2, persistence, "
            "most_dip_prone_qubits_factor_2); q6 serisi önbellekten dips.py tanımlarıyla"
        ),
        "x": {"label": "Tarih", "scale": "time"},
        "y": {"label": "T1", "scale": "log", "unit": "µs"},
        "series": [
            {
                "name": "T1 olayı",
                "style": "dots",
                "points": [[a, sig(b)] for a, b in zip(t, val, strict=True)],
            },
            {
                "name": "Kayan seviye",
                "style": "line",
                "points": [
                    [a, sig(b) if np.isfinite(b) else None] for a, b in zip(t, lvl, strict=True)
                ],
            },
            {
                "name": "Dip (seviyenin 2 kat altı)",
                "style": "dots",
                "points": [[t[i], sig(val[i])] for i in np.flatnonzero(flag)],
            },
        ],
    }


def chart_t2_in_dips(dd: ddload.DD, dips: dict[str, Any]) -> dict[str, Any]:
    """dips.py's ``t2_during_t1_dips`` block, keeping the points."""
    pairs, _ = cohlib.paired(dd)
    obs, pred = [], []
    for p in pairs:
        if p.t1.size < 20:
            continue
        z1, z2 = np.log10(p.t1), np.log10(p.t2)
        l1, l2 = cohlib.rolling_level(z1), cohlib.rolling_level(z2)
        d1, d2 = z1 - l1, z2 - l2
        ok = np.isfinite(d1) & np.isfinite(d2)
        g_lv = np.maximum(1.0 / 10**l2 - 0.5 / 10**l1, 0.0)
        pd_ = np.log10(1.0 / (0.5 / p.t1 + g_lv)) - l2
        dip = ok & (d1 <= -DIP)
        obs.append(d2[dip])
        pred.append(pd_[dip])
    od, pdd = np.concatenate(obs), np.concatenate(pred)
    ref = dips["t2_during_t1_dips"]
    check("paired dips", od.size, ref["t1_dip_events_paired"], 0)
    check("paired dips doc", od.size, 621, 0)
    check("observed median", float(np.median(od)), -0.234, 0.0006)
    check("predicted median", float(np.median(pdd)), -0.194, 0.0006)
    check("spearman", float(stats.spearmanr(od, pdd).statistic), 0.81, 0.005)
    check("share negative", float(np.mean(od < 0)), 0.979, 0.0006)
    check("share below predicted", float(np.mean(od < pdd)), 0.738, 0.0006)
    return {
        "id": "koh-dip-t2",
        "type": "scatter",
        "title": "`T1` dipinde `T2` de düşüyor, `T1` düşüşünün tek başına öngördüğünden fazla",
        "subtitle": (
            "Eşli 621 `T1` dip olayı (seviyenin 2 kat altı): x, yalnız `T1` değişseydi beklenecek "
            "log `T2` sapması (`Gamma_phi` kayan seviyesinde sabit); y, gözlenen log `T2` "
            "sapması; dekad"
        ),
        "read": (
            "Noktaların %97,9'u sıfırın altında; gözlenen medyan -0,234, öngörülen -0,194 dekad, "
            "Spearman 0,81. %73,8'i köşegenin altında: `T2` öngörülenden fazla düşüyor, yani "
            "`T1` düştüğü turda faz kaybı da artıyor. `T1` dip yapmadığında medyan `T2` sapması "
            "0,008."
        ),
        "caveat": (
            "Bu, aynı turun `T1` ve `T2` fitleri arasında paylaşılan bir değişimdir. Doğrulayıcı "
            '"gerçek düşüş" ifadesini zayıflattı: IBM yönteminde iki deneye ortak bir etki '
            "dışlanmadı (02 §4.2 ve Doğrulama)."
        ),
        "source": (
            "02 §4.2 ve Doğrulama; results/coherence/dips.json (t2_during_t1_dips); noktalar "
            "önbellekten dips.py tanımlarıyla"
        ),
        "x": {"label": "Öngörülen T2 sapması", "scale": "linear", "unit": "dekad"},
        "y": {"label": "Gözlenen T2 sapması", "scale": "linear", "unit": "dekad"},
        "diag": True,
        "series": [
            {
                "name": "T1 dip olayı",
                "points": [
                    [round(float(a), 4), round(float(b), 4)] for a, b in zip(pdd, od, strict=True)
                ],
            }
        ],
    }


def chart_t2_over_2t1(profile: dict[str, Any], adr: dict[str, Any]) -> dict[str, Any]:
    der = profile["derived"]
    counts = der["s_bin_counts"]
    check("paired events", sum(counts), 19899, 0)
    check("s > 1 events", counts[-1], 20, 0)
    check("s > 1 qubits", der["T2_gt_2T1_events"]["qubits_with_any"], 15, 0)
    check("record-level count", profile["records"]["T2_gt_2T1_records"]["count"], 424, 0)
    check("ADR-027 files", adr["rejections_per_file"]["files_with_any_t2_gt_2t1"], 379, 0)
    return {
        "id": "koh-t2-2t1",
        "type": "bar",
        "title": "Fiziksel sınır `T2 <= 2 T1` 19.899 eşli olayın yalnız 20'sinde aşılıyor",
        "subtitle": (
            "`s = T2/(2 T1)` dağılımı; eşli olaylar (aynı turda, `T2` damgası `T1`'den en çok 1 "
            "saat sonra); olay sayısı log ekseninde"
        ),
        "read": (
            "20 olay (%0,10) 15 kübitte: `q140` 4, `q117` 3, diğer 13 kübit birer; `s` 1,0001 "
            "ile 1,764 arasında. Bu olaylarda `T1` seviyesinin yaklaşık 0,30 dekad altında, `T2` "
            "ise seviyesinde (-0,013): aşımı şişmiş bir `T2` değil, `T2`'nin izlemediği bir `T1` "
            "düşüşü yaratıyor."
        ),
        "caveat": (
            "Bu 20 olay bir `T1` fit aykırı değerini, iki deney arasında `T1`'in gerçekten "
            "değişmesini ya da üstel olmayan bir bozunmayı ayıramaz (02 §2.1). Kayıt düzeyinde "
            "424 kayıt (18 kübit) var; ADR-027 bunları 379 dosyada reddediyor."
        ),
        "source": (
            "02 §0, §2.1; results/coherence/profile.json (derived.s_bin_counts, "
            "T2_gt_2T1_events, records.T2_gt_2T1_records); results/coherence/adr027.json"
        ),
        "x": {"label": "s = T2/(2 T1)", "scale": "band"},
        "y": {"label": "Eşli olay", "scale": "log"},
        "categories": [
            "0 ile 0,25",
            "0,25 ile 0,5",
            "0,5 ile 0,75",
            "0,75 ile 0,9",
            "0,9 ile 1",
            "1'den büyük",
        ],
        "series": [{"name": "Eşli olay", "values": [int(c) for c in counts]}],
    }


def chart_stale(dd: ddload.DD, profile: dict[str, Any]) -> dict[str, Any]:
    want = {}
    for field in ("T1", "T2"):
        for w in profile["records"]["staleness"][field]["worst"]:
            want[(f"q.{field}", w["qubit"])] = w["stale_files"]
    fms = dd.file_ms
    rows = []
    for field, q in STALE_ROWS:
        dates = np.array(dd.d(field)[:, q], dtype=np.float64)
        age = (fms - dates) / ddload.MS_PER_HOUR
        stale = np.isfinite(age) & (age > STALE_H)
        check(f"stale files {field} q{q}", int(stale.sum()), want[(field, q)], 0)
        spans = [[iso(fms[a]), iso(fms[b])] for a, b in runs(stale.tolist())]
        if len(spans) > 200:
            raise ValueError(f"too many spans for {field} q{q}: {len(spans)}")
        rows.append(
            {
                "label": f"q{q} {field[2:]} ({int(stale.sum())} dosya)",
                "spans": spans,
                "group": field[2:],
            }
        )
    check("stale files q72 T1 doc", want[("q.T1", 72)], 1126, 0)
    check("stale files q11 T1 doc", want[("q.T1", 11)], 876, 0)
    check("stale files q17 T1 doc", want[("q.T1", 17)], 482, 0)
    check("stale files q149 T2 doc", want[("q.T2", 149)], 351, 0)
    return {
        "id": "koh-bayat",
        "type": "gantt",
        "title": "Dört kübitin değeri haftalarca yeniden ölçülmeden taşındı",
        "subtitle": (
            "Değerin 72 saatten eski olduğu dosyalar (en az üç tur ölçümsüz); ardışık bayat "
            "dosyalar tek aralıkta birleştirildi; 1.760 dosya"
        ),
        "read": (
            "`q17`'nin `T1`'i 482 dosyada bayat, en eski hali 2.206 saat: Nisan 2026'da ölçülmüş "
            "bir değer 14 Temmuz'a kadar taşındı. `q72` `T1` 1.126, `q11` `T1` 876, `q149` `T2` "
            "351 dosyada bayat ve üçü 6 Ekim'de hâlâ bayat; `q103` `T1` daha kısa (76 dosya, en "
            "çok 132,7 saat). Dosya başına kurulan her hedef (ADR-027 dahil) bu eski değerleri "
            "tazelerle uyarısız karıştırır."
        ),
        "source": "02 §2.2, §6; results/coherence/profile.json (records.staleness)",
        "x": {"label": "Dosya tarihi", "scale": "time"},
        "rows": rows,
    }


def chart_adr027(adr: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "share_of_sum_top_1_qubit_quantiles",
        "share_of_sum_top_5pct_quantiles",
        "share_of_sum_top_10pct_quantiles",
    )
    g = adr["gamma"]["all_files"]
    lam = adr["lambda"]["all_files"]
    check("lambda top 10% median", lam[keys[2]][2], 0.48, 0.005)
    check("gamma top 10% median", g[keys[2]][2], 0.20, 0.005)
    check("lambda mean over median", lam["mean_over_median_quantiles"][2], 2.30, 0.005)
    check("gamma mean over median", g["mean_over_median_quantiles"][2], 1.12, 0.005)
    usable = adr["rejections_per_file"]["usable"][2]

    def series(name: str, block: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": name,
            "values": [round(block[k][2], 3) for k in keys],
            "lo": [round(block[k][1], 3) for k in keys],
            "hi": [round(block[k][3], 3) for k in keys],
        }

    return {
        "id": "koh-adr027",
        "type": "bar",
        "title": "ADR-027'nin anlık lambda toplamının yarıya yakını kübitlerin %10'unda",
        "subtitle": (
            "Dosya başına anlık toplamın (kullanılabilir kübitlerin gamma ya da lambda toplamı) "
            "en büyük paylı kübitlerce taşınan kısmı: 1.760 dosyanın medyanı, çizgiler yüzde 10 "
            "ile yüzde 90 dilimleri; eşit dağılım karşılaştırma için"
        ),
        "read": (
            "Faz kaybı en güçlü %10 kübit (16 kübit) lambda toplamının medyan %48'ini taşıyor "
            "(dosyaların yüzde 10 ile 90'ı arasında %46 ile %52), gamma toplamının %20'sini. "
            "Ortalama/medyan oranı lambda'da 2,30, gamma'da 1,12. Anlık lambda hedefi bu yüzden "
            "birkaç kübitin faz kaybını yarıya yakın ağırlıkla yansıtıyor."
        ),
        "caveat": (
            'Doğrulayıcı "anlık lambda çoğunlukla 16 kübitin ifadesidir" sözünü abartılı buldu: '
            'medyan pay %48, yarının altında; "çoğunluk" en çok dosyaların yarısında doğru. '
            'Doğru okuma "yarıya yakın".'
        ),
        "source": (
            "02 §8 ve Doğrulama; results/coherence/adr027.json (gamma, lambda: all_files, "
            "share_of_sum_*)"
        ),
        "x": {"label": "Kübit grubu", "scale": "band"},
        "y": {"label": "Toplamdaki pay", "scale": "linear", "min": 0, "max": 0.6},
        "categories": ["En büyük tek kübit", "En büyük %5", "En büyük %10"],
        "series": [
            series("lambda (faz sönümü)", lam),
            series("gamma (genlik sönümü)", g),
            {"name": "Eşit dağılım", "values": [round(1.0 / usable, 4), 0.05, 0.10]},
        ],
    }


def chart_seasonality(temporal: dict[str, Any]) -> dict[str, Any]:
    s1 = temporal["T1"]["seasonality_rounds"]
    s2 = temporal["T2"]["seasonality_rounds"]
    check("hour p T1", s1["kruskal_hour_p"], 0.69, 0.005)
    check("hour p T2", s2["kruskal_hour_p"], 0.95, 0.005)
    check("weekday p T1", s1["kruskal_weekday_p"], 0.89, 0.005)
    check("weekday p T2", s2["kruskal_weekday_p"], 0.86, 0.005)
    check("rounds 20-24", s1["rounds_per_hour_bin"][5], 46, 0)
    # cohlib.q levels (0, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1): index 2 is 10%, 6 is 90%
    dq = temporal["T1"]["rounds"]["device_dev_quantiles"]
    check("T1 device dev 10%", dq[2], -0.095, 0.0005)
    check("T1 device dev 90%", dq[6], 0.054, 0.0005)
    spread = [
        max(s["median_dev_per_hour_bin"]) - min(s["median_dev_per_hour_bin"]) for s in (s1, s2)
    ]
    check("largest hour-bin spread", max(spread), 0.013, 0.0005)
    edges = s1["hour_bins_utc"]
    cats = [
        f"{a:02d}-{b:02d} UTC ({n} tur)"
        for a, b, n in zip(edges[:-1], edges[1:], s1["rounds_per_hour_bin"], strict=True)
    ]
    return {
        "id": "koh-mevsimsellik",
        "type": "bar",
        "title": "Turun saatine göre `T1` ve `T2` seviyesi değişmiyor",
        "subtitle": (
            "Cihaz tur sapmasının (kübitlerin kendi tüm geçmiş medyanlarından log sapmalarının "
            "tur medyanı) dört saatlik UTC dilimlerinde medyanı, dekad; 133 büyük tur. Eksen, "
            "turdan tura `T1` cihaz sapmasının yüzde 10 ile 90 dilimlerini (-0,095 ile +0,054 "
            "dekad) içerecek genişlikte"
        ),
        "read": (
            "Dilim medyanları arasındaki en büyük fark 0,013 dekad (yaklaşık %3). "
            "Kruskal-Wallis p: saat için 0,69 (`T1`) ve "
            "0,95 (`T2`), haftanın günü için 0,89 ve 0,86. `Gamma_phi` ve `s` dahil sekiz testin "
            "hiçbiri Bonferroni eşiği 0,00625'i geçmiyor."
        ),
        "caveat": (
            'Bir tur saniyeler içinde damgalandığı için "saat", turun yazılma saatidir; turlar '
            "20:00 ile 24:00 arasında yoğunlaşıyor (133 turun 46'sı). Tek tek olaylara bakan "
            "tablo betimleyicidir, çünkü bir turun olayları bağımsız değil."
        ),
        "source": (
            "02 §3.4; results/coherence/temporal.json (T1/T2.seasonality_rounds, multiple_testing)"
        ),
        "x": {"label": "Turun UTC saati", "scale": "band"},
        "y": {
            "label": "Medyan tur sapması",
            "scale": "linear",
            "unit": "dekad",
            "min": -0.1,
            "max": 0.1,
        },
        "markers": [
            {"axis": "y", "value": -0.095, "label": "turdan tura `T1` sapmasının %10 dilimi"},
            {"axis": "y", "value": 0.054, "label": "%90 dilimi"},
        ],
        "categories": cats,
        "series": [
            {"name": "T1", "values": [round(v, 4) for v in s1["median_dev_per_hour_bin"]]},
            {"name": "T2", "values": [round(v, 4) for v in s2["median_dev_per_hour_bin"]]},
        ],
    }


def main() -> int:
    dd = ddload.DD()
    profile = load("coherence/profile.json")
    spatial = load("coherence/spatial.json")
    dips = load("coherence/dips.json")
    adr = load("coherence/adr027.json")
    temporal = load("coherence/temporal.json")
    sx_profile = load("gates_1q/sx_profile.json")
    per = dip_series(dd)
    charts = [
        chart_distributions(dd),
        chart_variance_share(profile, sx_profile),
        chart_t1_map(spatial),
        chart_t2_map(spatial),
        chart_dip_example(per, dips),
        chart_t2_in_dips(dd, dips),
        chart_t2_over_2t1(profile, adr),
        chart_stale(dd, profile),
        chart_adr027(adr),
        chart_seasonality(temporal),
    ]
    charts = [fit_hist_x(c) for c in charts]
    section = {
        "section": "koherans",
        "toc_tr": "Koherans",
        "title_tr": "Koherans: `T1`, `T2` ve onlardan türeyen hızlar",
        "intro_tr": [
            (
                "Bir kübitin `T1` ve `T2` değerleri aynı turda, saniyeler arayla damgalanıyor: "
                "19.899 eşli olayın hepsinde `T2` damgası `T1` damgasından 1 ile 112 s sonra "
                "geliyor. IBM `T2`'yi Hahn yankısından raporluyor; bu yüzden "
                "`Gamma_phi = 1/T2 - 1/(2 T1)`, yankıdan sonra kalan saf faz kaybı hızıdır. "
                "Arşivde değer başına fit belirsizliği yok."
            ),
            (
                "İki alanın yapısı farklı. `T2` büyük ölçüde kübite özgü bir sabit gibi "
                "davranıyor; `T1`'in log varyansının ise yalnız 0,386'sı kübitler arasında, "
                "kalanı aynı kübitte turdan tura değişim. Bu değişimin görünür bir parçası, "
                "seviyenin en az 2 kat altına inen ve çoğunlukla bir sonraki turda geri dönen "
                "`T1` dipleri; `T2` bu diplerde de düşüyor."
            ),
            (
                "Aynı turdaki `T1` ve `T2` sapmaları 0,70 korelasyonlu. İki fitin hataları "
                "birbirinden bağımsızsa bu, her sapmanın varyansının en az yarısının iki fit "
                "arasında paylaşıldığını gösterir. Paylaşılan parçanın kübitin gerçek değişimi mi "
                "yoksa IBM yönteminde iki deneye ortak bir etki mi olduğunu arşiv ayıramıyor (02 "
                "Doğrulama); paylaşılmayan kalanın ne olduğu da bilinmiyor ve ona tahmin gürültüsü "
                "denmiyor."
            ),
        ],
        "bullets_tr": [
            (
                "**Varyansın yeri.** log `T1` varyansının 0,386'sı kübitler arasında; `T2` için "
                "0,817, `Gamma_phi` için 0,882 (`T1` için 20.063, `T2` için 20.626 olay). Hangi "
                "kübit olduğunu "
                "bilmek `T2`'yi büyük ölçüde, `T1`'in yarıdan azını belirliyor."
            ),
            (
                "**Komşu yapısı tespit edilmedi.** Kübit medyanı log `T1` için Moran's I -0,017 "
                "(p = 0,86, 156 kübit). Tur medyanı `T1` sapmalarının varyansının yalnız %5,5'ini "
                "açıklıyor; bağlı çiftlerin artık korelasyonu (-0,005) dört ve daha fazla adım "
                "uzaktaki çiftlerinkine (-0,004) eşit."
            ),
            (
                "**`T1` dipleri.** 19.595 `T1` olayının 630'u (%3,2; 151 kübit) kayan seviyenin "
                "en az 2 kat altında. 602 epizodun 574'ü tek olay; toparlanma medyanı 25,0 saat, "
                "yani bir sonraki tur. Tek turluk olmaları veriyle tutarlı, kanıtlanmış değil "
                "(28 art arda dip çifti, karıştırmada ortalama 21,6, p = 0,10)."
            ),
            (
                "**`T2` dipleri izliyor.** Eşli 621 dip olayının %97,9'unda `T2` de seviyesinin "
                "altında, medyan -0,234 dekad; yalnız `T1` düşüşünden beklenen -0,194 dekad "
                "(Spearman 0,81). Bu iki fit arasında paylaşılan bir değişim; ortak bir yöntem "
                "etkisi dışlanmadı."
            ),
            (
                "**`T2 > 2 T1` nadir.** 19.899 eşli olayın 20'si (%0,10; 15 kübit). Bu olaylarda "
                "`T1` seviyesinin yaklaşık 0,30 dekad altında, `T2` seviyesinde: `T2`'nin "
                "izlemediği bir `T1` düşüşü. Kayıt düzeyinde 424 kayıt (18 kübit)."
            ),
            (
                "**Bayat değerler.** `q72` `T1` (1.126 dosyada 72 saatten eski), `q11` `T1` "
                "(876), `q17` `T1` (482 dosya, en çok 2.206 saat, 14 Temmuz'a kadar) ve `q149` "
                "`T2` (351) yeniden ölçülmeden taşındı."
            ),
            (
                "**ADR-027 lambda'sı yoğunlaşıyor.** Faz kaybı en güçlü %10 kübit, dosya başına "
                "anlık lambda toplamının medyan %48'ini taşıyor (yarıya yakın, 1.760 dosya); "
                "gamma için %20."
            ),
            (
                "**Saat ya da gün etkisi yok.** Tur düzeyinde Kruskal-Wallis p: saat için 0,69 "
                "(`T1`) ve 0,95 (`T2`), haftanın günü için 0,89 ve 0,86; sekiz testin hiçbiri "
                "Bonferroni eşiği 0,00625'i geçmiyor (133 tur)."
            ),
        ],
        "charts": charts,
    }
    path = write_section("koherans", section)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
