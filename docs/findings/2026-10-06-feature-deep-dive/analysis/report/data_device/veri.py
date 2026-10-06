# ruff: noqa: RUF001
"""Report section ``veri``: what the archive is, which fields carry information, and coverage.

Sources: ``01-data-layer.md`` (every field, identities, lengths, file structure),
``00-overview.md`` sections 1, 2 and 5 (feature map, data rules, corrections) and
``06-device-time-topology.md`` section 2 (documents, stamps, configuration as dated events).

Numbers come from ``results/data-layer/profile.json``, ``results/data-layer/identities.json``,
``results/device/documents.json`` and ``results/device/layer_fidelity.json``. Three series no
results file holds are computed from the field cache through ``ddload`` with the owner's
definitions: files per UTC day (live against historical, ``has_configuration``), and the
presence intervals of the gantt chart (first to last file carrying a field or value, in file
order). The script asserts that every recomputed figure that also appears in a results file or
document agrees with it, and prints the checks.

The sub-split of the 19 non-informative dictionary rows (copies, constants, changing
configuration lengths, empty) is this script's classification of the rows of 01 section 3,
using the identities of 01 section 5; the 12 / 2 / 19 split itself is 00 section 1.

Writes ``results/report/veri.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common as cm
import ddload

SECTION = "veri"

# The 33 rows of the data dictionary (01 section 3), by status. The first two groups are
# 00 section 1; the split of the remaining 19 is this script's, from 01 sections 3 and 5.
DICTIONARY: dict[str, list[str]] = {
    "informative": [
        "q.T1",
        "q.T2",
        "q.readout_error",
        "q.prob_meas0_prep1",
        "q.prob_meas1_prep0",
        "q.init_error",
        "g1.sx.gate_error",
        "g1.measure_2.gate_error",
        "g2.cz.gate_error",
        "g2.rzz.gate_error",
        "gen.zz",
        "gen.lf",
    ],
    "setting": ["g1.measure.threshold", "g1.measure_2.threshold"],
    "copy": [
        "g1.x/id/rx.*",
        "g1.xslow.gate_error",
        "g1.measure.gate_error",
        "g1.measure.gate_length",
        "g1.measure_reset.threshold",
        "g1.measure_reset_2.threshold",
        "g1.measure_reset.gate_length",
        "g1.measure_reset_2.gate_length",
    ],
    "constant": [
        "g1.sx.gate_length",
        "g1.xslow.gate_length",
        "g1.rz.gate_error",
        "g1.rz.gate_length",
        "g1.measure_2.gate_length",
        "g1.reset_2.gate_length",
    ],
    "length": [
        "q.readout_length",
        "g1.reset.gate_length",
        "g2.cz.gate_length",
        "g2.rzz.gate_length",
    ],
    "empty": ["gen.jq"],
}

# Informative fields in cadence order, with their chart labels.
CADENCE = (
    ("q.readout_error", "readout_error"),
    ("q.prob_meas0_prep1", "prob_meas0_prep1"),
    ("q.prob_meas1_prep0", "prob_meas1_prep0"),
    ("q.init_error", "init_error"),
    ("gen.zz", "zz"),
    ("q.T1", "T1"),
    ("q.T2", "T2"),
    ("g1.sx.gate_error", "sx"),
    ("g1.measure_2.gate_error", "measure_2"),
    ("g2.cz.gate_error", "cz"),
    ("g2.rzz.gate_error", "rzz"),
    ("gen.lf", "lf"),
)

STAMP_FIELDS = (
    ("q.T1", "T1"),
    ("q.T2", "T2"),
    ("q.readout_error", "readout_error"),
    ("q.prob_meas0_prep1", "prob_meas0_prep1"),
    ("q.prob_meas1_prep0", "prob_meas1_prep0"),
    ("q.init_error", "init_error"),
    ("g1.sx.gate_error", "sx"),
    ("g1.measure_2.gate_error", "measure_2"),
    ("g2.cz.gate_error", "cz"),
    ("g2.rzz.gate_error", "rzz"),
    ("gen.lf", "lf"),
    ("gen.zz", "zz"),
    ("g1.measure.threshold", "measure.threshold"),
    ("g1.measure_2.threshold", "measure_2.threshold"),
    ("g1.measure.gate_length", "measure uzunluğu"),
    ("g1.rz.gate_error", "rz hatası"),
    ("gen.jq", "jq"),
)


def stem_iso(stem: str) -> str:
    """``20260618T183429000000Z.json`` to ``2026-06-18T18:34:29Z``."""
    return f"{stem[:4]}-{stem[4:6]}-{stem[6:8]}T{stem[9:11]}:{stem[11:13]}:{stem[13:15]}Z"


def runs(dd: ddload.DD, mask: np.ndarray) -> list[list[str]]:
    """Consecutive runs of files where ``mask`` holds, as [first file time, last file time]."""
    out: list[list[str]] = []
    fms = dd.file_ms
    i, n = 0, mask.size
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            out.append([cm.iso(fms[i]), cm.iso(fms[j])])
            i = j + 1
        else:
            i += 1
    return out


def check(label: str, got: Any, want: Any) -> None:
    ok = got == want
    print(f"{'ok  ' if ok else 'DIFF'} {label}: recomputed {got!r}, document {want!r}")
    if not ok:
        raise SystemExit(f"recomputed figure disagrees with the document: {label}")


def chart_dictionary() -> dict[str, Any]:
    d = DICTIONARY
    n = {k: len(v) for k, v in d.items()}
    check("dictionary rows", sum(n.values()), 33)
    check("informative / setting / rest", (n["informative"], n["setting"]), (12, 2))
    cats = [
        "Bilgi taşıyan ölçüm",
        "Ayırıcı eşik ayarı",
        "Kopya (başka satırla aynı değer)",
        "Sabit (tek değer)",
        "Değişen konfigürasyon uzunluğu",
        "Boş (hep 0)",
    ]
    vals = [n["informative"], n["setting"], n["copy"], n["constant"], n["length"], n["empty"]]
    return {
        "id": "veri-sozluk",
        "type": "bar",
        "orient": "h",
        "title": "Sözlüğün 33 satırından yalnızca 12'si kopya olmayan ölçüm taşıyor",
        "subtitle": (
            "Veri sözlüğünün (01 §3) satırları, duruma göre; satır sayısı. Kalan 19 satırın "
            "alt ayrımı bu raporun 01 §3 ve §5'ten yaptığı sınıflama."
        ),
        "read": (
            f"12 bilgi taşıyan alan: `T1`, `T2`, `readout_error`, `prob_meas0_prep1`, "
            f"`prob_meas1_prep0`, `init_error`, `sx`, `measure_2`, `cz`, `rzz`, `zz`, `lf`. "
            f"İki eşik (`measure.threshold`, `measure_2.threshold`) bir ayırıcı ayarı kaydediyor. "
            f"{n['copy']} satır başka bir satırla aynı değeri taşıyor (örneğin `x`, `id`, `rx` "
            f"ve `xslow` hataları `sx` ile, `measure` hatası `readout_error` ile), "
            f"{n['constant']} satır sabit, {n['length']} satır cihaz geneli değişen bir uzunluk; "
            f"`jq` her belgede 0."
        ),
        "source": "00 §1, §2; 01 §3, §5; results/data-layer/profile.json, identities.json",
        "x": {"label": "satır sayısı", "scale": "linear"},
        "y": {"label": "", "scale": "band"},
        "categories": cats,
        "series": [{"name": "satır", "values": vals}],
    }


def chart_gap(profile: dict[str, Any]) -> dict[str, Any]:
    f = profile["fields"]
    cats = [lab for _, lab in CADENCE]
    med = [cm.r4(f[k]["event_gap_h_q"][3]) for k, _ in CADENCE]
    g = {lab: f[k]["event_gap_h_q"][3] for k, lab in CADENCE}
    g10 = {lab: f[k]["event_gap_h_q"][2] for k, lab in CADENCE}
    g90 = {lab: f[k]["event_gap_h_q"][4] for k, lab in CADENCE}
    return {
        "id": "veri-kadans-aralik",
        "type": "bar",
        "orient": "h",
        "title": "Bilgi taşıyan aileler iki kadansta: yaklaşık 4,5 saat ve yaklaşık 25 saat",
        "subtitle": (
            "Varlık başına ardışık iki yeniden ölçüm olayı arasındaki sürenin medyanı, saat; her "
            "alanın bütün varlıklarının bütün olayları birlikte"
        ),
        "read": (
            f"Readout ailesi (`readout_error` {tr_h(g['readout_error'])}, `init_error` "
            f"{tr_h(g['init_error'])}) ve `zz` ({tr_h(g['zz'])}) gün içinde birkaç kez "
            f"yenileniyor; `T1` ({tr_h(g['T1'])}), `sx` ({tr_h(g['sx'])}), `cz` "
            f"({tr_h(g['cz'])}), `rzz` ({tr_h(g['rzz'])}) ve `measure_2` "
            f"({tr_h(g['measure_2'])}) günde bir kez; `lf` kendi {cm.tr(g['lf'], 1)} saatlik "
            f"döngüsünde. Aralıklar geniş: `readout_error` için %10 ile %90 dilimleri "
            f"{tr_h(g10['readout_error'])} ile {tr_h(g90['readout_error'])}, `T1` için "
            f"{tr_h(g10['T1'])} ile {tr_h(g90['T1'])}; bunlara yeniden başlatmalar ve kaçan "
            "belgeler de giriyor."
        ),
        "caveat": (
            "`zz` belge oluşturulurken damgalanıyor; olayı yalnızca değer değişimi, süresi bir "
            "belge zamanı farkı (01 §4). Ağustos başına kadar kaçan belgeler olayları gizliyor, "
            "bu yüzden hızlı ailelerin görünen kadansı döneme bağlı (01 §6, 06 §3.4)."
        ),
        "source": "01 §3; 00 §2; results/data-layer/profile.json (event_gap_h_q)",
        "x": {"label": "olaylar arası süre, medyan", "unit": "saat", "scale": "linear"},
        "y": {"label": "", "scale": "band"},
        "categories": cats,
        "series": [{"name": "medyan", "values": med}],
    }


def tr_h(hours: float) -> str:
    return f"{cm.tr(hours, 1)} saat"


def chart_events(profile: dict[str, Any]) -> dict[str, Any]:
    f = profile["fields"]
    cats = [lab for _, lab in CADENCE]
    med = [f[k]["events_per_entity_q"][3] for k, _ in CADENCE]
    e = {lab: f[k]["events_per_entity_q"][3] for k, lab in CADENCE}
    daily = [e[k] for k in ("T1", "T2", "sx", "cz", "rzz")]
    return {
        "id": "veri-kadans-olay",
        "type": "bar",
        "orient": "h",
        "title": "Bir kübitin readout'u yaklaşık 580 kez, `T1`'i yaklaşık 130 kez yeniden ölçülmüş",
        "subtitle": (
            "Varlık başına yeniden ölçüm olayı sayısı, medyan; 1.760 belgenin tamamı, her alan "
            "kendi ömrü içinde (`init_error` 4 Ağustos'tan, `measure_2` 7 Ağustos'tan itibaren)"
        ),
        "read": (
            f"`readout_error` {cm.tr(int(e['readout_error']))}, `zz` {cm.tr(int(e['zz']))}, "
            f"`init_error` {cm.tr(int(e['init_error']))} (yalnızca 2 ay), `T1` "
            f"{cm.tr(int(e['T1']))}, `sx` {cm.tr(int(e['sx']))}, `cz` {cm.tr(int(e['cz']))}, "
            f"`rzz` {cm.tr(int(e['rzz']))}, `lf` {cm.tr(int(e['lf']))}, `measure_2` "
            f"{cm.tr(int(e['measure_2']))} (yalnızca 2 ay). Günlük ailelerde (`T1`, `T2`, `sx`, "
            f"`cz`, `rzz`) bir varlık 145 günde {cm.tr(int(min(daily)))} ile "
            f"{cm.tr(int(max(daily)))} kez yeniden ölçülmüş."
        ),
        "caveat": (
            "Sayılar ömre bağlı: `init_error` ve `measure_2` arşive Ağustos'ta katıldı. "
            "Ölçülmüş kuralda aynı değeri veren tekrar ölçümler olay sayılmıyor (00 §5 madde 2)."
        ),
        "source": "01 §3; 00 §2; results/data-layer/profile.json (events_per_entity_q)",
        "x": {"label": "varlık başına olay, medyan", "scale": "linear"},
        "y": {"label": "", "scale": "band"},
        "categories": cats,
        "series": [{"name": "olay", "values": med}],
    }


def chart_gantt(dd: ddload.DD, docs: dict[str, Any], lfj: dict[str, Any]) -> dict[str, Any]:
    fms = dd.file_ms
    end = cm.iso(fms[-1])
    start = cm.iso(fms[0])

    def present(field: str) -> np.ndarray:
        out: np.ndarray = np.isfinite(np.array(dd.v(field))).any(axis=1)
        return out

    thr = runs(dd, present("g1.measure.threshold"))
    init = runs(dd, present("q.init_error"))
    m2 = runs(dd, present("g1.measure_2.gate_error"))
    mres = runs(dd, present("g1.measure_reset.threshold"))
    xslow = runs(dd, present("g1.xslow.gate_error"))
    check("measure.threshold start", thr[0][0], "2026-06-08T18:56:28Z")
    check("init_error start", init[0][0], "2026-08-04T00:52:30Z")
    check("measure_2 start", m2[0][0], "2026-08-07T03:21:59Z")
    check("measure_reset start", mres[0][0], "2026-09-02T04:56:24Z")
    check("xslow runs", len(xslow), 2)
    check("xslow first start", xslow[0][0], "2026-05-14T12:32:42Z")
    check("xslow return", xslow[1][0], "2026-09-10T16:56:21Z")
    rl = np.array(dd.v("q.readout_length"))
    rl_runs = {v: runs(dd, np.all(rl == v, axis=1)) for v in (1560.0, 1700.0, 1660.0)}
    check("readout_length 1700 from", rl_runs[1700.0][0][0], "2026-06-08T18:56:28Z")
    check("readout_length 1660 from", rl_runs[1660.0][0][0], "2026-07-30T21:09:17Z")
    cols = [
        k for k, (a, b) in enumerate(dd.meta["directed_edges"]) if (a, b) in ((71, 72), (72, 73))
    ]
    cl = np.array(dd.v("g2.cz.gate_length"))[:, cols]
    q72 = {v: runs(dd, np.all(cl == v, axis=1)) for v in (68.0, 84.0)}
    check("q72 couplers 84 ns from", q72[84.0][0][0], "2026-09-05T17:51:36Z")
    live = dd.file("has_configuration").astype(bool)
    hist_idx = np.flatnonzero(~live)
    check("historical files", int(hist_idx.size), 443)
    tid = dd.file("target_ops_id")
    tsets = []
    for t in dd.meta["target_sets"]:
        idx = np.flatnonzero(tid == t["id"])
        tsets.append((t["n_ops"], cm.iso(fms[idx[0]]), cm.iso(fms[idx[-1]]), int(idx.size)))
    check("target-set file counts", [x[3] for x in tsets], [702, 241, 53, 764])
    mc = np.flatnonzero(dd.file("config.mcps") >= 0)
    check("mcps first live file", cm.iso(fms[mc[0]]), "2026-07-16T03:00:13Z")
    gaps = [
        [stem_iso(g["after"]), stem_iso(g["before"])] for g in docs["cadence"]["gaps_above_12h"]
    ]
    check("file gaps above 12 h", len(gaps), 14)
    ledger = dd.meta["ledger"]
    lf_first_in = lfj["cadence"]["first_event_inside_archive"]
    rows = [
        {"label": "Arşiv belgeleri (1.760)", "spans": [[start, end]], "group": "arşiv"},
        {"label": "12 saati aşan dosya boşlukları", "spans": gaps, "group": "arşiv"},
        {
            "label": "Tarihsel getirmeler (443)",
            "spans": [[cm.iso(fms[hist_idx[0]]), cm.iso(fms[hist_idx[-1]])]],
            "group": "arşiv",
        },
        {
            "label": "Yoklama defteri (ledger)",
            "spans": [[ledger[0]["poll_time_utc"], ledger[-1]["poll_time_utc"]]],
            "group": "arşiv",
        },
        {"label": "measure.threshold", "spans": thr, "group": "şema"},
        {"label": "init_error", "spans": init, "group": "şema"},
        {"label": "measure_2", "spans": m2, "group": "şema"},
        {"label": "measure_reset, reset_2", "spans": mres, "group": "şema"},
        {"label": "xslow (iki dönem)", "spans": xslow, "group": "şema"},
        {
            "label": "lf: arşiv öncesi değer taşınıyor",
            "spans": [[start, lf_first_in]],
            "group": "şema",
        },
        {"label": "lf: arşiv içi olaylar", "spans": [[lf_first_in, end]], "group": "şema"},
        {"label": "readout_length 1.560 ns", "spans": rl_runs[1560.0], "group": "uzunluk ve hedef"},
        {"label": "readout_length 1.700 ns", "spans": rl_runs[1700.0], "group": "uzunluk ve hedef"},
        {"label": "readout_length 1.660 ns", "spans": rl_runs[1660.0], "group": "uzunluk ve hedef"},
        {"label": "q72 kuplörleri 68 ns", "spans": q72[68.0], "group": "uzunluk ve hedef"},
        {"label": "q72 kuplörleri 84 ns", "spans": q72[84.0], "group": "uzunluk ve hedef"},
    ]
    for n_ops, a, b, _ in tsets:
        rows.append(
            {
                "label": f"hedef kümesi, {cm.tr(n_ops)} işlem",
                "spans": [[a, b]],
                "group": "uzunluk ve hedef",
            }
        )
    rows.append(
        {
            "label": "mcps anahtarı",
            "spans": [[cm.iso(fms[mc[0]]), end]],
            "group": "uzunluk ve hedef",
        }
    )
    return {
        "id": "veri-omur",
        "type": "gantt",
        "title": "Birçok alan arşive sonradan katıldı; bu başlangıçlar eksik veri değil",
        "subtitle": (
            "Her satır, bir alanın ya da değerin taşındığı ilk ve son belge arası (belge "
            "sırasıyla, `last_update_date`); 13 Mayıs ile 6 Ekim 2026 arası 1.760 belge"
        ),
        "read": (
            "`measure.threshold` 8 Haziran'da, `init_error` 4 Ağustos'ta, `measure_2` 7 "
            "Ağustos'ta, `measure_reset` ve `reset_2` 2 Eylül'de ortaya çıkıyor; `xslow` 14 ile 29 "
            "Mayıs arasında ve 10 Eylül'den sonra var. `readout_length` 8 Haziran'da 1.560'tan "
            "1.700 ns'ye, 30 Temmuz'da 1.660 ns'ye geçiyor; ilk geçiş `measure.threshold`'un "
            "ilk belgesiyle aynı. Tek kuplör uzunluğu değişimi `q72`'nin iki kuplöründe (5 "
            "Eylül, 68'den 84 ns'ye). 14 dosya boşluğu 12 saati aşıyor, en uzunu 82,7 saat."
        ),
        "caveat": (
            "Hedef kümelerinden son ikisi 9 ile 10 Eylül'de çakışıyor: 2.224 işlemli kümeyi "
            "taşıyan "
            "tarihsel belgeler canlı belgelerden 1,5 güne kadar önce geliyor, yani tarihsel bir "
            "belgenin hedefi gün çözünürlüğünde tarihlenmiş sayılamaz (06 §6.2 madde 5)."
        ),
        "source": (
            "01 §3, §5, §6; 06 §2.1, §2.3; 00 §5 madde 8; results/device/documents.json, "
            "layer_fidelity.json; aralıklar önbellekten (ddload)"
        ),
        "x": {"label": "tarih", "scale": "time"},
        "rows": rows,
    }


def chart_month(docs: dict[str, Any]) -> dict[str, Any]:
    bm = docs["cadence"]["by_month"]
    months = sorted(bm)
    check("files by month", [bm[m]["files"] for m in months], [171, 194, 270, 304, 683, 138])
    cats = [cm.MONTHS_TR[m[5:7]] for m in months]
    cats[-1] = cats[-1] + " (5 gün)"
    fpd = {m: bm[m]["files_per_day"] for m in months}
    return {
        "id": "veri-kapsam-ay",
        "type": "stack",
        "title": "Eylül'de belge sayısı iki katını aştı; Eylül belgelerinin yarısı tarihsel",
        "subtitle": "Ay başına arşivlenen belge sayısı, canlı (`configuration` dolu) ve tarihsel",
        "read": (
            f"Günde {cm.tr(fpd[months[0]], 2)} belge (Mayıs), {cm.tr(fpd['2026-06'], 2)} "
            f"(Haziran), {cm.tr(fpd['2026-09'], 2)} (Eylül), {cm.tr(fpd['2026-10'], 2)} (Ekim'in "
            "ilk 5 günü). İlk tarihsel belge 5 Ağustos 2026; tarihsel belgeler Ağustos'ta 29, "
            "Eylül'de 349, Ekim'de 65. Mayıs yalnızca 18,5 gün kapsıyor."
        ),
        "source": "06 §2.1; 01 §6; results/device/documents.json (cadence.by_month)",
        "x": {"label": "ay", "scale": "band"},
        "y": {"label": "belge", "scale": "linear"},
        "categories": cats,
        "series": [
            {"name": "canlı", "values": [bm[m]["live"] for m in months]},
            {"name": "tarihsel", "values": [bm[m]["historical"] for m in months]},
        ],
    }


def chart_daily(dd: ddload.DD) -> dict[str, Any]:
    fms = dd.file_ms
    live = dd.file("has_configuration").astype(bool)
    day = np.floor(fms / 8.64e7).astype(np.int64)
    days = np.arange(day.min(), day.max() + 1)
    n_live = np.array([int(np.sum((day == k) & live)) for k in days])
    n_hist = np.array([int(np.sum((day == k) & ~live)) for k in days])
    check("files counted per day", int(n_live.sum() + n_hist.sum()), 1760)
    check("live files", int(n_live.sum()), 1317)
    empty = int(np.sum((n_live + n_hist) == 0))
    labels = [cm.iso_day(k * 8.64e7) for k in days]
    return {
        "id": "veri-kapsam-gun",
        "type": "line",
        "wide": True,
        "title": (
            "Ağustos ortasına kadar günde birkaç belge ve boş günler; Eylül'den itibaren "
            "sürekli kapsam"
        ),
        "subtitle": (
            f"UTC günü başına arşivlenen belge sayısı, canlı ve tarihsel; {len(days)} gün "
            "(13 Mayıs ile 6 Ekim 2026)"
        ),
        "read": (
            f"{empty} günde hiç belge yok; en uzun boşluk 7 ile 10 Ağustos arası 82,7 saat. "
            "Tarihsel getirmeler 5 Ağustos'ta başlıyor ve Eylül'de canlı belgelerle aynı "
            "büyüklükte. Kapsam seyrekken iki belge arasında yayımlanan bir readout oturumu "
            "kaybolabiliyor; bu dönemlerin olay hızları alt sınır (05 §2.3, 06 §3.4)."
        ),
        "source": "06 §2.1; 00 §5 madde 7; günlük sayılar önbellekten (file.last_update_ms)",
        "x": {"label": "tarih", "scale": "time"},
        "y": {"label": "belge / gün", "scale": "linear", "min": 0},
        "markers": [
            {"axis": "x", "value": "2026-08-05T23:45:31Z", "label": "ilk tarihsel belge"},
            {"axis": "x", "value": "2026-09-02T16:49:30Z", "label": "yoklama defteri"},
        ],
        "series": [
            {
                "name": "canlı",
                "style": "line",
                "points": [[d, int(v)] for d, v in zip(labels, n_live, strict=True)],
            },
            {
                "name": "tarihsel",
                "style": "line",
                "points": [[d, int(v)] for d, v in zip(labels, n_hist, strict=True)],
            },
        ],
    }


def chart_identities(ident: dict[str, Any]) -> dict[str, Any]:
    c = ident["checks"]
    pairs = (
        ("sx_vs_id_error", "sx = id"),
        ("sx_vs_rx_error", "sx = rx"),
        ("sx_vs_x_error", "sx = x"),
        ("sx_vs_xslow_error", "sx = xslow"),
        ("readout_error_vs_measure_error", "readout_error = measure"),
        ("cz_gate_error_direction", "cz [a,b] = [b,a]"),
        ("rzz_gate_error_direction", "rzz [a,b] = [b,a]"),
        ("readout_length_vs_measure_length_values", "uzunluk: readout = measure"),
        ("cz_vs_rzz_error_same_coupler", "cz ile rzz"),
    )
    cats = [lab for _, lab in pairs]
    same, date_only, value = [], [], []
    for k, _ in pairs:
        n, vm, dm = c[k]["compared"], c[k]["value_mismatch"], c[k]["date_mismatch"]
        # The three shares are exact only when value mismatches are absent or every date
        # differs; both hold for every pair here (identities.json), and anything else stops.
        if vm == 0:
            dvd = dm
        elif dm == n:
            dvd = n - vm
        else:
            raise SystemExit(f"{k}: joint value and date mismatches are not determined")
        same.append(cm.r4(100.0 * (n - vm - dvd) / n))
        date_only.append(cm.r4(100.0 * dvd / n))
        value.append(cm.r4(100.0 * vm / n))
    czr = c["cz_vs_rzz_error_same_coupler"]
    ml = c["readout_length_vs_measure_length_values"]
    ro = c["readout_is_mean_of_p01_p10"]
    return {
        "id": "veri-kopyalar",
        "type": "stack",
        "title": (
            "Takma adlar ve kuplör yönleri değerde hiç ayrışmıyor; `cz` ile `rzz` ayrı kalibrasyon"
        ),
        "subtitle": (
            "Kayıt kayıt karşılaştırma, 1.760 belgenin tamamı; her çiftte kayıtların payı, %: "
            "aynı değer ve tarih, aynı değer ama farklı tarih, farklı değer. Karşılaştırılan kayıt "
            "136.032 ile 619.520 arası"
        ),
        "read": (
            "İlk sekiz çiftte değeri farklı kayıt sayısı 0. `cz` ile `rzz` aynı yönlü kuplörde "
            f"{cm.tr(czr['compared'])} kaydın {cm.tr(czr['value_mismatch'])}'ünde "
            f"({cm.pct(czr['value_mismatch'] / czr['compared'])}) farklı: ayrı kalibrasyonlar. "
            "`measure` uzunluğu `readout_length` ile aynı değeri taşıyor ama tarihi kayıtların "
            f"{cm.pct(ml['date_mismatch'] / ml['compared'])}'sinde farklı, çünkü belge "
            "oluşturulurken damgalanıyor."
        ),
        "caveat": (
            "Takma adlarda ve yönlerde görülen tarih farklarının hepsi yer tutucu "
            "(`gate_error >= 1`) kayıtlarında; maskelendikten sonra seriler aynı, yani bir kopya "
            "ayrı bilgi değil (04 §0, 05 §1.3, 06 §6.2 madde 8; 01 §5'in \"olay sayıları farklı "
            'olabilir" ifadesini düzeltir). Değerlerin eşitliği bir kopyalama mekanizmasını '
            "göstermiyor (04 Doğrulama). `readout_error` = (`prob_meas0_prep1` + "
            f"`prob_meas1_prep0`) / 2 eşitliği aynı damgalı {cm.tr(ro['same_stamp_records'])} "
            f"kaydın hepsinde 1e-12 içinde tutuyor; bu, readout kayıtlarının "
            f"{cm.pct(ro['same_stamp_records'] / ro['records_total'])}'i (01 §5)."
        ),
        "source": "01 §5; 00 §3, §5; results/data-layer/identities.json",
        "x": {"label": "karşılaştırılan çift", "scale": "band"},
        "y": {"label": "kayıtların payı", "unit": "%", "scale": "linear", "min": 0, "max": 100},
        "categories": cats,
        "series": [
            {"name": "aynı değer ve tarih", "values": same},
            {"name": "aynı değer, farklı tarih", "values": date_only},
            {"name": "farklı değer", "values": value},
        ],
    }


def chart_stamps(profile: dict[str, Any], docs: dict[str, Any]) -> dict[str, Any]:
    f = profile["fields"]
    cats = [lab for _, lab in STAMP_FIELDS]
    vals = [cm.r4(100.0 * f[k]["date_equals_file_date_share"]) for k, _ in STAMP_FIELDS]
    measured = [f[k]["date_equals_file_date_share"] for k, _ in STAMP_FIELDS[:11]]
    ss = docs["stamp_semantics"]
    q = ss["last_update_minus_newest_measured_h_q"]
    return {
        "id": "veri-damga",
        "type": "bar",
        "orient": "h",
        "title": (
            "Ölçülmüş alanların tarihi bir yazım zamanı; eşik, `zz` ve sabitlerinki yalnızca "
            "belge zamanı"
        ),
        "subtitle": (
            "Kaydın tarihinin belgenin `last_update_date` değerine eşit olduğu kayıtların payı, "
            "%; her alanın tüm kayıtları"
        ),
        "read": (
            f"Ölçülmüş 11 alanda pay en çok {cm.pct(max(measured), 2)}; eşiklerde, `zz`'de, "
            "`rz`'de, `jq`'da ve `measure` uzunluğunda %100. İkinci gruptaki tarih belgenin "
            "oluşturulma anı, bilgi taşımıyor. `last_update_date` de bir ölçüm zamanı değil: "
            f"en yeni ölçüm damgasına belgelerin yalnızca "
            f"%{cm.tr(100 * ss['share_last_update_equals_newest_measured_stamp'], 1)}'inde eşit, "
            f"medyan {cm.tr(q[3], 2)} saat sonra (%90 dilimi {cm.tr(q[5], 2)} saat)."
        ),
        "caveat": (
            "Bu yüzden `zz` ve eşikler gün çözünürlüğünde okunmalı. `lf` damgası 217 belgede "
            "`last_update_date`'ten sonra, 60 denetlenebilir canlı belgenin 49'unda o belgeyi "
            "dosyalayan yoklamadan da sonra; `lf` saat ölçeğinde öteki alanlarla sıralanmamalı "
            "(06 §6.2 madde 1)."
        ),
        "source": (
            "01 §3; 06 §2.2, §6.2; results/data-layer/profile.json, results/device/documents.json"
        ),
        "x": {
            "label": "tarihi belge zamanına eşit kayıt",
            "unit": "%",
            "scale": "linear",
            "min": 0,
            "max": 100,
        },
        "y": {"label": "", "scale": "band"},
        "categories": cats,
        "series": [{"name": "pay", "values": vals}],
    }


def main() -> int:
    dd = ddload.DD()
    profile = cm.load("data-layer/profile.json")
    ident = cm.load("data-layer/identities.json")
    docs = cm.load("device/documents.json")
    lfj = cm.load("device/layer_fidelity.json")
    check("files", dd.n_files, 1760)
    live = dd.file("has_configuration").astype(bool)
    n_live, n_hist = int(live.sum()), int((~live).sum())
    ro = ident["checks"]["readout_is_mean_of_p01_p10"]
    charts = [
        chart_dictionary(),
        chart_gap(profile),
        chart_events(profile),
        chart_gantt(dd, docs, lfj),
        chart_month(docs),
        chart_daily(dd),
        chart_identities(ident),
        chart_stamps(profile, docs),
    ]
    payload = {
        "section": SECTION,
        "title_tr": "Veri: arşivde ne var, ne yok",
        "intro_tr": [
            (
                "Arşiv, IBM'in `ibm_fez` cihazı için yayımladığı kalibrasyon belgelerinin "
                "anlık görüntüleri: `calibration-data` dalının `7b84b50` ucunda "
                f"{cm.tr(dd.n_files)} "
                "belge, 13 Mayıs 2026 12:13 ile 6 Ekim 2026 02:57 (UTC) arası; 156 kübit, 176 "
                "kuplör ve 97 `lf_<N>` adı. Her belge bir kez okunup alan başına bir diziye "
                "çevrildi; bütün analizler bu önbellekten okuyor."
            ),
            (
                "Kökte arşiv bir ölçüm kaydı değil, IBM'in kalibrasyon takviminin örneklediği "
                "varlık başına zaman serileri. Her değer bir sayı ve en iyi durumda bir toplu "
                "yazım zamanı taşıyor; hiçbir değer belirsizlik taşımıyor (00 §1)."
            ),
            (
                "Sözlüğün 33 satırından 12'si kopya olmayan ölçülmüş değer, 2'si ayırıcı eşik "
                "ayarı; kalan 19'u kopya, sabit, konfigürasyon uzunluğu ya da boş. Bilgi taşıyan "
                "aileler iki kadansta yenileniyor: readout ve ilişkili alanlar yaklaşık 4,5 "
                "saatte, `zz` yaklaşık 5,2 saatte bir; koherans, kapılar ve `measure_2` yaklaşık "
                "25 saatte bir; `lf` 26,5 ile 26,6 saatte bir (belgeler olay tanımına göre iki "
                "değer veriyor)."
            ),
            (
                "Kapsam zamanla değişti. 5 Ağustos'a kadar yalnızca canlı yoklamalar var; iki "
                "yoklama arasında yayımlanıp bir sonraki yoklamadan önce yenisiyle değişen ara "
                "belgeler arşive girmedi. Sonra tarihsel getirmeler geliyor. Aylar arası olay hızı "
                "ya da kadans karşılaştırmaları dönemi kontrol etmeli (01 §6)."
            ),
        ],
        "bullets_tr": [
            (
                f"**{cm.tr(dd.n_files)} belge**: {cm.tr(n_live)} canlı yoklama (`configuration` "
                f"dolu) ve {cm.tr(n_hist)} tarihsel getirme (`configuration: null`); "
                "`backend_version` her belgede 1.3.37, dört hedef işlem kümesi (01 §6)."
            ),
            (
                "**12 bilgi taşıyan alan** (33 satırdan): `T1`, `T2`, `readout_error`, iki atama "
                "olasılığı, `init_error`, `sx`, `measure_2`, `cz`, `rzz`, `zz`, `lf` (00 §1, §2)."
            ),
            (
                "**Kopyalar ayrı bilgi değil**: `x`, `id`, `rx`, `xslow` hataları `sx` ile, "
                "`measure` hatası `readout_error` ile, kuplörün iki yönü birbiriyle aynı değeri "
                "taşıyor; karşılaştırılan 136.032 ile 309.760 kayıtta 0 değer farkı (01 §5)."
            ),
            (
                f"**Readout aritmetiği**: `readout_error` = (`prob_meas0_prep1` + "
                f"`prob_meas1_prep0`) / 2, aynı damgalı {cm.tr(ro['same_stamp_records'])} "
                "kaydın hepsinde; iki olasılık 549.120 değerin hepsinde 1/4.096'nın katı (01 §5)."
            ),
            (
                "**Tarih anlamı alana göre değişiyor**: ölçülmüş alanlarda kayıt tarihi bir toplu "
                "yazım zamanı; eşiklerde, `zz`'de, `rz`'de ve uzunluklarda yalnızca belge zamanı. "
                "`last_update_date` en yeni ölçüm damgasına belgelerin yalnızca %19,5'inde eşit "
                "(06 §2.2)."
            ),
            (
                "**Şema başlangıçları eksik veri değil**: `measure.threshold` 8 Haziran, "
                "`init_error` 4 Ağustos, `measure_2` 7 Ağustos, `measure_reset` ve `reset_2` 2 "
                "Eylül 2026; `xslow` iki ayrı dönemde (00 §5 madde 8)."
            ),
            (
                '**Yer tutucular** (`gate_error >= 1`, "kalibre edilmedi") olay oluşturulmadan '
                "önce maskeleniyor; her belgede yer tutucu olanlar `sx` için `q72`, `cz` için 4, "
                "`rzz` için 5 kuplör (01 §4, §5)."
            ),
            (
                "**Kapsam**: günde 9,25 belge (Mayıs) ile 22,77 (Eylül); 12 saati aşan 14 dosya "
                "boşluğu, en uzunu 82,7 saat; yoklama defteri 2 Eylül'den itibaren 1.981 satır "
                "(06 §2.1)."
            ),
        ],
        "charts": charts,
    }
    path = cm.write_section(SECTION, payload)
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
