"""Report section "bagimlilik": cross-feature dependency (07) for the advisor page.

Writes ``results/report/bagimlilik.json`` (format: ``analysis/report/spec_check.py``). Every
number is read from ``results/cross/*.json`` except the per-qubit scores of the two quality
axes for the device maps, which no results file holds: they are recomputed from the cache with
07's own code (``levels.levels``, ``normal_scores`` and ``pca`` imported from
``analysis/cross/levels.py``), sign-aligned to the stored loadings, and checked against the
stored eigenvalues, loadings and the stored Spearman of the scores with qubit degree and radius.

Notation follows ``00-overview.md``: 07's ``p10`` is shown as P(0|1) (``prob_meas0_prep1``)
and its ``p01`` as P(1|0) (``prob_meas1_prep0``). Not charted here on purpose: the decay of the
``sx``-P(0|1) correlation with the gap and the coincidence lifts (the root section owns them).
"""

# Turkish text uses the dotless i, which RUF001 flags as ambiguous; it is intended. The section
# text is long Turkish prose in f-strings that ruff format does not split, hence E501.
# ruff: noqa: RUF001, E501

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cross"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ddload
import levels as lvmod
import q2common as rc
import xcommon as xc

DISP = {
    "T1": "T1",
    "T2": "T2",
    "RO": "RO",
    "p01": "P(1|0)",
    "p10": "P(0|1)",
    "init": "init_error",
    "m2": "measure_2",
    "sx": "sx",
    "cz": "cz",
    "rzz": "rzz",
    "zz": "|zz|",
    "adj_cz": "cz (komşu)",
    "adj_rzz": "rzz (komşu)",
    "adj_zz": "|zz| (komşu)",
}
READOUT_BLOCK = {"RO", "p01", "p10", "init", "m2"}
# The same names for prose: field identifiers in backticks, the readout symbols plain.
MD = {
    k: (v if k in ("RO", "p01", "p10") or v.endswith("(komşu)") else f"`{v}`")
    for k, v in DISP.items()
}


def pair_label(a: str, b: str, sep: str = " · ") -> str:
    return f"{DISP[a]}{sep}{DISP[b]}"


def sym_matrix(fields: list[str], values: dict[frozenset[str], float]) -> list[list[float | None]]:
    out: list[list[float | None]] = []
    for a in fields:
        row: list[float | None] = []
        for b in fields:
            row.append(None if a == b else rc.r4(values.get(frozenset((a, b))), 3))
        out.append(row)
    return out


def pc_scores(dd: ddload.DD, mv: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-qubit PC1 and PC2 scores of 07's set A, recomputed with 07's own functions."""
    fs = mv["fields"]
    med = lvmod.levels(dd)["median"]
    m = np.column_stack([med[f] for f in fs])
    okq = np.all(np.isfinite(m), axis=1)
    zmat = np.column_stack([lvmod.normal_scores(m[okq, c]) for c in range(len(fs))])
    w, v = lvmod.pca(zmat)
    for c in range(2):
        comp = mv["pca"][c]
        rc.check(f"PC{c + 1} eigenvalue", float(w[c]), comp["eigenvalue"], 1e-4)
        ref = np.array([comp["loadings"][f] for f in fs])
        v[:, c] = lvmod.align_sign(v[:, c], ref)
        rc.check(f"PC{c + 1} loadings", float(np.max(np.abs(v[:, c] - ref))), 0.0, 1e-4)
    qubits = np.flatnonzero(okq)
    rc.check("set A qubits", qubits.size, mv["qubits"], 0)
    return zmat @ v[:, :2], qubits, w


def main() -> int:
    lev = rc.load("cross/levels.json")
    com = rc.load("cross/comovement.json")
    led = rc.load("cross/leadlag.json")
    cmj = rc.load("cross/common_mode.json")
    summ = rc.load("cross/summary.json")
    fams = list(xc.ALL_FAMS)
    charts: list[dict[str, Any]] = []
    sl = summ["levels"]

    # ---- 1. between-qubit level correlations, all 55 pairs (23 tested here)
    fields = lev["fields"]
    sp = {frozenset((p["a"], p["b"])): p["spearman"] for p in lev["pairs"]}
    mine = [p for p in lev["pairs"] if p["owner"] == "07"]
    rc.check("tested level pairs", len(mine), sl["pairs_tested"], 0)
    mine_r = [p["spearman"] for p in mine]
    block = [p["spearman"] for p in lev["pairs"] if {p["a"], p["b"]} <= READOUT_BLOCK]
    t1sx = sp[frozenset(("T1", "sx"))]
    sxcz = sp[frozenset(("sx", "adj_cz"))]
    t1t2 = sp[frozenset(("T1", "T2"))]
    charts.append(
        {
            "id": "seviye-korelasyon-matrisi",
            "type": "heatmap",
            "title": "Kübit seviyeleri aile blokları içinde bağlı; test edilen 23 aileler arası çiftin hiçbiri anlamlı değil",
            "subtitle": (
                "Kübit başına seviyelerin (yaşam boyu `log10` olay medyanı) Spearman korelasyonu; 11 alan, "
                "çifte göre 116 ile 156 kübit. Kuplör aileleri, kübite komşu kuplörlerin ortalaması. "
                "P(0|1) = `prob_meas0_prep1`, P(1|0) = `prob_meas1_prep0`. Köşegen boş."
            ),
            "read": (
                f"Belirgin değerler başka belgelere ait çiftlerde: okuma bloğu {rc.dec(min(block))} "
                f"(`init_error` ile `measure_2`) ile {rc.dec(max(block))} (RO ile P(0|1)) arasında, `T1` ile "
                f"`sx` {rc.dec(t1sx)}, `sx` ile `cz` (komşu) {rc.dec(sxcz)}, `T1` ile `T2` {rc.dec(t1t2)}. "
                f"07'nin test ettiği 23 aileler arası çift {rc.dec(min(mine_r))} ile {rc.dec(max(mine_r))} "
                f"arasında; Benjamini-Hochberg sonrası en küçük q {rc.dec(sl['min_spearman_bh_q'])}, karşılıklı "
                f"bilgi de hiçbirinde anlamlı değil. Bu örneklem, bu çiftler için yaklaşık 0,3'ün ötesinde bir "
                f"sıra korelasyonunu dışlar; daha zayıf bağları dışlamaz."
            ),
            "caveat": (
                "Doğrulayıcı: altı çift (`measure_2` ile üç komşu kuplör alanı; RO, P(1|0) ve P(0|1) ile "
                "`|zz|` (komşu)) uzamsal öz-korelasyonu anlamlı iki alanı birleştirir; bu durumda "
                "permütasyon testinin geçerlilik önermesi tutmaz. Hiçbiri anlamlı olmadığından sıfır "
                "sonucu değişmez."
            ),
            "source": "07 §7.1, §5 and Verification; results/cross/levels.json (pairs), summary.json (levels)",
            "rows": [DISP[f] for f in fields],
            "cols": [DISP[f] for f in fields],
            "values": sym_matrix(fields, sp),
            "scale": "div",
            "domain": [-1, 1],
            "fmt": ".2f",
        }
    )

    # ---- 2. the two quality axes: PCA loadings with bootstrap intervals
    mv = lev["multivariate"]["A_10_fields_no_init"]
    pcs = mv["pca"]
    fs_a = mv["fields"]
    pa3 = pcs[2]
    charts.append(
        {
            "id": "iki-kalite-ekseni",
            "type": "bar",
            "orient": "h",
            "title": "Okuma kalitesi ile koherans-ve-kapı kalitesi iki ayrı eksendir",
            "subtitle": (
                f"Kübit seviyelerinin normal skorlarından PCA: ilk iki bileşenin yükleri ve %95 bootstrap "
                f"aralıkları ({mv['qubits']} kübit, {len(fs_a)} alan; q72 ve q99 eksik alan nedeniyle dışarıda; "
                f"{mv['pca_bootstrap_reps']} yeniden örnekleme)."
            ),
            "read": (
                f"PC1 (özdeğer {rc.dec(pcs[0]['eigenvalue'], 2)}, varyansın "
                f"{rc.pct(pcs[0]['variance_share'], 0)}'i) okuma eksenidir: RO, P(0|1), P(1|0) ve "
                f"`measure_2` yükleri {rc.dec(min(pcs[0]['loadings'][f] for f in ('RO', 'p01', 'p10', 'm2')), 2)} "
                f"ile {rc.dec(max(pcs[0]['loadings'][f] for f in ('RO', 'p01', 'p10', 'm2')), 2)} arasında. PC2 "
                f"({rc.dec(pcs[1]['eigenvalue'], 2)}, {rc.pct(pcs[1]['variance_share'], 0)}) koherans-ve-kapı "
                f"eksenidir: `cz` (komşu) {rc.dec(pcs[1]['loadings']['adj_cz'])}, `rzz` (komşu) "
                f"{rc.dec(pcs[1]['loadings']['adj_rzz'])}, `sx` {rc.dec(pcs[1]['loadings']['sx'])}, `T1` "
                f"{rc.dec(pcs[1]['loadings']['T1'])}. Her okuma alanının PC2 aralığı sıfırı içerir. Üçüncü "
                f"bileşen ({rc.dec(pa3['eigenvalue'], 2)}) paralel analiz eşiğini "
                f"({rc.dec(pa3['parallel_analysis_q95'], 2)}) geçmez."
            ),
            "caveat": (
                'Bileşenlerin dikliğini PCA kendisi dayatır; "iki ayrı eksen" kanıtı yüklerin örüntüsüdür. '
                "`init_error` eklenince (116 kübit) aynı iki bileşen kalır ve `init_error` okuma eksenine "
                "yüklenir."
            ),
            "source": "07 §7.5; results/cross/levels.json (multivariate.A_10_fields_no_init.pca)",
            "x": {"label": "Yük", "scale": "linear", "min": -0.6, "max": 0.7},
            "categories": [DISP[f] for f in fs_a],
            "series": [
                {
                    "name": f"PC{c + 1}",
                    "values": [rc.r4(pcs[c]["loadings"][f], 3) for f in fs_a],
                    "lo": [rc.r4(pcs[c]["loadings_ci95"][f][0], 3) for f in fs_a],
                    "hi": [rc.r4(pcs[c]["loadings_ci95"][f][1], 3) for f in fs_a],
                }
                for c in range(2)
            ],
        }
    )

    # ---- 3. no archetypes: silhouette against two nulls
    arch = mv["archetypes_ward"]
    ks = [2, 3, 4, 5, 6]
    sil = [arch[f"k{k}"]["silhouette"] for k in ks]
    pg = [arch[f"k{k}"]["p_gaussian_null"] for k in ks]
    ari = [arch[f"k{k}"]["bootstrap_ari_median"] for k in ks]
    k3 = arch["k3"]["profiles"]["2"]
    charts.append(
        {
            "id": "arketip-yok",
            "type": "line",
            "title": "Kübitler ayrık türlere ayrılmıyor: kümeler korelasyonlu bir süreklilikten iyi değil",
            "subtitle": (
                f"Ward kümelemesinin siluet değeri, küme sayısı k = 2 ile 6; iki sıfır modelinin %95 "
                f"noktası (200'er çekim): sütunları ayrı ayrı karıştırılmış veri ve gözlenen korelasyon "
                f"matrisli Gauss bulutu. {mv['qubits']} kübit, {len(fs_a)} alan."
            ),
            "read": (
                f"Siluet ({rc.dec(min(sil))} ile {rc.dec(max(sil))}) karıştırılmış sıfırın eşiğini her k "
                f"için aşar, yani alanlar korelasyonludur; ama korelasyonlu Gauss eşiğini hiçbir k için aşmaz "
                f"(p {rc.dec(min(pg))} ile {rc.dec(max(pg))}). Etiketler de kararsız: bootstrap ARI medyanı "
                f"{rc.dec(min(ari), 2)} ile {rc.dec(max(ari), 2)}. k = 3'teki {k3['size']} kübitlik \"hemen her "
                f'şeyde kötü" grup, iki eksenin de kötü olduğu kuyruktur, ayrı bir tür değil.'
            ),
            "source": "07 §7.6; results/cross/levels.json (multivariate.A_10_fields_no_init.archetypes_ward)",
            "x": {"label": "Küme sayısı k", "scale": "linear", "min": 2, "max": 6},
            "y": {"label": "Siluet", "scale": "linear", "min": 0},
            "series": [
                {
                    "name": "gözlenen siluet",
                    "style": "line+dots",
                    "points": [[k, rc.r4(s, 3)] for k, s in zip(ks, sil, strict=True)],
                },
                {
                    "name": "korelasyonlu Gauss sıfırı, %95",
                    "style": "line",
                    "points": [
                        [k, rc.r4(arch[f"k{k}"]["silhouette_gaussian_null_q95"], 3)] for k in ks
                    ],
                },
                {
                    "name": "karıştırılmış sıfır, %95",
                    "style": "line",
                    "points": [[k, rc.r4(arch[f"k{k}"]["silhouette_null_q95"], 3)] for k in ks],
                },
            ],
        }
    )

    # ---- 4. within-qubit co-movement: nearest-event residual correlations
    sc = summ["comovement"]
    rows4 = []
    for p in com["pairs"]:
        r = p["raw"]
        if p["control"]:
            grp = "pozitif kontrol"
        elif r["r_bh_reject_q05"]:
            grp = "BH sonrası anlamlı"
        else:
            grp = "anlamlı değil"
        rows4.append(
            {
                "label": pair_label(p["anchor"], p["other"]),
                "est": rc.r4(r["r"], 3),
                "lo": rc.r4(r["r_ci95_cluster_bootstrap"][0], 3),
                "hi": rc.r4(r["r_ci95_cluster_bootstrap"][1], 3),
                "group": grp,
                "_c": p["control"],
            }
        )
    rows4.sort(key=lambda x: (x["_c"], x["est"]))
    for x in rows4:
        del x["_c"]
    rc.check(
        "co-movement survivors",
        sum(x["group"] == "BH sonrası anlamlı" for x in rows4),
        sc["raw"]["n_r_bh_survivors"],
        0,
    )
    ctrl = {(p["anchor"], p["other"]): p for p in com["pairs"] if p["control"]}
    t1t2c = ctrl[("T1", "T2")]["raw"]["r"]
    rop10 = ctrl[("p10", "RO")]["raw"]["r"]
    sxp10 = next(p for p in com["pairs"] if (p["anchor"], p["other"]) == ("sx", "p10"))
    charts.append(
        {
            "id": "kubit-ici-ortak-hareket",
            "type": "forest",
            "title": "Bir kübitte aileler birlikte hareket ediyor, ama kontrollerin yanında çok zayıf",
            "subtitle": (
                "En yakın olay eşleşmesiyle (aynı kübit, 3 saat içinde; `|zz|` ile 12 saat) artık "
                "korelasyonu: normal skorların Pearson r'si, ham artıklar; kübitler üzerinden küme "
                "bootstrap %95 aralığı. 23 çift ve 2 pozitif kontrol."
            ),
            "read": (
                f"23 çiftten {sc['raw']['n_r_bh_survivors']} tanesi Benjamini-Hochberg sonrası anlamlı "
                f"(ortak mod çıkarılınca {sc['cm_removed']['n_r_bh_survivors']}), ama en büyük r "
                f"{rc.dec(sc['raw']['max_abs_r'])} (`sx` ile P(0|1), {rc.intk(sxp10['nearest_pairs'])} "
                f"eşleşme). Kontroller {rc.dec(t1t2c)} (`T1` ile `T2`) ve {rc.dec(rop10)} (RO ile P(0|1)): "
                f"araç, bağımlılık varsa onu görüyor. Anlamlı çiftlerin çoğunda iki büyüklük birlikte "
                f"kötüleşir; istisnalar `sx` ile P(1|0) ve `|zz|` ile okuma hataları (büyük `|zz|`, küçük "
                f"okuma hatası)."
            ),
            "caveat": (
                "Artık, aynı varlığın ±7 gün içindeki diğer olaylarının medyanına göre tanımlıdır. "
                "Doğrulayıcı, aynı artıkların zaman aralığı dilimlerinde pencere ±2 güne indirilince `sx` "
                "ile P(0|1) korelasyonunun en kısa dilimde 0,108'den 0,032'ye düştüğünü gösterdi; paylaşılan "
                "kısmın zaman ölçeği (saatler mi, günler mi) ve kökeni henüz belirlenmemiştir."
            ),
            "source": "07 §7.2, §4.1 and Verification; results/cross/comovement.json (pairs[*].raw), summary.json (comovement)",
            "x": {"label": "Artık korelasyonu r", "scale": "linear"},
            "ref": 0,
            "rows": rows4,
        }
    )

    # ---- 5. no lead or lag out of time (model: every form, predictors at least 3 h earlier)
    sll = summ["leadlag"]["strict_all"]
    rows5 = []
    for p in led["pairs"]:
        b = p.get("strict_all")
        if not b or b.get("ratio") is None:
            continue
        lo, hi = b["ratio_ci95"]
        grp = (
            "aralık 1'in altında"
            if hi < 1
            else ("aralık 1'in üstünde" if lo > 1 else "aralık 1'i içeriyor")
        )
        rows5.append(
            {
                "label": pair_label(p["predictor"], p["target"], " → "),
                "est": rc.r4(b["ratio"], 6),
                "lo": rc.r4(lo, 6),
                "hi": rc.r4(hi, 6),
                "group": grp,
            }
        )
    rows5.sort(key=lambda x: x["est"])
    rc.check("lead-lag directions", len(rows5), sll["directions_scored"], 0)
    rc.check(
        "lead-lag above 1",
        sum(x["group"] == "aralık 1'in üstünde" for x in rows5),
        sll["n_ci95_entirely_above_1"],
        0,
    )
    rc.check("lead-lag best ratio", rows5[0]["est"], sll["min_ratio"], 1e-6)
    s1 = summ["leadlag"]["lag1_all"]
    s3 = summ["leadlag"]["lags123_linear"]
    best = sll["min_ratio_direction"].split("->")
    worst = sll["max_ratio_direction"].split("->")
    charts.append(
        {
            "id": "onculuk-gecikme-yok",
            "type": "forest",
            "title": "Bir ailenin yakın geçmişi, başka bir ailenin bir sonraki değerini öngörmüyor",
            "subtitle": (
                f"Zaman dışı test dönemindeki ortalama mutlak hata / yalnız sabit terimli referansın hatası, "
                f"{len(rows5)} yön; model: tüm biçimler, yalnızca hedeften en az 3 saat önce damgalanmış "
                f"öngörücü olayları (hedefin kendi turundan değil). Hedef varlıkları üzerinden küme bootstrap "
                f"%95 aralığı; 1'in altı kazançtır."
            ),
            "read": (
                f"En iyi oran {rc.dec(sll['min_ratio'], 5)} ({MD[best[0]]} → {MD[best[1]]}), yani yaklaşık "
                f"binde 1,5 kazanç, ve anlamlı değil; {len(rows5)} yönün hiçbiri Benjamini-Hochberg'den geçmez. "
                f"{sll['n_ci95_entirely_above_1']} aralığın tamamı 1'in üstünde (en kötüsü {MD[worst[0]]} → "
                f"{MD[worst[1]]}, {rc.dec(sll['max_ratio'], 4)}): eğitimde uydurulan ve genellemeyen aşırı "
                f"uyum, sinyal değil. Diğer iki modelde de anlamlı yön yok (gecikme 1, tüm biçimler: "
                f"{s1['directions_scored']} yön; doğrusal gecikme 1 ile 3: {s3['directions_scored']} yön)."
            ),
            "caveat": (
                "Test dönemi her hedefin son %30'udur ve 2026-08'deki kapsam değişiminden sonraya düşer; "
                "yalnızca daha önce var olmuş ya da üç olaydan uzun gecikmeyle işleyen bağlar test edilmedi. "
                "Başka belgelere ait bağlar (örneğin `T1` ile `sx`) bu testte yok."
            ),
            "source": "07 §7.3, §6; results/cross/leadlag.json (pairs[*].strict_all), summary.json (leadlag)",
            "x": {"label": "Test hatası / referans hatası", "scale": "linear"},
            "ref": 1,
            "rows": rows5,
        }
    )

    # ---- 6. device-wide common mode share by family
    cms = cmj["common_mode_share"]
    vi = summ["common_mode"]["variogram_vs_independence"]
    small = [f for f in fams if vi[f]["shortest_ratio_over_prediction"] <= 1.05]
    ro_long = [vi[f]["long_device_to_entity_ratio"] for f in ("RO", "p01", "p10")]
    charts.append(
        {
            "id": "cihaz-ortak-mod-payi",
            "type": "bar",
            "orient": "v",
            "title": "Cihaz çapındaki ortak bileşen her ailede küçük, en büyüğü koherans ailesinde",
            "subtitle": (
                "Tur ortak modunun (aynı turda ölçülen varlıkların medyan artığı, en az 20 varlık) artık "
                "varyansındaki payı, aile başına: sağlam biçim `1 - (MAD(r_cm) / MAD(r))^2` ve düz varyans "
                "payı. Olay sayısı aileye göre 7.925 ile 90.383."
            ),
            "read": (
                f"Sağlam pay {rc.dec(cms['zz']['share_robust'])} (`|zz|`) ile {rc.dec(cms['T1']['share_robust'])} "
                f"(`T1`) arasında; düz varyans payı daha küçük (`T1` {rc.dec(cms['T1']['share_plain'])}, `sx` "
                f"{rc.dec(cms['sx']['share_plain'])}). En kısa gecikmede cihaz serisi "
                f"{rc.join_tr([MD[f] for f in small])} için bağımsız varlıkların öngördüğü kadar küçülür. Okuma "
                f"alanlarında cihaz/varlık yarı-varyans oranı ay ölçeğinde (744 ile 1.488 saat) "
                f"{rc.dec(min(ro_long))} ile {rc.dec(max(ro_long))}, `T1`'de "
                f"{rc.dec(vi['T1']['long_device_to_entity_ratio'])}: ortak kısım çoğunlukla yavaş kayan bir "
                f"cihaz seviyesidir."
            ),
            "caveat": (
                "Cihaz serisi karşılaştırmaları 14 ile 111 cihaz çiftine dayanır ve bağımsızlık öngörüsü "
                "Gauss yaklaşımıyla kurulur; oranlar test değil, gösterge niteliğindedir."
            ),
            "source": "07 §3.1, §4.3; results/cross/common_mode.json (common_mode_share), summary.json (common_mode.variogram_vs_independence)",
            "y": {"label": "Artık varyansındaki pay", "scale": "linear", "min": 0},
            "categories": [DISP[f] for f in fams],
            "series": [
                {"name": "sağlam pay", "values": [rc.r4(cms[f]["share_robust"], 3) for f in fams]},
                {
                    "name": "düz varyans payı",
                    "values": [rc.r4(cms[f]["share_plain"], 3) for f in fams],
                },
            ],
        }
    )

    # ---- 7. device-day changes: family blocks
    dpairs = cmj["device_daily"]["pairs"]
    dsp = {frozenset((p["a"], p["b"])): p["spearman"] for p in dpairs}
    surv = [p for p in dpairs if p["bh_reject_q05"]]
    rc.check(
        "device-day survivors", len(surv), len(summ["common_mode"]["device_daily_bh_survivors"]), 0
    )
    cross_fam = [p for p in surv if {p["a"], p["b"]} == {"p01", "sx"}]
    if len(cross_fam) != 1:
        raise AssertionError("expected P(1|0)-sx to be the cross-family device-day survivor")
    cf = cross_fam[0]
    days = [p["common_days"] for p in dpairs]
    jj = cmj["device_daily"]["joint_jumps"]
    charts.append(
        {
            "id": "gunluk-cihaz-degisimleri",
            "type": "heatmap",
            "title": "Cihaz düzeyindeki günlük değişimler aile blokları halinde hareket ediyor",
            "subtitle": (
                f"Operasyonel gün (16:00 UTC'den başlar) başına cihaz medyanının günden güne değişimleri "
                f"arasında Spearman korelasyonu; 11 aile, {len(dpairs)} çift, çifte göre {min(days)} ile "
                f"{max(days)} ortak gün. Köşegen boş."
            ),
            "read": (
                f"{len(dpairs)} çiftten {len(surv)} tanesi Benjamini-Hochberg'den geçer ve biri dışında hepsi "
                f"aile içidir (`T1` ile `T2` {rc.dec(dsp[frozenset(('T1', 'T2'))])}, okuma alanları kendi "
                f"aralarında, `cz` ile `rzz` {rc.dec(dsp[frozenset(('cz', 'rzz'))])}). Tek aileler arası çift "
                f"P(1|0) ile `sx`: {rc.dec(cf['spearman'])} ({cf['common_days']} gün, q {rc.dec(cf['bh_q'], 4)}); "
                f"ortak bir sürücü adayı, mekanizma değil. En az üç ailenin aynı gün sıçradığı "
                f"{jj['days_with_ge3_families_jumping']} günden yalnızca 2026-05-14 farklı fiziksel aileleri "
                f"birleştirir (koherans düşer, tüm kapı hataları artar)."
            ),
            "caveat": "Okuma üçlüsü kısmen aritmetik olarak birlikte hareket eder: RO, P(0|1) ve P(1|0)'ın ortalamasıdır.",
            "source": "07 §3.2, §7.7; results/cross/common_mode.json (device_daily)",
            "rows": [DISP[f] for f in fams],
            "cols": [DISP[f] for f in fams],
            "values": sym_matrix(fams, dsp),
            "scale": "div",
            "domain": [-1, 1],
            "fmt": ".2f",
        }
    )

    # ---- 8. the zz-readout candidate at three levels
    cmp = {(p["anchor"], p["other"]): p for p in com["pairs"]}
    qd = {frozenset((p["a"], p["b"])): p for p in cmj["change_matrix"]["raw"]["pairs"]}
    rows8 = []
    for f in ("RO", "p01", "p10"):
        r = cmp[("zz", f)]["raw"]
        rows8.append(
            {
                "label": f"olay: |zz| · {DISP[f]}",
                "est": rc.r4(r["r"], 3),
                "lo": rc.r4(r["r_ci95_cluster_bootstrap"][0], 3),
                "hi": rc.r4(r["r_ci95_cluster_bootstrap"][1], 3),
                "group": "olay (en yakın eşleşme)",
            }
        )
    for f in ("RO", "p01", "p10"):
        p = qd[frozenset((f, "adj_zz"))]
        rows8.append(
            {
                "label": f"kübit-gün: |zz| (komşu) · {DISP[f]}",
                "est": rc.r4(p["r"], 3),
                "group": "kübit-gün",
            }
        )
    for f in ("RO", "p01", "p10"):
        p = next(x for x in dpairs if {x["a"], x["b"]} == {f, "zz"})
        rows8.append(
            {
                "label": f"cihaz-gün: |zz| · {DISP[f]}",
                "est": rc.r4(p["spearman"], 3),
                "lo": rc.r4(p["ci95_block_bootstrap"][0], 3),
                "hi": rc.r4(p["ci95_block_bootstrap"][1], 3),
                "group": "cihaz-gün (anlamlı değil)",
            }
        )
    zro = cmp[("zz", "RO")]["raw"]
    dro = next(x for x in dpairs if {x["a"], x["b"]} == {"RO", "zz"})
    charts.append(
        {
            "id": "zz-okuma-aday",
            "type": "forest",
            "title": "Aday bağ: `|zz|` büyükken kübitin okuma hatası küçük",
            "subtitle": (
                "`|zz|` ile okuma hataları arasındaki korelasyon, üç düzeyde: olay (en yakın eşleşme, 12 saat "
                "içinde; küme bootstrap %95), kübit-gün (günlük medyan artıklar; aralık yok) ve cihaz-gün "
                "değişimleri (blok bootstrap %95)."
            ),
            "read": (
                f"Olay düzeyinde RO ile {rc.dec(zro['r'])} ({rc.intk(cmp[('zz', 'RO')]['nearest_pairs'])} "
                f"eşleşme), P(1|0) ile {rc.dec(cmp[('zz', 'p01')]['raw']['r'])}, P(0|1) ile "
                f"{rc.dec(cmp[('zz', 'p10')]['raw']['r'])}; üçü de Benjamini-Hochberg sonrası anlamlı. Kübit-gün "
                f"düzeyinde {rc.dec(qd[frozenset(('RO', 'adj_zz'))]['r'])}, "
                f"{rc.dec(qd[frozenset(('p01', 'adj_zz'))]['r'])} ve {rc.dec(qd[frozenset(('p10', 'adj_zz'))]['r'])} "
                f"(anlamlı). Cihaz-gün düzeyinde RO ile {rc.dec(dro['spearman'])} (q {rc.dec(dro['bh_q'])}): "
                f"blok bootstrap aralığı sıfırı dışlıyor, ama 55 çiftlik Benjamini-Hochberg düzeltmesinden "
                f"sonra anlamlı değil; işaret aynı."
            ),
            "caveat": (
                "Aday, mekanizma değil: `zz` yalnızca dosya zamanı taşır ve nasıl üretildiği hiçbir IBM "
                "kaynağında belgelenmemiş. Bir okuma kalibrasyonunun `zz` değerini mi beslediği, yoksa ikisinin "
                "kübitin tek bir değişimine mi yanıt verdiği buradan karar verilemez."
            ),
            "source": "07 §7.2, §7.5, §7.7; results/cross/comovement.json, common_mode.json (change_matrix.raw, device_daily)",
            "x": {"label": "Korelasyon", "scale": "linear"},
            "ref": 0,
            "rows": rows8,
        }
    )

    # ---- 9 and 10. the two axes on the device (scores recomputed with 07's code)
    dd = ddload.DD()
    scores, qubits, _ = pc_scores(dd, mv)
    edges = [(int(a), int(b)) for a, b in xc.coupler_pairs(dd, "zz")]
    degree = np.zeros(156)
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
    coords = np.array(next(iter(dd.meta["config_values"]["coords"].values()))["value"], dtype=float)
    cx, cy = coords[qubits, 0], coords[qubits, 1]
    radial = np.hypot(cx - cx.mean(), cy - cy.mean())
    spat = mv["pc_spatial"]
    rc.check(
        "PC1 vs degree",
        xc.spearman(scores[:, 0], degree[qubits]),
        spat["pc1"]["spearman_degree"],
        1e-4,
    )
    rc.check(
        "PC2 vs radius", xc.spearman(scores[:, 1], radial), spat["pc2"]["spearman_radial"], 1e-4
    )
    excl = ", ".join(f"q{q}" for q in mv["qubits_excluded"])

    def nodes(c: int) -> dict[str, float | None]:
        out: dict[str, float | None] = {str(q): None for q in range(156)}
        for k, q in enumerate(qubits):
            out[str(int(q))] = rc.r4(scores[k, c], 3)
        return out

    p1, p2 = spat["pc1"], spat["pc2"]
    charts.append(
        {
            "id": "okuma-ekseni-haritasi",
            "type": "map",
            "title": "Okuma ekseni kübitin kafesteki derecesini izler, komşuluk öbekleri oluşturmaz",
            "subtitle": (
                f"Kübit başına PC1 (okuma ekseni) skoru, {qubits.size} kübit (ıraksak ölçek; yüksek değer kötü "
                f"okuma). {excl} eksik alan nedeniyle boş."
            ),
            "read": (
                f"PC1 skoru kübitin kuplör sayısıyla artar (Spearman {rc.dec(p1['spearman_degree'])}). Ağır "
                f"altıgen kafeste kuplörlerin çoğu derece 3 ve derece 2 kübitleri birleştirdiğinden komşular "
                f"birbirine benzemez: Moran's I {rc.dec(p1['morans_i']['I'])} (iki yönlü p "
                f"{rc.dec(p1['morans_i']['p_perm_two_sided'])})."
            ),
            "caveat": (
                '03\'ün doğrulayıcısına göre okumadaki "dama tahtası" görünümü büyük ölçüde derece '
                "sınıflarıdır: her derece sınıfının medyanı çıkarılınca RO'nun Moran's I değeri -0,047'ye "
                "(p 0,59) iner. Frekans grubu yorumu RO için desteklenmiyor."
            ),
            "source": "07 §5, §7.5; 03 Verification; results/cross/levels.json (multivariate.A_10_fields_no_init.pc_spatial)",
            "scale": "div",
            "node_values": nodes(0),
            "node_label": "PC1 skoru",
        }
    )
    charts.append(
        {
            "id": "koherans-kapi-ekseni-haritasi",
            "type": "map",
            "title": "Koherans-ve-kapı ekseni cihazda öbeklenir; merkeze doğru kötüleşme betimleyici bir aday",
            "subtitle": (
                f"Kübit başına PC2 (koherans-ve-kapı ekseni) skoru, {qubits.size} kübit (ıraksak ölçek; yüksek "
                f"değer kötü kapı ve kısa `T1`). {excl} boş."
            ),
            "read": (
                f"PC2 uzamsal olarak öz-korelasyonludur (Moran's I {rc.dec(p2['morans_i']['I'])}, iki yönlü p "
                f"{rc.dec(p2['morans_i']['p_perm_two_sided'])}) ve merkezden uzaklaştıkça azalır (Spearman "
                f"{rc.dec(p2['spearman_radial'])}); kübit derecesiyle Spearman {rc.dec(p2['spearman_degree'])}."
            ),
            "caveat": (
                "Öbeklenme kısmen yapı gereğidir: komşu kuplör ortalamaları (`cz`, `rzz`) PC2'ye yüklenir ve "
                "komşu kübitler kuplör paylaşır."
            ),
            "source": "07 §5, §7.5; results/cross/levels.json (multivariate.A_10_fields_no_init.pc_spatial)",
            "scale": "div",
            "node_values": nodes(1),
            "node_label": "PC2 skoru",
        }
    )

    # ---- section text
    pr1 = pcs[0]
    section = {
        "section": "bagimlilik",
        "title_tr": "Aileler arası bağımlılık: kalibrasyon aileleri neyi paylaşıyor, neyi paylaşmıyor",
        "intro_tr": [
            (
                "Bu bölüm on bir ölçüm ailesi arasındaki ilişkileri inceler: `T1`, `T2`, RO "
                "(`readout_error`), P(1|0), P(0|1), `init_error`, `measure_2`, `sx`, `cz`, `rzz` ve `|zz|`. "
                "Kuplör aileleri kübite, komşu kuplörlerin ortalaması olarak taşınır. Test ailesi, başka "
                "belgelere ait bağlar çıkarıldıktan sonra kalan 23 aileler arası çifttir; `T1` ile `T2` ve "
                "RO ile P(0|1) yalnızca pozitif kontrol olarak aynı araçlardan geçirilir."
            ),
            (
                "Saat, neyin paylaşılabileceğini sınırlar: bir kübitte `T1` ve `T2` saniyeler arayla, `sx` "
                "yaklaşık bir saat sonra, `cz` ve `rzz` saatler sonra damgalanır; okuma yaklaşık 4,5 saatte "
                "bir yenilenir. Bu aralıklardan kısa süren bir dalgalanma, iki aile arasında ortak olarak "
                "görülemez."
            ),
            (
                "Genel tablo: kübitler arasında aileler iki ayrı kalite eksenine ayrılır; bir kübitin içinde "
                "ortak hareket saptanabilir ama çok küçüktür; bir ailenin yakın geçmişi diğerinin bir sonraki "
                "değerini öngörmez; cihaz çapındaki ortak bileşen küçüktür. Kalıcı olmayan bileşenin küçük bir "
                "kısmı aileler arasında paylaşılıyor; bu kısmın zaman ölçeği ve kökeni henüz belirlenmemiştir, geri kalanı "
                "hiçbir aileler arası testle bir kaynağa bağlanamıyor."
            ),
        ],
        "bullets_tr": [
            (
                f"**Kübitler arası seviye bağı saptanmadı.** 23 çiftin hiçbiri Benjamini-Hochberg düzeltmesinden sonra "
                f"anlamlı değil (en küçük q {rc.dec(sl['min_spearman_bh_q'])}); bütün %95 aralıkları "
                f"{rc.dec(sl['ci95_lowest_lower'])} ile {rc.dec(sl['ci95_highest_upper'])} arasında (116 ile 156 "
                f"kübit). Kübitler arası yapı başka belgelere ait çiftlerde, örneğin `T1` ile `sx` {rc.dec(t1sx)}."
            ),
            (
                f"**İki ayrı kalite ekseni.** {mv['qubits']} kübit ve {len(fs_a)} alanda bir okuma faktörü "
                f"(özdeğer {rc.dec(pr1['eigenvalue'], 2)}, varyansın {rc.pct(pr1['variance_share'], 0)}'i) ve "
                f"bir koherans-ve-kapı faktörü ({rc.dec(pcs[1]['eigenvalue'], 2)}, "
                f"{rc.pct(pcs[1]['variance_share'], 0)}) paralel analizi aşar. Okuma ekseni ile koherans-ve-kapı "
                f"ekseni neredeyse ayrı; bu, yük örüntüsüne dayanan betimleyici bir okuma."
            ),
            (
                f"**Korelasyonlu sürekliliğin ötesinde arketip yok.** k = 2 ile 6 arasında Ward kümeleri, gözlenen korelasyonları taşıyan bir Gauss "
                f"bulutunu hiçbir k için geçemez (p {rc.dec(min(pg))} ile {rc.dec(max(pg))}) ve kararsızdır "
                f"(bootstrap ARI medyanı {rc.dec(min(ari), 2)} ile {rc.dec(max(ari), 2)})."
            ),
            (
                f"**Kübit içi ortak hareket saptanabilir ama çok küçük.** Ham artıklarda 23 çiftten "
                f"{sc['raw']['n_r_bh_survivors']} tanesi, ortak mod çıkarılınca {sc['cm_removed']['n_r_bh_survivors']} "
                f"tanesi anlamlı; en büyük korelasyon {rc.dec(sc['raw']['max_abs_r'])} (`sx` ile P(0|1)), "
                f"kontrollerde {rc.dec(t1t2c)} ve {rc.dec(rop10)}. Doğrulayıcının pencere testinden sonra "
                f"paylaşılan kısmın zaman ölçeği açık bir sorudur."
            ),
            (
                f"**Öncülük ya da gecikme saptanmadı.** Üç modelin hiçbirinde 45 (ya da 44) yönden anlamlı olan yok; en "
                f"iyi zaman dışı oran {rc.dec(sll['min_ratio'], 5)} ({MD[best[0]]} → {MD[best[1]]})."
            ),
            (
                f"**Cihaz çapındaki pay küçük.** Tur ortak modu artık varyansının {rc.dec(cms['zz']['share_robust'])} "
                f"(`|zz|`) ile {rc.dec(cms['T1']['share_robust'])} (`T1`) arasını taşır; okuma ve koherans için "
                f"cihaz payı ay ölçeğinde büyür, yani yavaş kayan bir cihaz seviyesidir."
            ),
            (
                f"**Günlük cihaz değişimleri aile içinde hareket eder.** {len(dpairs)} aile çiftinden {len(surv)} "
                f"tanesi anlamlı ve biri dışında hepsi aile içi; aileler arası tek çift P(1|0) ile `sx` "
                f"({rc.dec(cf['spearman'])}, {cf['common_days']} gün), bir aday."
            ),
            (
                f"**Aday bağ: `|zz|` ve okuma.** `|zz|` artıkları okuma hatalarıyla negatif korelasyonlu (RO ile "
                f"{rc.dec(zro['r'])}, {rc.intk(cmp[('zz', 'RO')]['nearest_pairs'])} eşleşme); işaret kübit-gün "
                f"düzeyinde ({rc.dec(qd[frozenset(('RO', 'adj_zz'))]['r'])}) ve anlamlı olmadan cihaz-gün "
                f"düzeyinde ({rc.dec(dro['spearman'])}) tekrar eder. `zz` yalnızca dosya zamanı taşıdığından "
                f"mekanizma ve zamanlama karara bağlanamaz."
            ),
        ],
        "charts": charts,
    }
    path = rc.write_section("bagimlilik", section)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
