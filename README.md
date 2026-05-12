# SuperconducTED

Fuzzy-logic noise engine for Qiskit Aer-based quantum computer emulators.

[![CI](https://github.com/SuperconducTED/superconducted-noise-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/SuperconducTED/superconducted-noise-engine/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![status](https://img.shields.io/badge/status-research%20preview-orange)

## Why this exists

Qiskit Aer's `NoiseModel` accepts crisp scalar parameters (T1, T2, gate error,
readout error) but cannot represent the *epistemic* uncertainty introduced by
calibration drift between IBM hardware updates. SuperconducTED wraps Aer with a
Takagi-Sugeno-Kang (TSK) fuzzy inference layer that ingests IBM calibration
snapshots and produces an ensemble of crisp `NoiseModel` instances sampled from
a fuzzy uncertainty envelope. Aggregated simulation across the ensemble yields
interval-valued predictions that bracket real hardware behavior across
calibration cycles.

The reference benchmark is Bautra et al. 2026 (~0.686% fidelity deviation vs.
real IBM hardware). SuperconducTED's transferability across calibration cycles
is the primary IT2-aligned differentiator that Bautra/SimDisQ do not address.

## Architecture at a glance

A six-stage pipeline: calibration ingestion → feature extraction → fuzzification +
TSK rule firing → defuzzification → squashing → channel projection. Aer
integration uses a Factory/Ensemble pattern that respects Aer's
no-per-shot-Python-hook constraint: epistemic uncertainty is realized at
ensemble construction time, not at simulation time. See [docs/architecture.md](docs/architecture.md)
for the full picture and [docs/decisions.md](docs/decisions.md) for the ADR ledger.

## Quick start

```bash
git clone https://github.com/SuperconducTED/superconducted-noise-engine.git
cd superconducted-noise-engine
python -m venv .venv
# Windows:  .venv\Scripts\activate
# POSIX:    source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e . --no-deps
pytest
```

## Calibration polling (Phase 0 deliverable)

The `superconducted-poll` console script archives IBM backend calibration
snapshots so the team can accumulate the ≥630 historical records needed for
ANFIS training. It is cron-friendly: one invocation = one polling round. It is
idempotent: existing snapshot files are skipped.

```bash
cp .env.example .env
# Edit .env and paste your IBM_QUANTUM_TOKEN
superconducted-poll --backend ibm_brisbane
```

Add a cron entry (POSIX) or Task Scheduler entry (Windows) to invoke it on
your chosen cadence. Recommended: every 4 hours.

### Polling failure modes

| Symptom                                  | Cause                                          | Resolution                                                                        |
| ---------------------------------------- | ---------------------------------------------- | --------------------------------------------------------------------------------- |
| Exit 1,`IBMNotAuthorizedError` in log  | Missing or invalid `IBM_QUANTUM_TOKEN`       | Regenerate the token at quantum.cloud.ibm.com and update `.env`.                |
| Exit 1, channel error                    | `IBM_QUANTUM_CHANNEL` does not match account | Try `ibm_quantum_platform` (default) or `ibm_quantum` (legacy).               |
| Snapshot skipped,`NotImplementedError` | Access tier rejects historical queries         | Set `IBM_QUANTUM_INSTANCE` to your hub/group/project, or omit `--historical`. |
| Backend unavailable                      | Backend not in your allow-list                 | Check your IBM Quantum account's available backends.                              |
| Exit 1, retries exhausted                | Transient HTTP failure beyond retry budget     | Re-run; if persistent, raise `SUPERCONDUCTED_HTTP_RETRIES`.                     |

Never commit a real token. `.env` is gitignored; `.env.example` is the
template.

## Team

Five contributors plus a faculty advisor. See [docs/team.md](docs/team.md) for
the roster and module ownership table.


test test

## License

MIT — see [LICENSE](LICENSE).
