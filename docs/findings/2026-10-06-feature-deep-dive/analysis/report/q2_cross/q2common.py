"""Shared helpers for the two report sections built in this folder ("iki-kubit", "bagimlilik").

Contract: pure formatting and file writing, no access to the cache. The report page renders
each section JSON as-is (format: ``analysis/report/spec_check.py``), so numbers in Turkish
prose use a decimal comma and a dot for thousands, and chart data are plain floats rounded to
a few significant digits to keep the files small.
"""

# The Turkish text and the scientific notation need the dotless i, the multiplication sign and
# superscript digits, which RUF001 and RUF002 flag as ambiguous; they are intended here.
# ruff: noqa: RUF001, RUF002

from __future__ import annotations

import json
import math
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import numpy as np

DEEP_DIVE = Path(__file__).resolve().parents[3]
RESULTS = DEEP_DIVE / "results"
REPORT_OUT = RESULTS / "report"

SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def load(rel: str) -> Any:
    """A results JSON by its path relative to ``results/`` (for example ``gates_2q/zz.json``)."""
    return json.loads((RESULTS / rel).read_text(encoding="utf-8"))


def r4(x: Any, nd: int = 4) -> float | None:
    """Round to ``nd`` significant digits for chart data; None for missing or non-finite."""
    if x is None:
        return None
    v = float(x)
    if not math.isfinite(v):
        return None
    return float(f"{v:.{nd}g}")


def dec(x: float, d: int = 3) -> str:
    """Fixed decimals, rounded half up as written, with a Turkish decimal comma.

    ``dec(0.8962, 3)`` gives ``0,896``; ``dec(0.998535, 5)`` gives ``0,99854`` (binary
    formatting would give ``0,99853``, unlike the documents, which round the printed value).
    """
    q = Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    if q == 0:
        q = abs(q)
    return f"{q:.{d}f}".replace(".", ",")


def join_tr(items: list[str]) -> str:
    """``a, b ve c`` (Turkish list joining)."""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " ve " + items[-1]


def intk(n: float) -> str:
    """An integer with a dot as the thousands separator: ``intk(22092)`` gives ``22.092``."""
    return f"{round(float(n)):,d}".replace(",", ".")


def pct(share: float, d: int = 1) -> str:
    """A share as a Turkish percentage (sign first): ``pct(0.8881)`` gives ``%88,8``."""
    return "%" + dec(100.0 * float(share), d)


def sci(x: float, d: int = 2) -> str:
    """Scientific notation in prose: ``sci(0.002745)`` gives ``2,75 × 10⁻³``."""
    v = float(x)
    if v == 0:
        return "0"
    e = math.floor(math.log10(abs(v)))
    m = v / 10**e
    if round(abs(m), d) >= 10:
        e += 1
        m = v / 10**e
    return f"{dec(m, d)} × 10{str(e).translate(SUPERSCRIPT)}"


def stem_iso(stem: str) -> str:
    """``20260513T121322000000Z.json`` to ``2026-05-13T12:13:22Z``."""
    s = stem.removesuffix(".json")
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}T{s[9:11]}:{s[11:13]}:{s[13:15]}Z"


def ms_iso(ms: float) -> str:
    """Epoch milliseconds to an ISO UTC string with seconds."""
    return str(np.datetime64(int(ms), "ms").astype("datetime64[s]")) + "Z"


def hist(values: Any, edges: Any) -> tuple[list[float], list[int]]:
    """Counts of the finite ``values`` in ``edges``; every finite value must fall inside."""
    a = np.asarray(values, dtype=np.float64)
    a = a[np.isfinite(a)]
    e = np.asarray(edges, dtype=np.float64)
    counts, _ = np.histogram(a, bins=e)
    if int(counts.sum()) != a.size:
        raise ValueError(f"{a.size - int(counts.sum())} values fall outside the histogram edges")
    return [r4(v) for v in e], [int(k) for k in counts]


def log_edges(lo_exp: float, hi_exp: float, step: float = 0.1) -> list[float]:
    """Edges ``10**k`` for ``k`` from ``lo_exp`` to ``hi_exp`` in ``step`` decades."""
    n = round((hi_exp - lo_exp) / step)
    return [float(f"{10 ** (lo_exp + i * step):.4g}") for i in range(n + 1)]


def check(name: str, got: float, want: float, tol: float) -> None:
    """Fail loudly when a recomputed number does not reproduce the owner's figure."""
    if not (abs(float(got) - float(want)) <= tol):
        raise AssertionError(f"{name}: recomputed {got} does not match the document's {want}")


def write_section(name: str, section: dict[str, Any]) -> Path:
    """Write ``results/report/<name>.json`` (UTF-8, Turkish characters unescaped, LF)."""
    text = json.dumps(section, ensure_ascii=False, indent=1) + "\n"
    if "—" in text:
        raise ValueError("em dash in section text")
    REPORT_OUT.mkdir(parents=True, exist_ok=True)
    path = REPORT_OUT / f"{name}.json"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path
