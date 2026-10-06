# ruff: noqa: RUF001
"""Shared helpers of the report sections ``veri`` and ``cihaz`` (data layer; device and time).

Imported by ``veri.py`` and ``cihaz.py`` in this folder (Python puts a script's own folder
first on ``sys.path``). Nothing here computes a finding; it locates files, loads results JSONs,
formats Turkish numbers and writes a section file.

Contracts:

- ``load(rel)``: a results JSON under ``results/`` (for example ``"device/schedule.json"``).
- ``tr(x, nd)``: a number in Turkish prose form, decimal comma and dot thousands
  (``tr(0.7, 2) == "0,70"``, ``tr(1760) == "1.760"``); negative numbers keep a hyphen-minus.
- ``write_section(name, payload)``: ``results/report/<name>.json`` with
  ``json.dumps(ensure_ascii=False, indent=1)`` and a trailing newline, LF line endings.
  ``ddload.write_json`` is not used because it escapes non-ASCII characters.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE.parents[1]
RESULTS = ANALYSIS.parent / "results"
OUT = RESULTS / "report"

sys.path.insert(0, str(ANALYSIS))
sys.path.insert(0, str(ANALYSIS / "device"))

MONTHS_TR = {
    "01": "Ocak",
    "02": "Şubat",
    "03": "Mart",
    "04": "Nisan",
    "05": "Mayıs",
    "06": "Haziran",
    "07": "Temmuz",
    "08": "Ağustos",
    "09": "Eylül",
    "10": "Ekim",
    "11": "Kasım",
    "12": "Aralık",
}


def load(rel: str) -> Any:
    return json.loads((RESULTS / rel).read_text(encoding="utf-8"))


MINUS = "-"


def tr(x: float, nd: int = 2) -> str:
    """Turkish prose number: ``nd`` decimals, decimal comma, dot as thousands separator.

    Negative numbers carry an ASCII hyphen-minus, as every other section does.
    """
    if isinstance(x, int) or (float(x).is_integer() and nd == 0):
        s = f"{round(float(x)):,}".replace(",", ".")
    else:
        if not math.isfinite(float(x)):
            raise ValueError(f"not finite: {x!r}")
        s = f"{float(x):,.{nd}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return s.replace("-", MINUS)


def sci(x: float, nd: int = 1) -> str:
    """Scientific notation in Turkish form, e.g. ``sci(2.69e-07) == "2,7e-7"``."""
    mant, exp = f"{float(x):.{nd}e}".split("e")
    return f"{mant.replace('.', ',')}e{int(exp)}"


def pct(x: float, nd: int = 1) -> str:
    """Share as a Turkish percentage, e.g. ``pct(0.685) == "%68,5"``."""
    return "%" + tr(100.0 * float(x), nd)


def iso(ms: float) -> str:
    return datetime.fromtimestamp(float(ms) / 1000.0, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_day(ms: float) -> str:
    return datetime.fromtimestamp(float(ms) / 1000.0, UTC).strftime("%Y-%m-%d")


def date_tr(text: str) -> str:
    """``"2026-06-08..."`` to ``"8 Haziran 2026"``."""
    return f"{int(text[8:10])} {MONTHS_TR[text[5:7]]} {text[:4]}"


def to_ms(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000.0


def r4(x: float) -> float:
    """Four significant digits for chart data (keeps the section file small)."""
    return float(f"{float(x):.4g}")


def write_section(name: str, payload: dict[str, Any]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.json"
    text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path
