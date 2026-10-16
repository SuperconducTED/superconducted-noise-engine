# 2026-10-16: website-facts-register

## Problem / Motivation

The organisation's new website (`SuperconducTED/superconducted.github.io`, decided by Mert on
2026-10-16) shows a facts strip on its Home page: the qubit count of the machine the archive
follows, the archive's snapshot count, the distinct device states against the NC-012 training
floor, and the test-suite size. The register's Purpose section covers the org's public pages, so
every one of those figures needs a row before the site may show it. The test count already has
one (NC-021); the other three did not: NC-014 mentions "156 qubits" only inside its source note,
NC-043's snapshot count (975) is from 2026-09-08, and the last distinct-state count (NC-047, 563)
is from early September.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/numerical-claims.md` | Adds NC-067 (156 qubits on `ibm_fez`), NC-068 (2,050 snapshot files) and NC-069 (868 distinct device states of the 1,170 floor), all measured at `calibration-data` @ `d62f2cdcd4bfcc6ccf2a250a150ab3bf982fe854`. |
| `docs/implementations/2026-10-16-website-facts-register.md` | This record. |

## Implementation approach

All three values are read from git objects at one pinned `calibration-data` commit
(`d62f2cd`, committed 2026-10-16T09:55:12Z), so they describe the same archive state:

- **NC-067.** In the newest snapshot at that commit,
  `snapshots/2026-10/ibm_fez/20261016T091344000000Z.json`, three independent fields agree:
  `target.num_qubits`, `configuration.n_qubits` and `len(properties.qubits)` are all 156.
- **NC-068.** `git ls-tree -r --name-only d62f2cd -- snapshots/`, counting lines ending `.json`:
  2,050. This is NC-043's procedure at a later ref; NC-043 keeps its own value because it is the
  denominator of the NC-041 survey at `3d1569d`.
- **NC-069.** The number of distinct `qubit_digest` values in `health/state-index.tsv` at the same
  commit: 868. This is the unit NC-012 counts, the same one NC-025 and NC-047 measured.

## Mathematical / Statistical details

**Cross-check of NC-069.** `health/metrics.json` at the same commit reports
`states_remaining = 308` for the NC-012 floor, which implies 1170 − 308 = 862 states, not 868. The
file says it was generated at 2026-10-16T08:20Z from index head `20261016T062913000000Z.json`.
Cutting the index at that head and counting distinct digests gives 862, so the two methods agree;
the 6 extra states were appended to the index after the metrics were written. The index is
therefore the source of the row, and the cross-check is recorded in its notes.

**Ratio.** 868 / 234 ≈ 3.7 distinct states per trainable parameter (NC-045), below the 5 the
floor is derived from: the training gate is not met. Distinct is not independent (NC-025's
caveat), so 868 is an upper bound on the independent-sample count.

**Not carried.** `metrics.json` also projects a completion date for the floor; the ADR-025
amendment makes projections non-registrable, so neither the row nor the website shows one.

## Design decisions

- **Ids NC-067 to NC-069, not NC-061 to NC-063.** NC-061 is the next free id on `main`, but the
  2026-10-13 review of PR #113 asked it to renumber its six colliding rows (NC-052..057) to start
  at NC-061. Taking NC-067 onward keeps both branches mergeable in either order. A gap, if #113
  ends up using different ids, is not a defect under `scripts/check_ids.py`'s own rules.
- **New rows rather than updating NC-043 and NC-047.** Both are tied to the evidence they were
  measured for (the NC-041 survey; the PR #70 backfill). Changing their values would break those
  documents' arithmetic.
- **One pinned commit for all three.** A facts strip that mixes refs could show a state count from
  one hour and a file count from another; one ref keeps them consistent.

## Verification

```bash
REF=d62f2cdcd4bfcc6ccf2a250a150ab3bf982fe854
git fetch origin calibration-data
git ls-tree -r --name-only $REF -- snapshots/ | grep -c '\.json$'                    # 2050
git show $REF:health/state-index.tsv | awk -F'\t' 'NR>1{print $3}' | sort -u | wc -l  # 868
git show $REF:snapshots/2026-10/ibm_fez/20261016T091344000000Z.json \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['target']['num_qubits'], d['configuration']['n_qubits'], len(d['properties']['qubits']))"  # 156 156 156
python scripts/check_ids.py                                                          # no collisions
```

`python -m pytest tests/test_check_ids.py` passes (22 tests) on this branch.

## Related docs

- `docs/numerical-claims.md`: NC-012, NC-021, NC-025, NC-043, NC-045, NC-047, and the new NC-067
  to NC-069.
- The website's record: `SuperconducTED/superconducted.github.io`
  `docs/implementations/2026-10-16-superconducted-website.md`.
- ADR-025 (projections are non-registrable) in `docs/decisions.md`.
