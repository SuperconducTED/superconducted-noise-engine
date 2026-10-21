"""Render the example figure of docs/implementations/2026-10-16-brand-chart-style.md.

Illustrative data from a fixed seed: no number on the figure is a measurement of any device,
and the figure says so. Needs the `figures` extra. From the repository root:

    python docs/implementations/2026-10-16-brand-chart-style/render_example.py

Writes example-light.png and example-dark.png next to this file. Byte identity across
machines needs the same matplotlib version and the same fonts (the brand fonts, or neither).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from superconducted import figures as scf

HERE = Path(__file__).resolve().parent


def render(dark: bool) -> Path:
    """Draw the three roles and a per-entity panel on one figure; return the PNG's path."""
    scf.use(dark=dark)
    rng = np.random.default_rng(20261016)
    cycles = np.arange(24, dtype=float)
    centre = 100.0 + 12.0 * np.sin(cycles / 4.0)
    half_width = 9.0 + 2.0 * np.cos(cycles / 6.0)
    measured = centre + rng.normal(0.0, 4.0, cycles.size)

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.0, 3.4))
    fig.suptitle("Illustrative data, fixed seed: not a measurement")
    scf.band(left, cycles, centre - half_width, centre + half_width, label="Engine interval")
    scf.crisp(left, cycles, centre[0], label="Single snapshot (frozen)")
    scf.measured(left, cycles, measured, label="Measured")
    left.set_title("The three roles")
    left.set_xlabel("Calibration cycle")
    left.set_ylabel("T1 (illustrative)")
    left.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncols=3)  # below, off the data

    top = 0.0
    for q, colour in enumerate(scf.series(4)):
        drift = 90.0 + 8.0 * q + rng.normal(0.0, 2.5, cycles.size).cumsum() / 3.0
        right.plot(cycles, drift, color=colour, label=f"Q{q}")
        top = max(top, float(drift.max()))
    right.set_ylim(top=top + 10.0)  # headroom, so the legend row sits above every line
    right.set_title("Per-qubit series")
    right.set_xlabel("Calibration cycle")
    right.legend(loc="upper left", ncols=4)

    scf.mono_ticks(fig)
    out = HERE / f"example-{'dark' if dark else 'light'}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


if __name__ == "__main__":
    for mode in (False, True):
        print(render(mode))
