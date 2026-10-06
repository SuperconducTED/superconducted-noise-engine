# 01 · The data layer: every field at `7b84b50`, and the rules for reading it

Written 2026-10-06 on branch `mert/feature-deep-dive` (from PR #111's head `5c65d06`). This is
a dated document: reconcile it later by appending an as-of section, never by editing the text
below.

**Every figure here is provisional.** Basis: all 1,760 `ibm_fez` snapshot files at
`calibration-data` `7b84b506ef77beb6e6c1b25a7357c574cfaf5117` (2026-05-13T12:13:22Z to
2026-10-06T02:57:42Z), extracted and profiled on 2026-10-06 on the lead's laptop (Windows 11,
CPython 3.12, numpy 2.4.4). Nothing here is registered in `docs/numerical-claims.md`;
registration happens on the verification desktop. Every number below is a field of
`results/data-layer/profile.json` or `results/data-layer/identities.json`.

## 1. What the layer is

One extraction pass reads every snapshot blob through a single `git cat-file --batch`
process (one request written and its answer read before the next) and writes one `.npy` per
field and per file-level array, plus a `meta.json`. Nobody re-parses the roughly 3 GB of JSON
after that: every scope document in this folder reads the cache through `analysis/ddload.py`.

| Item | Value |
| --- | --- |
| Archive ref | `7b84b506ef77beb6e6c1b25a7357c574cfaf5117` (the `calibration-data` tip on 2026-10-06) |
| Files | 1,760 `ibm_fez` documents, ordered by `properties.last_update_date` |
| Extraction | `analysis/extract_cache.py`, 72 s on the laptop |
| Cache | 131 `.npy` files plus `meta.json`, 184 MB, outside the repository (default `~/.cache/superconducted-feature-deep-dive/7b84b506/`, or `DD_CACHE`) |
| Cache digest | sha256 over every `.npy` name and its bytes, in name order: `10df569c700977aa71c649a09f8beceb0bab0e2008a0dd5696d98acfcc91f5da` (`meta.json` is excluded because it records the run time) |
| Extraction checks | 0 duplicate records within a file, 0 unparsable or ambiguous coupler names, 0 couplers named in both orientations, 0 unexpected record keys, 0 non-numeric values |

Rebuild and re-profile (from the repository root, with the archive commit's blobs local):

```bash
python docs/findings/2026-10-06-feature-deep-dive/analysis/extract_cache.py --repo . --ref 7b84b506ef77beb6e6c1b25a7357c574cfaf5117 --out ~/.cache/superconducted-feature-deep-dive/7b84b506
python docs/findings/2026-10-06-feature-deep-dive/analysis/data_layer/profile_cache.py
python docs/findings/2026-10-06-feature-deep-dive/analysis/data_layer/identity_checks.py
```

The scripts here sit under `docs/`, not `scripts/`, so CI runs ruff on them but not
`mypy --strict` (whose scope is `src/superconducted` and `scripts`). `ddload.py` imports the
event rule from `scripts/feature_patterns.py` so the two can never drift apart.

## 2. Field names and shapes

Every field is a pair of arrays of shape `(n_files, n_entities)`: values, and the date IBM
stamped on each value (ms since the epoch). NaN means the record is absent from that file.

| Prefix | Source in the document | Entities (columns) |
| --- | --- | --- |
| `q.<name>` | `properties.qubits[q]` records | 156 qubits |
| `g1.<gate>.<param>` | `properties.gates` with one qubit | 156 qubits |
| `g2.<gate>.<param>` | `properties.gates` with two qubits | 352 **directed** couplers (`[a, b]` and `[b, a]` kept apart) |
| `gen.jq`, `gen.zz` | `properties.general` names `jq_<ab>`, `zz_<ab>` | 176 undirected couplers |
| `gen.lf` | `properties.general` names `lf_<N>` | 97 names, `lf_4` to `lf_100` |
| `gen.lf_chain` | `properties.general_qlists` | per file and lf name, the index of its qubit chain in `meta.json` `lf_chains` |
| `file.<name>` | per-file values | 1,760 files |

Coupler names in `general` carry no separator (`jq_717` could be 7-17 or 71-7). Each name was
split every possible way and kept only when exactly one split is an edge of the coupling map
(from the first live document's `configuration.coupling_map`, 352 directed edges); all 352
names parsed uniquely.

## 3. Every field

"Date = file date" is the share of present records whose stamp equals the document's
`last_update_date`. Near 1 means IBM re-stamps the field whenever a document is assembled, so
its date carries no information. "Rule" is the event rule this layer assigns (section 4).

| Field | Entities | Unit | Files (first to last) | Present in lifetime | Distinct values | Median (1%, 99%) | Date = file date | Rule | Events per entity, median | Median gap (h) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `q.T1` | 156 | us | 1760 (20260513 to 20261006) | 0.9999 | 20063 | 126 (30.1, 259) | 0.0000 | measured | 130 | 24.8 |
| `q.T2` | 156 | us | 1760 (20260513 to 20261006) | 0.9936 | 20626 | 92.4 (5.53, 237) | 0.0041 | measured | 134 | 24.7 |
| `q.readout_error` | 156 | none | 1760 (20260513 to 20261006) | 1.0000 | 2203 | 0.01 (0.00293, 0.238) | 0.0034 | measured | 580 | 4.47 |
| `q.prob_meas0_prep1` | 156 | none | 1760 (20260513 to 20261006) | 1.0000 | 1525 | 0.0137 (0.00439, 0.185) | 0.0025 | measured | 574 | 4.56 |
| `q.prob_meas1_prep0` | 156 | none | 1760 (20260513 to 20261006) | 1.0000 | 1355 | 0.0061 (0.000244, 0.167) | 0.0026 | measured | 572 | 4.51 |
| `q.readout_length` | 156 | ns | 1760 (20260513 to 20261006) | 1.0000 | 3 | 1660 (1560, 1700) | 0.0034 | value only | 3 | n/a |
| `q.init_error` | 156 | none | 1091 (20260804 to 20261006) | 0.7425 | 23550 | 0.00185 (0.0002, 0.0106) | 0.0067 | measured | 241 | 4.73 |
| `g1.sx.gate_error` | 156 | none | 1760 (20260513 to 20261006) | 1.0000 | 20208 | 0.000312 (0.000143, 0.00705) | 0.0055 | measured | 132 | 24.9 |
| `g1.sx.gate_length` | 156 | ns | 1760 (20260513 to 20261006) | 1.0000 | 1 | 24 (24, 24) | 0.0055 | value only | 1 | n/a |
| `g1.x.*`, `g1.id.*`, `g1.rx.*` | 156 | as `sx` | 1760 (20260513 to 20261006) | 1.0000 | as `sx` | as `sx` | 0.0055 | as `sx` | as `sx` | as `sx` |
| `g1.xslow.gate_error` | 156 | none | 872 (20260514 to 20261006) | 0.4983 | 6533 | 0.000318 (0.000145, 0.0118) | 0.0041 | measured | 43 | 25.1 |
| `g1.xslow.gate_length` | 156 | ns | 872 (20260514 to 20261006) | 0.4983 | 1 | 1000 (1000, 1000) | 0.0041 | value only | 1 | n/a |
| `g1.rz.gate_error` | 156 | none | 1760 (20260513 to 20261006) | 1.0000 | 1 | 0 (0, 0) | 1.0000 | value only | 1 | n/a |
| `g1.rz.gate_length` | 156 | ns | 1760 (20260513 to 20261006) | 1.0000 | 1 | 0 (0, 0) | 1.0000 | value only | 1 | n/a |
| `g1.measure.gate_error` | 156 | none | 1760 (20260513 to 20261006) | 1.0000 | 2203 | 0.01 (0.00293, 0.238) | 0.0034 | measured | 580 | 4.47 |
| `g1.measure.gate_length` | 156 | ns | 1760 (20260513 to 20261006) | 1.0000 | 3 | 1660 (1560, 1700) | 1.0000 | value only | 3 | 940 |
| `g1.measure.threshold` | 156 | none | 1533 (20260608 to 20261006) | 1.0000 | 50856 | -8.9e+06 (-8.05e+07, 2.48e+07) | 1.0000 | value only | 328 | 4.79 |
| `g1.measure_2.gate_error` | 156 | none | 1058 (20260807 to 20261006) | 1.0000 | 746 | 0.0139 (0.0022, 0.41) | 0.0040 | measured | 51 | 24.7 |
| `g1.measure_2.gate_length` | 156 | ns | 1058 (20260807 to 20261006) | 1.0000 | 1 | 1340 (1340, 1340) | 1.0000 | value only | 1 | n/a |
| `g1.measure_2.threshold` | 156 | none | 1058 (20260807 to 20261006) | 1.0000 | 18876 | -4.03e+06 (-5.02e+07, 1.39e+07) | 1.0000 | value only | 125 | 4.94 |
| `g1.measure_reset.gate_length` | 156 | ns | 817 (20260902 to 20261006) | 1.0000 | 1 | 1684 (1684, 1684) | 1.0000 | value only | 1 | n/a |
| `g1.measure_reset.threshold` | 156 | none | 817 (20260902 to 20261006) | 1.0000 | 16848 | -8.83e+06 (-7.71e+07, 2.68e+07) | 1.0000 | value only | 108 | 4.99 |
| `g1.measure_reset_2.gate_length` | 156 | ns | 817 (20260902 to 20261006) | 1.0000 | 1 | 1364 (1364, 1364) | 1.0000 | value only | 1 | n/a |
| `g1.measure_reset_2.threshold` | 156 | none | 817 (20260902 to 20261006) | 1.0000 | 17628 | -4.12e+06 (-5.29e+07, 1.59e+07) | 1.0000 | value only | 117 | 4.88 |
| `g1.reset.gate_length` | 156 | ns | 1760 (20260513 to 20261006) | 1.0000 | 3 | 1684 (1584, 1724) | 1.0000 | value only | 3 | 940 |
| `g1.reset_2.gate_length` | 156 | ns | 817 (20260902 to 20261006) | 1.0000 | 1 | 1364 (1364, 1364) | 1.0000 | value only | 1 | n/a |
| `g2.cz.gate_error` | 352 | none | 1760 (20260513 to 20261006) | 1.0000 | 22093 | 0.00278 (0.00158, 1) | 0.0038 | measured | 131 | 25.1 |
| `g2.cz.gate_length` | 352 | ns | 1760 (20260513 to 20261006) | 1.0000 | 3 | 68 (68, 88) | 0.0038 | value only | 1 | n/a |
| `g2.rzz.gate_error` | 352 | none | 1760 (20260513 to 20261006) | 1.0000 | 18211 | 0.00271 (0.00153, 1) | 0.0026 | measured | 110 | 25.3 |
| `g2.rzz.gate_length` | 352 | ns | 1760 (20260513 to 20261006) | 1.0000 | 4 | 68 (68, 116) | 0.0026 | value only | 1 | n/a |
| `gen.jq` | 176 | GHz | 1760 (20260513 to 20261006) | 1.0000 | 1 | 0 (0, 0) | 1.0000 | value only | 1 | n/a |
| `gen.zz` | 176 | GHz | 1760 (20260513 to 20261006) | 1.0000 | 83444 | 6.18e-06 (0, 2.52e-05) | 1.0000 | value only | 486 | 5.16 |
| `gen.lf` | 97 | none | 1760 (20260513 to 20261006) | 1.0000 | 8051 | 0.76 (0.518, 0.986) | 0.0000 | measured | 83 | 26.6 |

The `measure_2`, `measure_reset`, `measure_reset_2`, `reset_2` and `init_error` start dates
and the `measure.threshold` start (2026-06-08T18:56:28Z) are schema starts, not faults: before
them the record does not exist in any file. Read missingness only inside a field's lifetime
("Present in lifetime").

## 4. The event rules: which one applies to which field

An **event** is one re-measurement of one entity. Two rules exist, and `ddload.series()`
implements both:

| Rule | When it applies | Event | Event time |
| --- | --- | --- | --- |
| **measured** (`ddload.MEASURED`) | the field carries the date IBM measured it | a file where the value AND the stamped date are both new (the rule of `scripts/feature_patterns.py`, imported) | the stamped date |
| **value only** (`ddload.ASSEMBLY`) | the date is re-stamped at document assembly, or the field is a configuration-like length | a file where the value differs from the previous present value | the first file's `last_update_date` |

Fields under the value-only rule: every `threshold`, `gen.zz`, `gen.jq`, `g1.rz.*`, every
`gate_length` and `q.readout_length`. The lengths are value-only for a second reason:
`q.readout_length` carries the readout stamp, but its two changes (below) happened in files
where that stamp did not move, so the measured rule would see one event instead of three.

**Placeholders are masked before events are formed**, never after: `gate_error >= 1`
(`ddload.placeholder_error`) for every gate error. Its stamp is the assembly time and is later
than the document's `last_update_date` in exactly the placeholder records (1,975 for `sx`, 312
for `measure_2`, 17,364 for `cz`, 24,790 for `rzz`).

## 5. Facts every scope can rely on

**Duplicates, re-checked record by record over all 1,760 files** (`identities.json`):

| Pair | Records compared | Value mismatches | Date mismatches |
| --- | --- | --- | --- |
| `sx` vs `id` / `rx` / `x` error | 274,560 each | 0 / 0 / 0 | 979 / 645 / 374 |
| `sx` vs `xslow` error | 136,032 (`xslow` absent in the other 138,528) | 0 | 310 |
| `readout_error` vs `measure` error | 274,560 | 0 | 0 |
| `readout_length` vs `measure` length | 274,560 | 0 | 273,626 (the `measure` length is assembly-stamped) |
| `cz` error, `[a, b]` vs `[b, a]` | 309,760 | 0 | 8,682 |
| `rzz` error, `[a, b]` vs `[b, a]` | 309,760 | 0 | 12,395 |
| `cz` vs `rzz` error on the same directed coupler | 619,520 | 604,244 | 619,520 |

So the aliases and the two directions of a coupler always carry the same **value** but not
always the same **date**: the event counts of an alias or of one direction can differ from
`sx`'s or the other direction's. `cz` and `rzz` are separate calibrations.

**Readout arithmetic.** `p01 = prob_meas1_prep0` and `p10 = prob_meas0_prep1` are each a
multiple of 1/4096 in all 549,120 values (4,096 shots). `readout_error = (p01 + p10) / 2` to
within 1e-12 in all 188,100 records where the three fields carry the identical stamp; that is
68.5% of the 274,560 readout records, so in the rest the three were stamped at different times.
`prob_meas1_prep0` is exactly 0 in 2,468 records.

**Constant or empty fields.** `gen.jq` is 0 for all 176 couplers in every file, so it carries
no information. `g1.rz.*` is 0 (a virtual gate). `sx`, `x`, `id`, `rx` lengths are 24 ns and
the `xslow` length 1,000 ns throughout. `xslow` is present for every qubit or for none: from
2026-05-14T12:32:42Z, absent again from 2026-05-29T16:46:42Z, and present from
2026-09-10T16:56:21Z to the end.

**Device-wide length changes** (value-only events, the same files for every qubit):

| File | `readout_length` (= `measure` length) | `reset` length |
| --- | --- | --- |
| up to 2026-06-08T18:56:28Z | 1,560 ns | 1,584 ns |
| 2026-06-08T18:56:28Z | 1,700 ns, all 156 qubits | 1,724 ns |
| 2026-07-30T21:09:17Z | 1,660 ns, all 156 qubits | 1,684 ns |

The first change is the same file in which `measure.threshold` first appears. `reset` is
always the readout length plus 24 ns, and `measure_reset` equals `reset` (1,684 ns);
`reset_2` and `measure_reset_2` are `measure_2`'s 1,340 ns plus 24 ns. Two-qubit lengths:
`cz` and `rzz` are 68 ns on most couplers; both couplers of `q72` (71-72 and 72-73, both
permanently faulty) went from 68 to 84 ns on 2026-09-05T17:51:36Z, the only length change of
any coupler; 102-103 and 146-147 are at 88 ns for both gates throughout, and the `rzz` of
68-69, 80-81 and 106-107 at 116 ns throughout.

**Permanently faulty entities.** `gate_error >= 1` in every file of the field's lifetime:
`sx` on `q72`; `cz` on 27-28, 32-33, 71-72, 72-73; `rzz` on 32-33, 71-72, 72-73, 95-99,
99-115. `gen.zz` is exactly 0 on 32-33 in every file. `q72`'s `T2` is absent from every file,
its `T1` from some.

## 6. File-level structure

| Item | Value |
| --- | --- |
| Files with a `configuration` section | 1,317; the other 443 carry `configuration: null`, which the archive README attributes to historical fetches (whose `target` comes from `target_history`) |
| Historical files by month | 29 in 2026-08, 349 in 2026-09, 65 in 2026-10; none before |
| Top-level `timestamp` | equal to `properties.last_update_date` in every file (so it is not the poll time; poll times are in the ledger) |
| `backend_version` | `1.3.37` in all 1,760 files; `schema_version` `1.0.0` in all |
| `target.operations` | 4 distinct sets, each a superset of the previous: 1,444 ops (702 files, to 2026-08-06), 1,600 (+ `measure_2`, 241 files, 2026-08-07 to 09-01), 2,068 (+ `measure_reset`, `measure_reset_2`, `reset_2`, 53 files, 09-02 to 09-10), 2,224 (+ `xslow`, 764 files, from 09-09); the last two overlap on 09-09 and 09-10, where 414 of the 2,224-op files are historical fetches |
| `configuration` keys that change | `basis_gates` (gains `xslow` from 2026-09-10T19:20:51Z), `gates`, `instruction_signatures` and `supported_instructions` (4 versions each, following the target sets), `clops_v` (the string `"None"` until 2026-06-24, then JSON null); the other 38 keys are constant |
| Consecutive-file gap | median 1.26 h, 90% 4.06 h, max 82.7 h |
| Distinct states (`health/state-index.tsv`) | 760 over 1,759 matched files; one file (`20260630T214008000000Z.json`) has no row by its own name |
| Ledger | 1,981 poll rows from 2026-09-02 (`new` 844, `duplicate-partial` 637, `duplicate` 490, `collision` 10) |
| Collision files | 2 (`20260928T014620000000Z`, `20261003T213246000000Z`) |
| `lf` chains | 6,524 distinct qubit chains across the 97 `lf_<N>` names (a chain of N qubits each); 34 to 79 distinct chains per name |
| `lf` stamps | later than the document's `last_update_date` in 217 files, by at most 6.4 h |

**What "distinct state" means.** The state digest covers `properties.qubits` only, with each
record's date normalised away. A file whose only change is a gate re-measurement (`sx`, `cz`,
`rzz`) or a `general` value is therefore a "duplicate state". The 760 states are distinct
qubit-record states, not distinct calibrations.

**Coverage changes over time.** The archive files a document whenever the poller sees a new
`last_update_date`. Before the historical backfill (from 2026-08), intermediate documents
missed between polls are simply absent, so the visible event rate of the fast families
(readout, every ~4.5 h) depends on the period. Any cadence or rate comparison across months has
to control for this.

## 7. The shared variogram

`ddload.variogram(series)` pools, over every pair of events of every entity, the half squared
difference of `log10` values against the time between them, in lag bins that keep the readout
cadence and the daily rounds apart. It is the common instrument for the open root question
(what the large non-persistent component of every series is):

- estimation noise around a fixed level gives a flat curve at every lag;
- a drifting level (random walk) adds a part that grows linearly with lag;
- real fluctuations with a correlation time tau rise over lags near tau, then flatten;
- the value at the shortest lag (the nugget) is noise plus anything faster than that lag.

For readout the noise variance of each value is computable from the 4,096 shots, so
`variogram(..., noise_var=...)` also reports the part of each bin that shot noise alone
explains. Each family document applies the same function to its own fields.

## 8. Who owns what in this deep dive

| Document | Fields owned | Assigned cross-family link |
| --- | --- | --- |
| `02-coherence.md` | `q.T1`, `q.T2`, derived rates (`1/T1`, pure dephasing, ADR-027's gamma and lambda) | none (T1 and T2 against each other is inside the scope) |
| `03-readout-measurement.md` | `q.readout_error`, `q.prob_meas0_prep1`, `q.prob_meas1_prep0`, `q.readout_length`, `q.init_error`, every `g1.measure*`, `g1.reset*` field | readout errors against `T1` decay during readout |
| `04-single-qubit-gates.md` | `g1.sx.*`, `g1.x.*`, `g1.id.*`, `g1.rx.*`, `g1.xslow.*`, `g1.rz.*` | `sx` against its `T1`/`T2` coherence limit |
| `05-two-qubit-gates-couplings.md` | `g2.cz.*`, `g2.rzz.*`, `gen.jq`, `gen.zz` | `cz`/`rzz` against their two qubits (coherence limit, `sx`, readout) |
| `06-device-time-topology.md` | every `file.*` array, `meta.json` structure (configuration, target, state index, ledger, collisions), `gen.lf` and its chains; the calibration schedule, change points and fault map across families, the coupling graph and coordinates | `lf` against the gate errors of its chain |
| `07-cross-feature-dependency.md` | no fields of its own; reads all | every other relationship between families; skips the three assigned links above and `lf` against its chain |

## 9. Sources

Project sources only: the archive's own `README.md` and `collisions/README.md` at the ref (for
the historical-fetch attribution of `configuration: null` and the state digest's scope);
`scripts/feature_patterns.py` (the measured event rule);
`docs/roadmap/2026-10-05-feature-patterns-and-method.md` (the findings this deep dive starts
from).
