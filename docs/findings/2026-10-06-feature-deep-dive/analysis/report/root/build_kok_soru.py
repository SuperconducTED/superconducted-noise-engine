# ruff: noqa: RUF001
"""Build the "kok-soru" (root question) section of the advisor report page.

Writes ``results/report/kok-soru.json`` in the section contract of ``../spec_check.py``.

The section presents the non-persistent component (``00-overview.md`` sections 4.1 to 4.3,
section 4 of every scope document and their "Verification (2026-10-06)" sections). Where a
verifier weakened or refuted a claim, the text and the chart caveats use the verifier's reading.

Data sources, in order of preference:

- Fields of the existing results JSONs (``results/<scope>/``), read as written by the scope
  scripts and the verifiers. Nothing is re-derived when a field holds it.
- Two series that no results file holds are recomputed from the field cache with the owners'
  own helpers (imported, not re-implemented):
  1. the per-round-pair robust semivariance of log10 ``T1`` changes (``regime.json`` stores only
     its quantiles, monthly medians and first 25 rows), via ``coherence/regime.py``
     ``round_table`` and ``robust_sv``;
  2. the same-round deviations of log10 ``T1`` and ``T2`` (``nonpersistent.json`` stores only
     their correlations), via ``coherence/cohlib.py`` ``paired`` and
     ``coherence/nonpersistent.py`` ``deviations``.
  Each recomputation is checked against the stored figures (``check`` raises on a mismatch),
  and the reconciliation is printed.

Only ``q.T1`` and ``q.T2`` are loaded from the cache. Turkish text follows the report's rules:
decimal comma in prose, field names in backticks, no em dash.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "coherence"))

import cohlib
import ddload
import nonpersistent
import regime

DEEP = Path(__file__).resolve().parents[3]
RES = DEEP / "results"
OUT = RES / "report" / "kok-soru.json"
SEED = 20261006
N_SCATTER = 2000
MIN_PAIRS_PLOT = 20  # variogram bins with fewer pairs are not drawn (only lf_100 30-42 h, 6)


def load(rel: str) -> Any:
    return json.loads((RES / rel).read_text(encoding="utf-8"))


def check(name: str, got: float, want: float, tol: float) -> None:
    ok = abs(got - want) <= tol
    print(f"{'ok  ' if ok else 'FAIL'} {name}: recomputed {got:.6g}, results/document {want:.6g}")
    if not ok:
        raise SystemExit(f"recomputed {name} does not match the results file")


def utc(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000.0, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def r4(v: float) -> float:
    return float(f"{v:.4g}")


def thousands(n: int) -> str:
    """Turkish thousands separator: 21540 -> '21.540'."""
    return f"{n:,}".replace(",", ".")


def norm_bins(
    bins: list[dict[str, Any]], denom: float, lo_h: float, x_key: str = "mean_lag_h"
) -> list[list[float]]:
    """[x, semivariance / denom] for every bin from ``lo_h`` with enough pairs."""
    out = []
    for b in bins:
        if b["lag_h_lo"] < lo_h or not b["pairs"] or b["pairs"] < MIN_PAIRS_PLOT:
            continue
        x = b[x_key] if x_key in b else 0.5 * (b["lag_h_lo"] + b["lag_h_hi"])
        out.append([round(float(x), 3), r4(b["semivariance"] / denom)])
    return out


# ---------------------------------------------------------------- charts from results files


def chart_vario_daily() -> dict[str, Any]:
    npj = load("coherence/nonpersistent.json")["variograms"]
    sxj = load("gates_1q/sx_variogram.json")
    ro = load("readout/noise.json")["variograms"]["ro_log10"]["mixed_only"]["decomposition"]
    t1 = npj["log10_T1"]["all"]
    t2 = npj["log10_T2"]["all"]
    d1 = t1["summary"]["bin_744_1488h"]["semivariance"]
    d2 = t2["summary"]["bin_744_1488h"]["semivariance"]
    dsx = sxj["summary_all"]["semivariance"]["lag_744_to_3624h"]["value"]
    dro = next(r["semivariance"] for r in ro if r["lag_h"] == "744-1488")
    ro_pts = []
    for r in ro:
        a, b = (float(z) for z in r["lag_h"].split("-"))
        ro_pts.append([0.5 * (a + b), r4(r["semivariance"] / dro)])
    s_t1 = norm_bins(t1["bins"], d1, 18.0)
    s_t2 = norm_bins(t2["bins"], d2, 18.0)
    s_sx = norm_bins(sxj["variogram_all"]["bins"], dsx, 18.0)
    check("T1 18-30 h / 744-1488 h", s_t1[0][1], 0.817, 0.001)
    check("T2 18-30 h / 744-1488 h", s_t2[0][1], 0.791, 0.001)
    check("sx 18-30 h / 744-3624 h", s_sx[0][1], 0.81, 0.005)
    check("RO intraday 2-4 h / 744-1488 h", ro_pts[0][1], 0.433, 0.001)
    return {
        "id": "vario-koherans-okuma",
        "type": "line",
        "title": (
            "Uzun gecikme yarıvaryansının büyük kısmı ilk ölçülebilir gecikmede var (RO'da 0,43)"
        ),
        "subtitle": (
            "Log10 değerlerin yarıvaryansı, her ailenin kendi belgesindeki uzun gecikme "
            "düzeyine bölünmüş (`T1`, `T2` ve RO için 744 ile 1.488 saat kutusu, `sx` için 744 "
            "ile 3.624 saat). `T1`, `T2` ve `sx` için 18 saatten başlayan kutular (155 ile 156 "
            "kübit, x ortalama gecikme); RO için yalnızca gün içi oturumlar, 2 ile 4 saatten "
            "başlayan 5 kutu (x kutu ortası)."
        ),
        "read": (
            "Her eğrinin ilk noktası, uzun gecikme düzeyinin ne kadarının bir günde (RO için 2 "
            "ile 4 saatte) zaten bulunduğunu gösteriyor: `T1` 0,817, `T2` 0,791, `sx` 0,81, RO "
            "0,433. Geri kalanı haftalar ile aylar içinde azalan hızla ekleniyor. Hiçbir eğri "
            "düz değil (sabit düzey artı gürültü) ve hiçbiri gecikmeyle orantılı büyümüyor "
            "(rastgele yürüyüş): yavaş kayan bir düzey artı büyük bir nugget."
        ),
        "caveat": (
            "`T1` ve `T2` için 2 ile 18 saat arasındaki havuzlanmış kutular çizilmedi: 6 ile 9 "
            "saatteki 447 çiftin 302'si 2026-05-30 öncesindeki sakin döneme düşüyor, bu yüzden "
            "gün altı hafıza olarak okunamaz (02 §4.1). Kısa kutular ve paydalar ailelere göre "
            "farklı; karşılaştırma yalnızca büyüklük mertebesinde (00 §4.1)."
        ),
        "source": (
            "00 §4.1; 02 §4.1; 03 §4.3; 04 §4; results/coherence/nonpersistent.json "
            "(variograms.log10_T1/T2.all), results/gates_1q/sx_variogram.json (variogram_all), "
            "results/readout/noise.json (variograms.ro_log10.mixed_only)"
        ),
        "x": {"label": "Gecikme", "scale": "log", "unit": "saat"},
        "y": {"label": "Yarıvaryans / uzun gecikme düzeyi", "scale": "linear", "min": 0},
        "markers": [{"axis": "y", "value": 1, "label": "uzun gecikme düzeyi"}],
        "series": [
            {"name": "T1", "points": s_t1, "style": "line+dots"},
            {"name": "T2", "points": s_t2, "style": "line+dots"},
            {"name": "sx", "points": s_sx, "style": "line+dots"},
            {"name": "RO (gün içi oturumlar)", "points": ro_pts, "style": "line+dots"},
        ],
    }


def chart_vario_gates() -> dict[str, Any]:
    vj = load("gates_2q/variograms.json")
    lf = load("device/layer_fidelity.json")["variogram"]["lf_100"]["bins"]
    cz, rzz, zz = vj["cz"], vj["rzz"], vj["abs_zz"]
    dlf = next(b["semivariance"] for b in lf if b["lag_h_lo"] == 744.0)
    s_cz = norm_bins(cz["variogram"]["bins"], cz["summary"]["long_lag_ge_744h_mean"], 18.0)
    s_rzz = norm_bins(rzz["variogram"]["bins"], rzz["summary"]["long_lag_ge_744h_mean"], 18.0)
    s_zz = norm_bins(zz["variogram"]["bins"], zz["summary"]["long_lag_ge_744h_mean"], 0.0)
    s_lf = norm_bins(lf, dlf, 18.0)
    check("cz 18-30 h / mean >= 744 h", s_cz[0][1], 0.64, 0.002)
    check("rzz 18-30 h / mean >= 744 h", s_rzz[0][1], 0.54, 0.002)
    check("|zz| 0-2 h / mean >= 744 h", s_zz[0][1], 0.60, 0.003)
    check("lf_100 18-30 h / 744-1488 h", s_lf[0][1], 0.82, 0.005)
    return {
        "id": "vario-kapilar",
        "type": "line",
        "title": "Kapılarda da nugget uzun gecikme düzeyinin yarısını aşıyor",
        "subtitle": (
            "Log10 yarıvaryans, sahibin uzun gecikme düzeyine bölünmüş: `cz` (172 kuplör), "
            "`rzz` (171) ve `|zz|` (172) için 744 saat ve üstü kutuların ortalaması, `lf_100` "
            "(süreç biçimi EPLG, tek seri, 83 olay) için 744 ile 1.488 saat kutusu. `cz`, `rzz` "
            "ve `lf_100` 18 saatten, `|zz|` 0 ile 2 saatten başlıyor; x ortalama gecikme. "
            "20'den az çiftli kutu çizilmedi (yalnızca `lf_100` 30 ile 42 saat, 6 çift)."
        ),
        "read": (
            "Bir tur arayla yarıvaryans uzun gecikme düzeyinin `cz` için 0,64'ü, `rzz` için "
            "0,54'ü, `lf_100` için 0,82'si; `|zz|` 0 ile 2 saatte 0,60. Yavaş parça haftalar ile "
            "aylar içinde azalan hızla büyüyor. `|zz|` birkaç saatte tam büyüklüğüne ulaşıyor ve "
            "yaklaşık 372 saate kadar düz kalıyor."
        ),
        "caveat": (
            "`|zz|` gecikmeleri ölçüm zamanı değil dosya zamanı (05 §4.3). `lf_100` zinciri "
            "neredeyse her olayda yeniden seçiliyor (83 olayda 59 zincir), bu da kendi varyansını "
            "ekliyor (06 §4; doğrulayıcı bunu 16 aynı zincir çiftine dayandığı için zayıflattı). "
            "`cz` ve `rzz` için gün altı kutular ayrı grafikte."
        ),
        "source": (
            "00 §4.1; 05 §4.1, §4.3; 06 §4 and Verification; results/gates_2q/variograms.json "
            "(cz, rzz, abs_zz), results/device/layer_fidelity.json (variogram.lf_100)"
        ),
        "x": {"label": "Gecikme", "scale": "log", "unit": "saat"},
        "y": {"label": "Yarıvaryans / uzun gecikme düzeyi", "scale": "linear", "min": 0},
        "markers": [{"axis": "y", "value": 1, "label": "uzun gecikme düzeyi"}],
        "series": [
            {"name": "cz", "points": s_cz, "style": "line+dots"},
            {"name": "rzz", "points": s_rzz, "style": "line+dots"},
            {"name": "|zz| (dosya zamanı)", "points": s_zz, "style": "line+dots"},
            {"name": "lf_100", "points": s_lf, "style": "line+dots"},
        ],
    }


def chart_share_bar() -> dict[str, Any]:
    np_s = load("coherence/nonpersistent.json")["variograms"]
    sxs = load("gates_1q/sx_variogram.json")["summary_all"]
    vj = load("gates_2q/variograms.json")
    lfv = load("device/layer_fidelity.json")["variogram"]
    ro = load("readout/noise.json")["variograms"]

    def coh(name: str) -> tuple[float, float]:
        s = np_s[name]["all"]["summary"]
        return s["ratio_18_30h_over_744_1488h"], s["ratio_18_30h_over_744_1488h_robust"]

    def readout(name: str) -> float:
        rows = ro[name]["mixed_only"]["decomposition"]
        short = next(r["semivariance"] for r in rows if r["lag_h"] == "2-4")
        long_ = next(r["semivariance"] for r in rows if r["lag_h"] == "744-1488")
        return float(short / long_)

    def lf(name: str) -> tuple[float, float]:
        bins = lfv[name]["bins"]
        a = next(b for b in bins if b["lag_h_lo"] == 18.0)
        b = next(b for b in bins if b["lag_h_lo"] == 744.0)
        return (
            a["semivariance"] / b["semivariance"],
            a["semivariance_robust"] / b["semivariance_robust"],
        )

    rows: list[tuple[str, float, float | None]] = [
        ("T1 (18-30 sa)", *coh("log10_T1")),
        ("T2 (18-30 sa)", *coh("log10_T2")),
        ("Gamma_phi (18-30 sa)", *coh("log10_gamma_phi")),
        ("RO, gün içi (2-4 sa)", readout("ro_log10"), None),
        ("P(0|1), gün içi (2-4 sa)", readout("p0g1_fresh_log10"), None),
        ("P(1|0), gün içi (2-4 sa)", readout("p1g0_log10"), None),
        (
            "sx (18-30 sa)",
            sxs["semivariance"]["daily_over_long"],
            sxs["semivariance_robust"]["daily_over_long"],
        ),
        ("cz (18-30 sa)", vj["cz"]["summary"]["nugget_over_long"], None),
        ("rzz (18-30 sa)", vj["rzz"]["summary"]["nugget_over_long"], None),
        ("|zz| (0-2 sa, dosya zamanı)", vj["abs_zz"]["summary"]["nugget_over_long"], None),
        ("lf_100 (18-30 sa)", *lf("lf_100")),
        ("lf_50 (18-30 sa)", *lf("lf_50")),
        ("lf_10 (18-30 sa)", *lf("lf_10")),
    ]
    robust_2q = {
        "cz (18-30 sa)": vj["cz"]["summary_robust"]["nugget_over_long"],
        "rzz (18-30 sa)": vj["rzz"]["summary_robust"]["nugget_over_long"],
        "|zz| (0-2 sa, dosya zamanı)": vj["abs_zz"]["summary_robust"]["nugget_over_long"],
    }
    rows = [(n, c, robust_2q.get(n, rb)) for n, c, rb in rows]
    doc = {  # 00 §4.1 table, "Short over long (robust)"
        "T1 (18-30 sa)": (0.817, 0.679),
        "T2 (18-30 sa)": (0.791, 0.702),
        "Gamma_phi (18-30 sa)": (0.813, 0.717),
        "RO, gün içi (2-4 sa)": (0.433, None),
        "P(0|1), gün içi (2-4 sa)": (0.513, None),
        "P(1|0), gün içi (2-4 sa)": (0.544, None),
        "sx (18-30 sa)": (0.81, 0.83),
        "cz (18-30 sa)": (0.64, 0.62),
        "rzz (18-30 sa)": (0.54, 0.54),
        "|zz| (0-2 sa, dosya zamanı)": (0.60, 0.83),
        "lf_100 (18-30 sa)": (0.82, 0.58),
        "lf_50 (18-30 sa)": (0.65, 0.55),
        "lf_10 (18-30 sa)": (0.94, 0.91),
    }
    for n, c, rb in rows:
        dc, drb = doc[n]
        check(f"share {n} classical", c, dc, 0.005)
        if drb is not None and rb is not None:
            check(f"share {n} robust", rb, drb, 0.005)
    return {
        "id": "kisa-gecikme-payi",
        "type": "bar",
        "orient": "h",
        "title": "Aileler en kısa gecikmede uzun gecikme düzeyinin 0,43 ile 0,82'sini taşıyor",
        "subtitle": (
            "En kısa kullanılan kutudaki yarıvaryansın sahibin uzun gecikme düzeyine oranı, "
            "klasik ve sağlam (Cressie-Hawkins) kestiriciyle; parantezde en kısa kutu. Okuma "
            "alanları için sağlam oran belgede verilmiyor."
        ),
        "read": (
            "Varlık ailelerinde klasik oran 0,433 (RO, gün içi) ile 0,817 (`T1`) arasında; "
            "`lf_10` 0,94 ile bunun üstünde. Her ailede bileşenin büyük kısmı ilk ölçülebilir "
            "gecikmede orada. Sağlam oran `T1`, `T2` ve `lf_100` için belirgin biçimde düşük, "
            "`sx` ve `|zz|` için yüksek: sayılar kestiriciye bağlı."
        ),
        "caveat": (
            "Yalnızca büyüklük mertebesinde karşılaştırılabilir: kısa kutular farklı (okuma 2 "
            "ile 4 saat, `|zz|` 0 ile 2 saat dosya zamanı, diğerleri 18 ile 30 saat), paydalar "
            "farklı (744 ile 1.488 saat; `sx` için 744 ile 3.624 saat; `cz`, `rzz` ve `|zz|` için "
            "744 saat üstü kutuların ortalaması) ve okumanın oranı havuzlanmış log10 ölçeğinde."
        ),
        "source": (
            "00 §4.1 (table); 02 §4.1; 03 §4.3; 04 §4; 05 §4.1, §4.3; 06 §4; "
            "results/coherence/nonpersistent.json, results/readout/noise.json, "
            "results/gates_1q/sx_variogram.json, results/gates_2q/variograms.json, "
            "results/device/layer_fidelity.json"
        ),
        "x": {"label": "En kısa gecikme / uzun gecikme", "scale": "linear", "min": 0, "max": 1},
        "y": {"label": "Aile (en kısa kutu)", "scale": "band"},
        "categories": [n for n, _, _ in rows],
        "series": [
            {"name": "klasik", "values": [round(c, 3) for _, c, _ in rows]},
            {"name": "sağlam", "values": [None if rb is None else round(rb, 3) for *_, rb in rows]},
        ],
    }


def chart_readout_shot() -> dict[str, Any]:
    sv = load("readout/noise.json")["standardized_variograms"]

    def pts(key: str) -> list[list[float]]:
        out = []
        for b in sv[key]:
            if b["pairs"] and b["robust_ratio"] is not None:
                out.append([0.5 * (b["lag_h_lo"] + b["lag_h_hi"]), b["robust_ratio"]])
        return out

    ro = pts("ro_linear_mixed_only")
    ro24 = next(p[1] for p in ro if p[0] == 3.0)
    check("RO standardized 2-4 h", ro24, 4.252, 0.0005)
    return {
        "id": "okuma-atis-gurultusu",
        "type": "line",
        "title": "Binom atış gürültüsü okumanın kısa gecikme değişkenliğinin dörtte biri",
        "subtitle": (
            "Standartlaştırılmış yarıvaryogram: her çiftin değişimi kendi binom atış gürültüsü "
            "varyansına bölünmüş, kutu başına z² medyanının 0,4549'a oranı. Yalnızca gün içi "
            "oturumlar (4.096 atış), 156 kübit, x kutu ortası, log ölçek. 1 değeri saf atış "
            "gürültüsü."
        ),
        "read": (
            "2 ile 4 saatte RO 4,252 birimde (24.477 kübit çifti; doğrulayıcı 4,253): atış "
            "gürültüsü bu değişkenliğin 1/4,252 = 0,235'ini açıklıyor; P(0|1) için yaklaşık beşte "
            "iki (2,530), P(1|0) için altıda bir (5,794). Aynı kuraldan geçen iid binom plasebo "
            "1,005 veriyor, yani fazlalık kuralın yapaylığı değil. Fazlalık 2 ile 4 saatten bir "
            "güne az büyüyor (4,252'den 4,759'a): nugget gibi davranıyor."
        ),
        "caveat": (
            "0,5 ile 2 saat kutusu 933 kübit çifti ama yalnızca 5 oturum çiftine dayanıyor; bu "
            "gecikmede bir düşüş iddia edilemez (03 §4.4). 07 §4.4'teki 0,202 (her kübitin ±7 "
            "günlük düzeyine göre artık varyansındaki atış payı, medyan) farklı bir büyüklük. "
            "Fazlalığın kestirim hatası mı gerçek dalgalanma mı olduğu açık; belge ona ölçüm "
            "gürültüsü demiyor."
        ),
        "source": (
            "03 §4.3, §4.4, §4.7 and Verification; 00 §4.1 item 3; results/readout/noise.json "
            "(standardized_variograms.*_linear_mixed_only), "
            "results/verify/readout/noise_check.json"
        ),
        "x": {"label": "Gecikme", "scale": "log", "unit": "saat"},
        "y": {"label": "Atış gürültüsü birimi", "scale": "log"},
        "markers": [{"axis": "y", "value": 1, "label": "saf binom atış gürültüsü"}],
        "series": [
            {"name": "RO", "points": ro, "style": "line+dots"},
            {"name": "P(0|1)", "points": pts("p0g1_fresh_linear_mixed_only"), "style": "line+dots"},
            {"name": "P(1|0)", "points": pts("p1g0_linear_mixed_only"), "style": "line+dots"},
            {
                "name": "iid binom plasebo (doğrulayıcı, 2-4 sa)",
                "points": [[3.0, 1.005]],
                "style": "dots",
            },
        ],
    }


def chart_comovement_gap() -> dict[str, Any]:
    cm = load("cross/comovement.json")["pairs"]
    sxp = next(p for p in cm if p["anchor"] == "sx" and p["other"] == "p10")
    w2 = load("verify/cross/comovement_check.json")["gap_bins_stress_sx_p10"]["W2d"]["sx-p10"]
    czr = load("gates_2q/cz_vs_rzz.json")["changes"]["local_deviation_spearman_by_abs_offset"]
    sxt = load("gates_1q/sx_coherence.json")["within_by_stamp_offset"]["T1"]

    def mid(lo: float, hi: float) -> float:
        return 0.5 * (lo + hi)

    s7 = [[mid(b["gap_h_lo"], b["gap_h_hi"]), round(b["raw"]["r"], 4)] for b in sxp["by_gap"]]
    s2 = [[mid(*b["bin_h"]), round(b["r"], 4)] for b in w2]
    s_cz = [
        [mid(b["abs_offset_h_lo"], b["abs_offset_h_hi"]), round(b["rho"], 4)]
        for b in czr
        if b["abs_offset_h_hi"] <= 48.0
    ]
    s_t1 = [
        [0.5, round(-sxt["abs_offset_le_1h"]["rho"], 4)],
        [3.5, round(-sxt["abs_offset_1_to_6h"]["rho"], 4)],
    ]
    check("sx-P(0|1) 0-0.5 h, 7 d", s7[0][1], 0.108, 0.0005)
    check("sx-P(0|1) 0-0.5 h, 2 d", s2[0][1], 0.032, 0.0005)
    check("cz-rzz 0-1 h", s_cz[0][1], 0.205, 0.0005)
    check("sx-T1 within 1 h (sign flipped)", s_t1[0][1], 0.096, 0.0005)
    return {
        "id": "ortak-parca-zaman",
        "type": "line",
        "title": (
            "Deneyler arası ortak parça en yakın ölçümlerde en büyük görünüyor; "
            "zaman ölçeği kurulmadı"
        ),
        "subtitle": (
            "Aynı kübit ya da kuplörde iki ayrı deneyin kendi düzeyinden sapmaları arasındaki "
            "korelasyon, iki ölçüm arasındaki süreye göre (x kutu ortası, log ölçek). `sx` ile "
            "P(0|1): normal skorların Pearson'ı, ±7 ve ±2 günlük düzey penceresi; `cz` ile `rzz`: "
            "aynı kuplörde Spearman; `sx` ile `T1`: aynı turda Spearman, işareti çevrilmiş (-ρ), "
            'böylece her seride pozitif değer "ikisi birlikte kötüleşiyor" anlamına geliyor.'
        ),
        "read": (
            "`sx` ile P(0|1) 0 ile 0,5 saatte 0,108 (1.530 çift), 6 saatten sonra sıfırdan ayırt "
            "edilemiyor; `cz` ile `rzz` 1 saat içinde 0,205 (5.424 çift), 2 ile 12 saatte 0,04 ile "
            "0,08; `sx` ile `T1` 1 saat içinde 0,096 (9.826 olay), 1 ile 6 saatte 0,024. Ayrı "
            "deneylerin bağımsız kestirim hataları hiçbir aralıkta korelasyon üretmez."
        ),
        "caveat": (
            "Zaman ölçeği kurulmuş değil. Düzey penceresi ±2 güne inince `sx` ile P(0|1) en kısa "
            "kutuda 0,032'ye düşüyor: 2 ile 7 günde hareket eden ortak bir düzey de aynı kısa "
            "aralık korelasyonunu üretir (07 doğrulama, iddia 1). `sx` ile `T1` yakın-uzak farkı "
            "aynı kalibrasyon işi ile farklı iş ayrımına da uyuyor (04 doğrulama). `cz`-`rzz` "
            "düşüşü tur başına da sürüyor (104 tur, Spearman -0,393), ama 12 ile 24 saatteki "
            "0,099 tümseği açıklanmadı. Kutular farklı olaylardan oluşuyor; kontrollü bir sönüm "
            "ölçümü değil."
        ),
        "source": (
            "07 §4.2 and Verification claim 1; 05 §4.4 and Verification; 04 §7 and Verification; "
            "results/cross/comovement.json (pairs sx-p10 by_gap), "
            "results/verify/cross/comovement_check.json (gap_bins_stress_sx_p10.W2d), "
            "results/gates_2q/cz_vs_rzz.json (changes.local_deviation_spearman_by_abs_offset), "
            "results/gates_1q/sx_coherence.json (within_by_stamp_offset.T1)"
        ),
        "x": {"label": "İki ölçüm arasındaki süre", "scale": "log", "unit": "saat"},
        "y": {"label": "Korelasyon", "scale": "linear"},
        "markers": [{"axis": "y", "value": 0, "label": "bağımsız hatalar"}],
        "series": [
            {"name": "sx ile P(0|1), ±7 gün düzey", "points": s7, "style": "line+dots"},
            {
                "name": "sx ile P(0|1), ±2 gün düzey (doğrulayıcı)",
                "points": s2,
                "style": "line+dots",
            },
            {"name": "cz ile rzz, aynı kuplör", "points": s_cz, "style": "line+dots"},
            {"name": "sx ile T1, -ρ", "points": s_t1, "style": "line+dots"},
        ],
    }


def chart_hop() -> dict[str, Any]:
    sp = load("gates_2q/spatial.json")
    ch = load("verify/gates_2q/challenge_check.json")["a_shared_qubit_correlation"]
    vals = {}
    for fam in ("cz", "rzz"):
        own = sp[f"{fam}_deviation_correlation_in_space"]
        vals[fam] = [
            round(own["share_a_qubit"]["rho"], 4),
            round(ch[fam]["by_hop"]["2"]["spearman"], 4),
            round(ch[fam]["by_hop"]["3"]["spearman"], 4),
            round(own["four_or_more_hops"]["rho"], 4),
        ]
    check("cz share a qubit", vals["cz"][0], 0.220, 0.0005)
    check("rzz share a qubit", vals["rzz"][0], 0.226, 0.001)
    return {
        "id": "ortak-kubit-adim",
        "type": "bar",
        "orient": "v",
        "title": "Kuplör sapmaları yalnızca bir kübiti paylaştıklarında birlikte hareket ediyor",
        "subtitle": (
            "İki kuplörün aynı turdaki sapmaları (komşu medyanından ve tur medyanından "
            "arındırılmış) arasında Spearman korelasyonu, kuplörler arası adım sayısına göre. "
            "1 adım: bir kübiti paylaşan 244 kuplör çifti (29.513 eşleşme, `cz`); 4 ve üstü: "
            "13.886 çift."
        ),
        "read": (
            "Bir kübiti paylaşan kuplörlerde `cz` 0,220, `rzz` 0,225; çift başına medyan 0,209 "
            "ve 0,228; en az 30 turu olan 230 çiftin yüzde 91'inde pozitif. 2 adımda "
            "korelasyon sıfıra iniyor (-0,008 "
            "ve -0,019). `cz` için aynı sapmaların 1 ve 2 tur gecikmeli korelasyonu -0,035 ve "
            "-0,050: detrendlemeden sızan yavaş ortak bir kayma değil."
        ),
        "caveat": (
            "Paylaşılan kübitin bildirilen `sx`, `T1` ve okuma sapmaları bunu açıklamıyor "
            '(kısmi korelasyon 0,219 ve 0,225), ama o değerler başka turlarda ölçüldü; "tek '
            'kübit etkisi değil" desteklenmiyor. Paylaşılmayan çoğunluk karakterize edilmedi; '
            "kübitin fiziksel durumu ile her iki deneye ortak bir kalibrasyon girdisi ayrılamıyor."
        ),
        "source": (
            "05 §4.4 and Verification; 00 §4.1 item 5; results/gates_2q/spatial.json "
            "(*_deviation_correlation_in_space), results/verify/gates_2q/challenge_check.json "
            "(a_shared_qubit_correlation.*.by_hop, cross_round)"
        ),
        "x": {"label": "Kuplörler arası adım", "scale": "band"},
        "y": {"label": "Spearman korelasyonu", "scale": "linear"},
        "categories": ["1 (ortak kübit)", "2", "3", "4 ve üstü"],
        "series": [
            {"name": "cz", "values": vals["cz"]},
            {"name": "rzz", "values": vals["rzz"]},
        ],
    }


def chart_subday() -> dict[str, Any]:
    ch = load("verify/gates_2q/challenge_check.json")["b_short_gap_fraction_of_one_round_cz"]
    vj = load("gates_2q/variograms.json")
    sxb = load("gates_1q/sx_variogram.json")["variogram_all"]["bins"]
    cats = [("2-4 sa", 2.0), ("6-9 sa", 6.0), ("9-12 sa", 9.0), ("12-18 sa", 12.0)]
    cz = [round(ch[c.replace(" sa", "h")]["frac"], 3) for c, _ in cats]

    def frac(bins: list[dict[str, Any]], lo: float) -> float | None:
        day = next(b["semivariance"] for b in bins if b["lag_h_lo"] == 18.0)
        b = next(b for b in bins if b["lag_h_lo"] == lo)
        return round(b["semivariance"] / day, 3) if b["pairs"] else None

    rzz = [frac(vj["rzz"]["variogram"]["bins"], lo) for _, lo in cats]
    sx = [frac(sxb, lo) for _, lo in cats]
    czown = [frac(vj["cz"]["variogram"]["bins"], lo) for _, lo in cats]
    for (c, _), a, b in zip(cats, cz, czown, strict=True):
        check(f"cz fraction {c} (verifier vs bins)", float(a), float(b or 0), 0.002)
    check("sx 6-9 h / 18-30 h", float(sx[1] or 0), 0.9707, 0.001)
    return {
        "id": "gun-alti-birikim",
        "type": "bar",
        "orient": "v",
        "title": "Gün altı birikim en açık `cz` ve `rzz`'de; `sx` 6 saatte tek tur düzeyine yakın",
        "subtitle": (
            "Gün altı gecikme kutusundaki log10 yarıvaryansın 18 ile 30 saat (tek tur) değerine "
            "oranı. `cz` 11, `rzz` 6 cihaz geneli ikinci ölçüm olayından (bir turdan 3 ile 16 "
            "saat sonra); `sx` havuzlanmış kutular (en kısa olay aralığı 6,31 saat, 6 ile 9 "
            "saatte 456 çift)."
        ),
        "read": (
            "`cz` tek tur değerinin 2 ile 4 saatte 0,33'ünde, 6 ile 9 saatte 0,64'ünde, 9 ile 12 "
            "saatte 0,73'ünde, 12 ile 18 saatte 0,89'unda; `rzz` 2 ile 4, 6 ile 9 ve 12 ile 18 "
            "saatte 0,30, 0,72 ve 0,99. `sx` ise 6 ile 9 saatte 0,97 (önyükleme yüzde 95 "
            "aralığı 0,73 ile 1,29): bu gecikmede bir yükseliş görülmüyor. "
            "Arşivin bileşeni saatler içinde birikirken gösterdiği en açık yer `cz` ve `rzz`."
        ),
        "caveat": (
            '05 §4.2\'nin "ikinci kalibrasyonlar" adı ve kısa aralıktaki değişimin öncekinden '
            "küçük olduğuna dair kuplör çifti düzeyindeki p-değerleri doğrulamada çürütüldü "
            "(sözde yineleme); olay düzeyinde işaret testi p = 0,065 (`cz`, 11 olay) ve 0,69 "
            "(`rzz`, 6 olay). 2 ile 4 saat kutusu her ailede tek bir olay. Yükselişin cihazın "
            "korelasyon zamanı mı, olaylar arasındaki yeniden kalibrasyon mu olduğu ayrılamıyor. "
            "`rzz` ve `sx` oranları bu raporda variograms.json kutularından hesaplandı."
        ),
        "source": (
            "05 §4.2 and Verification; 04 §4 and Verification; 00 §4.1 item 2; "
            "results/verify/gates_2q/challenge_check.json "
            "(b_short_gap_fraction_of_one_round_cz, b_occasion_level), "
            "results/gates_2q/variograms.json (rzz.variogram), "
            "results/gates_1q/sx_variogram.json (variogram_all, bins_bootstrap)"
        ),
        "x": {"label": "Gecikme kutusu", "scale": "band"},
        "y": {"label": "Yarıvaryans / tek tur değeri", "scale": "linear", "min": 0},
        "markers": [{"axis": "y", "value": 1, "label": "tek tur (18 ile 30 saat)"}],
        "categories": [c for c, _ in cats],
        "series": [
            {"name": "cz", "values": cz},
            {"name": "rzz", "values": rzz},
            {"name": "sx", "values": sx},
        ],
    }


def chart_coincidence() -> dict[str, Any]:
    pairs = load("cross/coincidence.json")["pairs"]
    ver = load("verify/cross/coincidence_check.json")["pairs"]
    sym = {"p10": "P(0|1)", "p01": "P(1|0)"}

    def lab(a: str, b: str) -> str:
        return f"{sym.get(a, a)} ile {sym.get(b, b)}"

    plan = [
        ("T2", "RO", "T2 ile okuma"),
        ("T2", "p01", "T2 ile okuma"),
        ("T2", "p10", "T2 ile okuma"),
        ("sx", "RO", "sx ile"),
        ("sx", "p10", "sx ile"),
        ("sx", "m2", "sx ile"),
        ("zz", "T1", "zz ile"),
        ("zz", "T2", "zz ile"),
        ("zz", "sx", "zz ile"),
        ("zz", "RO", "zz ile"),
        ("zz", "p01", "zz ile"),
        ("zz", "p10", "zz ile"),
        ("zz", "m2", "zz ile"),
        ("T1", "T2", "aile içi kontrol"),
        ("RO", "p10", "aile içi kontrol"),
    ]
    rows = []
    days = []
    for a, b, g in plan:
        p = next(x for x in pairs if x["a"] == a and x["b"] == b)
        bl = p["big_lag0"]
        lo, hi = bl["lift_qubit_ci95"]
        days.append(bl["qubit_days_both_observed"])
        rows.append(
            {
                "label": lab(a, b),
                "est": round(bl["lift_qubit"], 3),
                "lo": round(lo, 3),
                "hi": round(hi, 3),
                "group": g,
            }
        )
        if (a, b) == ("sx", "p10"):
            for key, txt in (("sx-p10@3.0sd", "3 sd"), ("sx-p10@2.0sd", "2 sd")):
                rows.append(
                    {
                        "label": f"sx ile P(0|1), {txt} (doğrulayıcı)",
                        "est": round(ver[key]["qubit_null_lift"], 3),
                        "group": g,
                    }
                )
    check("coincidence sx-P(0|1) qubit-null lift", rows[4]["est"], 1.59, 0.005)
    check("coincidence T1-T2 control", rows[-2]["est"], 9.31, 0.005)
    check("verifier sx-P(0|1) at 2 sd", rows[6]["est"], 1.07, 0.005)
    print(f"     qubit-days both observed: {min(days)} to {max(days)}")
    return {
        "id": "buyuk-sapma-cakisma",
        "type": "forest",
        "title": "Büyük sapmalar aynı kübit-günde şanstan sık çakışıyor, ama etki uç kuyrukta",
        "subtitle": (
            "Aynı operasyon gününde iki farklı ailenin kendi EWMA düzeyinden 3 sağlam sd'den "
            "büyük sapmasının birlikte görülme sayısının, bayrakları o gün gözlenen kübitler "
            "arasında karıştıran boş hipotezin ortalamasına oranı (lift); yüzde 95 aralık 2.000 "
            f"kübit önyüklemesinden; çift başına {thousands(min(days))} ile "
            f"{thousands(max(days))} kübit-gün. Log ölçek, 1 = şans."
        ),
        "read": (
            "Sahibin 3 sd tanımıyla aileler arası lift 1,22 (`T2` ile P(1|0)) ile 1,96 (`sx` ile "
            "`m2`) arasında; aynı "
            "aile içindeki kontroller çok daha yüksek (`T1` ile `T2` 9,31, RO ile P(0|1) 4,63). "
            "Boş hipotez her günün cihaz geneli bayrak sayısını koruduğu için, 3 sd eşiğinde "
            "1'in üstündeki kısım cihaz genelindeki kötü günlerle açıklanmıyor."
        ),
        "caveat": (
            "Doğrulayıcıya göre etki eşiğe bağlı: `sx` ile P(0|1) kendi tanımıyla 3 sd'de 1,54, "
            "2 sd'de 1,07 (p = 0,040). Her çift 80 ile 110 ortak işaretli kübit-güne dayanıyor "
            "ve `T2` ile RO doğrulayıcının tanımında 2026-08-01'den sonra 1,01. `zz` ile `T1`, "
            "`T2` ve `sx` çiftlerinde aralık 1'i içeriyor; `sx` ile `m2` ve `zz` ile `m2` yalnızca "
            "kübit boş hipotezini geçiyor, zaman boş hipotezini geçmiyor. Bağımsız fit hataları "
            "çakışma üretemez, ama birkaç günlük "
            "ortak bir düzey adımı ya da ortak bir kalibrasyon durumu üretebilir."
        ),
        "source": (
            "07 §7.4, §4.5 and Verification claim 3; results/cross/coincidence.json "
            "(pairs[*].big_lag0.lift_qubit, lift_qubit_ci95), "
            "results/verify/cross/coincidence_check.json"
        ),
        "x": {"label": "Lift (gözlenen / boş hipotez)", "scale": "log"},
        "ref": 1,
        "rows": rows,
    }


# ---------------------------------------------------------------- charts recomputed from cache


def chart_t1_size(dd: ddload.DD) -> dict[str, Any]:
    stored = load("coherence/regime.json")["T1"]["change_level"]
    s1 = cohlib.events(dd, "q.T1")
    starts, vals = regime.round_table([(s.entity, s.t_ms, s.y) for s in s1])
    rows = []
    for i in range(len(vals) - 1):
        common = sorted(set(vals[i]) & set(vals[i + 1]))
        d = np.array([vals[i + 1][e] - vals[i][e] for e in common])
        rows.append((float(starts[i + 1]), regime.robust_sv(d * d), float(len(common))))
    a = np.array(rows)
    k, p = regime.pettitt(a[:, 1])
    check("T1 round pairs", float(a.shape[0]), float(stored["round_pairs"]), 0)
    check("T1 robust sv minimum", float(a[:, 1].min()), stored["robust_sv_quantiles"][0], 1e-8)
    check("T1 robust sv median", float(np.median(a[:, 1])), stored["robust_sv_quantiles"][4], 1e-7)
    check("T1 Pettitt p", p, stored["pettitt_p"], 1e-16)
    check(
        "T1 median before Pettitt",
        float(np.median(a[: k + 1, 1])),
        stored["robust_sv_median_before_pettitt"],
        1e-7,
    )
    check(
        "T1 median after Pettitt",
        float(np.median(a[k + 1 :, 1])),
        stored["robust_sv_median_after_pettitt"],
        1e-7,
    )
    if [utc(a[k, 0]), utc(a[k + 1, 0])] != stored["pettitt_between_utc"]:
        raise SystemExit("Pettitt dates differ from regime.json")
    q_lo, q_hi = (regime.ms(v) for v in regime.REGIMES["quiet_2026-05-15T12_to_2026-05-28T00"])
    quiet = a[(a[:, 0] >= q_lo) & (a[:, 0] < q_hi), 1]
    print(
        f"     quiet-window round pairs: {quiet.size}, min {quiet.min():.6g}, max {quiet.max():.6g}"
    )
    n_lo, n_hi = int(a[:, 2].min()), int(a[:, 2].max())
    print(f"     qubits per round pair: {n_lo} to {n_hi}")
    before, after = float(np.median(a[: k + 1, 1])), float(np.median(a[k + 1 :, 1]))
    step = [
        [utc(a[0, 0]), r4(before)],
        [utc(a[k, 0]), r4(before)],
        [utc(a[k + 1, 0]), r4(after)],
        [utc(a[-1, 0]), r4(after)],
    ]
    first = stored["first_10_round_pairs"]
    drop = next(r for r in first if abs(r["median_change"] + 0.162453) < 1e-6)
    jump = next(r for r in first if abs(r["median_change"] - 0.131723) < 1e-6)
    return {
        "id": "t1-bilesen-buyuklugu",
        "type": "line",
        "title": "`T1` bileşeninin büyüklüğü Mayıs 2026'da yaklaşık yirmi kat değişti",
        "subtitle": (
            "Ardışık iki cihaz geneli tur arasında (her biri en az 78 kübit) log10 `T1` "
            "değişiminin sağlam (Cressie-Hawkins) yarıvaryansı, ikinci turun zamanında; 132 tur "
            f"çifti, her birinde iki turda da ölçülen {n_lo} ile {n_hi} kübit. Log ölçek. "
            "İkinci seri Pettitt noktasının "
            "öncesindeki ve sonrasındaki medyan."
        ),
        "read": (
            "2026-05-15 ile 05-27 arasındaki 13 turda bir kübitin `T1` değeri turdan tura "
            "neredeyse değişmedi (0,000404 ile 0,000686). 2026-05-28T06 turundaki +0,132 dekadlık "
            "cihaz geneli adımdan sonra değer 0,01 civarına çıktı; 2026-06-26/29'daki Pettitt "
            "noktasında medyan 0,0092'den 0,0146'ya yükseldi (p = 5,5×10⁻¹²)."
        ),
        "caveat": (
            "Sakin pencerede değişimlerin lag-1 otokorelasyonu -0,33 (sonra -0,486 ve -0,501); 13 "
            'turla bu değer "kübitler daha sakindi" ile "değerler farklı üretildi" arasında '
            "karar vermiyor ve arşiv cihazın ortamı ile değerlerin üretimi arasında ayrım "
            "yapamıyor (02 §3.2). Haziran adımı 2026-06-27 ile 06-29 arasındaki 61,8 saatlik "
            "dosya boşluğuna düşüyor; zamanlaması bu boşluk kadar belirsiz. Diğer aileler için "
            "sakin pencere ölçülmedi."
        ),
        "source": (
            "02 §3.2 and Verification; 00 §4.2; results/coherence/regime.json "
            "(T1.change_level); per-pair values recomputed in this report with "
            "analysis/coherence/regime.py (round_table, robust_sv, pettitt)"
        ),
        "x": {"label": "İkinci turun zamanı", "scale": "time"},
        "y": {"label": "Sağlam yarıvaryans", "scale": "log", "unit": "dekad²"},
        "markers": [
            {"axis": "x", "value": drop["second_round_utc"], "label": "-0,162 dekad adımı"},
            {"axis": "x", "value": jump["second_round_utc"], "label": "+0,132 dekad adımı"},
            {"axis": "x", "value": stored["pettitt_between_utc"][1], "label": "Pettitt (06-26/29)"},
        ],
        "series": [
            {
                "name": "tur çifti",
                "points": [[utc(t), r4(v)] for t, v in zip(a[:, 0], a[:, 1], strict=True)],
                "style": "line+dots",
            },
            {"name": "Pettitt öncesi ve sonrası medyan", "points": step, "style": "line"},
        ],
    }


def chart_t1_t2(dd: ddload.DD) -> dict[str, Any]:
    stored = load("coherence/nonpersistent.json")["t1_t2_comovement"]
    pairs, _ = cohlib.paired(dd)
    xs, ys = [], []
    for p in pairs:
        x = nonpersistent.deviations(np.log10(p.t1))
        y = nonpersistent.deviations(np.log10(p.t2))
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 20:
            continue
        xs.append(x[ok])
        ys.append(y[ok])
    x, y = np.concatenate(xs), np.concatenate(ys)
    pear = float(np.corrcoef(x, y)[0, 1])
    slope, icpt = (float(v) for v in np.polyfit(x, y, 1))
    check("T1/T2 events", float(x.size), float(stored["events"]), 0)
    check("T1/T2 qubits", float(len(xs)), float(stored["qubits"]), 0)
    check("T1/T2 Pearson", pear, stored["pearson"], 5e-6)
    check("T1/T2 OLS slope", slope, stored["ols_slope_pooled"], 5e-6)
    rng = np.random.default_rng(SEED)
    pick = np.sort(rng.choice(x.size, N_SCATTER, replace=False))
    sub_r = float(np.corrcoef(x[pick], y[pick])[0, 1])
    print(f"     scatter subsample Pearson {sub_r:.3f} (all events {pear:.3f})")
    x0, x1 = float(np.quantile(x, 0.001)), float(np.quantile(x, 0.999))
    return {
        "id": "t1-t2-ayni-tur",
        "type": "scatter",
        "title": "Aynı turda `T1` ve `T2` sapmaları birlikte hareket ediyor (r = 0,70)",
        "subtitle": (
            "Her kübitin log10 `T1` ve `T2` değerinin kendi yürüyen medyanından (olayın kendisi "
            "hariç 14 komşu olay) sapması; aynı dosyada saniyeler arayla damgalanmış eşleşik "
            "olaylar, 19.589 olay, 155 kübit. Çizimde 2.000 noktalık rastgele alt örneklem "
            f"(alt örneklemin kendi Pearson'ı {f'{sub_r:.2f}'.replace('.', ',')}); çizgi tüm "
            "olaylara uydurulan EKK doğrusu (eğim 0,58)."
        ),
        "read": (
            "Pearson 0,70 (ρ² = 0,49), Spearman 0,69; 155 kübitin hepsinde pozitif. Ayrı iki "
            "deneyin bağımsız fit hataları korelasyon üretemez; bu yüzden her sapmanın "
            "varyansının en az yaklaşık yarısı iki fit arasında paylaşılıyor. Kuyruk tek yönlü: "
            "`T1` sapmalarının yüzde 3,19'u -0,301 dekadın (yarıya düşüş) altında, yalnızca yüzde "
            "0,106'sı +0,301'in üstünde."
        ),
        "caveat": (
            "Doğrulayıcı sayıyı ikinci bir düzey tanımıyla (7 gün, 0,701), düzeysiz birinci "
            "farklarla (0,714) ve her turun medyan sapması çıkarılarak (0,69) yeniden üretti; "
            "plasebolar -0,03 (sonraki turun `T2`) ve 0,05 ile 0,07 (başka kübitin `T2`). Ama "
            "paylaşılan parça kübitin gerçek değişimi olarak kanıtlanmış değil: IBM yordamında "
            "aynı turda iki fiti aynı yönde saptıran ortak bir girdi aynı korelasyonu üretir. "
            "Bir turdaki okuma ya da hazırlama değişiminin `T1` ve `T2`'yi birlikte oynatıp "
            "oynatmadığını kimse test etmedi."
        ),
        "source": (
            "02 §4.2 and Verification; 00 §4.1 item 5; results/coherence/nonpersistent.json "
            "(t1_t2_comovement, heterogeneity.T1); points recomputed in this report with "
            "analysis/coherence/cohlib.py (paired) and nonpersistent.py (deviations); "
            "results/verify/coherence/comove_check.json"
        ),
        "x": {"label": "log10 `T1` sapması", "scale": "linear", "unit": "dekad"},
        "y": {"label": "log10 `T2` sapması", "scale": "linear", "unit": "dekad"},
        "fit": [
            [round(x0, 3), round(icpt + slope * x0, 4)],
            [round(x1, 3), round(icpt + slope * x1, 4)],
        ],
        "series": [
            {
                "name": "eşleşik olay (alt örneklem)",
                "points": [[round(float(x[i]), 4), round(float(y[i]), 4)] for i in pick],
            }
        ],
    }


# ---------------------------------------------------------------- text


TITLE = "Kök soru: ölçümden ölçüme taşınmayan bileşen nedir?"

INTRO = [
    (
        "Arşivdeki her bilgi taşıyan seri üç parçadan oluşuyor: aylarca kararlı kalan, kübite "
        "ya da kuplöre özgü bir düzey; haftalar ile aylar içinde yavaşça kayan bir düzey; ve bir "
        "ölçümden ötekine taşınmayan büyük bir bileşen. Bu son bileşen her varlık ailesinde "
        "hafızasız: log değişimlerinin lag-1 otokorelasyonu -0,425 ile -0,513 arasında, yani "
        "bir düzey etrafındaki bağımsız saçılımın -0,5 değerine yakın. En kısa ölçülebilir "
        "gecikmedeki yarıvaryans (nugget) uzun gecikme yarıvaryansının 0,43 ile 0,82'si "
        "(`lf_10` için 0,94). Kök soru şu: bu bileşen IBM'in kestirim gürültüsü mü, günlük "
        "örneklemenin bağımsız çekilişlere çevirdiği hızlı gerçek dinamik mi, yoksa turdan "
        "tura yeniden kalibrasyonun izi mi? Bir tahmin modelinin bandının ölçüm hassasiyeti "
        "bandı mı fiziksel bir band mı olduğu bu soruya bağlı."
    ),
    (
        "Kanıt iki basit okumayı dışlıyor. Birincisi, bileşenin tümüyle sabit bir düzey "
        "etrafında bağımsız kestirim hatası olması: yavaş düzey ve ayrı deneyler arasındaki "
        "korelasyonlar buna uymuyor; en sağlamı aynı turdaki `T1` ve `T2` sapmalarının 0,70 "
        "korelasyonu (doğrulayıcı iki düzey tanımıyla ve düzeysiz birinci farklarla, 0,714, "
        "yeniden üretti). Bu dışlama, IBM'in iki deneyine ortak ve aynı turda iki fiti birlikte "
        "saptıran bir yapaylık yoksa geçerli. İkincisi, okuma bileşeninin binom atış (shot) "
        "gürültüsü olması: atış gürültüsü okumanın en kısa gecikmedeki değişkenliğinin yaklaşık "
        "dörtte biri (0,235); aynı kuraldan geçirilen iid binom plasebo 1,005 veriyor."
    ),
    (
        "Kanıt, bileşenin büyük kısmının fiziksel olduğunu da göstermiyor. `T1`/`T2` dışında "
        "ortak parçalar küçük: aileler arası en kısa aralıkta mutlak değerce en fazla 0,130, bir "
        "kübiti paylaşan kuplörlerde 0,22. Ortak parçanın zaman ölçeği belirsiz: `sx` ile P(0|1) "
        "korelasyonu düzey penceresi ±7 günden ±2 güne inince 0,108'den 0,032'ye düşüyor, `sx` "
        "ile `T1` arasındaki yakın-uzak farkı aynı iş ile farklı iş ayrımıyla karışıyor, `cz` ve "
        "`rzz` için saatler içindeki yükseliş yeniden kalibrasyondan ayrılamıyor. Paylaşılmayan "
        "çoğunluğu ayıracak bir test arşivde yok ve bileşenin büyüklüğü sabit değil (`T1` için "
        "Mayıs 2026'da cihaz genelinde yaklaşık yirmi kat değişti). Bu yüzden bileşene ne "
        "kestirim gürültüsü ne de fiziksel diyoruz."
    ),
    (
        "Neyin ayırt edeceği (öneri; donanım zamanı ekibin kararı): birkaç `ibm_fez` kübiti ve "
        "kuplöründe birkaç saat boyunca dakika aralıklı ardışık tekrarlar (`T1`, Hahn eko, tek "
        "ve iki kübit RB, atış sayısı bilinen atama deneyleri), fit belirsizlikleri kaydedilerek, "
        "tekrarlar arasında yeniden kalibrasyonla ve kalibrasyonsuz. Kestirim gürültüsü en kısa "
        "gecikmeden itibaren düz, tekrar (fit) varyansında duran ve arşivin nugget değerine eşit "
        "bir yarıvaryogram öngörür; seyrek örneklenen hızlı dinamik dakikalar ile saatler "
        "içinde nugget değerine yükselen bir eğri ve nugget'ın altında bir tekrar varyansı "
        "öngörür; yeniden kalibrasyon değişkenliği kalibrasyonlarla hizalı sıçramalar öngörür. "
        "IBM meta verisi (RB ayarları, değer başına fit belirsizlikleri, iş kimlikleri, günlük "
        "okuma atış sayısı) RB aileleri için hesaplanabilir bir taban ve yakın ile uzak "
        "çiftlerin aynı işten gelip gelmediğini verir."
    ),
]

BULLETS = [
    (
        "**Her ailede hafızasız bir bileşen.** Log değişimlerinin lag-1 otokorelasyonu her "
        "varlık ailesinde -0,425 (`rzz`) ile -0,513 (`|zz|`) arasında, `lf` adlarıyla birlikte "
        "-0,36 ile -0,56. En kısa gecikmedeki pay 0,433 (RO, gün içi, 2 ile 4 saat) ile 0,817 "
        "(`T1`) arasında. Kısa kutular, paydalar ve kestiriciler ailelere göre farklı olduğu "
        "için karşılaştırma yalnızca büyüklük mertebesinde."
    ),
    (
        "**`T1` ile `T2` aynı turda birlikte sapıyor, ama bu paylaşım, kanıtlanmış gerçek "
        "değişim değil.** Pearson 0,70 (19.589 olay, 155 kübitin hepsinde pozitif); doğrulayıcı "
        "7 günlük düzeyle 0,701, düzeysiz birinci farklarla 0,714, tur medyanı çıkarılınca 0,69 "
        "buldu, plasebolar -0,03 ve 0,05 ile 0,07. Her sapmanın varyansının en az yaklaşık "
        "yarısı (ρ² = 0,49) iki fit arasında paylaşılıyor; aynı turda iki fite ortak bir yapaylık "
        "dışlanmadı."
    ),
    (
        "**Okumada bilinen kestirim gürültüsü azınlıkta.** Gün içi oturumlarda 2 ile 4 saatte "
        "RO değişimi atış gürültüsünün 4,252 katı (24.477 kübit çifti); binom atış gürültüsü "
        "bunun 0,235'ini açıklıyor (havuzlanmış log10 ölçeğinde 0,125). İid binom plasebo 1,005. "
        "Fazlalık yaklaşık 3 ile 12 saat arasında düz (oturum çifti medyanları 4,209 ile 4,493); "
        "2 saatin altında yalnızca 5 oturum çifti var."
    ),
    (
        "**Bileşenin büyüklüğü durağan değil.** `T1` için turdan tura sağlam yarıvaryans "
        "2026-05-15 ile 05-27 arasındaki 13 turda 0,000404 ile 0,000686, sonrasında tipik olarak "
        "0,0146. 2026-06-26/29'da ikinci bir adım var (medyan 0,0092'den 0,0146'ya, Pettitt "
        "p = 5,5×10⁻¹²). Değişenin cihazın ortamı mı değerlerin üretimi mi olduğu arşivden "
        "ayrılamıyor."
    ),
    (
        "**`T1`/`T2` dışındaki ortak parçalar küçük.** Bir kübiti paylaşan kuplörler `cz` 0,220 "
        "ve `rzz` 0,225 (244 kuplör çifti), 2 adım ve ötesinde -0,020 ile -0,008; `cz` ile "
        "`rzz` aynı kuplörde 1 saat içinde 0,205; `sx` ile aynı turdaki `T1` 1 saat içinde "
        "-0,096, 1 ile 6 saatte -0,024; 07'nin aileler arası çiftlerinde en kısa aralıkta "
        "mutlak değerce en fazla 0,130. Cihaz geneli ortak mod artık varyansın 0,012 ile "
        "0,130'u."
    ),
    (
        "**Ortak parçanın zaman ölçeği kurulmadı.** `sx` ile P(0|1) 0 ile 0,5 saatte 0,108, ±2 "
        "günlük düzeyle 0,032. `cz` yarıvaryansı aralıkla artıyor (tek tur değerinin 2 ile 4 "
        "saatte 0,33'ü, 12 ile 18 saatte 0,89'u), ama 11 olaya dayanıyor ve yeniden "
        "kalibrasyondan ayrılamıyor; olay düzeyinde işaret testi p = 0,065 (`cz`) ve 0,69 "
        "(`rzz`, 6 olay). 05'in çift düzeyindeki p-değerleri sözde yineleme nedeniyle çürütüldü."
    ),
    (
        "**`T1` için gün altı kanıt sınırlı.** Eşleştirilmiş test 9 olaya dayanıyor ve yalnızca "
        "biri 6 saatin altında (2026-06-12, 3,86 saat, 147 kübit). Medyan oran sahibin "
        "eşleştirmesiyle 0,96, doğrulayıcınınkiyle 1,05 (2026-05-30 sonrası 1,19). Desteklenen "
        'ifade "yaklaşık 4 ile 24 saat arasında yükseliş yok"; bir korelasyon zamanı değil.'
    ),
    (
        "**Büyük sapmalar aynı kübit-günde çakışıyor, ama yalnızca uçta.** 3 sd eşiğinde iki "
        "farklı ailenin aynı kübit-günde birlikte işaretlenmesi şansın 1,2 ile 2,1 katı; aile içi "
        "kontroller 4,6 ile 12,8. Doğrulayıcıda `sx` ile P(0|1) 3 sd'de 1,54, 2 sd'de 1,07: etki "
        "uç kuyrukla sınırlı ve çift başına 80 ile 110 ortak işaretli kübit-güne dayanıyor."
    ),
]


def main() -> None:
    # The Windows console is cp1252; the check lines print Turkish labels.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    dd = ddload.DD()
    charts = [
        chart_vario_daily(),
        chart_vario_gates(),
        chart_share_bar(),
        chart_readout_shot(),
        chart_t1_size(dd),
        chart_t1_t2(dd),
        chart_comovement_gap(),
        chart_hop(),
        chart_subday(),
        chart_coincidence(),
    ]
    section = {
        "section": "kok-soru",
        "title_tr": TITLE,
        "intro_tr": INTRO,
        "bullets_tr": BULLETS,
        "charts": charts,
    }
    text = json.dumps(section, ensure_ascii=False, indent=1) + "\n"
    if "—" in text:
        raise SystemExit("em dash in the section text")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(text.encode('utf-8')):,} bytes, {len(charts)} charts)")


if __name__ == "__main__":
    main()
