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
