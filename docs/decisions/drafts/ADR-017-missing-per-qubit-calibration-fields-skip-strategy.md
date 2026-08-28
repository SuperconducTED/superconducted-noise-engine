# ADR-017 — Missing per-qubit calibration fields: Skip strategy

**Status**: Accepted.

**Context**: Real IBM `properties()` responses occasionally omit per-qubit
`T1` and `T2` Nduv entries when the coherence measurement fails during the
calibration window. The exemplar at
`origin/calibration-data:snapshots/2026-05/ibm_fez/20260513T121322000000Z.json`
shows this on qubit 72 of `ibm_fez`: the qubit is still in
`properties.qubits` with `readout_error`, `prob_meas0_prep1`,
`prob_meas1_prep0`, and `readout_length` intact, but the `T1` and `T2`
records are simply absent. Any code that does `qubit["T1"]` raises. We
considered three treatments — Skip (drop the qubit from aggregates),
Impute (fill from a population statistic), and Fuzzy (carry uncertainty
forward via a max-entropy footprint). Impute invents data and biases the
aggregate toward the population, which is wrong for the per-snapshot
view. Fuzzy is the right long-term answer but requires the
fuzzification layer (ADR-007 / ADR-009) to land first.

**Decision**: Bootstrap uses the **Skip** strategy. The typed loader
(`superconducted.calibration.loader.load_snapshot`) materializes every
per-qubit field as `Optional[float]`. A field is `None` when the Nduv
entry is absent from the raw JSON *or* present with a JSON-null value;
a field is `float('nan')` when the Nduv entry is present with a NaN
value. `MissingnessStats` on the snapshot carries one
`FieldMissingness` per tracked field; each `FieldMissingness` has
three disjoint counters (`absent`, `explicit_null`, `nan_present`) so
the distinction is preserved for diagnostics and for the eventual
migration to a fuzzy treatment. The mean-aggregate features
(`mean_t1`, `mean_t2`) exclude `None` and NaN entries from the average
and return `None` when no qubit has a usable value, rather than
raising — the caller decides whether to skip the snapshot.

**Consequences**: Aggregates are unbiased relative to the
population-impute alternative but lose statistical power proportional
to the missingness rate. Per-snapshot `MissingnessStats` are persisted
in-memory only; surfacing them through `BasicCalibrationVectorizer` and
through the eventual fuzzy layer is a follow-up. The existing
`BasicCalibrationVectorizer.extract` predates this ADR and remains
unchanged: it consumes the raw `properties` dict directly and is
unaffected as long as at least one qubit per field has a finite value.

`mean_t1` and `mean_t2` are currently free module-level functions in
`features.py`, not implementations of `CalibrationFeatureExtractor`.
This is intentional for the bootstrap: the Skip strategy reduces to a
one-liner arithmetic mean over `Optional[float]`, and wrapping it in an
ABC subclass would add layering without changing behaviour. A
follow-up will introduce
`SkipStrategyVectorizer(CalibrationFeatureExtractor)` once a second
consumer pattern emerges (e.g. when ANFIS training begins consuming
vectorized features alongside the mean aggregates).
