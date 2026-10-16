"""SuperconducTED chart style: apply the brand's matplotlib style and draw the three roles.

::

    import matplotlib.pyplot as plt
    from superconducted import figures as scf

    scf.use()                                 # Cryostat, light ground; use(dark=True) for dark
    fig, ax = plt.subplots()
    scf.band(ax, x, lo, hi, label="Engine interval")
    scf.crisp(ax, x, y_snapshot, label="Single snapshot")
    scf.measured(ax, x, y, label="Measured")
    ax.legend()
    scf.mono_ticks(fig)                       # Space Mono tick labels (tabular figures)
    fig.savefig("t1.png")

Team code says WHAT it draws; this module decides how it looks. The three roles:

- ``band``: the engine's answer, an interval from lower to upper bound. Accent edges on a
  solid accent tint: the accent means "the range" and nothing else.
- ``crisp``: the single-snapshot prediction (Qiskit's ``NoiseModel.from_backend``, frozen at
  one calibration). Ink, dashed: a dashed line reads as a frozen reference.
- ``measured``: what the hardware actually did. Ink dots ringed in the ground colour, so they
  stay legible where they sit on the band or the crisp line.

Per-qubit (or any per-entity) series take the categorical sequence through the style's colour
cycle; ``series(n)`` returns the colours when you need them explicitly.

Contract: ``use()`` must run before ``band()``, ``crisp()``, ``measured()``, ``series()`` or
``band_handle()``; they raise ``RuntimeError`` otherwise. Each drawing helper returns the
matplotlib artist it created and forwards extra keyword arguments to matplotlib, but refuses a
colour override for its role (``TypeError``), because a role's colour is the point of the role.

Provenance: vendored from the brand kit, ``SuperconducTED/.github`` branch
``brand/superconducted-identity`` at commit ``06f1959``, folder ``brand/figures/``.
``roles.json`` and ``styles/*.mplstyle`` are byte-identical copies, pinned by
``tests/test_figures.py``; never edit them here (the brand regenerates them from its palette
source; re-vendor instead). This module differs from the brand's ``superconducted_figures.py``
in four ways only: type annotations for ``mypy --strict``; the engine ships the chosen
palette alone (Cryostat), so ``PALETTES`` is ``("cryostat",)`` and its two styles carry the
brand's generic names ``superconducted.mplstyle`` and ``superconducted-dark.mplstyle`` (the
brand's build copies them byte for byte from the Cryostat files); ``mono_ticks`` tells a
``Figure``, an ``Axes`` and an iterable of ``Axes`` apart by type, not by duck typing; error
messages name this module. Drawing behaviour is the brand's.

Needs the ``figures`` extra (matplotlib >= 3.8, the first release with
``tick_params(labelfontfamily=...)``). Importing this module imports ``matplotlib.pyplot``; it
does not choose a backend.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.collections import PolyCollection
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from numpy.typing import ArrayLike

HERE = Path(__file__).resolve().parent
STYLES = HERE / "styles"
ROLES_FILE = HERE / "roles.json"

with ROLES_FILE.open(encoding="utf-8") as _fh:
    _DOC: dict[str, Any] = json.load(_fh)

#: The palettes this copy ships styles for: the identity's chosen one only.
PALETTES: tuple[str, ...] = (str(_DOC["chosen"]),)

_current: dict[str, Any] | None = None

# Mark geometry, in points (1 pt = 1.33 px at 96 dpi). The dataviz method's specs: 2 px lines,
# >= 8 px markers with a 2 px ring in the ground colour, hairline chrome.
BAND_EDGE_WIDTH = 1.0
CRISP_WIDTH = 1.5
MEASURED_SIZE = 6.0
MEASURED_RING = 1.2

_Target = TypeVar("_Target", bound=Figure | Axes | Iterable[Axes])


def style_path(palette: str, dark: bool = False) -> Path:
    """Path of the ``.mplstyle`` file for a palette key and mode.

    Raises ``ValueError`` for any key outside ``PALETTES``, including the brand's other five
    options, whose styles stay in the brand repository as the record of the choice.
    """
    if palette not in PALETTES:
        raise ValueError(f"unknown palette {palette!r}; this copy ships {', '.join(PALETTES)} only")
    return STYLES / f"superconducted{'-dark' if dark else ''}.mplstyle"


def use(palette: str | None = None, dark: bool = False) -> dict[str, Any]:
    """Apply the style for ``palette`` on a light or dark ground; with no palette, the
    identity's own (roles.json ``"chosen"``: Cryostat, the owner's pick of 2026-10-16).

    Side effect: changes matplotlib's global rcParams (``plt.style.use``) and selects the roles
    the drawing helpers use. Returns the roles dict (``ground``, ``text``, ``band_fill``,
    ``series``, ...), as ``roles()`` does.
    """
    global _current
    palette = palette or str(_DOC["chosen"])
    plt.style.use(str(style_path(palette, dark)))
    _current = dict(
        _DOC["palettes"][palette]["dark" if dark else "light"], palette=palette, dark=dark
    )
    return roles()


def roles() -> dict[str, Any]:
    """The active roles (a copy). Raises ``RuntimeError`` before ``use()``."""
    if _current is None:
        raise RuntimeError("call superconducted.figures.use() first")
    return dict(_current)


def series(n: int | None = None) -> list[str]:
    """The categorical sequence for per-entity series, in its fixed order.

    The order is part of the colour-blind safety, so colours are taken from the start and
    never cycled: asking for more than the sequence holds raises ``ValueError`` (fold the rest
    into "other" or split the chart into small multiples).
    """
    seq = [str(colour) for colour in roles()["series"]]
    if n is None:
        return seq
    if n > len(seq):
        raise ValueError(
            f"the sequence has {len(seq)} colours; {n} series need small multiples "
            "or an 'other' group"
        )
    return seq[:n]


def _no_colour_override(kw: dict[str, Any], role: str) -> None:
    for k in ("color", "c", "facecolor", "edgecolor", "fc", "ec", "markerfacecolor", "mfc"):
        if k in kw:
            raise TypeError(f"{role}() sets its own colour (keyword {k!r}); that is the role")


def band(
    ax: Axes,
    x: ArrayLike,
    lo: ArrayLike,
    hi: ArrayLike,
    label: str | None = None,
    **kw: Any,
) -> PolyCollection:
    """The engine's interval: a solid accent tint between ``lo`` and ``hi``, with accent edges.

    ``lo`` and ``hi`` are arrays (or scalars) broadcastable to ``x``, with ``lo <= hi``
    everywhere (``ValueError`` otherwise). Returns the collection ``fill_between`` made. Drawn
    below the crisp line and the measured points.
    """
    r = roles()
    _no_colour_override(kw, "band")
    xs = np.asarray(x, dtype=float)
    los = np.broadcast_to(np.asarray(lo, dtype=float), xs.shape)
    his = np.broadcast_to(np.asarray(hi, dtype=float), xs.shape)
    if np.any(los > his):
        raise ValueError("band(): lower bound above upper bound")
    kw.setdefault("zorder", 1.5)
    kw.setdefault("linewidth", BAND_EDGE_WIDTH)
    return ax.fill_between(
        xs, los, his, facecolor=r["band_fill"], edgecolor=r["band_edge"], label=label, **kw
    )


def crisp(ax: Axes, x: ArrayLike, y: ArrayLike, label: str | None = None, **kw: Any) -> Line2D:
    """The single-snapshot prediction: a dashed ink line. ``y`` may be a scalar (a flat line)."""
    r = roles()
    _no_colour_override(kw, "crisp")
    xs = np.asarray(x, dtype=float)
    ys = np.broadcast_to(np.asarray(y, dtype=float), xs.shape)
    kw.setdefault("zorder", 2.5)
    kw.setdefault("linewidth", CRISP_WIDTH)
    kw.setdefault("linestyle", "--")
    (line,) = ax.plot(xs, ys, color=r["crisp"], label=label, **kw)
    return line


def measured(ax: Axes, x: ArrayLike, y: ArrayLike, label: str | None = None, **kw: Any) -> Line2D:
    """What the hardware did: ink dots with a ring in the ground colour, no connecting line."""
    r = roles()
    _no_colour_override(kw, "measured")
    kw.setdefault("zorder", 3.0)
    kw.setdefault("markersize", MEASURED_SIZE)
    kw.setdefault("markeredgewidth", MEASURED_RING)
    (line,) = ax.plot(
        x,
        y,
        linestyle="none",
        marker="o",
        color=r["measured"],
        markerfacecolor=r["measured"],
        markeredgecolor=r["measured_ring"],
        label=label,
        **kw,
    )
    return line


def band_handle(label: str) -> Patch:
    """A legend handle for a band, for legends built by hand."""
    r = roles()
    return Patch(
        facecolor=r["band_fill"], edgecolor=r["band_edge"], linewidth=BAND_EDGE_WIDTH, label=label
    )


def mono_ticks(target: _Target) -> _Target:
    """Set tick labels in the monospace face (Space Mono): tabular figures that align.

    ``target`` is a ``Figure``, an ``Axes``, or an iterable of ``Axes``; returned unchanged.
    Persists for ticks created later.
    """
    axes: list[Axes]
    if isinstance(target, Figure):
        axes = list(target.axes)
    elif isinstance(target, Axes):
        axes = [target]
    else:
        axes = list(target)
    for ax in axes:
        ax.tick_params(axis="both", which="both", labelfontfamily="monospace")
    return target
