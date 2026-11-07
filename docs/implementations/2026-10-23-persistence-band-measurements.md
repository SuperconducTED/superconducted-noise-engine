# 2026-10-23: persistence-band-measurements

## Problem / Motivation

The novelty check (`docs/findings/2026-10-23-novelty-check-q1-article.md` §4) said the
engine's drift claim is decided by one comparison, a fuzzy band against a non-fuzzy band over
recent snapshots, and that the comparison's bar could be measured before any model exists. The
gates record (`docs/findings/2026-10-23-adr-015-what-an-interval-needs.md` §3, §5) added two
facts the article cannot avoid: whether drift is state-dependent, and whether a fresh
chip-uniform channel costs more than a stale per-qubit one. Mert asked for the three
measurements to be run now, as the persistence-baseline PR named in
`docs/roadmap/2026-10-23-issue-64-pr-a-plan.md` §4. Nothing in the repository had measured any
of them; File 03 (#84 comment 5970300012) had a provisional whole-archive persistence figure
with no split and no scoring-row rule.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/evidence/persistence-band/README.md` | Pre-registered protocol (§2, committed before the run), its pre-run amendment (§2.1), the results (§3), caveats and the desktop runbook. |
| `docs/evidence/persistence-band/measure_persistence_band.py` | The measurement: archive walk at a pinned ref through `git show`, distinct states by `qubit_digest`, ADR-027 targets through `training/targets.py`, as-of pairing by files, persistence and rolling bands, heteroscedasticity oracle, homogeneity versus staleness; writes `results.tsv`, `pairs.tsv`, `summary.json`. Ruff-clean on 0.15.12; outside mypy's configured scope. |
| `docs/evidence/persistence-band/results.tsv`, `pairs.tsv`, `summary.json` | The run's output at the pinned ref: 476 result rows, 722 test pairs. |
| `docs/numerical-claims.md` | Four rows appended, NC-080 to NC-083, one per conclusion, in the dated-anchor form Issue #92 proposes. |
| `docs/implementations/2026-10-23-persistence-band-measurements.md` | This record. |

No source, test or ADR status changed. The branch stacks on PR #121's branch so the register
ids continue from NC-079; the PR retargets to `main` once #121 merges.

## Implementation approach

Documentation-first in the literal sense: the protocol was written and committed
(`3ed69e2e`), reviewed, amended in an append-only block and committed again (`ed746536`), and
only then run. The script reuses the repository's own definitions wherever one exists, so no
quantity here can drift from the ledger's: the archive walk and `git show` reader from
`scripts/init_error_analysis.py`, the distinct-state digest from
`scripts/canonical_snapshot_digest.py`, the loader's unit validation through
`calibration/loader.py::load_snapshot` (fed from a temporary file in the system temp
directory, never the scratchpad, because of the path-length limit), and the ADR-027 target
with its ordered skip rules from `training/targets.py`. The script asserts the distinct-state
count against `health/state-index.tsv` at the ref and refuses to continue if the zero-width
band covers anything on `change` rows (the L-009 mutation check applied to coverage).

## Mathematical / Statistical details

Let `y_q(t)` be the ADR-027 per-qubit target at state time `t` and `y(t)` its mean over
usable qubits. For horizon `H`, the future value is taken as of `t + H`: the latest archived
file at or before that time, accepted only if within 6 hours of it. Relative drift is
`d = y(t + H) / y(t) - 1`.

- **Persistence band.** `[y(t)(1 - r), y(t)(1 + r)]`. The scale `r` is the smallest value
  with training coverage at least 0.80 on rows where `y` changed, which is the order
  statistic of `|d|` at rank `ceil(0.8 n)` (`numpy.quantile(..., method="inverted_cdf")`).
- **Interval score.** Gneiting and Raftery (2007, §6.2, eq. 43) at `alpha = 0.2`, divided
  by `y(t)`: `2r + (2 / alpha) max(0, -r - d) + (2 / alpha) max(0, d - r)`. Proper for the
  central 80% interval, so a band fitted to 80% is scored at its own level. For a two-sided
  band with unequal relative half-widths the same with `r_lo`, `r_hi`.
- **Rolling percentile band.** The 10th and 90th percentiles of `y` over the distinct
  states in the trailing 7 or 30 days, at least 5 states; no fitted parameter.
- **Heteroscedasticity oracle.** For a binning `b(t)`, per-bin 80th percentiles fitted on
  the test rows themselves give the narrowest band constant within bins that covers 80% in
  every bin; its row-weighted mean width over the constant band's own test-fitted width
  bounds from below the width ratio any band that varies only through `b(t)` can reach at
  equal coverage. The out-of-sample conditional band uses training-fitted per-bin scales.
- **Bootstrap.** 1,000 resamples of training rows per fitted scale, `SeedSequence(84)`,
  5th and 95th percentiles. Rows are temporally correlated (NC-012), so these intervals are
  optimistic.
- **Homogeneity versus staleness.** `yhat` is the chip mean at `t` (fresh, uniform) or the
  qubit's own value as of `t - D`. Errors are `|yhat / y_q(t) - 1|` and `|yhat - y_q(t)|`;
  the relative form is a denominator artefact for lambda, which approaches zero at the
  `T_2 = 2 T_1` boundary ADR-027 admits, so the target-unit form is co-primary.

## Design decisions

- **Protocol before numbers, amendments append-only.** Four definitions were tightened
  after review and before the run (as-of by files, target-unit co-primary, row-weighted
  widths and the constant band's own oracle, `inverted_cdf`); the original wording stands in
  §2 and the corrections in §2.1, so a reader can see what moved and that no number existed
  yet. Alternative rejected: editing §2 in place, which would have hidden the review.
- **Scoring rows are change events.** A zero-width band scores 0.135 on `all` rows at 24 h;
  coverage on `all` is a statement about the clock, not the band (L-026). `all` is reported
  only to show that.
- **The stronger baseline replaces the weaker one, and says so.** The decision rule named the
  constant persistence band. The rolling 30-day percentile band beat it on interval score in
  all four cases, with no fitted parameter, so NC-081 records it as the bar. Keeping the
  weaker bar because it was pre-registered would have been pre-registration used against its
  purpose.
- **One script, evidence folder, not `scripts/`.** It is an analysis at a pinned ref, not a
  tool the pipeline calls; keeping it beside its README and output keeps the audit trail in
  one place and outside mypy's strict scope. Alternative: `scripts/`, like
  `feature_distribution.py`; rejected for this PR because nothing imports it.
- **Target space only.** The resolution question is a different measurement (gates record
  §4) and needs Aer; mixing it in would have made the first numbers depend on PR #79.

## Verification

- Reproduce (desktop or laptop), from the repository root with the pinned interpreter:
  `PYTHONPATH=src:. python docs/evidence/persistence-band/measure_persistence_band.py --repo . --ref 5828b4a2 --out /tmp/pb`
  (Windows: `PYTHONPATH=src;.`). `/tmp/pb/summary.json` must equal the committed
  `summary.json`; `results.tsv` must match to the printed precision.
- The script's own gates: `distinct_states == state_index_distinct == 924`; zero-width band
  coverage on `change` rows exactly 0.0 at both horizons (it aborts otherwise).
- Lint: `ruff check docs/evidence/persistence-band/measure_persistence_band.py` and
  `ruff format --check` on the same file pass on ruff 0.15.12.
- Cross-check against File 03 M3 (24 h, gamma, whole archive, no split): File 03 gave ±11.2%
  at 80%; the training-period fit here gives 0.1049 with a 90% interval reaching 0.1119.
  Same size, as expected; the difference is the split and the row definition.
- Not verified: Burak's desktop reproduction (owed; the figures stay provisional until it
  runs); any outcome-space statement.

## Related docs

- `docs/evidence/persistence-band/README.md` (protocol, results, runbook)
- `docs/numerical-claims.md` NC-080 to NC-083; NC-012, NC-041, NC-069
- `docs/findings/2026-10-23-novelty-check-q1-article.md` §4;
  `docs/findings/2026-10-23-adr-015-what-an-interval-needs.md` §3, §5
- `docs/roadmap/2026-10-23-issue-64-pr-a-plan.md` §4
- Issues #64 (FR-9, NFR-8 as amended by #84 comment 5970300012), #104; ADR-013, ADR-016,
  ADR-027; PR #121 (base of this branch)
