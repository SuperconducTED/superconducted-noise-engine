# Premise stage on the planted 3x3x3 grid: recovery and conditioning

These files back the "Planted recovery" and "Identifiability and conditioning"
paragraphs of `docs/implementations/2026-10-18-anfis-premise-stage.md`
(Issue #60, step 6(b)). They are measurements on **synthetic data from a
planted rule base**, not on the calibration archive, and they say nothing about
how well a model fits real devices. That is step 9's findings doc.

## Provenance

| | |
| --- | --- |
| **Commit** | `f5cdfb3` (adds only `reproduce.py` to the code commit `6d98f0d`) |
| **Measured** | 2026-10-18 |
| **Machine** | Linux cloud sandbox, 4 vCPUs, Python 3.13.16, numpy 2.4.4, scipy 1.17.1; the four commands ran in parallel |
| **Status** | Provisional, like any non-desktop run (NFR-8); the seconds per epoch are this machine's under that load, not NFR-5's desktop figure |

## Fixture

The M2 test fixture, `tests/test_anfis.py::_planted_grid`. When this folder was
made, the script's grids and training lattice were compared with the fixture's
and were equal value for value:

- **Planted grid:** three centres per input spanning the NC-041 [p1, p99] box
  in archive units: `mean_T1` 98.8 to 154.4 us, `mean_T2` 67.4 to 110.5 us,
  `mean_readout_error` 0.0171 to 0.0374.
- **Widths:** 20, 16 and 0.012 (IT2: `sigma_high` these, `sigma_low` 0.65 of them).
- **Consequents:** `uniform(0.05, 0.2)` with seed 7.
- **Warm start:** each centre shifted by `(0.12, -0.10, 0.08)` of the centre
  spacing, each width scaled by `(1.2, 0.85, 1.15)`, and consequents
  `uniform(0.05, 0.2)` with seed 42.
- **Training rows:** the 8x8x8 lattice over the box (512 rows); targets are
  the planted model's defuzzified outputs.
- **Held-out rows:** the 125 interior points of a 7x7x7 lattice over the same
  box, interleaved with the training lattice.

All premise errors are in the fit's standardized units
(`TrainingResult.diagnostics.standardization`), positive parameters as they
are, not in log space.

## Files

| File | One row per | Columns |
| --- | --- | --- |
| `recovery-t1.tsv`, `recovery-it2.tsv` | premise learning rate | epochs run, rejected steps, seconds per epoch, initial and final standardized loss, L2 and max premise error at the start and end, held-out max absolute error of the LSE-only fit and of the trained fit, held-out max absolute target |
| `loss-history-t1.tsv`, `loss-history-it2.tsv` | epoch of each run | the standardized training loss (`TrainingResult.loss_history`) |
| `hessian-t1.tsv`, `hessian-it2.tsv` | eigenvalue | the eigenvalues, ascending, of the Hessian of the re-solved loss `S / n` at the planted premise; search-space coordinates (log for positive parameters), standardized units, `ridge = 0`; central second differences with step `1e-3` |

## Reproduce

From the repository root, at `f5cdfb3`:

```bash
python docs/evidence/anfis-premise-stage/reproduce.py recovery t1 --epochs 40 --premise-lr 100 1000 10000
python docs/evidence/anfis-premise-stage/reproduce.py recovery it2 --epochs 40 --premise-lr 100 1000 10000
python docs/evidence/anfis-premise-stage/reproduce.py hessian t1
python docs/evidence/anfis-premise-stage/reproduce.py hessian it2
```

Everything except the seconds per epoch is deterministic on a given machine
(FR-14). Another BLAS may move the last digits.
