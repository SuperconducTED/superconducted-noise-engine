"""Render the slide-3 chart of the 2026-10-28 deck for Dr. Akba: NC-085's interval-score ladder.

Draws the four gamma 24 h interval scores of NC-085 (80% conformal bands on test change rows,
log target space) from the committed output ``docs/evidence/predictability/results.tsv``. It
computes nothing new: it reads four committed values, checks each against the value NC-085's
row of ``docs/numerical-claims.md`` writes, stops on a disagreement beyond rounding, and labels
each bar with the register's string.

From the repository root, with the pinned interpreter and the ``figures`` extra:

    PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe \
        docs/advisor/2026-10-28-akba-phase-4-experiment-deck/render_ladder_chart.py

Writes ``chart-ladder-en.png`` and ``chart-ladder-tr.png`` next to this file. Labels for the
Turkish chart are read from ``chart-labels.json`` beside it, so this file stays ASCII.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from superconducted import figures as scf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULTS = ROOT / "docs" / "evidence" / "predictability" / "results.tsv"
REGISTER = ROOT / "docs" / "numerical-claims.md"
LABELS = HERE / "chart-labels.json"

# Bottom to top on the chart: the latest reading first, the bar to beat last.
MODELS = ("persistence", "shrinkage", "linear", "rolling_band")


def ladder() -> dict[str, float]:
    """Return NC-085's gamma 24 h interval score per model, read from the committed TSV."""
    values: dict[str, float] = {}
    with RESULTS.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if (
                row["measurement"] == "horizon_band"
                and row["component"] == "gamma"
                and row["metric"] == "interval_score"
                and row["horizon_h"] == "24.0"
                and row["model"] in MODELS
            ):
                values[row["model"]] = float(row["value"])
    if set(values) != set(MODELS):
        raise SystemExit(f"expected {MODELS} in {RESULTS}, found {sorted(values)}")
    return values


def register_values() -> dict[str, str]:
    """Return the four gamma 24 h interval scores exactly as NC-085's row writes them."""
    text = REGISTER.read_text(encoding="utf-8")
    match = re.search(r"^\| NC-085 \|.*$", text, flags=re.MULTILINE)
    if match is None:
        raise SystemExit("NC-085 row not found in the register")
    found = re.search(
        r"gamma 24 h: persistence ([\d.]+), shrinkage ([\d.]+), ridge ([\d.]+), "
        r"rolling band ([\d.]+)",
        match.group(0),
    )
    if found is None:
        raise SystemExit("NC-085's gamma 24 h interval-score clause not found")
    return dict(zip(MODELS, found.groups(), strict=True))


def check_against_register(values: dict[str, float], written: dict[str, str]) -> None:
    """Stop unless every committed value is within 0.001 of the value NC-085 writes.

    The tolerance is the register's three-decimal rounding plus one unit of slack: NC-085
    writes ridge as 1.095 where ``results.tsv`` holds 1.09446, which rounds to 1.094. The
    chart labels each bar with the register's string, since the register is what the deck
    cites, and this function prints every case where the two roundings differ.
    """
    for model in MODELS:
        value, shown = values[model], written[model]
        if abs(value - float(shown)) > 0.001:
            raise SystemExit(f"{model}: results.tsv {value} against NC-085 {shown}")
        if f"{value:.3f}" != shown:
            print(f"note: {model} results.tsv {value:.5f} rounds to {value:.3f}; NC-085 {shown}")


def render(
    values: dict[str, float],
    written: dict[str, str],
    lang: str,
    labels: dict[str, dict[str, str]],
) -> Path:
    """Draw the horizontal bar ladder for one language; return the PNG's path.

    Bar lengths are the committed values; each bar's label is NC-085's own string.
    """
    roles = scf.use()
    text = labels[lang]
    plt.rcParams.update({"font.size": 20})
    fig, ax = plt.subplots(figsize=(8.4, 5.6), layout="constrained")
    names = [text[m] for m in MODELS]
    scores = [values[m] for m in MODELS]
    ys = list(range(len(MODELS)))
    looks = {
        "persistence": {"facecolor": roles["ground"], "edgecolor": roles["crisp"], "ls": "--"},
        "shrinkage": {"facecolor": roles["text_secondary"], "edgecolor": roles["text_secondary"]},
        "linear": {"facecolor": roles["grid"], "edgecolor": roles["axis"]},
        "rolling_band": {"facecolor": roles["band_fill"], "edgecolor": roles["band_edge"]},
    }
    for y, model, score in zip(ys, MODELS, scores, strict=True):
        look = looks[model]
        ax.barh(
            y,
            score,
            height=0.62,
            facecolor=look["facecolor"],
            edgecolor=look["edgecolor"],
            linestyle=look.get("ls", "-"),
            linewidth=2.0,
        )
        ax.text(
            score + 0.03,
            y,
            written[model],
            va="center",
            ha="left",
            fontsize=22,
            fontweight="bold",
            color=roles["text"],
        )
    ax.set_yticks(ys, names, fontsize=20)
    ax.set_xticks([])
    ax.set_xlim(0.0, max(scores) * 1.32)
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    # The metric's name is the slide's caption, in HTML text; the figure carries its source.
    fig.suptitle(text["source"], x=0.01, ha="left", fontsize=15, color=roles["text_secondary"])
    out = HERE / f"chart-ladder-{lang}.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def main() -> None:
    values = ladder()
    written = register_values()
    check_against_register(values, written)
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    for lang in ("en", "tr"):
        print(render(values, written, lang, labels))


if __name__ == "__main__":
    main()
