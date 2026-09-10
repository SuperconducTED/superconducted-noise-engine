# 2026-09-10: threshold-distributions

## Problem / Motivation

Issue #48 section 7.3 settled four alarm numbers: a coverage red below 15%, a coverage
amber below 50%, a 75% recovery target, and a 24 h staleness bound with a 12 h amber. Its
own fourth item says why they were not finished:

> Every threshold carries the distribution it came from. A threshold is a numerical claim:
> it asserts something about how often it will fire. None of these four numbers has a
> register row, and shipping a threshold whose firing rate nobody computed is how 75% got
> proposed twice.

That was accurate. The thread had already proposed 75% as an alarm, been shown it would
fire on 85.5% of windows, and proposed it again two minutes later. The register exists to
make that failure structurally hard, and these four numbers were outside it. This change
puts them in, with a committed script as their source rather than an ad-hoc computation
nobody can rerun.

Re-measuring rather than transcribing turned out to matter: **the coverage half of section
7.3 does not reproduce.**

## What changed

| File | One-sentence description |
| --- | --- |
| `scripts/threshold_distributions.py` | New: recomputes the coverage and staleness distributions from a `calibration-data` checkout and reports percentiles plus the firing rate of each candidate threshold. |
| `tests/test_threshold_distributions.py` | New: 18 unit tests pinning the window arithmetic, the nearest-rank percentile, the strictness of both share counters, and first-sighting derivation. |
| `docs/numerical-claims.md` | Adds NC-048 through NC-051: two base distributions and the firing rate of each threshold measured against them. |

## Implementation approach

**The coverage metric is recomputed exactly as the dashboard computes it**, not
approximated. `pipeline_health.build_metrics` truncates each ledger row to its hour, takes
the 72 hour-starts before a given boundary, and divides the hits by 72. The script does the
same and rolls the boundary one hour at a time. Reimplementing the definition loosely would
have produced a distribution for a quantity the thresholds are not applied to, which is the
exact error section 7.3 correctly diagnosed in the `16/24 = 67%` derivation it rejected.

**Only windows lying wholly inside the ledger span are counted.** A window reaching back
past the first ledger row reads low because the ledger did not exist yet, not because the
scheduler failed. Including those would manufacture a left tail and make any alarm derived
from it fire early on real data.

**First sightings are derived, never read.** `state_intervals` takes the earliest
`last_update_date` carrying each digest rather than trusting the index's `is_new_state`
column, matching `pipeline_health.first_sightings` and for the reason its docstring gives:
that column is decided by append order, and a sweep files documents out of order.

**The two distributions are reported separately and never pooled**, because they rest on
very different amounts of evidence. See the Verification section: this is the finding.

## Mathematical / Statistical details

**Coverage.** For an hour boundary `t`, let `H(t) = {t - 72h, t - 71h, ..., t - 1h}` be the
72 hour-starts in the window. An hour is *covered* when at least one ledger row falls inside
it. Coverage at `t` is `|H(t) ∩ covered| / 72`. The sample is `{coverage(t)}` for every hour
boundary `t` from `first + 72h` through `last` inclusive, where `first` and `last` are the
hour-truncated extremes of the ledger. A span of `n` hours therefore yields `n - 72 + 1`
windows, and fewer than 72 hours yields none.

Note that coverage counts *hours containing a poll*, not polls. Two polls in one hour cover
one hour. This is why coverage cannot be derived from a runs-per-day figure: 6.13 runs/day
bounds coverage above by 6.13/24 only when every poll lands in a distinct hour, and the
measured record says they do not.

**Percentiles are nearest-rank, never interpolated.** The p-th percentile is the value at
index `ceil(p / 100 * n) - 1` of the sorted sample. Every number published from this script
is therefore a value that was actually observed, which is what lets a reader check it
against the raw file. An interpolated p5 of "15%" could name a coverage no window ever had.

**Staleness.** Let `S` be the sorted set of first-sighting times, one per distinct qubit
digest. The sample is the consecutive differences of `S`, in hours. With `k` distinct states
there are `k - 1` intervals.

## Design decisions

**A committed script rather than a documented procedure.** Rule 1 accepts either. A script
was chosen because these thresholds will need re-checking every time the archive grows, and
because section 7.3's numbers were produced by exactly the ad-hoc route that cannot be
rerun. The cost is a new file under `scripts/`, which `[tool.mypy] files` already covers.

**Nearest-rank over `statistics.quantiles`.** The stdlib default interpolates. For a claim
that will be read as "this threshold sits at the p5 of observed behaviour", an interpolated
value is a number nobody observed, and the register's whole purpose is that every published
figure traces to something real.

**Four rows rather than one.** Two carry the base distributions (NC-048, NC-050) and two
carry the firing rates of the thresholds judged against them (NC-049, NC-051). Splitting
them means a future re-measurement of the distribution does not silently restate the
decision, and a change of threshold does not require re-deriving the distribution.

**Section 7.3's figures were not reverse-engineered.** Two candidate sources were tried and
neither reproduces them; a third was not invented to make them fit. The rows record what is
measurable and say plainly that the rest is not, which is the honest form.

## Verification

```bash
python -m pytest tests/test_threshold_distributions.py -q
python -m ruff check . && python -m ruff format --check .
python scripts/threshold_distributions.py --root <calibration-data checkout>
```

18 tests pass. `ruff check` and `ruff format --check` clean over the two new files. The full
suite collects and passes **465** at this branch, up from 447 by exactly the 18 added.
`mypy --strict` is clean on both new files; it cannot be run whole on this machine, where
numpy 2.5.3's shipped stubs stop it under the project's pinned `python_version`, and CI is
the authority for that gate as it is on `main`.

Measured at `calibration-data` @ `9d7e74c`:

```
== ledger_hour_coverage_72h ==
  ledger span     2026-09-02T16:00:00+00:00 .. 2026-09-10T20:00:00+00:00
  span hours      196 (8.2 days), covered hours 54
  windows         125
  min 22.2%  p5 23.6%  p50 27.8%  p95 30.6%  max 31.9%
  fires below 15%   0/125 = 0.0%
  fires below 50%   125/125 = 100.0%
  fires below 75%   125/125 = 100.0%

== hours between consecutive distinct device states ==
  intervals       565
  p50 3.94 h  p95 11.01 h  p98 16.67 h  max 82.68 h
  exceeds 12 h      23/565 = 4.1%
  exceeds 24 h      7/565 = 1.2%
```

### The finding: one half reproduces, the other does not

**Staleness reproduces exactly.** Section 7.3 reported 23 of 561 intervals above 12 h, 7 of
561 above 24 h, and a maximum of 82.68 h. Both counts and the maximum are identical here.
Only the denominator moved, 561 to 565, because the archive gained four states since. Those
two bounds are safe to adopt.

**Coverage does not reproduce, from any source in this repository.** Section 7.3 reported
399 windows, a maximum ever observed of 83.3%, p95 of 81.9%, red below 15% firing on 3.3%
of windows, and 75% firing on 85.5%. Measured against the metric itself: 125 windows,
maximum 31.9%, p95 30.6%, red firing on 0.0%, and 75% firing on 100%.

Three sources were checked, and the result locates the error precisely: **the median
reproduces, the tail does not.**

| Source | Windows | p50 | p95 | max |
| --- | --- | --- | --- | --- |
| §7.3 as reported | 399 | 27.8% | 81.9% | 83.3% |
| Live ledger @ `9d7e74c` | 125 | **27.8%** | 30.6% | 31.9% |
| Validation branch ledger @ `49c3c59` | 99 | **27.8%** | 30.6% | 31.9% |
| IBM publication clock, whole archive | 2816 | 31.9% | 55.6% | 73.6% |

Both ledgers give exactly the p50 §7.3 reports, so its median came from real ledger data.
None of the three yields its p95 or its maximum. The tail is the half that matters here,
because 15% and 75% are both drawn from it.

The reason a four-month coverage figure cannot exist here is structural. `ledger/` begins at
2026-09-02T16:49Z, when ADR-025 landed, and is the only record that counts no-op polls.
`calibration-data`'s own commit history reaches back only to 2026-08-01, and before the
ledger it recorded only polls that produced a document. There is no four-month poll-time
record to measure.

**What follows, and what does not.** Amber below 50% is not an alarm: it is true in every
window measured. Section 7.3 raised that concern about itself in its closing line and
understated it as chronic rather than constant. The 75% target likewise fires everywhere,
which is consistent with it being a target rather than an alarm, as section 7.3 concluded.

The 15% red is **unevidenced, not disproven.** The ledger contains no scheduler collapse:
the 2026-08-27..30 outage (NC-029) predates it entirely. 0 of 125 says only that it never
fires during degraded-normal operation, which is what an alarm should do. What fraction of
collapse-windows it would catch is simply unmeasured, and will stay unmeasured until either
a collapse happens with the ledger running or the pre-ledger poll history is reconstructed.

None of this is wired to anything: section 7.3 records that nothing colours against a
threshold yet. So this costs nothing today, which is precisely why it is the right moment to
record it.

## Related docs

- Issue #48 section 7.3 (the decision these rows serve) and its DoD item on registering new
  figures; issue #49 (which owns the scheduler collapse and the 75% recovery target)
- `docs/implementations/2026-09-05-pipeline-health-dashboard.md`, which builds the metric
- ADR-025 and its 2026-09-05 pipeline-health amendment in `docs/decisions.md`
- NC-009 and NC-029 (the poll cadence and the outage this distribution sits beside), NC-021
  (test count), NC-048 to NC-051 (added here)

**One code discrepancy recorded rather than fixed.** Section 7.3 states that
`STALENESS_BANDS` in `scripts/pipeline_health.py` already buckets at 24 and 72 h, "so the
code and this decision agree". The 24 h bound does agree. The constant is `(24, 72, 168)`
and carries no 12 h boundary, so the 12 h amber the same decision proposes is not
representable without adding a band. NC-051 records this. It is not fixed here because
nothing colours against either bound yet, and adding a band changes rendered bytes on a
branch with a commit-on-change guard.
