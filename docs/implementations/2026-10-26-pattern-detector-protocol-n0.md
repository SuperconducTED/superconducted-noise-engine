# 2026-10-26: pattern-detector protocol and row count (task N0 on #110)

## Problem / Motivation

The lead adopted the pattern detector on 2026-10-26 (audit §4.7; #110 comment 6412965244) and
amended the phase-4 plan's §4 so that its protocol may be written before gate L1. Task N0 is that
protocol: the question, unit, label, features, null, clauses, outcome table and the minimum rule,
committed before any row exists, followed by the count that the minimum rule needs. The
discipline is the one that held on 2026-10-23 (protocol commit, then the run from the committed
script, corrections as dated amendments) and it matters here because the label is built from the
disagreement itself, so a carelessly chosen null would have endorsed a pattern that is the label's
own arithmetic.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/evidence/pattern-detector/README.md` | New: the pre-registered protocol (sections 1 to 7), committed alone with an empty section 8; section 8 then receives the counts in a dated commit. |
| `docs/evidence/pattern-detector/count_events.py` | New: self-contained archive walk (`git show` at a pinned ref, distinct states by `qubit_digest`, the state-index reproduction guard), the event, level and label logic of the README, the counts section 6's decision tree needs at both deltas, the null's parameters, and a synthetic self-test; writes `counts.json`, `counts.tsv`, `rows.tsv.gz`. |
| `docs/evidence/pattern-detector/counts.json`, `counts.tsv`, `rows.tsv.gz` | New: the record run's outputs at the ref named in README section 8 (laptop, provisional). |
| `docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md` | §4.8 appended: the lead's direction after the adoption (he takes the offline half of #125 first; the neural model and the fuzzy system start later today; the team reproduces at the end; builder mode next session) and what it changes in the tables. |
| `docs/implementations/2026-10-26-pattern-detector-protocol-n0.md` | This record. |

## Implementation approach

**Order.** The README was committed first (`49256efe`) with section 8 empty. The script was then
written, self-tested on a synthetic archive, linted, and run once against the archive at a pinned
`calibration-data` ref with the collection pickled to the scratchpad; the committed script was
re-run from that pickle and its outputs compared with the first run's before they were committed,
so the record comes from the committed code. Section 8 was appended with the counts and the §6
branch they select.

**The archive walk** replicates, rather than imports, the helpers of `measure_persistence_band.py`
(PR #123's branch, not on `main`): `load_files` reads every `ibm_fez` file at the ref with the
`git show` helpers of `scripts/init_error_analysis.py`, parses it with
`superconducted.calibration.loader.parse_snapshot` (no temp file), keeps `log T1` per qubit and the
`T1` dates, and sorts by `properties.last_update_date`; `distinct_states` takes the first file of
each `qubit_digest`; the count of distinct states must equal the `is_new_state = 1` rows of
`health/state-index.tsv` at the same ref or the script stops. `recal_times` keeps PR #123's 20%
date rule for the sweep count.

**Events, level, label** follow README §2 exactly: an event is a value change of `log T1_q`
between consecutive files; the level is the state-weighted mean of `log T1_q` over the distinct
states strictly inside `(t - 30 d, t)` (own state excluded), present only with at least 5 states
and 3 distinct values; a row is an event with `|d| >= delta`; the label compares the median of the
next `k = 5` events' values with the reading and the level; fewer than `k` successors means
censored. Both deltas (0.37 and the fallback 0.25) are counted in one run so the §6 tree can be
applied without a second look at the data. `rows.tsv.gz` holds the labelled rows at `delta = 0.37`
as N1's input.

**Nothing is scored against the labels.** The null's parameters (pooled training `rho`, `q`, the
per-qubit robust `sigma_q`) are computed from increments, not from labels; the null forecast
itself and every Brier score belong to N1.

## Mathematical / Statistical details

The label, the null and the clauses are stated in the README (§2, §4, §5) and in the audit's
implementation doc (`2026-10-26-phase-4-pass-fail-audit-and-nn-amendment.md`, Mathematical
details). What N0 adds (and one correction: README §7 amendment 1 re-cites `delta`'s 0.37 to NC-085's
shrinkage-band half-width, not NC-084, after the advisor-brief session's check):

- **The local-level drift term in the null.** With `L_j = mu_j + e_j`, `mu_j = mu_{j-1} + eta_j`,
  `Var(e) = sigma_q^2`, `Var(eta) = q sigma_q^2`, the lag-1 autocorrelation of increments is
  `rho = -1 / (q + 2)`, so `q = -1 / rho - 2`, floored at 0 when `rho <= -0.5`. The pooled
  training `rho` fixes `q`; NC-084's -0.49 gives about 0.04.
- **The robust per-qubit scale.** An increment between two events is `e_{j+1} - e_j` plus a drift
  term of order `sqrt(q) sigma_q`; ignoring the small drift, its variance is `2 sigma_q^2`, so
  `sigma_q = 1.4826 · MAD(increments) / sqrt(2)`, the MAD because the dips this protocol labels
  would inflate a standard deviation. Qubits with fewer than 20 training increments get no scale.
- **The level-estimate error** entering the null forecast is `sigma_q / sqrt(n_i)` with `n_i` the
  window's distinct values, the standard error of a mean of `n_i` independent readings around the
  level; it is small (about a fifth of `sigma_q` at `n_i = 30`) and kept for honesty.
- **The minimum rule's arithmetic.** Ten positives per parameter for a logistic model with
  `d + 1` parameters gives 150 positives at `d = 14` and 60 at `d = 5`; the day bootstrap needs
  about 30 blocks to give a 90% interval shape that does not depend on two or three days; 30 test
  positives keep a 0.10 skill gap from being decided by a handful of events.

## Design decisions

- **Replicate, do not import, the PR #123 helpers.** This branch must run from `main` plus its own
  files; a `sys.path` reach into another branch's folder would break the moment the branches merge
  in a different order. The definitions are the same and named with their source.
- **Both deltas in one run.** The fallback is a pre-stated branch; counting it in the same run
  removes any temptation to re-run after seeing the first count.
- **`parse_snapshot` on the dict**, not a temp file: the loader exposes it and the predictability
  script's temp-file detour was only because of an older API.
- **Self-test before the walk**, as the 2026-10-24 lesson says (a synthetic archive caught a loader
  issue then; here it caught the synthetic archive's own too-few distinct values).
- **Re-run from the cache with the committed script** rather than re-walking: the walk is about ten
  minutes, the cache about a minute, and the comparison is byte-for-byte.
- **The lead's mid-turn direction** is recorded in the audit (§4.8) rather than by editing the
  rows it changes, so the tables stay a dated reading of 09:27 UTC and the change is visible.

## Verification

- Self-test (no git, no archive):

  ```bash
  PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/evidence/pattern-detector/count_events.py --selftest
  ```

  expected: `selftest ok: rows=8 y0=1 y1=0 rho=...`.

- Reproduce the counts at the record ref (about ten minutes on the laptop; replace `<ref>` with
  the sha in README §8; a cache path makes a second run take about a minute):

  ```bash
  PYTHONPATH="src;." C:/t/pin125/Scripts/python.exe docs/evidence/pattern-detector/count_events.py --repo . --ref <ref> --out <dir> --cache <dir>/collection.pkl
  ```

  then `diff <dir>/counts.tsv docs/evidence/pattern-detector/counts.tsv` is empty.

- Lint: `C:/t/ruffpin/Scripts/ruff.exe check docs/evidence/pattern-detector/count_events.py` and
  `ruff format --check` on the same file report nothing.

- No em dash in the new files: count `chr(0x2014)` in Python (a Git Bash grep with the bash escape for U+2014 tests the literal text, not the character) and expect 0.

## Related docs

- `docs/evidence/pattern-detector/README.md`
- `docs/audits/2026-10-26-phase-4-plan-pass-fail-audit.md` §4.3 to §4.8
- `docs/implementations/2026-10-26-phase-4-pass-fail-audit-and-nn-amendment.md`
- `docs/evidence/predictability/README.md`, `docs/evidence/persistence-band/README.md` (PR #124's
  and PR #123's branches)
- Issue #110 (comment 6412965244), Issue #125, PR #124 (`bf4c54e2`)
