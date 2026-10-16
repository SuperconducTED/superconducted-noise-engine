# 2026-10-16: brand-chart-style

## Problem / Motivation

On 2026-10-16 the SuperconducTED brand was finalised: the technical-cutaway mark, the Cryostat
palette and the tagline "Noise as a range, not a number." It ships a validated matplotlib chart
style (`SuperconducTED/.github`, folder `brand/figures/`, commit `06f1959`, merged to that
repository's `main` in PR #1) whose one colour rule is that the accent marks a range
(the engine's interval) and nothing else. The engine had no chart style at all, so every
figure the team draws would pick its own colours, and Phase 3 is about to produce the first
figures that show the engine's answer as an interval.

Before anything was changed, the engine was surveyed for what draws charts today:

| Producer | Where | Regenerable | Touched here |
| --- | --- | --- | --- |
| `scripts/pipeline_health.py::render_svg`, publishing `health/progress.svg` on `calibration-data` | `main` | Yes, deterministic, golden-tested | No: recoloured, then reverted (see "B" below) |
| `generate.py::burnup_svg` and `index.html` | orphan branch `phase-3-dashboard` | Yes, daily scheduled refresh | No (not on `main`; see Follow-ups) |
| `analysis/report/template.html` (d3) and `build_page.py`, the two Turkish advisor report pages | PR #111's branch only | Yes, from JSON | No (dated records of published versions, unmerged) |
| Three inline SVG diagrams in `docs/advisor/2026-09-09-akba-brief/01..03` | `main` | No, hand-written | No (dated record of a sent brief) |
| 66 PNGs under `docs/evidence/` | `main` | No | No: they are terminal screenshots of verification runs, not charts |

No branch of the engine imported matplotlib or plotly (`git grep` over every `origin` branch
except the two `calibration-data` branches, which hold data only). Mert decided on 2026-10-16
to vendor the kit now, because a matplotlib figure is coming this phase (A), and to try the
brand's roles on the one chart on `main` (B). B was built and then reverted the same day on
his call; this change ships A alone. No GitHub issue covers figures or the brand, so this
change has no linked issue.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/figures/superconducted_figures.py` | The brand's chart helper (`use`, `band`, `crisp`, `measured`, `series`, `band_handle`, `mono_ticks`), byte-identical to the typed version in SuperconducTED/.github#3 (commit `3ff5e86`). |
| `src/superconducted/figures/__init__.py` | The engine's only code here: re-exports the helper and allows the chosen palette (Cryostat) alone. |
| `src/superconducted/figures/roles.json` | Every named chart colour per palette and mode, byte-identical to the brand's file (unchanged since `06f1959`). |
| `src/superconducted/figures/styles/superconducted-cryostat.mplstyle` | The Cryostat light-ground matplotlib style, byte-identical to the brand's. |
| `src/superconducted/figures/styles/superconducted-cryostat-dark.mplstyle` | The Cryostat dark-ground style, byte-identical to the brand's. |
| `pyproject.toml` | New optional extra `figures = ["matplotlib>=3.8,<4"]`; the same requirement added to `dev`. |
| `requirements-dev.txt` | Pins `matplotlib==3.11.2`, the version the brand's style checks ran on. |
| `tests/test_figures.py` | 50 tests: all four vendored files pinned by sha256 and no unpinned file beside them, the re-exports being the brand's own functions, the style loading silently, every role's look and guard, `mono_ticks`, and a silent font fallback. |
| `docs/implementations/2026-10-16-brand-chart-style/` | The example figure (light and dark) and the script that renders it. |
| `docs/numerical-claims.md` | NC-021 (test-suite size) re-measured, in a separate docs-only commit that names the commit it measured. |

`scripts/pipeline_health.py`, `tests/test_pipeline_health.py` and the golden
`tests/fixtures/pipeline_health/expected/progress.svg` end the branch byte-identical to `main`.

## Implementation approach

### A. The kit, vendored as `superconducted.figures`

All four of the kit's files are copied byte for byte from the brand repository (`git show
3ff5e86:brand/figures/<path>`), and `tests/test_figures.py::TestVendoredFiles` pins each one's
sha256 and fails if any other file appears beside them, so a hand edit fails CI. The brand's
own rule is that `styles/` and `roles.json` are generated, never edited; a change belongs in the
brand repository and is re-vendored here.

The helper went across unchanged because the brand's copy was first annotated for this:
SuperconducTED/.github#3 (commit `3ff5e86`, on top of the brand's `main`) adds type
annotations, so the file passes `mypy --strict` here (its home is `src/superconducted`, in
mypy's `files`), and tells a `Figure`, an `Axes` and an iterable of `Axes` apart with
`isinstance`; the brand's 46 style checks pass before and after it with all 26 demos
byte-identical. Until #3 merges, this copy follows that PR's head; if review changes the
helper, re-vendor it and update the pin.

The styles keep the brand's palette names (`superconducted-cryostat.mplstyle` and
`-dark`), which is where the helper's `style_path` looks. The package's `__init__.py` is the
engine's only code: it re-exports the helper's functions (the same objects, a test checks
identity) and wraps `use` and `style_path` so that only the identity's chosen palette is
accepted. `PALETTES` is `("cryostat",)`; asking for one of the five other brand options raises
`ValueError` before anything is applied. Messages from inside the helper name it as the brand
does (`call superconducted_figures.use(<palette>) first`).

Contract (unchanged from the brand): `use(palette=None, dark=False)` applies the style
globally (`plt.style.use`) and selects the roles; `band`, `crisp`, `measured`, `series` and
`band_handle` raise `RuntimeError` before it. Each drawing helper returns its artist, forwards
extra keyword arguments to matplotlib, and raises `TypeError` on a colour keyword (`color`,
`c`, `facecolor`, `edgecolor`, `fc`, `ec`, `markerfacecolor`, `mfc`), because the colour is the
role. `series(n)` raises `ValueError` past the six-colour sequence instead of cycling.

Usage:

```python
import matplotlib.pyplot as plt
from superconducted import figures as scf

scf.use()                                   # Cryostat, light ground; dark=True for dark
fig, ax = plt.subplots()
scf.band(ax, cycles, lower, upper, label="Engine interval")
scf.crisp(ax, cycles, snapshot_value, label="Single snapshot (frozen)")
scf.measured(ax, cycles, values, label="Measured")
ax.legend()
scf.mono_ticks(fig)
fig.savefig("figure.png")
```

The brand's README (`brand/figures/README.md` at `06f1959`) holds the rules a figure author
needs: what each role means, the do and don't list, the fonts and how to install them.

### B. The pipeline-health SVG: tried, then kept as it was

`render_svg` was recoloured to the Cryostat roles (commit `3285755`): `text` for headings and
figures, `text_secondary` for labels and floor ticks, `ink` for every data mark, `grid` for the
empty track and unfired poll hours, and no accent, because the dashboard shows no interval. It
changed colours only (an element-by-element comparison found the same 120 elements and 12
text nodes, and `metrics.json` byte-identical) and every pair cleared the brand's contrast
floors. Mert reverted it the same day (commit `c163501`): the original green progress and
fired hours and blue daily bars read better as status than ink and grey do, and the brand
defines no status colours to replace them with. The revert restores the three files exactly as
they are on `main`.

### The example figure

There was no matplotlib figure to restyle, so there is no "before" for A. The example shows
the three roles and a per-qubit panel on **illustrative data from a fixed seed**, labelled as
such on the figure; no number on it is a measurement, so it needs no row in
`docs/numerical-claims.md`.

![Example, light ground](2026-10-16-brand-chart-style/example-light.png)

![Example, dark ground](2026-10-16-brand-chart-style/example-dark.png)

## Mathematical / Statistical details

**The band tint**, which the helper draws, is a solid colour, not an alpha: per sRGB channel
`t = (1 - a) * ground + a * accent`, rounded to 8 bits, with `a = 0.20` measured by the brand
between a colour-vision floor (0.19 light) and a contrast ceiling (0.23 light). Contrast is the
WCAG 2.x ratio `(L_hi + 0.05) / (L_lo + 0.05)` of relative luminances; the brand gates text at
4.5:1 and marks at 3:1. Both derivations are in the brand README ("The band tint rule") and are
checked by its `check_styles.py`; this change vendors their results and computes nothing.

## Design decisions

- **A copy over a dependency on the brand repository.** A git submodule or a pip install
  from the `.github` repository would make the engine's CI depend on another repository's
  branch. A copy pinned by hash keeps CI self-contained and makes drift a visible test failure.
- **Inside the package, not under `scripts/` or `docs/`.** Team figures will be drawn from
  notebooks, scripts and future report builders alike; `from superconducted import figures`
  works from all of them, and the wheel ships the data files (checked: `pip wheel .` carries
  `roles.json` and both styles).
- **Type the brand's helper and vendor it verbatim, over a typed engine-only copy or a
  mypy exclusion.** Excluding the module would leave the one file team figure code imports
  unchecked. A typed copy kept here (this change's first version) differed from the brand's
  in four hand-maintained ways, so a brand fix would reach the engine only if someone ported
  it. Annotating the source (SuperconducTED/.github#3) lets all four files be pinned by hash;
  the engine owns a thin `__init__.py` and nothing else (Mert's choice, 2026-10-16).
- **Cryostat only, enforced by the shim rather than by trimming the helper.** The other five
  palettes are the record of a decision already taken; shipping their styles would invite
  their use. Only Cryostat's two styles are vendored, and the wrapper refuses the others
  before matplotlib is touched, so the helper itself stays the brand's file.
- **matplotlib as an optional extra, also in `dev`.** The engine itself draws nothing, so
  runtime users do not pay for matplotlib. Listing it in `dev` too (and pinning it in
  `requirements-dev.txt`, which CI installs) means `tests/test_figures.py` imports it
  unconditionally: a missing matplotlib is a loud failure, not 50 silently skipped tests.
- **Status dashboards keep their own status colours (Mert, 2026-10-16).** The brand's chart
  roles describe a range, a snapshot and a measurement; a health dashboard's colours say
  "done", "fired" and "missed", which the brand has no colours for yet. Drawing those in ink
  and grey kept the brand's rule but lost the reading, so the pipeline-health SVG stays as it
  is on `main`.

## Verification

All on the pinned stack (Python 3.12.10, a fresh venv from `requirements.txt` and
`requirements-dev.txt`, then `pip install -e . --no-deps`, the CI recipe):

- `python -m pytest tests/test_figures.py -q`: 50 passed.
- `python -m pytest tests/ -q`: see NC-021 for the size and the commit it was run at.
- `ruff check .`, `ruff format --check .`, `mypy --strict`: clean.
- `git diff fec055c -- scripts/pipeline_health.py tests/test_pipeline_health.py
  tests/fixtures/pipeline_health` is empty: the dashboard is untouched.
- **The new guards can fail.** Each was broken on purpose and went red: one byte of
  `roles.json`; a solid crisp line; `mono_ticks` setting `sans-serif`; dropping `ec` from the
  colour-override guard; disabling the band's bound check; ringing measured points in ink;
  one byte of the vendored helper; an unpinned file beside the kit; `band` wrapped instead of
  re-exported; and `use()` without its palette refusal.
- **Vendoring the typed helper changed no drawing.** The example figure re-rendered with
  the verbatim helper is byte-identical to the one rendered with the earlier typed copy.
- **Nothing outside `superconducted.figures` needs matplotlib.** In a second venv built the
  way the `calibration-health` poll job builds it (`requirements.txt` only, then
  `pip install -e . --no-deps`), matplotlib is absent; `import superconducted` and
  `import superconducted.calibration.poller` load without it, `superconducted-poll --help`
  runs, and `import superconducted.figures` fails with a plain `ModuleNotFoundError` naming
  matplotlib.
- **The font fallback is silent.** With the style applied and the brand fonts absent (this
  machine), a full figure renders with no `matplotlib` warning; forcing a missing font
  produces `findfont` warnings, which the test would catch.
- Rerun the example: `python docs/implementations/2026-10-16-brand-chart-style/render_example.py`.

## Follow-ups

- Done the same day: `phase-3-dashboard` (orphan branch) drew its burn-up line in the
  accent; its generator now takes the Cryostat roles (`6d68e32` on that branch, pushed on
  Mert's word; the daily run regenerates the page). It kept its own status colours, for the
  same reason as the decision above. The brand's helper was annotated in
  SuperconducTED/.github#3, which is what lets this copy be verbatim.
- When SuperconducTED/.github#3 merges, nothing changes here unless review changed the
  helper; if it did, re-vendor and update the pin in `tests/test_figures.py`.
- If the brand defines status colours, the pipeline-health SVG and the phase-3 dashboard are
  the two places to apply them.
- When the first Phase 3 figure is drawn (the interval report of #64 is the natural first
  user of `band`), it should use `superconducted.figures`; any number it shows needs its row
  in `docs/numerical-claims.md`.

## Related docs

- Brand kit: `SuperconducTED/.github`, `brand/figures/README.md` (roles, rules, fonts,
  validation), merged to that repository's `main` in PR #1 (`06f1959`); the typed helper in
  PR #3 (`3ff5e86`), with its record `docs/implementations/2026-10-16-type-the-chart-helper.md`.
- `docs/implementations/2026-09-05-pipeline-health-dashboard.md` (the dashboard this change
  leaves as it is).
- ADR-004 in `docs/decisions.md` (pinned requirements files, loose ranges in
  `pyproject.toml`).
- `docs/numerical-claims.md`, Rule 6 and NC-021.
