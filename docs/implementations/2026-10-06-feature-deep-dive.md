# 2026-10-06: feature-deep-dive

## Problem / Motivation

On 2026-10-05 the lead showed Dr. Akba the first feature-pattern analysis
(`docs/roadmap/2026-10-05-feature-patterns-and-method.md`, findings P1 to P8). The direction
that came out of the meeting, in the lead's words recorded in the plan's as-of section, is to go
back to the collected feature data in depth before any strategic decision, so that the paper
starts from the root of the problem. On 2026-10-06 he asked for exactly that: every unique
snapshot, every feature, its characteristics, patterns, meaning, use cases, importance and its
effect on the others, researched from several perspectives and documented, with subagents used
economically and without overlapping scopes.

The first analysis read a subset of fields (`T1`, `T2`, readout, `sx`, `measure`, `measure_2`,
`cz`, `rzz` and a few lengths). Large parts of the archive had never been analysed:
`init_error`, `measure_2` in depth, the assignment probabilities' dynamics, every gate length,
the measurement thresholds, the reset and measure-reset durations, the whole `general` section
(`jq`, `zz` per coupler, `lf` layer-fidelity chains), the top-level `target` and
`configuration` sections, the calibration schedule, spatial and topology effects, change
points, nonlinear and lead or lag dependence, and the distinct-state structure. The open root
question (what the large non-persistent component of every series is) had no shared instrument.

This change is data understanding and documentation only. It builds no model, takes no
strategic decision, changes no ADR, and records no approval: A1 to A9 and Dr. Akba's answers
remain open.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/findings/2026-10-06-feature-deep-dive/analysis/extract_cache.py` | One pass over every `ibm_fez` snapshot blob at a pinned ref into a field cache: per-field value and stamped-date arrays per qubit, per directed coupler and per `general` entry, plus per-file provenance arrays and a `meta.json`. |
| `docs/findings/2026-10-06-feature-deep-dive/analysis/ddload.py` | Read-only loader (one memory-mapped field at a time), the two event rules (measured, imported from `scripts/feature_patterns.py`; value-only for assembly-stamped and configuration-like fields), placeholder masks, the shared variogram and the results-JSON provenance header. |
| `docs/findings/2026-10-06-feature-deep-dive/analysis/data_layer/profile_cache.py` | Mechanical profile of every field (coverage, values, date semantics, events, placeholders) and of the file-level structure. |
| `docs/findings/2026-10-06-feature-deep-dive/analysis/data_layer/identity_checks.py` | Record-by-record re-check of the duplicate identities and the readout arithmetic at the pinned ref, and a digest of the cache. |
| `docs/findings/2026-10-06-feature-deep-dive/analysis/data_layer/selftest_ddload.py` | Synthetic self-test of the event rules and the variogram. |
| `docs/findings/2026-10-06-feature-deep-dive/results/data-layer/*.json` | The profile and identity results every scope document builds on. |
| `docs/findings/2026-10-06-feature-deep-dive/01-data-layer.md` | The data dictionary: every field, its date semantics and event rule, the identities, the device-wide length changes, the file-level structure, the coverage caveat, the variogram, and the scope ownership table. |
| `docs/findings/2026-10-06-feature-deep-dive/02-coherence.md` to `07-cross-feature-dependency.md` | Six scope documents (coherence; readout and measurement; single-qubit gates; two-qubit gates and couplings; device, time and topology; cross-feature dependency), each with an appended verification section and inline verification markers. |
| `docs/findings/2026-10-06-feature-deep-dive/00-overview.md` | The synthesis: feature map, dependency map, root questions for the paper, data-quality rules, ranked unknowns, verification status per document. |
| `docs/findings/2026-10-06-feature-deep-dive/README.md` | Folder index. |
| `docs/findings/2026-10-06-feature-deep-dive/analysis/<scope>/*.py`, `results/<scope>/*.json` | The scripts behind every number of each scope document and their outputs (coherence, readout, gates_1q, gates_2q, device, cross). |
| `docs/findings/2026-10-06-feature-deep-dive/analysis/verify/<scope>/*.py`, `results/verify/<scope>/*.json` | The verifiers' independent re-computations, written from the loader without importing the owners' code. |

## Implementation approach

**Layer first, then fan out.** The lead's rule for this task was that the roughly 3 GB of
snapshot JSON is parsed once, inline, and every analysis reads a cache. `extract_cache.py`
streams the 1,760 blobs of the pinned ref through one `git cat-file --batch` process, writing
one request and reading its answer before the next (writing every request first deadlocks once
both pipes fill, which happened in an earlier session). It never checks the archive out. Every
record of every section is stored generically by its section, name and parameter, so no field
is silently dropped: the inventory in `meta.json` lists every key seen.

**Directed couplers, parsed names.** Two-qubit gate records keep both directions as separate
columns so the direction identity can be re-checked rather than assumed. `general` names such
as `jq_717` carry no separator; each is split every possible way and kept only when exactly one
split is an edge of the coupling map. All 352 names parsed uniquely.

**Date semantics decide the event rule.** The profile measures, per field, the share of records
whose stamp equals the document's `last_update_date`. Fields at 1.0 (thresholds, `zz`, `jq`,
`rz`, the measure and reset lengths) are re-stamped at assembly, so for them an event is a value
change. Lengths are value-only for a second reason: `readout_length` carries the readout stamp,
but its two device-wide changes happened in files where that stamp did not move.

**Disjoint ownership.** Six scope documents, each owning an explicit list of fields, one
document, one scripts folder and one results folder; the three cross-family links that would
otherwise be analysed twice are assigned (readout against `T1` decay to the readout owner, `sx`
against its coherence limit to the single-qubit owner, `cz`/`rzz` against their qubits to the
two-qubit owner, and `lf` against its chain to the device owner); the cross-feature owner covers
every other relationship. A cheaper verifier per document re-runs its load-bearing numbers and
tries to refute its interpretive claims, and one synthesis agent writes the overview.

**How the orchestration actually ran** (recorded because it differs from the plan):

| Run | Agents | Outcome |
| --- | --- | --- |
| 1 | 6 scope analysts (session model) piped into 6 verifiers, then 1 synthesis | All 6 analysts wrote their documents, scripts and results, then stopped at the account's usage limit before returning (about 2.6 million subagent tokens); no verifier or synthesis started. Documents 02 to 06 were complete on disk; 07 still had template placeholders for its summary, sections 4 and 7 and two figures. The work was committed as found (`4a85791`). |
| 2 | 1 finisher for 07, 6 verifiers (Sonnet, medium effort), 1 synthesis | The finisher completed 07 from its existing results (re-running its scripts, fixing a counting bug in `levels.py`, adding `summary.py`); 07's verifier and the synthesis ran. The five other verifiers were skipped by a defect in the orchestration script: a pipeline stage that returned `null` for the scopes needing no finisher dropped those items before the verify stage. The overview therefore said 02 to 06 were unverified (`d4a6421`). |
| 3 | 5 verifiers (Sonnet, medium effort), 1 overview reconciler | Verified 02 to 06; the reconciler revised the same-day overview to the verified state. |

Sixteen agents were launched against a planned thirteen. The three extra launches are run 1's
synthesis (started after the analysts failed, and itself stopped at the limit), run 2's finisher
and run 3's reconciler; all three follow from the two failures above.
Run 1's analysts were not re-run: their output on disk was complete, and every number in it
was later re-run by a verifier.

**Verification outcome.** In every scope the verifier re-ran all of the owner's scripts and
every results JSON reproduced field for field (only `measured_utc` differed; the re-run copies
in `results/` differ from the committed ones in that field alone). Each verifier recomputed the
document's load-bearing numbers with its own scripts; no headline number was refuted as a number.
Interpretive claims were weakened or refuted in every document, each marked inline, for example:
the `T1`/`T2` same-round correlation (0.70) is verified, but "a real change of the qubit" is
weakened to "shared between the two fits" (a common input to both experiments is not excluded);
readout's spatial "checkerboard" is mostly the lattice's degree classes; the "second calibration
within a day" p-values in 05 were pseudo-replicated and are refuted; the 2026-06-08 readout drop
is no longer "the one clear exception" among change points. The verification-status table at the head of
`00-overview.md` gives the verdicts per document.

**Known residue.** Several verifier scripts under `analysis/verify/` carry file-level
`# ruff: noqa` lines for naming and style rules (and, in `verify/gates_2q/v_core.py`, `F841`);
they pass the pinned ruff but are below the owners' scripts in polish. The verifiers name what
they did not re-verify; the overview's §6 item 3 lists it.

## Mathematical / Statistical details

**Event rules.** For one series (one field on one entity) with values `v_i` and stamps `d_i`
in file order, placeholders (`gate_error >= 1`) are set to missing first. Measured rule: file
`i` is an event when `v_i != v_prev` and `d_i != d_prev` against the previous present record.
Value-only rule: file `i` is an event when `v_i != v_prev`; its time is the file's
`last_update_date`.

**Variogram.** For every pair of events `i < j` of one series, with `z = log10(y)` and stamped
times `t` in hours, the lag is `t_j - t_i` and the half squared difference `(z_j - z_i)^2 / 2`.
Pairs are pooled over the entities of a family and binned by lag (bin edges in hours: 0, 0.5,
2, 4, 6, 9, 12, 18, 30, 42, 54, 84, 132, 204, 372, 744, 1488, 3624, so that the ~4.5 h readout
cadence and the daily rounds fall in separate bins). Each bin reports the mean (the classical
estimator) and the Cressie-Hawkins robust estimate
`gamma_CH = (mean |dz|^(1/2))^4 / (2 (0.457 + 0.494 / N))`, which is less sensitive to the heavy
tails these series have. Reading: estimation noise around a fixed level is flat at its variance
at every lag; a random-walk level adds `sigma_eta^2 * lag / 2`; fluctuations with a correlation
time `tau` rise over lags near `tau` and then flatten. With a known per-event noise variance
`s_i^2` (readout shot noise), each bin also reports `mean((s_i^2 + s_j^2) / 2)`, the part of the
semivariance noise alone explains.

**Shot noise of readout.** `p01` and `p10` are fractions of 4,096 shots; the binomial variance
of an estimate `p` is `p (1 - p) / 4096`, and the delta method gives the variance of
`log10(readout_error)` from those of `p01` and `p10` (the readout document states the exact form
it uses).

## Design decisions

- **Scripts under `docs/findings/`, not `scripts/`.** The task asked for one folder holding the
  documents and the scripts that reproduce every number. `mypy --strict` covers only
  `src/superconducted` and `scripts`, so these files are linted by ruff in CI but not
  type-checked; they are analysis code, not package code. This is the first `.py` under `docs/`.
- **Cache outside the repository.** The 184 MB cache lives in the user's home cache directory,
  not in the OneDrive-synced worktree; it is reproducible from the pinned ref in about a minute,
  and its digest is recorded in `01-data-layer.md`.
- **One `.npy` per field instead of one `.npz`.** The laptop had about 2 GB of free memory while
  six analyses ran at once; memory-mapping one field at a time keeps each analysis small.
- **The event rule is imported, not copied.** `ddload` imports `events` from
  `scripts/feature_patterns.py`, so this deep dive and the 2026-10-05 analysis cannot disagree
  about what an event is.
- **A shared variogram before fan-out.** Without one instrument, six owners would test the root
  question six incompatible ways, or not at all.
- **Branch.** `mert/feature-deep-dive` was cut from PR #111's head `5c65d06`, which stays frozen
  because a verification runbook is pinned to it. A pull request from this branch to `main` would
  also carry PR #111's commits until #111 merges; where to push is the lead's decision.

## Verification

```bash
python docs/findings/2026-10-06-feature-deep-dive/analysis/extract_cache.py --repo . --ref 7b84b506ef77beb6e6c1b25a7357c574cfaf5117 --out ~/.cache/superconducted-feature-deep-dive/7b84b506
python docs/findings/2026-10-06-feature-deep-dive/analysis/data_layer/selftest_ddload.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/data_layer/profile_cache.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/data_layer/identity_checks.py
ruff check . && ruff format --check .
```

The identity check's `cache_npy_sha256` must equal the digest in `01-data-layer.md`; the
profile and identity JSON must match the committed files in every value except `measured_utc`.

Checked on 2026-10-06 at `a776fb6` (laptop): the pinned ruff 0.15.12 passes `ruff check .` and
`ruff format --check .` over the whole repository; `python scripts/check_ids.py` finds no
colliding identifier (no document here defines an ADR or NC id); no test under `tests/` reads
`docs/findings/`, and the four tests that read anything under `docs/` (`test_check_ids`,
`test_feature_patterns`, `test_pipeline_health`, `test_parameterization`) pass, 211 cases, in the
scratch Python 3.12 venv with `PYTHONPATH=src`. `mypy --strict` does not cover `docs/`.

## The advisor report page (added later on 2026-10-06)

The lead then asked for an artifact for Dr. Akba that presents every finding with many charts,
in Turkish. It is built from this folder and adds no new analysis.

| File | One-sentence description |
| --- | --- |
| `analysis/report/spec_check.py` | The contract for one report section (Turkish text plus chart specs of nine types) and its validator: types, sizes, ISO times, finite numbers, no em dash. |
| `analysis/report/<section folder>/*.py`, `results/report/<section>.json` | Five folders (`data_device`, `root`, `coh_1q`, `readout`, `q2_cross`) whose scripts write the eight section specs from the scope results JSON and, where a chart needs a series no results file holds, from the cache with the owners' own functions. |
| `analysis/report/template.html` | The page and its d3 renderer (Turkish locale, both themes, a table view for every chart, hover tooltips, device maps on the heavy-hex layout). |
| `analysis/report/page_tr.json` | The page header and the closing sections in Turkish (root questions, unknowns, verification status, data rules), every figure quoted from `00-overview.md`; kept in JSON so the Python stays free of ruff's ambiguous-character rule. |
| `analysis/report/build_page.py` | Assembles the specs, the closing sections and the device layout into one self-contained HTML file. |

How it was checked. Five agents wrote the sections (disjoint folders); a verifier checked about
170 figures against the documents and found no wrong number, and its 14 wording findings (one
overclaiming title, fractions written as if percentages, "yok" where the documents say "not
detected", spelling consistency) were applied in the scripts and the specs regenerated. Every
chart was then rendered alone in headless Chrome and the 88 screenshots reviewed; the 32 visual
defects (unrendered backticks in legends, indistinguishable map flags, log axes rounded out to
whole decades, colliding marker labels, maps flattened by outliers) were fixed in the renderer.
The section scripts carry a file-level `# ruff: noqa: RUF001` for Turkish text, and two also
`E501`; the page itself is not committed (it is rebuilt with
`python analysis/report/build_page.py --out <file.html>`).

## Related docs

- `docs/findings/2026-10-06-feature-deep-dive/` (this deep dive)
- `docs/roadmap/2026-10-05-feature-patterns-and-method.md` (findings P1 to P8)
- `docs/roadmap/2026-10-04-three-engine-and-deep-model-plan.md` (the meeting record)
- `docs/implementations/2026-10-05-feature-pattern-analysis.md` (the event rule's origin)
- Issue #110, PR #111
