# 2026-05-16: loader-missing-fields

## Problem / Motivation

Issue #9. Real IBM `properties()` responses occasionally omit per-qubit
`T1` and `T2` Nduv entries when the coherence measurement fails during
the calibration window. The exemplar at
`origin/calibration-data:snapshots/2026-05/ibm_fez/20260513T121322000000Z.json`
shows the pattern: qubit 72 of `ibm_fez` is present in
`properties.qubits` with its readout calibration intact but the `T1`
and `T2` entries are simply absent. Any consumer doing `qubit["T1"]`
raises a `KeyError`. The bootstrap aggregator
`BasicCalibrationVectorizer` survives this incidentally because it
iterates the Nduv list, but no typed view of the snapshot existed and
no downstream code could treat absence as first-class. This change adds
that typed view and a Skip-strategy aggregator pair, per ADR-017.

## What changed

| File | One-sentence description |
| --- | --- |
| `src/superconducted/calibration/loader.py` | New: typed `ParsedCalibrationSnapshot` / `ParsedQubitCalibration` / `MissingnessStats` and `load_snapshot()`, with unit validation and absent/null/NaN distinction. |
| `src/superconducted/calibration/features.py` | Adds module-level `mean_t1` and `mean_t2` returning `Optional[float]` with Skip semantics; existing `BasicCalibrationVectorizer` untouched. |
| `src/superconducted/calibration/__init__.py` | Re-exports the new loader types, `load_snapshot`, `CalibrationParseError`, `mean_t1`, `mean_t2`. |
| `tests/calibration/__init__.py` | New (empty) package marker; mirrors `tests/__init__.py`. |
| `tests/calibration/test_loader.py` | Loader tests including the cornerstone absent-vs-null-vs-NaN test and unit-mismatch error message check. |
| `tests/calibration/test_features_missing_fields.py` | Skip-strategy aggregator tests, including end-to-end on the exemplar. |
| `tests/fixtures/calibration/ibm_fez_20260513T121322Z_q72_missing_t1t2.json` | Minimized exemplar: top-level + `properties.{backend_name,last_update_date,qubits}` only. |
| `tests/fixtures/calibration/README.md` | Fixture provenance, source SHA-256, regeneration recipe. |
| `docs/decisions.md` | Appends ADR-017 (Accepted) recording the Skip-strategy decision. |

`src/superconducted/calibration/poller.py` and
`src/superconducted/calibration/storage.py` are unchanged (locked under
ticket #002 per the Pass B prompt).

## Implementation approach

`load_snapshot(path)` reads the JSON, walks `properties.qubits`, and
for each qubit builds a `by_name` index over its Nduv list. For each
field in a fixed expected-unit table

```
T1, T2          -> "us"
readout_length  -> "ns"
readout_error, prob_meas0_prep1, prob_meas1_prep0 -> "" (dimensionless)
```

the loader either records the field as absent (no entry in `by_name`)
or validates the entry's `unit` against the expected one. A unit
mismatch is a hard `CalibrationParseError` — silent unit drift would
corrupt every downstream computation. A present-with-null `value` is
recorded under `MissingnessStats.explicit_null` and surfaced as `None`
on the typed dataclass, because consumers treat the two
indistinguishably. A NaN `value` is preserved as `float('nan')` and
counted under `MissingnessStats.nan_present`; the Skip-strategy
aggregators drop it from the mean.

Time fields are scaled to SI seconds at load (`*1e-6` for `us`,
`*1e-9` for `ns`); dimensionless fields are passed through. The
post-condition is that every `ParsedQubitCalibration` field carrying a
finite float is in SI units.

The aggregators `mean_t1` and `mean_t2` are deliberately simple list
comprehensions plus an arithmetic mean; they exclude `None` and NaN,
return `None` if the surviving list is empty, and never raise. The
existing `BasicCalibrationVectorizer.extract` is left alone — it raises
on empty inputs, which is the right behavior for its caller (the
3×3×3 rule-base feature vector). The two functions coexist because they
serve different consumers.

## Mathematical / Statistical details

The aggregate is the arithmetic mean over the surviving values:

```
mean_T1 = (sum_{i in S} T1_i) / |S|
```

where `S = { i : T1_i is not None and not isnan(T1_i) }` is the set of
qubit indices with a usable `T1`. If `|S| = 0` the function returns
`None`. The Skip strategy is unbiased relative to imputing from the
population: it does not pull the aggregate toward an external mean. It
does reduce statistical power by `|S| / n_qubits`, which is the
missingness rate the snapshot reports. The chosen exemplar's
missingness rate for `T1` is `1/156 ≈ 0.64 %`.

The dimensional analysis at unit scaling is fixed-factor: `1 us =
10^-6 s`, `1 ns = 10^-9 s`. The expected-unit table is a constant in
the loader; if IBM ever changes the wire format we want the loader to
fail loudly on first read rather than silently drift.

## Design decisions

Alternatives weighed for ADR-017:

- **Impute from population**: inject the population mean (or a
  per-snapshot mean over the surviving qubits) into the missing slot.
  Rejected because it biases the aggregate toward the population it was
  computed from and is indistinguishable downstream from real data —
  the missingness footprint disappears.
- **Fuzzy with a max-entropy footprint**: carry an interval-valued
  uncertainty for the missing entry forward into the fuzzification
  layer. This is the planned long-term migration target but requires
  ADR-007 / ADR-009 to resolve first. The typed loader makes this
  migration cheap: an `Optional[float]` field swaps to a
  `MembershipDegree`-typed field without restructuring callers.
- **Raise on missing fields**: simplest, but the snapshot is otherwise
  fully usable and many downstream consumers can absorb the gap. The
  Skip strategy preserves the snapshot.

Naming: the existing
`superconducted.types.CalibrationSnapshot` already represents the raw
archive form (`properties: dict[str, Any]`). The new types are
prefixed `Parsed` (`ParsedCalibrationSnapshot`,
`ParsedQubitCalibration`) to keep both shapes addressable without
clobbering imports.

Distinction between *absent* and *explicit null* is preserved in
`MissingnessStats` even though both collapse to `None` on the typed
field. The two paths reflect different upstream failure modes (the
Nduv was never recorded vs. the Nduv was recorded but its value didn't
serialize) and operators may want different alarms for each.

## Verification

Run from the repo root:

```bash
pytest tests/calibration/ -v
pytest -v
ruff check src/superconducted/calibration tests/calibration
mypy src/superconducted/calibration
```

Locked-file no-touch verification:

```bash
git diff --exit-code "$(git merge-base HEAD origin/main)" -- \
    src/superconducted/calibration/poller.py \
    src/superconducted/calibration/storage.py
```

Manual fixture regeneration recipe lives in
`tests/fixtures/calibration/README.md`.

## Related docs

- `docs/decisions.md` — ADR-017 (Skip strategy)
- `docs/decisions.md` — ADR-013 (Calibration feature engineering;
  future fuzzy treatment lands here)
- GitHub issue #9 (the originating bug report)
- Locked-file ticket: #002 (`poller.py`, `storage.py`)
