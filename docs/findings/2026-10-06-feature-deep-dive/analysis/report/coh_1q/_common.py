"""Shared helpers of the ``koherans`` and ``tek-kubit`` report sections.

Nothing here reads the field cache. The section scripts (``koherans.py``, ``tek_kubit.py``)
load what they need through ``ddload`` and the owner scripts' helpers, check every
recomputed headline against the figure its document states (``check``), and write one
section JSON each (``write_section``) in the format of ``analysis/report/spec_check.py``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

DEEP_DIVE = Path(__file__).resolve().parents[3]
RESULTS = DEEP_DIVE / "results"
REPORT = RESULTS / "report"
EM_DASH = chr(0x2014)  # the page forbids this character


def load(rel: str) -> dict[str, Any]:
    """A results JSON of the deep dive, by its path under ``results/``."""
    out: dict[str, Any] = json.loads((RESULTS / rel).read_text(encoding="utf-8"))
    return out


def check(label: str, got: float, want: float, tol: float) -> None:
    """Fail loudly when a recomputed figure drifts from the document's figure."""
    if not (math.isfinite(got) and abs(got - want) <= tol):
        raise AssertionError(f"{label}: recomputed {got!r}, document {want!r} (tol {tol})")


def sig(x: float, n: int = 4) -> float:
    """``x`` rounded to ``n`` significant digits (keeps the section file small)."""
    if x == 0 or not math.isfinite(x):
        return float(x)
    return round(float(x), n - 1 - math.floor(math.log10(abs(x))))


def iso(ms: float) -> str:
    """Milliseconds since the epoch to ``YYYY-MM-DDTHH:MM:SSZ`` (the page's time format)."""
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_edges(lo: float, hi: float, step: float = 0.05) -> FloatArray:
    """Bin edges in log10 units from ``lo`` to ``hi`` (inclusive) in steps of ``step``."""
    k = round((hi - lo) / step)
    out: FloatArray = lo + step * np.arange(k + 1, dtype=np.float64)
    return out


def log_hist(values: FloatArray, lo: float, hi: float, step: float = 0.05) -> dict[str, Any]:
    """Histogram of ``log10(values)`` with edges reported as raw values (for a log x axis)."""
    z = np.log10(np.asarray(values, dtype=np.float64))
    edges = log_edges(lo, hi, step)
    if z.min() < edges[0] or z.max() > edges[-1]:
        raise ValueError(f"values outside the bin range [{lo}, {hi}]: {z.min()}, {z.max()}")
    counts, _ = np.histogram(z, bins=edges)
    return {"edges": [sig(10.0**e, 4) for e in edges], "counts": [int(c) for c in counts]}


def log_range(values: FloatArray, step: float = 0.05) -> tuple[float, float]:
    """The smallest step-aligned log10 range that holds every value."""
    z = np.log10(np.asarray(values, dtype=np.float64))
    return (
        round(math.floor(z.min() / step) * step, 6),
        round(math.ceil(z.max() / step) * step, 6),
    )


def runs(flags: Sequence[bool]) -> list[tuple[int, int]]:
    """Maximal runs of True as (first index, last index) pairs."""
    out: list[tuple[int, int]] = []
    start = None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(flags) - 1))
    return out


def write_section(name: str, payload: dict[str, Any]) -> Path:
    """Write ``results/report/<name>.json`` (UTF-8, LF, ``ensure_ascii=False``, indent 1)."""
    text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    if EM_DASH in text:
        raise ValueError(f"{name}: em dash in the section text")
    REPORT.mkdir(parents=True, exist_ok=True)
    path = REPORT / f"{name}.json"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def fit_hist_x(chart: dict[str, Any]) -> dict[str, Any]:
    """Pin a log-x histogram's axis to its outer bin edges.

    Without explicit bounds the page rounds a log axis out to whole decades, which can leave
    the bars in a third of the plot width.
    """
    if chart["type"] == "hist" and chart["x"]["scale"] == "log":
        edges = [e for s in chart["series"] for e in s["edges"]]
        chart["x"]["min"] = min(edges)
        chart["x"]["max"] = max(edges)
    return chart
