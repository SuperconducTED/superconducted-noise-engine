"""Validate a section spec for the advisor report page built from this deep dive.

Each report section is one JSON file at ``results/report/<section>.json`` written by a script in
``analysis/report/<section>/``. The page renders it as-is, so the structure below is a contract.

Section object::

    {
      "section": "<id>",                 # kebab-case, unique
      "title_tr": "...",                 # Turkish section title
      "intro_tr": ["...", "..."],        # 1 to 4 short Turkish paragraphs
      "bullets_tr": ["...", ...],        # 0 to 8 Turkish key findings, each with its number
      "charts": [<chart>, ...]
    }

Chart object (common keys)::

    {
      "id": "<kebab-id>", "type": "<type>",
      "title": "...",          # Turkish, a statement of what the chart shows (short)
      "subtitle": "...",       # Turkish, what is plotted, with units and sample basis
      "read": "...",           # Turkish "how to read it", 1 to 3 sentences, with the key number
      "source": "...",         # document and section plus results file, e.g. "02 §4.2; regime.json"
      "caveat": "...",         # optional Turkish note, e.g. a verifier's weakening
      "x": {"label": "...", "scale": "linear|log|time|band", "unit": "...", "min": n, "max": n},
      "y": {"label": "...", "scale": "linear|log|band", "unit": "...", "min": n, "max": n},
      "markers": [{"axis": "x|y", "value": n or "ISO time", "label": "..."}]   # optional
    }

Types and their data keys:

- ``line``: ``series`` = [{"name", "points": [[x, y], ...], "style": "line|dots|line+dots",
  "band": [[x, lo, hi], ...] (optional)}]; x may be ISO time strings when x.scale is "time".
- ``scatter``: ``series`` = [{"name", "points": [[x, y] or [x, y, "label"], ...]}];
  optional ``diag`` (true draws y = x) and ``fit`` = [[x0, y0], [x1, y1]].
- ``bar``: ``categories`` = [str]; ``series`` = [{"name", "values": [n|null],
  "lo": [...], "hi": [...] (optional)}]; ``orient`` = "v" or "h".
- ``stack``: ``categories`` = [str]; ``series`` = [{"name", "values": [n]}] (stacked).
- ``hist``: ``series`` = [{"name", "edges": [n0..nk], "counts": [c1..ck]}].
- ``heatmap``: ``rows``, ``cols`` = [str]; ``values`` = [[n|null]] (rows x cols);
  ``scale`` = "seq" or "div"; ``domain`` = [lo, hi] (optional); ``fmt`` = d3 format string.
- ``forest``: ``rows`` = [{"label", "est", "lo", "hi", "group"}] (lo/hi optional);
  ``ref`` = number (optional reference line).
- ``map``: device map on the page's heavy-hex layout. ``node_values`` = {"<q>": n|null},
  ``edge_values`` = {"<a>-<b>": n|null} with a < b (optional), ``node_flags`` /
  ``edge_flags`` = {key: "<flag>"} (optional), ``flags`` = {"<flag>": "Turkish meaning"},
  ``scale`` = "seq", "seqlog" or "div", ``node_label`` and ``edge_label`` (value names).
- ``gantt``: time spans per row. ``rows`` = [{"label", "spans": [[ISO start, ISO end], ...],
  "group"}] (at most 40 rows, 200 spans each); x.scale is "time"; ``markers`` allowed.

Limits (keep the page light): at most 2,000 points per scatter series, 600 points per line
series, 60 categories per bar, 40 x 40 heatmap cells; the section file under 400 KB. No em
dash (U+2014) anywhere. Usage: ``python spec_check.py <section.json> [...]``.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

TYPES = {"line", "scatter", "bar", "stack", "hist", "heatmap", "forest", "map", "gantt"}
SCALES_X = {"linear", "log", "time", "band"}
SCALES_Y = {"linear", "log", "band"}
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?Z?)?$")


class SpecError(Exception):
    pass


def need(cond: bool, msg: str) -> None:
    if not cond:
        raise SpecError(msg)


def num(v: Any, where: str, allow_null: bool = False) -> None:
    if v is None and allow_null:
        return
    need(isinstance(v, (int, float)) and not isinstance(v, bool), f"{where}: not a number: {v!r}")
    need(math.isfinite(float(v)), f"{where}: not finite")


def xval(v: Any, scale: str, where: str) -> None:
    if scale == "time":
        need(isinstance(v, str) and bool(ISO.match(v)), f"{where}: time x must be ISO: {v!r}")
    elif scale == "band":
        need(isinstance(v, str), f"{where}: band x must be a string")
    else:
        num(v, where)


def check_chart(c: dict[str, Any], seen: set[str]) -> None:
    cid = c.get("id")
    need(
        isinstance(cid, str) and re.fullmatch(r"[a-z0-9-]+", cid or "") is not None,
        f"bad id {cid!r}",
    )
    need(cid not in seen, f"duplicate id {cid}")
    seen.add(cid)
    t = c.get("type")
    need(t in TYPES, f"{cid}: unknown type {t!r}")
    for k in ("title", "subtitle", "read", "source"):
        need(isinstance(c.get(k), str) and c[k].strip() != "", f"{cid}: missing {k}")
    x, y = c.get("x", {}), c.get("y", {})
    if t in ("line", "scatter", "hist"):
        need(x.get("scale") in SCALES_X and y.get("scale") in SCALES_Y, f"{cid}: x/y scale")
    if t == "line":
        need(len(c["series"]) >= 1, f"{cid}: no series")
        for s in c["series"]:
            need(len(s["points"]) <= 600, f"{cid}/{s['name']}: more than 600 points")
            for p in s["points"]:
                xval(p[0], x["scale"], f"{cid}/{s['name']}")
                num(p[1], f"{cid}/{s['name']}", allow_null=True)
            for b in s.get("band", []):
                xval(b[0], x["scale"], f"{cid} band")
                num(b[1], f"{cid} band")
                num(b[2], f"{cid} band")
    elif t == "scatter":
        for s in c["series"]:
            need(len(s["points"]) <= 2000, f"{cid}/{s['name']}: more than 2,000 points")
            for p in s["points"]:
                num(p[0], f"{cid} x")
                num(p[1], f"{cid} y")
    elif t in ("bar", "stack"):
        cats = c["categories"]
        need(0 < len(cats) <= 60, f"{cid}: categories")
        for s in c["series"]:
            need(len(s["values"]) == len(cats), f"{cid}/{s['name']}: length")
            for v in s["values"]:
                num(v, f"{cid}/{s['name']}", allow_null=(t == "bar"))
            for k in ("lo", "hi"):
                if k in s:
                    need(len(s[k]) == len(cats), f"{cid}/{s['name']}: {k} length")
    elif t == "hist":
        for s in c["series"]:
            need(len(s["edges"]) == len(s["counts"]) + 1, f"{cid}/{s['name']}: edges/counts")
    elif t == "heatmap":
        need(len(c["rows"]) <= 40 and len(c["cols"]) <= 40, f"{cid}: too many cells")
        need(len(c["values"]) == len(c["rows"]), f"{cid}: rows")
        for r in c["values"]:
            need(len(r) == len(c["cols"]), f"{cid}: cols")
            for v in r:
                num(v, f"{cid} cell", allow_null=True)
        need(c.get("scale") in ("seq", "div"), f"{cid}: scale")
    elif t == "forest":
        for r in c["rows"]:
            num(r["est"], f"{cid} est")
    elif t == "gantt":
        need(0 < len(c["rows"]) <= 40, f"{cid}: gantt rows")
        for r in c["rows"]:
            need(len(r["spans"]) <= 200, f"{cid}: too many spans")
            for a, b in r["spans"]:
                xval(a, "time", f"{cid} span")
                xval(b, "time", f"{cid} span")
    elif t == "map":
        need(c.get("scale") in ("seq", "seqlog", "div"), f"{cid}: scale")
        for k, v in c.get("node_values", {}).items():
            need(k.isdigit() and int(k) < 156, f"{cid}: node key {k}")
            num(v, f"{cid} node {k}", allow_null=True)
        for k, v in c.get("edge_values", {}).items():
            a, b = (int(z) for z in k.split("-"))
            need(a < b, f"{cid}: edge key {k} must be a<b")
            num(v, f"{cid} edge {k}", allow_null=True)


def check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    problems = []
    if "—" in text:
        problems.append("em dash present")
    if len(text.encode("utf-8")) > 400_000:
        problems.append(f"file is {len(text.encode('utf-8'))} bytes (> 400 KB)")
    try:
        sec = json.loads(text)
        need(re.fullmatch(r"[a-z0-9-]+", sec.get("section", "")) is not None, "bad section id")
        need(isinstance(sec.get("title_tr"), str), "missing title_tr")
        need(1 <= len(sec.get("intro_tr", [])) <= 4, "intro_tr must have 1 to 4 paragraphs")
        need(len(sec.get("bullets_tr", [])) <= 8, "at most 8 bullets")
        seen: set[str] = set()
        for c in sec.get("charts", []):
            check_chart(c, seen)
    except (SpecError, KeyError, TypeError, ValueError) as exc:
        problems.append(f"{type(exc).__name__}: {exc}")
    return problems


def main(argv: list[str]) -> int:
    bad = 0
    for arg in argv:
        problems = check_file(Path(arg))
        print(
            f"{'ok  ' if not problems else 'FAIL'} {arg}" + "".join(f"\n  - {p}" for p in problems)
        )
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
