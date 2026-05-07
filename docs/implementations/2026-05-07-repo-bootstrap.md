# 2026-05-07: repo-bootstrap

## Problem / Motivation

The SuperconducTED repository did not exist. The team needed scaffolding
for the Q1 paper deadline, including (a) a stable interface catalogue
covering every research axis still in flux, (b) the locked TSK
inference math and locked CPTP channel module, and (c) a robust
calibration polling script so the ≥630 historical snapshots needed for
ANFIS training could begin accumulating immediately.

## What changed

| File | One-sentence description |
| --- | --- |
| `LICENSE` | MIT license. |
| `.gitignore` | Standard Python excludes plus `.env` and `data/*` (with `.gitkeep` exception). |
| `.env.example` | Template for `IBM_QUANTUM_TOKEN`, `IBM_QUANTUM_CHANNEL`, retry knobs. |
| `README.md` | Public-facing overview, quick start, polling failure modes. |
| `CLAUDE.md` | Operational instructions for future Claude sessions: hard constraints, open decisions, locked zones, "before you write code" checklist. |
| `pyproject.toml` | PEP 621 metadata, hatchling backend, `[tool.ruff]` / `[tool.mypy]` / `[tool.pytest.ini_options]`. |
| `requirements.txt`, `requirements-dev.txt` | Pinned runtime + dev environments. |
| `.github/workflows/ci.yml` | Lint + format + type-check + test on Python 3.11 / 3.12. |
| `.github/ISSUE_TEMPLATE/{feature,bug}.md`, `.github/pull_request_template.md` | Standard contribution templates with hard-constraint review checkboxes. |
| `src/superconducted/__init__.py` | Package root; re-exports every public ABC and value type. |
| `src/superconducted/types.py` | Frozen dataclasses: `MembershipDegree`, `RuleFiringResult`, `CalibrationSnapshot`, `SimulationResult` — each with `__post_init__` validation. |
| `src/superconducted/interfaces.py` | Nine ABCs covering every open research decision. |
| `src/superconducted/calibration/poller.py` | Idempotent, race-safe, retry-aware IBM polling script. CLI entry `superconducted-poll`. |
| `src/superconducted/calibration/storage.py` | Filesystem persistence using `O_CREAT|O_EXCL` for race-safe atomic writes. |
| `src/superconducted/calibration/features.py` | `BasicCalibrationVectorizer` extracting (mean_T1, mean_T2, mean_readout_error). |
| `src/superconducted/fuzzy/membership.py` | Five MF shapes: Gaussian, Triangular, Trapezoidal, Tanh-based, IntervalGaussian. |
| `src/superconducted/fuzzy/tsk.py` | LOCKED. `TSKRule`, `TSKRuleBase`, `from_grid`. Trainer deferred to ADR-014. |
| `src/superconducted/fuzzy/defuzzification.py` | T1 weighted-average + IT2 Nie-Tan closed-form. |
| `src/superconducted/fuzzy/fuzzification.py` | `PostGateFuzzification` full; `Pre`/`Between` stubs deferred to ADR-007. |
| `src/superconducted/fuzzy/squashing.py` | Identity, ProbabilityClip, Sigmoid. |
| `src/superconducted/channels/kraus.py` | LOCKED. `KrausChannelProjector` (single-qubit amplitude+phase damping) + `NoOpNormalization`; SDP-based normalization deferred to ADR-008. |
| `src/superconducted/integration/aer_factory.py` | `FuzzyNoiseModel.prepare(circuit)` and `FuzzyNoiseModelEnsemble` (identical at bootstrap; sampling deferred to ADR-015). |
| `src/superconducted/benchmarks/circuits.py` | Random Clifford, GHZ, QFT (via `QFTGate`), VQE ansatz (via `efficient_su2`). |
| `src/superconducted/benchmarks/metrics.py` | Hellinger, KL, StateFidelity, R². |
| `src/superconducted/benchmarks/harness.py` | Engine-vs-reference benchmark runner; mean-aggregates ensemble counts (interval aggregation deferred to ADR-016). |
| `tests/conftest.py` | Shared fixtures: `tmp_storage`, `dummy_snapshot`, `make_mock_properties`, `make_mock_service`. Absolute imports. |
| `tests/test_interfaces.py` | ABC-instantiation + minimal-stub tests for all nine ABCs. |
| `tests/test_membership.py` | Numerical correctness across all five MF shapes. |
| `tests/test_tsk.py` | Rule firing, rule-base evaluation, `from_grid` Cartesian product, IT2 path, defuzzification correctness. |
| `tests/test_calibration.py` | Storage idempotency + race-safety, JSON encoder, vectorizer, snapshot validation, polling retries / `NotImplementedError` / `properties=None`, CLI exit codes. |
| `notebooks/README.md` | Naming convention; non-importable; promote reusable code before merging. |
| `data/.gitkeep` | Tracks the empty `data/` directory while contents stay gitignored. |
| `docs/architecture.md` | Canonical 6-stage pipeline, Aer Factory/Ensemble diagram, no-per-shot-hook invariant, polling docs, open-decision cross-reference. |
| `docs/decisions.md` | ADR-001 through ADR-016. |
| `docs/team.md` | Roster + module-ownership table. |
| `docs/implementations/_TEMPLATE.md` | Implementation-doc template per global CLAUDE.md. |
| `docs/implementations/2026-05-07-repo-bootstrap.md` | This file. |

## Implementation approach

**Interface-first design.** All swappable research axes route through
ABCs in `interfaces.py`. The TSK inference math (`fuzzy/tsk.py`) and the
CPTP channel construction (`channels/kraus.py`) are concrete and locked
because their correctness is critical and their flexibility is not the
point of the project. Everything else swaps behind an ABC, so trying a
new MF shape, normalization, or feature extractor is a config change,
not a rewrite.

**Bootstrap status per module.** Every Python module declares its
bootstrap status as `full`, `partial`, or `stub` in its docstring.
Deferred functions raise `NotImplementedError("Deferred to ADR-XXX")`
rather than silently no-oping, so the failure mode is loud and points
at the right ADR.

**Phase 0 priority: calibration polling.** The polling script ships on
day one because the dataset is the project's biggest empirical risk.
The script is one-shot (cron-friendly), idempotent (filename-keyed
race-safe writes via `O_CREAT|O_EXCL`), retry-aware (exponential
backoff on `RuntimeError`), and tolerant of access-tier limitations
(`NotImplementedError` on historical queries → log + skip).

## Mathematical / Statistical details

The bootstrap implements three pieces of math directly; everything else
is structural.

**TSK inference (`fuzzy/tsk.py`).**

- *Firing strength* per rule, T-norm = product:

      f = product over input dims i of mf_i.degree(x_i).low

  IT2 carries a separate ``f_high`` from the ``high`` channel of each
  membership degree.

- *Linear consequent* per rule, with bias:

      y = consequent_params @ [x_1, ..., x_d, 1]^T

  ``consequent_params`` shape is ``(output_dim, input_dim + 1)``.

**Defuzzification (`fuzzy/defuzzification.py`).**

- *T1 weighted average*:

      y_d = sum_k(f_k * c_kd) / sum_k(f_k)

  Errors with `ZeroDivisionError` on all-zero firing.

- *IT2 Nie-Tan closed form*:

      y = 0.5 * (sum_k(f_low_k * c_kd) / sum(f_low) +
                 sum_k(f_high_k * c_kd) / sum(f_high))

**Composed amplitude+phase damping (`channels/kraus.py`).**

CPTP-by-construction. With γ ∈ [0,1] for amplitude damping and
λ ∈ [0,1] for phase damping, the four Kraus operators are
`K_amp_i @ K_phs_j` for i,j ∈ {0,1}. Direct algebra confirms
``sum K^† K = I`` regardless of (γ, λ).

## Design decisions

- **Bootstrap status `full | partial | stub` per module** rather than
  hand-waving "TODO." Future contributors know exactly what's
  implemented and what raises `NotImplementedError` pointing at an ADR.
- **Race-safe writes via `O_CREAT|O_EXCL`** instead of write-tmp +
  rename. Both POSIX and Windows guarantee the open-or-fail semantic;
  the rename approach is vulnerable to the second writer clobbering the
  first.
- **Custom `serialize_target()`** rather than `Target.to_dict()`. The
  Target class doesn't have a stable `to_dict()` across Qiskit
  versions; the custom reduced projection (operation names, qargs,
  durations, errors, physical qubits) is forward-compatible.
- **`channel="ibm_quantum_platform"`** as default with `ibm_quantum`
  legacy override. The post-2025 IBM SDK migrated channels; defaulting
  to the modern channel avoids breaking new accounts, while the
  override keeps historical-property access working.
- **mypy 1.20.2 not 2.0.0** for the bootstrap. mypy 2.0.0 was released
  the same day as this commit; pinning the latest 1.x line buys time
  to evaluate 2.0 before adopting it.
- **Drop `PL` from ruff `select`**. PL rules are too noisy on small
  ABCs and factory constructors; we'd be writing `# noqa` everywhere.
  Selected rule families are `E, F, W, I, N, UP, B, C4, SIM, RET, RUF`.

## Verification

- `pip install -r requirements.txt -r requirements-dev.txt`
- `pip install -e . --no-deps`
- `ruff check .` — clean
- `ruff format --check .` — clean
- `mypy --strict src/superconducted` — clean
- `pytest tests/ -v` — all tests pass on Python 3.11 and 3.12
- `superconducted-poll --help` — prints usage and exits 0

For end-to-end polling against real IBM hardware, populate `.env` and
run `superconducted-poll --backend ibm_brisbane`.

## Related docs

- All ADRs in [`docs/decisions.md`](../decisions.md).
- [`docs/architecture.md`](../architecture.md).
- [`CLAUDE.md`](../../CLAUDE.md) (operational instructions for future
  sessions).
