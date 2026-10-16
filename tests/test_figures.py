"""superconducted.figures: the vendored brand chart style and its three drawing roles."""

from __future__ import annotations

import hashlib
import io
import logging
import warnings
from collections.abc import Iterator
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.colors import to_hex

from superconducted import figures as scf
from superconducted.figures import superconducted_figures as brand

BRAND_COMMIT = "3ff5e86"
"""SuperconducTED/.github, the typed helper of PR #3; the data files are as at 06f1959."""

FIGURES = Path(brand.HERE)

VENDORED_SHA256 = {
    "superconducted_figures.py": (
        "e98c3e471741c615420378588df48cbb01f0f0cee476c6f26e63338382f6dc04"
    ),
    "roles.json": "5a0f224fc96dc4a1a85120970939bb371ba6b443e6354db01bf323abd10dc2a3",
    "styles/superconducted-cryostat.mplstyle": (
        "aab480568cf1e21bf7405bc2725f1c4a276ba86c9b41d36b6221723ca755c60f"
    ),
    "styles/superconducted-cryostat-dark.mplstyle": (
        "6d1aca214f6d97ba6d5ce39e79bea231909f0b6c03cc015300215914b0d50a59"
    ),
}
"""sha256 of each file's bytes at BRAND_COMMIT (``git show <commit>:brand/figures/<path>``)."""

COLOUR_KEYWORDS = ("color", "c", "facecolor", "edgecolor", "fc", "ec", "markerfacecolor", "mfc")


@pytest.fixture(autouse=True)
def _fresh_style(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every test starts before use() and leaves matplotlib's global state as it found it."""
    monkeypatch.setattr(brand, "_current", None)
    with matplotlib.rc_context():
        yield
    plt.close("all")


def _hex(colour: object) -> str:
    return to_hex(colour).upper()  # type: ignore[arg-type]


class TestVendoredFiles:
    def test_every_vendored_file_is_byte_identical_to_the_brand_kit(self) -> None:
        """Never hand-edited: a change belongs in the brand repository, then re-vendored."""
        for name, expected in VENDORED_SHA256.items():
            body = (FIGURES / name).read_bytes().replace(b"\r\n", b"\n")
            assert hashlib.sha256(body).hexdigest() == expected, (
                f"{name} differs from brand/figures/{name} at {BRAND_COMMIT}"
            )

    def test_the_engine_ships_the_chosen_palette_only(self) -> None:
        assert scf.PALETTES == ("cryostat",)
        assert {p.name for p in Path(brand.STYLES).iterdir()} == {
            "superconducted-cryostat.mplstyle",
            "superconducted-cryostat-dark.mplstyle",
        }
        assert set(VENDORED_SHA256) == {
            p.relative_to(FIGURES).as_posix()
            for p in FIGURES.rglob("*")
            if p.is_file() and p.name != "__init__.py" and "__pycache__" not in p.parts
        }, "a file was added beside the vendored kit without a pin"

    def test_the_package_re_exports_the_brand_helper_not_a_copy(self) -> None:
        """Everything but use() and style_path() is the brand's own function object."""
        for name in ("band", "band_handle", "crisp", "measured", "mono_ticks", "roles", "series"):
            assert getattr(scf, name) is getattr(brand, name), name

    @pytest.mark.parametrize("dark", [False, True])
    def test_the_style_loads_without_a_warning(
        self, dark: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unknown or invalid rc keys reach matplotlib's logger, not warnings; watch both."""
        with caplog.at_level(logging.WARNING, logger="matplotlib"), warnings.catch_warnings():
            warnings.simplefilter("error")
            scf.use(dark=dark)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestUse:
    @pytest.mark.parametrize("dark", [False, True])
    def test_use_applies_the_ground_and_the_series_cycle(self, dark: bool) -> None:
        roles = scf.use(dark=dark)
        assert roles["palette"] == "cryostat" and roles["dark"] is dark
        assert _hex(matplotlib.rcParams["axes.facecolor"]) == roles["ground"]
        assert _hex(matplotlib.rcParams["figure.facecolor"]) == roles["ground"]
        cycle = [_hex(c) for c in matplotlib.rcParams["axes.prop_cycle"].by_key()["color"]]
        assert cycle == roles["series"]

    def test_the_named_palette_is_the_default(self) -> None:
        assert scf.use("cryostat") == scf.use()

    def test_another_brand_palette_is_refused_and_nothing_is_applied(self) -> None:
        with pytest.raises(ValueError, match="cryostat only"):
            scf.use("heatleak")
        with pytest.raises(RuntimeError):
            scf.roles()

    def test_roles_is_a_copy(self) -> None:
        scf.use()
        scf.roles()["band_fill"] = "#000000"
        assert scf.roles()["band_fill"] != "#000000"

    @pytest.mark.parametrize(
        "call",
        [
            lambda ax: scf.band(ax, [0, 1], 0, 1),
            lambda ax: scf.crisp(ax, [0, 1], 0),
            lambda ax: scf.measured(ax, [0, 1], [0, 1]),
            lambda ax: scf.series(),
            lambda ax: scf.band_handle("x"),
        ],
    )
    def test_every_role_refuses_to_draw_before_use(self, call: object) -> None:
        _, ax = plt.subplots()
        with pytest.raises(RuntimeError, match="use"):
            call(ax)  # type: ignore[operator]


class TestRoles:
    def test_band_is_a_solid_accent_tint_with_accent_edges(self) -> None:
        roles = scf.use()
        _, ax = plt.subplots()
        band = scf.band(ax, [0, 1, 2], [1, 2, 3], [2, 3, 5], label="Engine interval")
        assert _hex(band.get_facecolor()[0]) == roles["band_fill"]
        assert _hex(band.get_edgecolor()[0]) == roles["band_edge"] == roles["accent"]
        assert band.get_facecolor()[0][3] == 1.0, "a band is solid, never an alpha"
        assert band.get_zorder() == 1.5 and band.get_label() == "Engine interval"

    def test_band_refuses_a_lower_bound_above_the_upper(self) -> None:
        scf.use()
        _, ax = plt.subplots()
        with pytest.raises(ValueError, match="lower bound above upper bound"):
            scf.band(ax, [0, 1], [0, 2], [1, 1])

    def test_crisp_is_a_dashed_ink_line_and_takes_a_scalar(self) -> None:
        roles = scf.use()
        _, ax = plt.subplots()
        line = scf.crisp(ax, [0, 1, 2, 3], 4.0)
        assert _hex(line.get_color()) == roles["crisp"] == roles["ink"]
        assert line.get_linestyle() == "--" and line.get_linewidth() == scf.CRISP_WIDTH
        assert list(line.get_ydata()) == [4.0, 4.0, 4.0, 4.0]

    def test_measured_is_ringed_ink_dots_without_a_line(self) -> None:
        roles = scf.use()
        _, ax = plt.subplots()
        dots = scf.measured(ax, [0, 1, 2], [3, 1, 2])
        assert dots.get_linestyle() == "None" and dots.get_marker() == "o"
        assert _hex(dots.get_markerfacecolor()) == roles["measured"] == roles["ink"]
        assert _hex(dots.get_markeredgecolor()) == roles["measured_ring"] == roles["ground"]
        assert len(dots.get_xdata()) == 3

    @pytest.mark.parametrize("keyword", COLOUR_KEYWORDS)
    @pytest.mark.parametrize("role", ["band", "crisp", "measured"])
    def test_no_role_takes_a_colour_override(self, role: str, keyword: str) -> None:
        scf.use()
        _, ax = plt.subplots()
        draw = {
            "band": lambda **kw: scf.band(ax, [0, 1], 0, 1, **kw),
            "crisp": lambda **kw: scf.crisp(ax, [0, 1], 0, **kw),
            "measured": lambda **kw: scf.measured(ax, [0, 1], [0, 1], **kw),
        }[role]
        with pytest.raises(TypeError, match="sets its own colour"):
            draw(**{keyword: "#FF0000"})

    def test_series_comes_in_its_fixed_order_and_never_cycles(self) -> None:
        roles = scf.use()
        assert scf.series() == roles["series"] and len(roles["series"]) == 6
        assert scf.series(3) == roles["series"][:3]
        with pytest.raises(ValueError, match="small multiples"):
            scf.series(7)

    def test_the_accent_is_never_a_series_colour(self) -> None:
        for dark in (False, True):
            roles = scf.use(dark=dark)
            assert roles["accent"] not in roles["series"]

    def test_band_handle_matches_the_band(self) -> None:
        roles = scf.use()
        handle = scf.band_handle("Engine interval")
        assert _hex(handle.get_facecolor()) == roles["band_fill"]
        assert _hex(handle.get_edgecolor()) == roles["band_edge"]
        assert handle.get_label() == "Engine interval"


class TestMonoTicks:
    @pytest.mark.parametrize("shape", ["figure", "axes", "iterable"])
    def test_tick_labels_take_the_monospace_face(self, shape: str) -> None:
        scf.use()
        fig, axes = plt.subplots(1, 2)
        target = {"figure": fig, "axes": axes[0], "iterable": list(axes)}[shape]
        assert scf.mono_ticks(target) is target
        changed = list(axes) if shape != "axes" else [axes[0]]
        for ax in changed:
            ticks = ax.xaxis.get_major_ticks() + ax.yaxis.get_major_ticks()
            assert ticks, "no tick read, so nothing was checked"
            for tick in ticks:
                assert tick.label1.get_fontfamily() == ["monospace"]
        if shape == "axes":
            tick = axes[1].xaxis.get_major_ticks()[0]
            assert tick.label1.get_fontfamily() != ["monospace"]


def test_a_whole_figure_renders_with_a_silent_font_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without the brand fonts the style falls back to DejaVu with no findfont warning."""
    scf.use()
    x = np.arange(8, dtype=float)
    fig, ax = plt.subplots()
    scf.band(ax, x, x - 1.0, x + 1.0, label="Engine interval")
    scf.crisp(ax, x, 3.0, label="Single snapshot")
    scf.measured(ax, x, x, label="Measured")
    ax.set_title("Illustrative data")
    ax.legend()
    scf.mono_ticks(fig)
    buffer = io.BytesIO()
    with caplog.at_level(logging.WARNING, logger="matplotlib"):
        fig.savefig(buffer, format="png")
    assert buffer.getvalue().startswith(b"\x89PNG")
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
