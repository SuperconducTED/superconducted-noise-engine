# Feature deep-dive report page, 2026-10-06

The Turkish report page built on 2026-10-06 for Dr. Fırat Akba from the feature deep dive in
`docs/findings/2026-10-06-feature-deep-dive/`. It presents every finding of that folder in ten
sections and 88 charts. It was published as a private Claude artifact,
https://claude.ai/artifact/KKmUx6dQNNxjs9rr7GWqWQ, version 2 (`1791315923-0147`); a private
artifact opens only for people its owner has shared it with. This folder is the dated record of
that version.

| File | What |
| --- | --- |
| `ibm-fez-ozellik-incelemesi.html` | The published page wrapped in the minimal skeleton the artifact host adds (doctype, charset, viewport). It is interactive (hover details, a table view under every chart) and needs the network for d3 7.9.0 from cdnjs and for Google Fonts. It follows the viewer's light or dark theme. |

Every figure on the page is provisional: measured on the lead's laptop at `calibration-data`
`7b84b506ef77beb6e6c1b25a7357c574cfaf5117` (1,760 `ibm_fez` files), not registered in
`docs/numerical-claims.md`, and to be re-run on the verification desktop. The page records no
decision: A1 to A9 and the plan's §9 questions remain open.

## Where each part comes from

| Part | Source |
| --- | --- |
| Header, tiles, closing sections (root questions, unknowns, verification status, data rules) | `docs/findings/2026-10-06-feature-deep-dive/analysis/report/page_tr.json`, every figure quoted from `00-overview.md` |
| Sections 1 to 8 (text and chart data) | `docs/findings/2026-10-06-feature-deep-dive/results/report/*.json`, written by the scripts in `analysis/report/<section folder>/` from the scope results JSON and, where a chart needs a series no results file holds, from the field cache |
| Page and charts | `analysis/report/template.html` (d3 renderer), assembled by `analysis/report/build_page.py` |

The section texts use the corrected readings of the scope documents' verification sections
(for example, the same-round `T1`/`T2` correlation of 0.70 as a part shared between the two
fits, not as a demonstrated change of the qubit). A verifier checked about 170 figures on the
page against the documents and found no wrong number; two visual review passes covered every
chart. All of that verification ran on the same laptop.

## Rebuilding the page and the PDF

The field cache must exist first (`docs/findings/2026-10-06-feature-deep-dive/01-data-layer.md`
§1). From the repository root:

```bash
python docs/findings/2026-10-06-feature-deep-dive/analysis/report/build_page.py --standalone --out docs/advisor/2026-10-06-feature-deep-dive-report/ibm-fez-ozellik-incelemesi.html
```

A PDF is not committed. To print one (98 A4 pages on 2026-10-06), build a light-theme copy and
print it with headless Chrome; the window width is the printable A4 width, so the charts are
drawn at the printed size, and the page's print stylesheet keeps colours, keeps each chart card
on one page and starts each section on a new page:

```bash
python docs/findings/2026-10-06-feature-deep-dive/analysis/report/build_page.py --standalone --theme light --out print.html
chrome --headless=new --disable-gpu --no-pdf-header-footer --window-size=718,1000 --virtual-time-budget=25000 --print-to-pdf=out.pdf file:///<absolute path>/print.html
```
