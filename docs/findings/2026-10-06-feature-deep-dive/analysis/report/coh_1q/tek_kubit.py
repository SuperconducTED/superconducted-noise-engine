"""Report section ``tek-kubit``: the findings of ``04-single-qubit-gates.md`` in Turkish.

Writes ``results/report/tek-kubit.json`` (format: ``analysis/report/spec_check.py``).

Figures come from ``results/gates_1q/*.json`` where a results file holds them. Series that
no results file holds (event histograms, per-qubit medians for the map and the scatters, the
coherence-limit ratios) are recomputed from the field cache with the owner's definitions,
imported from ``analysis/gates_1q/g1common.py`` and ``analysis/gates_1q/sx_coherence.py``;
every recomputed headline is checked against the figure the document states before anything
is written. Variograms are not charted here (another section owns them). Wording follows the
document's Verification section wherever it weakened a claim.
"""

# The section text is Turkish: the dotless i (U+0131) is intended, not a confusable.
# ruff: noqa: RUF001

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ddload

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gates_1q"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from typing import Any

import g1common as g
import numpy as np
import sx_coherence as sxc
from _common import check, fit_hist_x, load, log_hist, log_range, sig, write_section
from scipy import stats

SPLIT_MS = g.ms_of("2026-07-25T00:00:00Z")  # sx_profile.py: calendar midpoint of the record
SX_NS = 24.0
XSLOW_NS = 1000.0


def degrees(dd: ddload.DD) -> list[int]:
    adj: list[set[int]] = [set() for _ in range(156)]
    for a, b in dd.meta["coupling_map"]:
        adj[a].add(b)
        adj[b].add(a)
    return [len(x) for x in adj]


def chart_aliases(aliases: dict[str, Any]) -> dict[str, Any]:
    names = ["id", "rx", "x", "xslow"]
    a = aliases["aliases"]
    for n, want in zip(names, (979, 645, 374, 310), strict=True):
        check(f"{n} value mismatch", a[n]["value_mismatch"], 0, 0)
        check(f"{n} date mismatch", a[n]["date_mismatch"], want, 0)
        check(f"{n} outside placeholders", a[n]["date_mismatch_outside_placeholder_records"], 0, 0)
        check(f"{n} identical series", a[n]["series_identical_to_sx_after_masking"], 155, 0)
    check("compared x", a["x"]["compared"], 274560, 0)
    check("compared xslow", a["xslow"]["compared"], 136032, 0)
    for n in names:
        if a[n]["value_mismatch"] or a[n]["date_mismatch_outside_placeholder_records"]:
            raise ValueError(f"{n}: a mismatch the subtitle calls zero is not zero")
    return {
        "id": "tk-takma-ad",
        "type": "bar",
        "orient": "h",
        "title": "`x`, `id`, `rx` ve `xslow` her kayıtta `sx` ile aynı değeri bildiriyor",
        "subtitle": (
            "Her takma adın `sx` ile karşılaştırılan kayıtlarında değer ve tarih uyuşmazlıkları; "
            "`id`, `rx`, `x` için 274.560, `xslow` için 136.032 kayıt. Değer uyuşmazlığı ve "
            "ölçülmüş kayıtta tarih uyuşmazlığı her takma adda 0 olduğu için çizilmedi"
        ),
        "read": (
            "Değer uyuşmazlığı hiçbirinde yok. Çubuklar tarih uyuşmazlıklarını sayıyor (979, 645, "
            "374, 310); hepsi `q17`, `q72` ve `q149`'un yer tutucu kayıtlarında (bu kayıtlar "
            "`sx` için toplam 1.975, `xslow` için 915; uyuşmazlık bunların bir kısmında) ve "
            "fark daima "
            "tam 1 saniye; ölçülmüş kayıtlarda uyuşmazlık 0. Yer tutucular maskelenince her "
            "takma adın 155 serisi `sx`'inkiyle özdeş: kübit başına tek bir tek-kübit hata serisi "
            "var."
        ),
        "caveat": (
            "IBM `sx`, `id` ve `x` hatalarının eşit varsayıldığını belgeliyor; `rx` ve `xslow` "
            "eşitliği yalnız arşivde gözlenen bir olgu. Doğrulayıcı `xslow` için \"`sx`'ten "
            'kopyalanmış" sözünü zayıflattı: veri iki alanın her kayıtta eşit olduğunu '
            "gösteriyor, bir kopyalama mekanizmasını değil."
        ),
        "source": "04 §0, §1, §6 ve Doğrulama; results/gates_1q/aliases_and_schema.json (aliases)",
        "x": {"label": "Kayıt sayısı", "scale": "linear"},
        "y": {"label": "Takma ad", "scale": "band"},
        "categories": names,
        "series": [
            {
                "name": "Tarih uyuşmazlığı, yer tutucu kayıtta",
                "values": [a[n]["date_mismatch_in_placeholder_records"] for n in names],
            },
        ],
    }


def xslow_windows(dd: ddload.DD) -> list[tuple[float, float]]:
    """sx_coherence.xslow_floor's presence windows: runs of files carrying xslow records."""
    xv = np.array(dd.v("g1.xslow.gate_error"))
    pres = np.isfinite(xv).any(axis=1)
    fm = dd.file_ms[pres]
    idx = np.flatnonzero(pres)
    br = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate([[0], br + 1])
    ends = np.concatenate([br, [idx.size - 1]])
    return [(float(fm[a]), float(fm[b])) for a, b in zip(starts, ends, strict=True)]


def chart_xslow(dd: ddload.DD, rows: list[dict[str, Any]]) -> dict[str, Any]:
    windows = xslow_windows(dd)
    full, t1_only = [], []
    for r in rows:
        inside = np.zeros(r["t"].size, dtype=bool)
        for a, b in windows:
            inside |= (r["t"] >= a) & (r["t"] <= b)
        full.append((sxc.coh_limit(r["T1"], r["T2"], XSLOW_NS) / r["e"])[inside])
        t1_only.append((sxc.coh_limit(r["T1"], 2.0 * r["T1"], XSLOW_NS) / r["e"])[inside])
    fa, ta = np.concatenate(full), np.concatenate(t1_only)
    check("xslow events", fa.size, 6033, 0)
    check("xslow share above", float(np.mean(fa > 1.0)), 0.9967, 0.00005)
    check("xslow median", float(np.median(fa)), 17.2, 0.05)
    check("xslow T1-only share", float(np.mean(ta > 1.0)), 0.9927, 0.00005)
    check("xslow T1-only median", float(np.median(ta)), 8.9, 0.05)
    lo, hi = log_range(np.concatenate([fa, ta]))
    return {
        "id": "tk-xslow",
        "type": "hist",
        "title": "1.000 ns'lik `xslow`'un bildirdiği hata, kendi koherans sınırının çok altında",
        "subtitle": (
            "`xslow` kayıtlarının bulunduğu iki dönemde (2026-05-14 ile 05-29 ve 2026-09-10'dan "
            "sonra) eşli 6.033 olay: 1.000 ns için koherans sınırının bildirilen hataya oranı, "
            "log10 ekseninde 0,05 dekadlık kutular"
        ),
        "read": (
            "Tam sınırla olayların %99,67'sinde oran 1'in üstünde (medyan 17,2 kat); `T2 = 2 T1` "
            "alınıp saf faz kaybı sıfırlansa bile %99,27 (medyan 8,9 kat). 1.000 ns'lik bir "
            "talimat, 24 ns'lik `sx` ile aynı hatayı bildiriyor; bu hata, o süre boyunca yalnız "
            "boşta beklemenin yaratacağı bozunmadan da küçük."
        ),
        "caveat": (
            "Eşitlik 136.032 kaydın hepsinde yeniden üretildi; bir kopyalama mekanizması "
            "gösterilmedi, veri yalnız eşitliği gösteriyor (04 Doğrulama). Sınır formülü "
            "`T2`'nin düşük olduğu yerde vekildir, ama yalnız `T1` varyantı (%99,27) bundan "
            "etkilenmez. `xslow`'un ne için olduğunu hiçbir kaynak söylemiyor."
        ),
        "source": (
            "04 §0, §1 ve Doğrulama; results/gates_1q/sx_coherence.json (xslow_coherence_floor); "
            "oranlar önbellekten sx_coherence.py tanımlarıyla"
        ),
        "x": {"label": "Koherans sınırı / bildirilen hata", "scale": "log"},
        "y": {"label": "Olay sayısı", "scale": "linear"},
        "markers": [{"axis": "x", "value": 1, "label": "oran = 1"}],
        "series": [
            {"name": "Tam sınır (T1 ve T2)", **log_hist(fa, lo, hi)},
            {"name": "Yalnız T1 (T2 = 2 T1)", **log_hist(ta, lo, hi)},
        ],
    }


def chart_sx_distribution(series: list[Any]) -> dict[str, Any]:
    y = np.concatenate([s.y for s in series])
    check("sx events", y.size, 20207, 0)
    check("sx median", float(np.median(y)), 3.10e-4, 0.5e-6)
    check("sx 1%", float(np.quantile(y, 0.01)), 1.42e-4, 0.5e-6)
    check("sx 99%", float(np.quantile(y, 0.99)), 2.54e-3, 0.5e-5)
    check("share above 1e-3", float(np.mean(y > 1e-3)), 0.0488, 0.00005)
    check("count above 1e-2", int(np.sum(y > 1e-2)), 7, 0)
    lo, hi = log_range(y)
    return {
        "id": "tk-sx-dagilim",
        "type": "hist",
        "title": "`sx` hatası 3e-4 çevresinde toplanıyor, üst kuyruk 1e-2'yi geçiyor",
        "subtitle": (
            "Olay başına `sx` hatası (yer tutucular olaylar kurulmadan maskelendi; 155 kübit, "
            "20.207 olay), log10 ekseninde 0,05 dekadlık kutular"
        ),
        "read": (
            "Medyan 3,10e-4; yüzde 1'lik dilim 1,42e-4, yüzde 99'luk dilim 2,54e-3, en büyük "
            "olay 1,71e-2 (`q149`). Olayların %4,88'i 1e-3'ün, 7'si 1e-2'nin üstünde. log "
            "varyansın 0,744'ü kübitler arasında: kuyruğun bir kısmı kötü kübitlerden, bir kısmı "
            "kübit içi sıçramalardan geliyor (sonraki grafik)."
        ),
        "source": "04 §0, §2; results/gates_1q/sx_profile.json (distribution)",
        "x": {"label": "sx hatası", "scale": "log"},
        "y": {"label": "Olay sayısı", "scale": "linear"},
        "markers": [
            {"axis": "x", "value": 3.0952e-4, "label": "medyan 3,10e-4"},
            {"axis": "x", "value": 2.5414e-3, "label": "yüzde 99: 2,54e-3"},
        ],
        "series": [{"name": "sx olayı", **log_hist(y, lo, hi)}],
    }


def chart_tail(
    series: list[Any], profile: dict[str, Any], temporal: dict[str, Any]
) -> dict[str, Any]:
    r = np.concatenate([np.log10(s.y) - g.running_level(np.log10(s.y)) for s in series])
    r = r[np.isfinite(r)]
    check("residual events", r.size, 20207, 0)
    check("share above +log2", float(np.mean(r > g.LOG10_2)), 0.01945, 0.000005)
    check("share below -log2", float(np.mean(r < -g.LOG10_2)), 0.00277, 0.000005)
    check("share above half decade", float(np.mean(r > 0.5)), 0.00564, 0.000005)
    check("share below half decade", float(np.mean(r < -0.5)), 0.0, 0.0)
    ref = profile["changes"]["residual_from_running_level"]
    check("Bowley skew", ref["bowley_skew"], 0.047, 0.0005)
    sp = temporal["spikes"]
    check("single-event spike episodes", sp["share_of_episodes_single_event"], 0.937, 0.0005)
    step = 0.05
    lo = np.floor(r.min() / step) * step
    hi = np.ceil(r.max() / step) * step
    edges = lo + step * np.arange(round((hi - lo) / step) + 1)
    counts, _ = np.histogram(r, bins=edges)
    centres = 0.5 * (edges[:-1] + edges[1:])
    return {
        "id": "tk-kuyruk",
        "type": "line",
        "title": "Kübit içinde `sx` sapmaları yukarı doğru tek taraflı",
        "subtitle": (
            "Her olayın kayan seviyesinden log10 sapması (her yandan en çok 5 olayın medyanı, "
            "olayın kendisi hariç); 0,05 dekadlık kutularda olay sayısı, log ekseni; 20.207 olay"
        ),
        "read": (
            "Gövde simetrik (Bowley çarpıklığı 0,047), kuyruklar değil: olayların %1,95'i "
            "seviyenin 2 katından fazla üstünde, %0,28'i 2 katından fazla altında; yarım dekadın "
            "üstünde %0,56, altında hiç olay yok. 366 sıçrama epizodunun %93,7'si tek olay: "
            "sıçrama bir sonraki ölçümde, yaklaşık bir gün sonra, geçmiş oluyor."
        ),
        "caveat": (
            "Tek taraflı sapmalar hatayı kötüleştiren ayrık olaylara (örneğin rezonansa giren bir "
            "kusur) uyar; ara sıra yukarı yönde başarısız olan bir RB fiti de aynı deseni üretir. "
            "Bu bir ipucu, karar değil (04 §4). Sıçramaların turlarda kümelenmesi tespit "
            'edilmedi (dağılım indeksi 1,16, p = 0,10); doğrulayıcıya göre bu "kümelenmiyor" '
            'değil, "kümelenme tespit edilmedi" demek.'
        ),
        "source": (
            "04 §0, §3, §4 ve Doğrulama; results/gates_1q/sx_profile.json "
            "(changes.residual_from_running_level), sx_temporal.json (spikes)"
        ),
        "x": {"label": "Kayan seviyeden sapma", "scale": "linear", "unit": "dekad"},
        "y": {"label": "Olay sayısı", "scale": "log"},
        "markers": [
            {"axis": "x", "value": -g.LOG10_2, "label": "2 kat altı"},
            {"axis": "x", "value": g.LOG10_2, "label": "2 kat üstü"},
        ],
        "series": [
            {
                "name": "Olay sayısı",
                "style": "line+dots",
                "points": [
                    [round(float(c), 3), int(n) if n > 0 else None]
                    for c, n in zip(centres, counts, strict=True)
                ],
            }
        ],
    }


def chart_stability(series: list[Any]) -> dict[str, Any]:
    pts, f, s2 = [], [], []
    for s in series:
        z = np.log10(s.y)
        a, b = z[s.t_ms < SPLIT_MS], z[s.t_ms >= SPLIT_MS]
        if a.size >= 5 and b.size >= 5:
            f.append(float(np.median(a)))
            s2.append(float(np.median(b)))
            pts.append([sig(10 ** f[-1]), sig(10 ** s2[-1]), f"q{s.entity}"])
    fa, sa = np.array(f), np.array(s2)
    check("halves qubits", fa.size, 155, 0)
    check("halves spearman", float(stats.spearmanr(fa, sa).statistic), 0.972, 0.0005)
    terc_f = np.digitize(fa, np.quantile(fa, [1 / 3, 2 / 3]))
    terc_s = np.digitize(sa, np.quantile(sa, [1 / 3, 2 / 3]))
    check("same tercile", float(np.mean(terc_f == terc_s)), 0.858, 0.0005)
    check("median shift", float(np.median(np.abs(fa - sa))), 0.017, 0.0005)
    return {
        "id": "tk-kararlilik",
        "type": "scatter",
        "title": "Kübitlerin `sx` seviyeleri beş ay boyunca yerinde duruyor",
        "subtitle": (
            "Kübit başına `sx` hata medyanı: 2026-07-25'ten önceki olaylar (x) ve sonraki olaylar "
            "(y), log eksenler; her yarıda en az 5 olay, 155 kübit"
        ),
        "read": (
            "Noktalar köşegene yapışık: sıra korelasyonu 0,972, kübitlerin %85,8'i aynı üçte "
            "birlik dilimde kalıyor, medyan kayma 0,017 dekad. Kübit seviyeleri 1,54e-4 (`q131`) "
            "ile 5,31e-3 (`q27`) arasında, 34,5 kat."
        ),
        "caveat": (
            "Seviye sabit olsa da her olay seviyenin etrafında büyük ve hafızasız bir bileşen "
            "taşıyor (değişimlerin lag-1 otokorelasyonu -0,49; robust büyüklük 0,086 dekad, "
            "yaklaşık 1,22 kat). 11 kübitte anlamlı seviye değişimi var (blok permütasyon, BH "
            "0,05); en büyüğü `q102`'de +0,64 dekad (2026-07-19)."
        ),
        "source": (
            "04 §2, §3, §4 ve Doğrulama; results/gates_1q/sx_profile.json (stability), "
            "sx_temporal.json (entity_changepoints)"
        ),
        "x": {"label": "Medyan, ilk yarı", "scale": "log"},
        "y": {"label": "Medyan, ikinci yarı", "scale": "log"},
        "diag": True,
        "series": [{"name": "Kübit", "points": pts}],
    }


def chart_ratio(rows: list[dict[str, Any]], coh: dict[str, Any]) -> dict[str, Any]:
    ratio = np.concatenate([r["ec"] / r["e"] for r in rows])
    check("matched events", ratio.size, 18301, 0)
    check("ratio median", float(np.median(ratio)), 0.402, 0.0005)
    check("ratio 10%", float(np.quantile(ratio, 0.1)), 0.178, 0.0005)
    check("ratio 90%", float(np.quantile(ratio, 0.9)), 0.992, 0.0005)
    check("share above 1", float(np.mean(ratio > 1.0)), 0.0982, 0.00005)
    check("qubits median above 1", len(coh["ratio"]["qubits_with_median_ratio_gt_1"]), 13, 0)
    lo, hi = log_range(ratio)
    return {
        "id": "tk-koherans-orani",
        "type": "hist",
        "title": "Koherans sınırı, bildirilen `sx` hatasının medyanda beşte ikisi",
        "subtitle": (
            "Eşli 18.301 olay (`T1` ve `T2` olayı `sx` damgasından en çok 6 saat uzakta): 24 "
            "ns'lik koherans sınırının bildirilen hataya oranı, log10 ekseninde 0,05 dekadlık "
            "kutular"
        ),
        "read": (
            "Medyan 0,402 (yüzde 10'luk dilim 0,178, yüzde 90'lık dilim 0,992); olayların "
            "%9,82'sinde oran 1'in üstünde. Medyanda bildirilen hatanın beşte ikisi 24 ns'lik "
            "boşta beklemenin bozunmasına karşılık geliyor; kalanı bu bozunma değil. Sınırın "
            "medyan %29'u `T1` teriminden geliyor, kalanı `T2` teriminden."
        ),
        "caveat": (
            "Medyan oranı 1'in üstünde olan 13 kübitin hepsinde `T2` düşük (5,2 ile 35,6 µs; "
            "eşli olaylarda cihaz medyanı 94,5 µs). Formül üstel faz kaybını varsayar; düşük bir "
            "yankı `T2`'si yavaş gürültüden geliyorsa 24 ns'de biriken faz kaybı çok daha "
            "küçüktür. Sınır bir alt sınır değil bir vekildir, en zayıf olduğu yer de `T2`'nin "
            "kötü olduğu yer."
        ),
        "source": (
            "04 §7; results/gates_1q/sx_coherence.json (ratio, matching); oranlar önbellekten "
            "sx_coherence.py tanımlarıyla"
        ),
        "x": {"label": "Koherans sınırı / bildirilen sx hatası", "scale": "log"},
        "y": {"label": "Olay sayısı", "scale": "linear"},
        "markers": [
            {"axis": "x", "value": 0.4018, "label": "medyan 0,40"},
            {"axis": "x", "value": 1, "label": "oran = 1"},
        ],
        "series": [{"name": "Eşli olay", **log_hist(ratio, lo, hi)}],
    }


def chart_sx_vs_t1(
    rows: list[dict[str, Any]], deg: list[int], coh: dict[str, Any]
) -> dict[str, Any]:
    med = {
        int(r["q"]): (float(np.median(np.log10(r["T1"]))), float(np.median(np.log10(r["e"]))))
        for r in rows
    }
    qs = sorted(med)
    x = np.array([med[q][0] for q in qs])
    y = np.array([med[q][1] for q in qs])
    check("between qubits", len(qs), 155, 0)
    check("spearman sx T1", float(stats.spearmanr(x, y).statistic), -0.434, 0.0005)
    b = coh["between_qubits"]
    check("CI lo", b["spearman_median_log_sx_vs_T1"]["ci95"][0], -0.558, 0.0005)
    check("CI hi", b["spearman_median_log_sx_vs_T1"]["ci95"][1], -0.291, 0.0005)
    check("coh limit rho", b["spearman_median_log_sx_vs_coh_limit"]["rho"], 0.199, 0.0005)
    check("T2 rho", b["spearman_median_log_sx_vs_T2"]["rho"], -0.161, 0.0005)
    series = []
    for d in (1, 2, 3):
        pts = [[sig(10 ** med[q][0]), sig(10 ** med[q][1]), f"q{q}"] for q in qs if deg[q] == d]
        series.append({"name": f"Derece {d} ({len(pts)} kübit)", "points": pts})
    return {
        "id": "tk-sx-t1",
        "type": "scatter",
        "title": "Kübitler arasında `T1`'i kısa olanın `sx` hatası yüksek",
        "subtitle": (
            "Kübit başına eşli olayların medyanı: `T1` (µs, x) ve `sx` hatası (y), log eksenler; "
            "renk kübitin bağlantı derecesi; 155 kübit"
        ),
        "read": (
            "Spearman -0,434 (%95 güven aralığı -0,558 ile -0,291; 2.000 bootstrap). Aynı "
            "kübitlerde koherans sınırıyla yalnız 0,199 (0,022 ile 0,355), `T2` ile -0,161 "
            "(-0,315 ile 0,016): `sx`, sınırı belirleyen `T2`'den çok `T1`'i izliyor."
        ),
        "caveat": (
            "Bu kübitler arası bir ilişki, nedensellik göstermez. Derece sınıfları `sx` ve `T1` "
            "üzerinde aynı yönde ayrışıyor (sonraki grafik); ortak bir kübit özelliği ikisini "
            "birlikte belirliyor olabilir."
        ),
        "source": (
            "04 §7 (between qubits); results/gates_1q/sx_coherence.json (between_qubits); "
            "kübit medyanları önbellekten sx_coherence.py eşleştirmesiyle"
        ),
        "x": {"label": "Medyan T1", "scale": "log", "unit": "µs"},
        "y": {"label": "Medyan sx hatası", "scale": "log"},
        "series": series,
    }


def chart_degree(sx_spatial: dict[str, Any], spatial: dict[str, Any]) -> dict[str, Any]:
    t = sx_spatial["tests"]
    sx_med = [t["level_by_degree_median"][k]["median"] for k in ("1", "2", "3")]
    sx_n = [t["level_by_degree_median"][k]["n"] for k in ("1", "2", "3")]
    t1_med = [10**v for v in spatial["per_qubit_stats"]["T1"]["median_by_degree_1_2_3"]]
    check("sx degree p", t["level_by_degree_kruskal"]["p"], 0.003, 0.00005)
    check("sx degree 3 median", sx_med[2], 2.69e-4, 0.5e-6)
    check("sx degree 2 median", sx_med[1], 3.22e-4, 0.5e-6)
    check("T1 degree 1 median", t1_med[0], 132.0, 0.5)
    check("T1 degree 2 median", t1_med[1], 125.0, 0.5)
    check("T1 degree 3 median", t1_med[2], 142.0, 0.5)
    check("T1 degree p (02)", spatial["per_qubit_stats"]["T1"]["kruskal_degree_p"], 0.0028, 0.00005)
    check("sx n by degree", sum(sx_n), 155, 0)
    sx_pct = [100.0 * (v / sx_med[1] - 1.0) for v in sx_med]
    t1_pct = [100.0 * (v / t1_med[1] - 1.0) for v in t1_med]
    check("sx degree 3 percent", sx_pct[2], -16.6, 0.05)
    check("T1 degree 3 percent", t1_pct[2], 13.2, 0.05)
    return {
        "id": "tk-derece",
        "type": "bar",
        "title": "3. dereceli kübitlerde `sx` hatası %17 düşük, `T1` %13 uzun",
        "subtitle": (
            "Kübit medyanlarının derece sınıfı içindeki medyanı, 2. derece sınıfına göre fark (%); "
            "`sx` için 8, 99, 48 kübit, `T1` için 8, 100, 48 kübit (1. derece yalnız 8 kübit)"
        ),
        "read": (
            "`sx`: 3,28e-4, 3,22e-4, 2,69e-4 (derece 1, 2, 3; Kruskal-Wallis p = 0,003, 10 "
            "testlik Bonferroni eşiği 0,005'in altında; yalnız uzun sıralarda 3. ile 2. derece "
            "p = 0,013). `T1`: 132, 125, 142 µs; doğrulayıcı bu deseni p = 0,0037 ile buldu, 02 "
            "§5 aynı testte p = 0,0028 veriyor."
        ),
        "caveat": (
            "Nedeni gösterilmedi. 48 üçüncü derece kübitin hepsi uzun sıralarda, 28 bağlayıcı sıra "
            "kübitinin hepsi 2. derecede; derece ile sıra tipi örtüşüyor. `sx` kübitler arasında "
            "`T1`'i izlediği için etki `T1` üzerinden geçiyor olabilir; bu bir ipucu, bulgu "
            "değil (04 Doğrulama). `T1` derece testi 02'nin 36 testlik Bonferroni eşiğini "
            "geçmiyor."
        ),
        "source": (
            "04 §5 ve Doğrulama; 02 §5; results/gates_1q/sx_spatial.json "
            "(tests.level_by_degree_*); results/coherence/spatial.json (per_qubit_stats.T1)"
        ),
        "x": {"label": "Bağlantı derecesi", "scale": "band"},
        "y": {"label": "Derece 2'ye göre fark", "scale": "linear", "unit": "%"},
        "categories": ["Derece 1", "Derece 2 (referans)", "Derece 3"],
        "series": [
            {"name": "sx hatası", "values": [round(v, 1) for v in sx_pct]},
            {"name": "T1", "values": [round(v, 1) for v in t1_pct]},
        ],
    }


def chart_map(series: list[Any], deg: list[int], sx_spatial: dict[str, Any]) -> dict[str, Any]:
    level = {s.entity: float(np.median(np.log10(s.y))) for s in series}
    check("qubits with a level", len(level), 155, 0)
    for d, key in ((1, "1"), (2, "2"), (3, "3")):
        got = 10 ** float(np.median([v for q, v in level.items() if deg[q] == d]))
        want = sx_spatial["tests"]["level_by_degree_median"][key]["median"]
        check(f"degree {d} median of levels", got, want, 0.5e-7)
    check("Moran I", sx_spatial["tests"]["morans_i_level"]["I"], -0.049, 0.0005)
    check("Moran p", sx_spatial["tests"]["morans_i_level"]["p_two_sided_perm"], 0.56, 0.005)
    worst = max(level, key=lambda q: level[q])
    check("worst qubit", worst, 27, 0)
    nodes: dict[str, float | None] = {str(q): sig(10 ** level[q]) for q in sorted(level)}
    nodes["72"] = None
    return {
        "id": "tk-sx-harita",
        "type": "map",
        "title": "Kübit medyanı `sx` hatasında mekânsal yapı saptanmadı; en kötü kübitler dağınık",
        "subtitle": (
            "Her kübitin `sx` olaylarının medyanı, heavy-hex yerleşiminde, log renk ölçeği; 155 "
            "kübit (`q72` her dosyada yer tutucu)"
        ),
        "read": (
            "Moran's I -0,049 (p = 0,56). En kötüler `q27` 5,31e-3, `q11` 1,99e-3, `q0` 1,93e-3, "
            "`q149` 1,38e-3, `q24` 1,30e-3; çipin farklı yerlerinde. `q72`'nin komşuları sıradan: "
            "`q71` 155 kübit içinde 110., `q73` 71."
        ),
        "caveat": (
            "RB tüm kübitlerde eşzamanlı koşulduğu halde bağlı kübitlerin sıçramaları aynı turda "
            "şanstan sık görülmüyor (174 çiftte 9 ortak tur, beklenen 8,92). Bu bölümün Moran "
            "testlerini doğrulayıcı yeniden üretmedi; mekânsal testlerden yalnız derece testi "
            "yeniden üretildi."
        ),
        "source": (
            "04 §5; results/gates_1q/sx_spatial.json (tests, worst_qubits, q72_neighbours); "
            "kübit medyanları önbellekten"
        ),
        "scale": "seqlog",
        "node_label": "medyan sx hatası",
        "node_values": nodes,
        "node_flags": {"72": "yer"},
        "flags": {"yer": "her dosyada yer tutucu (gate_error = 1)"},
    }


def chart_spikes(coh: dict[str, Any]) -> dict[str, Any]:
    c = coh["coincidence"]
    check("spikes", c["spikes"], 324, 0)
    check("T1 1.5 observed", c["T1"]["factor_1.5"]["p_dip_given_spike"], 0.167, 0.0005)
    check(
        "T1 1.5 null mean",
        c["T1"]["factor_1.5"]["null_shifted_p_dip_given_spike_mean"],
        0.109,
        0.0005,
    )
    check(
        "T1 1.5 null max",
        c["T1"]["factor_1.5"]["null_shifted_p_dip_given_spike_max"],
        0.140,
        0.0005,
    )
    check("excess median", c["excess_accounted_by_coh_limit"]["q"][2], 0.005, 0.0003)
    keys = (("T1", "factor_1.5"), ("T1", "factor_2"), ("T2", "factor_1.5"), ("T2", "factor_2"))
    return {
        "id": "tk-sicrama-dip",
        "type": "bar",
        "title": "`sx` sıçramalarında `T1` dipi şanstan sık görülüyor, `T2` dipi değil",
        "subtitle": (
            "Eşli 18.301 olaydaki 324 `sx` sıçramasında (kayan seviyenin 2 katından fazla üstü) "
            "aynı turda `T1` ya da `T2` dipi görülme oranı; kaydırılmış eşleştirmede (36 "
            "kaydırma) ortalama ve en büyük oran"
        ),
        "read": (
            "`T1`'in 1,5 kat dipi sıçramaların %16,7'sinde (324'te 54); kaydırılmış eşleştirmede "
            "ortalama %10,9, en çok %14,0. 2 kat eşiğinde de gözlenen oran 36 kaydırmanın "
            "hepsini aşıyor; `T2` için kaydırmaların aralığında kalıyor. Koherans sınırı bir "
            "sıçramanın fazla hatasının yalnız medyan %0,5'ini açıklıyor (`T1` dipli 54 "
            "sıçramada %13,6)."
        ),
        "caveat": (
            "324 sıçramanın 270'inde `T1` dipi yok. Sıçrama yapan kübitler genel olarak daha çok "
            "`T1` dipi gösteriyor (iki oran arasında Spearman 0,23), bu yüzden doğru karşılaştırma "
            "kaydırılmış eşleştirme. İkisini birlikte hareket ettiren şey bilinmiyor: aynı "
            "turdaki `sx` ile `T1` sapmaları arasındaki zayıf bağ (-0,062) deneyler arasında "
            "paylaşılan bir parça; zaman ölçeği ve fiziksel mi yöntemsel mi olduğu belirlenmedi "
            "(04 Doğrulama)."
        ),
        "source": "04 §0, §7 ve Doğrulama; results/gates_1q/sx_coherence.json (coincidence)",
        "x": {"label": "Dip tanımı", "scale": "band"},
        "y": {"label": "Sıçramada dip oranı", "scale": "linear"},
        "categories": ["T1, 1,5 kat altı", "T1, 2 kat altı", "T2, 1,5 kat altı", "T2, 2 kat altı"],
        "series": [
            {
                "name": "Sıçramada gözlenen",
                "values": [c[f][k]["p_dip_given_spike"] for f, k in keys],
            },
            {
                "name": "Kaydırılmış, ortalama",
                "values": [c[f][k]["null_shifted_p_dip_given_spike_mean"] for f, k in keys],
            },
            {
                "name": "Kaydırılmış, en büyük",
                "values": [c[f][k]["null_shifted_p_dip_given_spike_max"] for f, k in keys],
            },
        ],
    }


def main() -> int:
    dd = ddload.DD()
    aliases = load("gates_1q/aliases_and_schema.json")
    profile = load("gates_1q/sx_profile.json")
    temporal = load("gates_1q/sx_temporal.json")
    coh = load("gates_1q/sx_coherence.json")
    sx_spatial = load("gates_1q/sx_spatial.json")
    spatial = load("coherence/spatial.json")
    series = ddload.series(dd, g.SX_FIELD, rule=ddload.MEASURED, mask=ddload.placeholder_error)
    built = sxc.build(dd, SX_NS)
    rows = built["rows"]
    check("unmatched sx events", built["n_unmatched"], 1906, 0)
    deg = degrees(dd)
    charts = [
        chart_aliases(aliases),
        chart_xslow(dd, rows),
        chart_sx_distribution(series),
        chart_tail(series, profile, temporal),
        chart_stability(series),
        chart_ratio(rows, coh),
        chart_sx_vs_t1(rows, deg, coh),
        chart_degree(sx_spatial, spatial),
        chart_map(series, deg, sx_spatial),
        chart_spikes(coh),
    ]
    charts = [fit_hist_x(c) for c in charts]
    section = {
        "section": "tek-kubit",
        "toc_tr": "Tek-kübit kapıları",
        "title_tr": "Tek-kübit kapıları: `sx`, takma adları, `xslow` ve `rz`",
        "intro_tr": [
            (
                "`sx` hatası, belgelerde tek kübitli bir üniter kapının ölçülen tek hatası: IBM "
                "onu tüm kübitlerde eşzamanlı randomized benchmarking (RB) ile türetiyor. `x`, "
                "`id`, `rx` ve `xslow` her kayıtta aynı değeri bildiriyor, dolayısıyla kübit "
                "başına tek bir tek-kübit hata serisi var. `rz` sabit (hata 0, süre 0): McKay ve "
                "diğerlerinin (2017) sanal Z kapısı."
            ),
            (
                "Kübit seviyeleri 34,5 kat aralığa yayılıyor ve aylar boyunca yerinde duruyor. "
                "Seviyenin etrafında olaydan olaya hafızasız bir bileşen var: değişimlerin lag-1 "
                "otokorelasyonu -0,49, lag-2 -0,003. Bu bileşenin robust büyüklüğü 0,086 dekad, "
                "yaklaşık 1,22 kat (04 Doğrulama); gövdesi simetrik, kuyruğu yukarı yönde tek "
                "taraflı."
            ),
            (
                "Kübitler arasında `sx`, `T1`'i koherans sınırından daha iyi izliyor. Aynı turda "
                "`sx` sapması `T1` sapmasıyla zayıf ama kaydırılmış eşleştirmelerin aralığı "
                "dışında kalan bir korelasyon gösteriyor (-0,062; damgalar 1 saat içindeyse "
                "-0,096). Bu, iki "
                "deney arasında paylaşılan bir parça; doğrulayıcıya göre zaman ölçeği ve fiziksel "
                "mi yoksa ortak bir SPAM ya da hazırlık kayması mı olduğu belirlenmedi. "
                "Bileşenin büyük kısmının ne olduğu bilinmiyor; ona tahmin gürültüsü denmiyor."
            ),
        ],
        "bullets_tr": [
            (
                "**Bir ölçüm, beş ad.** `x`, `id`, `rx` 274.560 kaydın, `xslow` 136.032 kaydın "
                "hiçbirinde `sx`'ten farklı değer taşımıyor. 979, 645, 374 ve 310 tarih "
                "uyuşmazlığının hepsi `q17`, `q72` ve `q149`'un yer tutucu kayıtlarında ve fark "
                "tam 1 saniye."
            ),
            (
                "**`xslow`'un çelişkisi.** 1.000 ns'lik bir talimat 24 ns'lik `sx` ile aynı hatayı "
                "bildiriyor. 1.000 ns'nin koherans sınırı bildirilen hatayı 6.033 eşli olayın "
                "%99,67'sinde aşıyor (medyan 17,2 kat; saf faz kaybı olmadan da %99,27, 8,9 kat). "
                "Eşitlik kesin; bir kopyalama mekanizması gösterilmedi."
            ),
            (
                "**Dağılım ve kuyruk.** Olay başına medyan 3,10e-4 (yüzde 1: 1,42e-4; yüzde 99: "
                "2,54e-3; 20.207 olay); %4,88'i 1e-3'ün üstünde. Kayan seviyenin 2 katından fazla "
                "üstünde %1,95, altında %0,28: kuyruk tek taraflı."
            ),
            (
                "**Kararlı seviyeler.** Kayıt ikiye bölündüğünde kübit medyanlarının sıra "
                "korelasyonu 0,972 (155 kübit); kübitlerin %85,8'i aynı üçte birlik dilimde "
                "kalıyor. Cihaz geneli kayma (30 günde 0,0008 dekad) ve saat ya da gün etkisi "
                "(Kruskal-Wallis p 0,73 ve 0,50) yok."
            ),
            (
                "**Koherans sınırı bir vekil.** 24 ns'lik sınır bildirilen hatanın medyanda "
                "0,40'ı (yüzde 10: 0,18; yüzde 90: 0,99; 18.301 eşli olay); %9,8'inde 1'in "
                "üstünde ve bunlar düşük `T2`'li kübitlerde toplanıyor."
            ),
            (
                "**Kübitler arasında `sx` `T1`'i izliyor.** Kübit medyanlarında log `sx` ile log "
                "`T1` arasında Spearman -0,434 (%95 güven aralığı -0,558 ile -0,291); koherans "
                "sınırıyla 0,199, `T2` ile -0,161."
            ),
            (
                "**Derece etkisi.** 3. dereceli kübitlerde medyan `sx` 2,69e-4, 2. derecede "
                "3,22e-4 (p = 0,003). Doğrulayıcıya göre `T1` aynı deseni gösteriyor (132, 125, "
                "142 µs; p = 0,0037); etki `T1` üzerinden geçiyor olabilir, bu bir ipucu."
            ),
            (
                "**Sıçramalar ve `T1` dipleri.** `sx` sıçramalarının %16,7'sinde `T1` seviyesinin "
                "1,5 kat altında; kaydırılmış eşleştirmede ortalama %10,9, en çok %14,0. Koherans "
                "sınırı bir sıçramanın fazla hatasının yalnız medyan %0,5'ini açıklıyor."
            ),
        ],
        "charts": charts,
    }
    path = write_section("tek-kubit", section)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
