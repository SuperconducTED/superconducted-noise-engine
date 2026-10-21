# Provisional benchmark-resolution measurement

Status: **diagnostic only; not yet a registered numerical claim**.

This is the laptop run required by issue #58. It is `provisional, placeholder ladder`:
#59's accepted calibration survey is not merged, and the geometric ladder must be rerun
against that survey before #62's resolution probe. In addition, QFT(3)'s nearly uniform
output makes its counts-mode R² denominator shot-noise dominated. The TSV preserves that
cell, but no QFT R² or protocol-level counts resolution is registered while its treatment
remains an open decision on #58.

## Provenance

- Generator commit: `1ae6c3a0c2811412ba89376c557e122347d454a0`.
- Evidence commit: `611901784979dbc5a62eec48fa27987f27a1d055`.
- Source baseline: the agreed #57 fixture in PR #69, inspected without copying it into
  this branch. The mean 24 ns `sx` closed-form targets over its 155 usable qubits are
  `gamma_0 = 0.00017266737044123665` and
  `lambda_0 = 0.0006630210259092216`; q72 is skipped without imputation.
- Explicit basis: `cz,id,rx,rz,sx,x`, exactly the May fixture's unitary gate set.
- Counts protocol: 32 independent pairs, 4096 shots per sample, predeclared base seed 58.
  Replicate `i` uses seeds `58 + 2i` and `58 + 2i + 1` for the same-model floor and
  reuses `58 + 2i` for the paired A/B comparison.
- Density protocol: exact Aer density-matrix evolution with semantic `shots=1`; no
  simulator seed is used.
- Software: Python 3.13.14, Qiskit 2.4.1, Qiskit Aer 0.17.2, NumPy 2.4.4,
  SciPy 1.17.1, Windows.
- Canonical measured wall time: 15.404588 seconds. Runtime is informational, not an acceptance
  threshold.
- TSV SHA-256: `7720006383eef24dcadfa9f66115db23eec078115c22de820fdfa61360e94cfd`.
- Regeneration contract (NFR-1): the schema, protocol/input/provenance fields, verdicts,
  ordering, and seeded counts rows match exactly. Density-matrix measurement fields may
  differ across machines by at most absolute `1e-12`; repeated serialization of the same
  locally measured rows remains byte-identical. The committed TSV itself is not rounded.

Run from the repository root:

```powershell
python -m scripts.resolution_measurement --gamma "0.00017266737044123665" --lambda "0.0006630210259092216" --deltas "0.1" "0.01" "0.001" "0.0001" --repeats 32 --shots 4096 --seed 58 --basis-gates cz,id,rx,rz,sx,x --output docs/evidence/resolution-measurement/resolution.tsv
```

## Decision rule

For a counts metric discrepancy `D`, each delta uses

```text
d0_i = D(A_seed(58+2i), A_seed(58+2i+1))
d1_i = D(A_seed(58+2i), B_seed(58+2i))
threshold = mean(d0) + 3 * sample_std(d0, ddof=1)
resolved = mean(d1) >= threshold
```

Here `D` is Hellinger distance or the lead- and caller-approved correction
`D_R2 = 1 - R²`. The latter has identity value zero and grows as fit worsens; applying the
same inequality to raw R² would reverse the physical direction.

Density mode records `1 - F(rho_A, rho_B)` and resolves a cell only when it exceeds the
stated `1e-10` numerical floor. A protocol-level mode result uses the caller-approved
conservative quantifier: every defined circuit/metric cell at that delta must resolve.
The per-cell rows remain the audit trail.

## Observed diagnostics

- Counts mode: no tested delta resolves every defined cell. QFT Hellinger resolves only
  `0.1`; QFT `1 - R²` resolves none. GHZ Hellinger and `1 - R²` each resolve `0.01` and
  `0.1`.
- QFT `1 - R²` has same-model mean `2.2015236552710293`, sample standard deviation
  `1.5700033940263955`, and threshold `6.9115338373502162`. This empirically confirms the
  structural instability raised on #58: the denominator is governed by finite-shot
  fluctuations around an almost uniform distribution.
- Density-matrix mode: both circuits exceed `1e-10` at every tested delta, including
  `0.0001`. This means `0.0001` is the smallest **tested** resolved delta, not a lower
  bound on the true resolution; no extrapolation below the ladder is made.

The exact values for all 24 `(circuit, mode, metric, delta)` cells are in
`resolution.tsv`. Numerical-claim IDs are deliberately not allocated in this draft. The
counts claim remains blocked on the QFT R² decision, every laptop result remains
provisional until Burak's batch-1 desktop verification, and any eventual IDs will be
chosen from the merge-time ledger head rather than reserved here.

---

## As of 2026-10-21: spread-anchored, engine-true rerun

Everything above describes the 2026-09-06 run and is left as written. This section adds
the rerun FR-7 requires once #59's survey exists, in a second file,
`resolution-2026-10-21-spread-ladder.tsv`. `resolution.tsv` is unchanged and still
regenerates exactly at this commit.

Two inputs changed, both chosen by @bengisucvd on 2026-10-21 before the run:

- **Ladder.** `delta_k = s_gamma * 2^k` for `k = 3, 2, 1, 0, -1, -2, -3`, where
  `s_gamma = 7.600232779751463e-05` is the sample standard deviation (`ddof=1`) of the
  per-qubit `sx` target `gamma_q = 1 - exp(-t_q / T1_q)` over the 155 usable qubits of
  `tests/fixtures/calibration/ibm_fez_20260513T121322Z_with_gates.json` (NC-038; q72
  skipped as `t1_missing`). It is the target-space counterpart of #59 decision 3's
  within-device spread `s_q`. Multiplying by a power of two is exact in binary floating
  point, so the seven rungs are exact multiples.
- **Eligibility.** The controlled model follows ADR-028: `--eligibility-snapshot` applies
  the shipped `CalibrationGateEligibilityPolicy` to the same fixture (624 operations,
  `id`, `rx`, `sx`, `x` on all 156 qubits), so the zero-length virtual `rz` carries no
  channel, exactly as in `FuzzyNoiseModel.prepare` since PR #96. The 2026-09-06 run
  noised `rz` too. At `delta = s_gamma` this changes the density discrepancy from
  `1.492e-05` to `1.349e-05` (QFT) and from `1.619e-05` to `6.545e-06` (GHZ), so the two
  runs are not directly comparable cell by cell. Those four figures are in neither TSV;
  they come from the density rows of
  `measure_resolution(gamma=0.00017266737044123665, lam=0.0006630210259092216,
  deltas=[7.600232779751463e-05], repeats=2, shots=64, seed=58,
  basis_gates=["cz", "id", "rx", "rz", "sx", "x"], eligible_operations=E)` with `E = None`
  and with `E = eligible_operations_from_snapshot(<the fixture>)`; density rows do not
  depend on `repeats`, `shots` or `seed`.

Unchanged: `gamma_0`, `lambda_0` (NC-040), basis `cz,id,rx,rz,sx,x`, 32 pairs, 4096 shots,
base seed 58 with the same seed schedule, the `1e-10` density floor, the decision rule,
and the conservative all-cells quantifier.

### Provenance

- Generator and evidence commit: `eba93cf2432e97cc23c446adf4acbcbf63ba357d` (script, tests
  and TSV land together; the script at that commit is the generator).
- Merged tree: `main` @ `6cf008d` into this branch.
- Software: Python 3.12.10, Qiskit 2.4.1, Qiskit Aer 0.17.2, NumPy 2.4.4, SciPy 1.17.1,
  Windows (Mert's laptop).
- Measured wall time: 15.508779 seconds (informational).
- TSV SHA-256: `b43cdeb5dd7f339f4c228d50535191253530620bcb076f51ed7485744988d052`.
- `s_gamma` was re-measured two ways before use: through `training.targets.qubit_targets`
  and by the closed form applied directly to the fixture JSON; both give
  `7.600232779751463e-05` (the 2026-09-06 figure on #58, `7.600232779751465e-05`,
  differs only in the sixteenth significant digit).

Run from the repository root:

```powershell
python -m scripts.resolution_measurement --gamma "0.00017266737044123665" --lambda "0.0006630210259092216" --deltas 0.000608018622380117 0.0003040093111900585 0.00015200465559502926 7.600232779751463e-05 3.8001163898757316e-05 1.9000581949378658e-05 9.500290974689329e-06 --repeats 32 --shots 4096 --seed 58 --basis-gates cz,id,rx,rz,sx,x --eligibility-snapshot tests/fixtures/calibration/ibm_fez_20260513T121322Z_with_gates.json --output docs/evidence/resolution-measurement/resolution-2026-10-21-spread-ladder.tsv
```

### Observed

- **Counts mode: no cell resolves at any rung.** All 28 counts cells fail, so the
  protocol verdict `not resolved on ladder` no longer rests on the QFT `1 - R²` cell
  alone. The closest cell is GHZ Hellinger at `8 s_gamma`: between-model mean
  `0.021947`, threshold `0.034789`. At 4096 shots, counts mode does not separate two
  engines whose `gamma` differs by up to eight times the device's own cross-qubit spread.
- **Density-matrix mode: every rung resolves**, down to `s_gamma / 8 = 9.500290974689329e-06`,
  where `1 - F` is `2.2573045155294125e-07` (QFT) and `1.1535033328513578e-07` (GHZ), three
  orders of magnitude above the `1e-10` floor. The smallest tested rung is again the
  ladder's floor, not the instrument's: `<= 9.5e-06 tested, ladder-limited`. No value
  below the ladder is inferred.
- **Analytic check.** Fidelity is stationary at `delta = 0`, so `1 - F` should scale as
  `delta^2` for small `delta`. Halving `delta` divides the QFT discrepancy by `3.31`,
  `3.55`, `3.73`, `3.85`, `3.92`, `3.96` down the ladder, converging to `4`; GHZ behaves the
  same way.

These are laptop figures, provisional until Burak's next batched desktop record. Their NC
ids are taken at merge time.
