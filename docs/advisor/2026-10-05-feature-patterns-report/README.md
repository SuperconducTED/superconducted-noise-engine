# Feature-pattern report page, 2026-10-05

The Turkish report page @mertefesensoy built on 2026-10-05 for Issue #110 (decision A9) and
showed to Dr. Fırat Akba at the meeting held that day (the lead's account; the meeting record
is the plan's as-of section "the meeting with Dr. Akba"). It was published as a private Claude
artifact, https://claude.ai/artifact/ELxiuQnPCLCenzEc3hN3GE, version 2
(`1791221881-079e`). This folder is the dated record of that version.

| File | What |
| --- | --- |
| `ibm-fez-kapi-hatalari.pdf` | 10 pages, printed 2026-10-05 from the HTML below with the print-only stylesheet in this README. The 820-row table is left collapsed, as on the page; its rows are in the HTML. |
| `ibm-fez-kapi-hatalari.html` | The published page wrapped in the minimal skeleton the artifact host adds (doctype, charset, viewport, light `color-scheme`). It is interactive (log or linear 0-1 scale, hover details, sortable table) and needs the network for d3 7.9.0 from cdnjs and for Google Fonts. |

## What the page holds and where each part comes from

| Section | Source |
| --- | --- |
| Anlık görüntü (snapshot chart, tiles, notes, table) | `snapshots/2026-10/ibm_fez/20261001T002643000000Z.json` on `calibration-data` at `a0d2e7d9839a95f3a70b96b7d68a69d45d7781d6`, blob `d74784d342e39125e7dddcb9aed6bbb340e183a9` |
| Özellik paternleri (P1 to P8) | `docs/evidence/feature-patterns/2026-10-05-09fcc45.json`, the `scripts/feature_patterns.py` report over all 1,753 `ibm_fez` files at `calibration-data` `09fcc45` |
| Literatür ve yöntem | `docs/roadmap/2026-10-05-feature-patterns-and-method.md` §3 and §4, and `docs/roadmap/2026-10-05-gate-error-literature-survey.md` |
| Protokol ve sonraki adımlar | the same feature-patterns document, §5 to §7 |

The tables and charts of the "Özellik paternleri" section are filled from that JSON when the
page loads, so they carry the same figures as the roadmap document. Every archive figure is
provisional until re-run on the verification desktop.

**The snapshot chart's de-duplication rules**, checked on that one file before they were
applied (the archive-wide checks are in the evidence README):

- 1,952 `gate_error` records collapse to 820 independent measurements;
- `sx`, `x`, `rx`, `id` and `xslow` carry the same value on all 156 qubits, so one point per
  qubit;
- `cz` and `rzz` list each coupler in both directions with the same value on all 176 couplers,
  so one point per coupler;
- `rz` is a virtual gate with error exactly 0 in all 156 records, which a log axis cannot show,
  so it is omitted;
- 25 records on 11 gates carry `gate_error = 1`, IBM's "not calibrated" placeholder; they are
  drawn apart as crosses, and their stamps (after the document's own `last_update_date`) are
  not treated as calibration times;
- `measure` equals `qubits[].readout_error` on all 156 qubits.

**State of the page when it was printed.** It describes the plan as it stood before the
meeting was recorded: its "M0" next step and its "A1-A9 stand as written" line are the
pre-meeting state. The meeting's direction, a deeper pass over the feature data before any
strategic decision, is recorded in the plan, not here.

## Regenerating the PDF

On Windows with Microsoft Edge, from this folder: save the stylesheet below into the page's
`<head>` as a copy named `print.html`, serve the folder with
`python -m http.server 8767 --bind 127.0.0.1`, and run

```bash
msedge --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header \
  --blink-settings=preferredColorScheme=1 --window-size=1240,1754 \
  --virtual-time-budget=8000 --print-to-pdf=out.pdf http://127.0.0.1:8767/print.html
```

The window size matches the page size so the charts, which measure their container when the
page loads, are drawn at the printed width. The stylesheet:

```html
<style>
@page { size: 1240px 1754px; margin: 16px; }
@media print {
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .toc, .hint, .tip, .ftip { display: none !important; }
  .scroller { overflow: visible !important; }
  .card, .pcard, .answer, .tile, .mt, .notes, details.tablebox, footer { break-inside: avoid; }
  #paternler, #yontem, #adimlar { break-before: page; }
  .wrap::before {
    content: "PDF kaydı: claude.ai artifact ELxiuQnPCLCenzEc3hN3GE, sürüm 1791221881-079e; 5 Ekim 2026'da basıldı. Ayrıntılar: docs/advisor/2026-10-05-feature-patterns-report/README.md";
    font: 12px "JetBrains Mono", ui-monospace, Consolas, monospace;
    color: var(--muted);
  }
}
</style>
```

A regenerated PDF will not be byte-identical (fonts are fetched at print time and PDF
metadata carries a timestamp); compare it page by page.
