"""Assemble the Turkish advisor report page from the section specs and the page template.

Reads ``results/report/<section>.json`` (written by the section scripts in this folder) in the
order of ``page_tr.json``, adds the page header and the closing sections from ``page_tr.json``
(root questions, unknowns, verification status, data rules), adds the device layout from the
cache, and writes one self-contained HTML file. The Turkish text lives in ``page_tr.json`` so
this file stays ASCII; every closing-section figure there is quoted from ``00-overview.md``
(its verification-status table, section 4 and section 6).

Usage: ``python build_page.py --out <file.html>``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ddload

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "results" / "report"


def verification_section(v: dict[str, Any]) -> dict[str, Any]:
    """The verification band: its table and two charts, built from ``page_tr.json`` rows."""
    rows = v["rows"]
    words = v["verdict_words"]
    cats = [r[0] for r in rows]
    stack = dict(v["chart_verdicts"])
    stack["categories"] = cats
    stack["series"] = [
        {"name": name, "values": [r[4 + k] for r in rows]}
        for k, name in enumerate(v["verdict_names"])
    ]
    bars = dict(v["chart_numbers"])
    bars["categories"] = cats
    bars["series"] = [{"name": v["table_head"][2], "values": [r[3] for r in rows]}]
    return {
        "section": v["section"],
        "toc_tr": v["toc_tr"],
        "title_tr": v["title_tr"],
        "intro_tr": v["intro_tr"],
        "table_tr": {
            "head": v["table_head"],
            "rows": [
                [r[1], r[2], str(r[3]), ", ".join(f"{r[4 + k]} {w}" for k, w in enumerate(words))]
                for r in rows
            ],
        },
        "charts": [stack, bars],
        "blocks_tr": v["blocks_tr"],
    }


def layout() -> dict[str, Any]:
    """Heavy-hex coordinates, couplers and qubit degrees from the cache's configuration."""
    dd = ddload.DD()
    coords = next(iter(dd.meta["config_values"]["coords"].values()))["value"]
    couplers = [list(c) for c in dd.meta["couplers"]]
    degree = [0] * len(coords)
    for a, b in couplers:
        degree[a] += 1
        degree[b] += 1
    return {"coords": coords, "couplers": couplers, "degree": degree}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--standalone",
        action="store_true",
        help="wrap the page in its own html/head/body so it opens directly in a browser",
    )
    ap.add_argument(
        "--theme",
        choices=("auto", "light", "dark"),
        default="auto",
        help="with --standalone: pin a theme (light for print and PDF)",
    )
    args = ap.parse_args(argv)
    text = json.loads((HERE / "page_tr.json").read_text(encoding="utf-8"))
    sections: list[dict[str, Any]] = []
    missing = []
    for sid, toc in text["order"]:
        path = REPORT / f"{sid}.json"
        if not path.exists():
            missing.append(sid)
            continue
        sec = json.loads(path.read_text(encoding="utf-8"))
        sec["toc_tr"] = toc
        sections.append(sec)
    sections += [text["questions"], verification_section(text["verification"])]
    data = {"page": text["page"], "layout": layout(), "sections": sections}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = (HERE / "template.html").read_text(encoding="utf-8").replace("__REPORT_DATA__", blob)
    if "—" in html:
        raise SystemExit("em dash in the assembled page")
    if args.standalone:
        theme = "" if args.theme == "auto" else f' data-theme="{args.theme}"'
        html = (
            f'<!doctype html><html lang="tr"{theme}><head><meta charset="utf-8">'
            '<meta name="viewport" '
            'content="width=device-width, initial-scale=1, viewport-fit=cover">'
            "<style>:root{color-scheme:light}body{margin:0}img{max-width:100%}"
            "[hidden]{display:none!important}</style></head><body>" + html + "</body></html>\n"
        )
    args.out.write_text(html, encoding="utf-8", newline="\n")
    n_charts = sum(len(s.get("charts", [])) for s in sections)
    print(f"wrote {args.out}: {len(sections)} sections, {n_charts} charts, {len(html):,} bytes")
    if missing:
        print("missing sections: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
