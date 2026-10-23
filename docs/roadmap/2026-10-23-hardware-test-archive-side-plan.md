# #125 archive side: the four predictors per qubit, computed from the archive at submission time

**Date**: 2026-10-23 · **Author and owner**: Mert Efe Şensoy · **Status**: plan before code, per
the engineering standard; the code lands in the same PR as this plan's implementation record ·
**Design it implements**: `docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md` §2 (on
PR #124's branch until that merges) · **Issue**: #125

## 1. What this half does, and what it leaves to the offline half

The hardware test compares four predictors of a qubit's calibration quantities at submission
time `t_s`. This half produces them from the archive and nothing else; it runs no circuit,
builds no noise model and submits nothing. Its output is a table Burak's offline half reads
to build the Arm A decay predictions and the Arm B noise models, and that the scoring reads
after the run.

Per qubit `q` and per quantity in {`T1`, `T2`, `readout_error`, `prob_meas0_prep1`,
`prob_meas1_prep0`}:

| Column | Definition | Source of truth |
| --- | --- | --- |
| `reading` | the value in the latest archived **file** with `last_update_date <= t_s` (files, not states: a state is a first occurrence, and the lookup of "the current value" is over files, lesson L-027), or the live `backend.properties()` document captured at `t_s` when one is supplied | design §2 row `reading` |
| `level` | geometric mean of the quantity over the distinct device **states** in the trailing 30 days (`(t_s - 30 d, t_s]`), finite and positive values only, at least 5 states | design §2 row `level`; the persistence README's level definition |
| `band_lo`, `band_hi` | 10th and 90th percentile of the same window of states, `numpy.quantile` default linear interpolation: this is NC-081's rolling-band object. The `inverted_cdf` method belongs to the *fitted scales* of the persistence and predictability runs and is not used here | design §2 row `band` |
| `n_window` | states that contributed | provenance |
| `n_distinct` | distinct finite values of the quantity for that qubit over all states at the ref up to `t_s`; the "20 re-measurement events" floor of design §3 reads this column | design §3 |
| `log_disagreement` | `log(reading) - log(level)`, the Arm A selection statistic for `T1`; `NaN` when either side is missing or non-positive (qubit 72's `T1`) | design §3 |

A second mode, `--mode execution`, emits only `reading` as of a later time `t_execute`, from
the latest archived file at or before it or from a supplied live document: that is the
`reading_at_execution` control, computed after the fact.

**Provenance of a live document.** The archive's documents are reproducible from the ref; a
live `backend.properties()` document is not. When one is supplied it is copied verbatim into
the output directory as `live-properties-<t_s>.json`, its SHA-256 is written to
`manifest.json`, and it enters the window as a new state (its qubit-block digest will differ
from every archived one) with time `t_s`.

The channel itself (ADR-027's amplitude damping, the readout assignment matrix) is built by
the offline half from these raw quantities, so Arm A and Arm B share one noise model and this
half never duplicates `channels/kraus.py` or `training/targets.py` logic.

## 2. Reuse, so there is one definition of each thing

- Archive walk at a pinned ref: `training.dataset.iter_archive` and `resolve_archive_ref`
  (PR #113, now on `main`). No new `git show` code. `iter_archive` yields every backend's
  documents in path order, so documents are filtered on `backend`, sorted by
  `(last_update_date, path)`, and only then deduplicated into states; documents after `t_s`
  are dropped and counted; documents `parse_snapshot` rejects are counted and skipped, as the
  builder does, never fatal. The manifest records the full SHA `resolve_archive_ref` returns.
- Distinct device states: `training.dataset.qubit_block_digest`, the NC-012 unit, applied
  incrementally in `last_update_date` order (first file per digest is the state).
- Parsing and units: `calibration.loader.parse_snapshot` (SI seconds for `T1`, `T2`,
  dimensionless readout). Output is in SI seconds and dimensionless, stated in the header.
- Time: `properties.last_update_date`, UTC, as everywhere else in the repository.

## 3. Selection helpers, so the pre-registration can cite a command

- `--select-discriminating K` (default 8): the `K` qubits with the largest
  `|log_disagreement|` for `T1` among qubits with at least 20 distinct `T1` values across the
  whole archive at the ref (the "20 re-measurement events" rule of design §3). Written to
  `selection.json` with the statistic per chosen qubit.
- `--propose-controls K` (default 4): the `K` qubits whose whole-archive standard deviation of
  `log T1` is nearest the median over qubits, excluding the discriminating set. Proposed once,
  before the first job, and then frozen in the pre-registration commit; the script proposes,
  the commit decides.

## 4. Files

| File | Change |
| --- | --- |
| `scripts/hardware_test_predictors.py` | new: the core as pure functions over an iterable of `(path, doc)`, plus a CLI that wires `iter_archive`; mypy strict, ruff |
| `tests/test_hardware_test_predictors.py` | new: synthetic archive documents in the real schema; no git, no network |
| `docs/implementations/2026-10-XX-hardware-test-archive-side.md` | after the code, per template |
| `docs/evidence/hardware-reading-vs-level/` | created by the QPU side when job 1 runs, not here; this half's dry output is written to a scratch directory and not committed until a job exists |

Not touched: `src/` (nothing here belongs in a package module yet; if the offline half needs
the functions importable from `src`, that move is a one-line follow-up under `training/`,
Mert's area), LOCKED modules, the harness, the data branch.

## 5. Tests, written first

- `level` is the geometric mean of the window's positive values; a non-positive value is
  excluded, not zeroed.
- The window excludes states older than 30 days and includes the state at exactly `t_s`.
- `reading` is the latest state's value; a supplied live document overrides it and joins the
  window as its newest state.
- Fewer than 5 window states gives `NaN` level and band with `n_window` recorded, never a
  silent number.
- Two documents with the same qubit block are one state; the earlier file is the state's time.
- `--mode execution` returns only `reading` and ignores the window.
- Discriminating selection respects the 20-distinct-values floor and orders by
  `|log_disagreement|`; the controls proposal excludes the discriminating set and picks the
  median-scatter qubits.
- The CLI writes `predictors.tsv`, `selection.json` and `manifest.json` (ref SHA, `t_s`,
  window, counts, Python and numpy versions) and exits non-zero on an unreachable ref.

## 6. Verification

`pytest tests/test_hardware_test_predictors.py -v`; `ruff check .`; `ruff format --check .`;
`mypy --strict`. A dry run against `calibration-data` @ `5828b4a2` with
`--at 2026-10-23T09:34:56Z` is checked on three numbers, not by eye. (1) `n_window` counts a
qubit's *positive finite* values among the window's states, so it equals the window's state
count only where no value is missing; the check is that every qubit's `n_window` equals that
count **except where a value is missing, and the exceptions are listed** (an `n_window` that
simply echoes the state count for every qubit is a tautology, not a test; the listing is what
can fail). (2) For every qubit with a `level`, `band_lo <= level <= band_hi` for `T1` (the
geometric mean of a sample lies between its 10th and 90th percentiles unless the sample is
tiny or degenerate; any violation is printed). (3) The eight selected qubits all have
`n_distinct >= 20`. Amended after the run, before review: the run's own result for (1) was
264 for all 156 qubits with no exceptions, because qubit 72's `T1`, absent for most of the
archive, has been published again throughout the last 30 days; the design's §3 sentence that
IBM omits it needs that correction. No number is registered from this half alone; the dry
output is not committed.

## 7. What this plan does not decide

The decay model, the layouts, the shots and the scoring (offline half); the thresholds and the
four control qubits (the pre-registration commit); the budget (job 1's usage report); whether
readout's `level` should be corrected by the chip's current excursion (predictability README
§3.6a, a refinement noted for the design and not adopted here).
