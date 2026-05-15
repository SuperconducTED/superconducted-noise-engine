# Implementation: Harness Metric Sanity Checks

## Problem/Motivation
The core benchmarking metrics (Hellinger Distance, KL Divergence, State Fidelity, and R2 Score) require rigorous mathematical validation. Before using them to evaluate noise engine outputs, we must ensure they adhere strictly to their theoretical constraints (identity, symmetry, asymmetry, and bounds).

## What Changed
| Module | Change |
| :--- | :--- |
| `tests/test_harness_validation.py` | Added 10 boundary/property tests for all core metrics. |
| `docs/implementations/` | Added this mathematical detail and implementation document. |

## Implementation Approach
We introduced a dedicated test suite using `pytest` to evaluate the metric classes in an isolated environment. The tests supply predetermined input distributions and quantum states to verify that the computed outputs match theoretical expectations.

## Mathematical Details
The test suite covers the following mathematical properties and formulas:

**1. Hellinger Distance**
Calculates the statistical distance between two probability distributions $P$ and $Q$.
$$H(P, Q) = \frac{1}{\sqrt{2}} \sqrt{\sum_i (\sqrt{p_i} - \sqrt{q_i})^2}$$
- Validated Identity: $H(P, P) = 0.0$
- Validated Symmetry: $H(P, Q) = H(Q, P)$
- Validated Disjoint Bounds: $H(P, Q) = 1.0$ (when completely disjoint)

**2. Kullback-Leibler (KL) Divergence**
Measures how one probability distribution $P$ diverges from a second, expected probability distribution $Q$.
$$D_{KL}(P \parallel Q) = \sum_x P(x) \log\left(\frac{P(x)}{Q(x)}\right)$$
- Validated Identity: $D_{KL}(P \parallel P) = 0.0$
- Validated Asymmetry: $D_{KL}(P \parallel Q) \neq D_{KL}(Q \parallel P)$

**3. State Fidelity**
Measures the "closeness" of two quantum states described by density matrices $\rho$ and $\sigma$.
$$F(\rho, \sigma) = \left( \text{Tr} \sqrt{\sqrt{\rho} \sigma \sqrt{\rho}} \right)^2$$
- Validated Identity: $F(\rho, \rho) = 1.0$
- Validated Symmetry: $F(\rho, \sigma) = F(\sigma, \rho)$
- Validated Orthogonality: $F(\rho, \sigma) = 0.0$ (for completely orthogonal states)

**4. R2 Score**
Assesses the goodness of fit.
$$R^2 = 1 - \frac{\sum_i (y_i - f_i)^2}{\sum_i (y_i - \bar{y})^2}$$
- Validated Perfect Match: $R^2 = 1.0$
- Validated Constant Mismatch Fallback: Returns $0.0$ when reference is uniform and output deviates.

## Design Decisions
- **Isolated testing:** We directly instantiate metric classes without invoking the full simulation runtime to isolate mathematical logic from engine overhead.

## Verification
All mathematical constraints were verified via `pytest` passing successfully.

## Related Docs
- This document replaces the deprecated `docs/findings/harness-validation.md`.