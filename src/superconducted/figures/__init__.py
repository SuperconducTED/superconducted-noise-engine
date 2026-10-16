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

Team code says WHAT it draws; the brand's helper decides how it looks. The three roles:
``band`` (the engine's interval: a solid accent tint with accent edges, the accent meaning
"the range" and nothing else), ``crisp`` (a single from_backend snapshot: ink, dashed) and
``measured`` (what the hardware did: ink dots ringed in the ground colour). Per-entity series
take ``series(n)``, the brand's fixed categorical sequence.

Contract: ``use()`` must run first; the drawing helpers raise ``RuntimeError`` before it,
return the matplotlib artist they create, forward extra keyword arguments, and raise
``TypeError`` on a colour override, because a role's colour is the point of the role.

Provenance: ``superconducted_figures.py``, ``roles.json`` and ``styles/`` are the brand kit's
files, byte for byte (``SuperconducTED/.github``, ``brand/figures/``, commit ``3ff5e86``, the
typed helper of SuperconducTED/.github#3; the data files are unchanged since ``06f1959``).
``tests/test_figures.py`` pins all four by sha256: never edit them here, re-vendor instead.
This module is the engine's only code: it re-exports the helper and allows the identity's
chosen palette (Cryostat) alone, the one whose styles the engine ships.

Needs the ``figures`` extra (matplotlib >= 3.8). Importing this module imports
``matplotlib.pyplot``; it does not choose a backend.
"""

from __future__ import annotations

from typing import Any

from . import superconducted_figures as _brand
from .superconducted_figures import (
    BAND_EDGE_WIDTH,
    CRISP_WIDTH,
    MEASURED_RING,
    MEASURED_SIZE,
    band,
    band_handle,
    crisp,
    measured,
    mono_ticks,
    roles,
    series,
)

#: The palettes the engine ships styles for: the identity's chosen one only.
PALETTES: tuple[str, ...] = (str(_brand._DOC["chosen"]),)


def style_path(palette: str, dark: bool = False) -> str:
    """Path of the ``.mplstyle`` file for a palette key and mode.

    Raises ``ValueError`` for any key outside ``PALETTES``, including the brand's other five
    options, whose styles stay in the brand repository as the record of the choice.
    """
    if palette not in PALETTES:
        raise ValueError(
            f"unknown palette {palette!r}; the engine ships {', '.join(PALETTES)} only"
        )
    return _brand.style_path(palette, dark)


def use(palette: str | None = None, dark: bool = False) -> dict[str, Any]:
    """Apply the style on a light or dark ground and select the roles; see the brand's ``use``.

    Refuses any palette outside ``PALETTES`` before anything is applied. Side effect: changes
    matplotlib's global rcParams. Returns the roles dict, as ``roles()`` does.
    """
    style_path(palette or PALETTES[0], dark)
    return _brand.use(palette, dark)


__all__ = [
    "BAND_EDGE_WIDTH",
    "CRISP_WIDTH",
    "MEASURED_RING",
    "MEASURED_SIZE",
    "PALETTES",
    "band",
    "band_handle",
    "crisp",
    "measured",
    "mono_ticks",
    "roles",
    "series",
    "style_path",
    "use",
]
