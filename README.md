<p align="center"><a href="https://superconducted.github.io/"><img src="https://raw.githubusercontent.com/SuperconducTED/.github/main/brand/web/readme-header-noise-engine.svg" alt="SuperconducTED noise engine: fuzzy-logic noise engine for Qiskit Aer-based quantum computer emulators" width="100%"></a></p>

# SuperconducTED noise engine

A fuzzy-logic noise engine for Qiskit Aer. It reads IBM's calibration history and aims to give
quantum simulations a range that brackets what the drifting hardware does, instead of one crisp
number. *Noise as a range, not a number.*

[![CI](https://github.com/SuperconducTED/superconducted-noise-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/SuperconducTED/superconducted-noise-engine/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.11%20%7C%203.12-0A1B24)
![license](https://img.shields.io/badge/license-MIT-0A1B24)
![status](https://img.shields.io/badge/status-research%20preview-0A1B24)
[![website](https://img.shields.io/badge/website-superconducted.github.io-0A1B24)](https://superconducted.github.io/)

## Why this exists

IBM measures the noise of its quantum computers many times a day (each qubit's T1 and T2, gate
errors, readout errors), and those numbers drift from one calibration to the next. Qiskit Aer's
`NoiseModel` takes them as crisp scalars: `NoiseModel.from_backend` freezes the latest
calibration, which is exact for that moment and quietly wrong once the machine moves on.

SuperconducTED wraps Aer with a Takagi-Sugeno-Kang (TSK) fuzzy inference layer. It learns how
calibration features relate to noise from an archive of IBM calibration snapshots, and builds an
ensemble of noise models from it. The research aim is interval-valued simulation output that
tracks the hardware across calibration cycles, with the fuzzy layer providing the uncertainty
that a single calibration-based model leaves out.

## Where it stands

**Research preview.** Statements here are aims unless a result is cited.

- **Working today:** the calibration archive and its health monitoring, feature extraction, the
  fuzzy pipeline from end to end, channel projection, and an ensemble of Aer noise models.
- **In progress:** training the rule base with ANFIS. Training needs at least five distinct device
  states per trainable parameter: 234 parameters, so at least 1,170 states (register rows NC-045
  and NC-012).
- **Open:** how the ensemble's members are made to differ (ADR-015), how their results are
  combined into an interval (ADR-016), and whether the type-1 or the interval type-2 path is used
  (ADR-009). Until these are settled, the engine's outputs are point estimates.

The latest status report is [docs/state-of-the-project/](docs/state-of-the-project/), the plan
is in [docs/roadmap/](docs/roadmap/), and every decision is in the
[ADR ledger](docs/decisions.md).

## How it works

Seven stages take one calibration snapshot to one set of Aer noise channels:

1. **Ingest** the snapshot from IBM and archive it.
2. **Extract** three features: the chip's mean T1, mean T2 and mean readout error.
3. **Fuzzify and fire rules:** Gaussian sets over each feature, combined by product into rule
   firing strengths (the rule base is `fuzzy.tsk.TSKRuleBase`).
4. **Defuzzify:** a weighted average of the rules' linear proposals (type-1), or the Nie-Tan
   form for interval type-2.
5. **Squash** the outputs into valid parameter ranges.
6. **Check eligibility:** only gates the snapshot reports get a channel.
7. **Project** each gate's parameters onto an amplitude- and phase-damping channel that Aer can
   serialise.

Aer calls `NoiseModel.to_dict()` once per submission and runs every shot in C++, so the
uncertainty is realised across the ensemble's members, not per shot. The full picture is in
[docs/architecture.md](docs/architecture.md); the idea and the equations, in plain language, are
on the website's [How it works](https://superconducted.github.io/en/how-it-works/) page.

## Quick start

Python 3.11 or newer (CI tests 3.11 and 3.12):

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

## Calibration polling

The `superconducted-poll` console script archives IBM backend calibration snapshots: the
archive ANFIS training draws its distinct device states from. One invocation is one polling
round, and existing snapshot files are skipped, so it is safe to run on a schedule.

```bash
cp .env.example .env
# Edit .env and paste your IBM_QUANTUM_TOKEN
superconducted-poll --backend ibm_fez
```

Add a cron entry (POSIX) or a Task Scheduler entry (Windows) at the cadence you choose. The
project's own archive is filled by the scheduled workflow
[`calibration-poll.yml`](.github/workflows/calibration-poll.yml), which targets one round an hour
(register row NC-008), on the `calibration-data` branch.

### Polling failure modes

| Symptom | Cause | Resolution |
| --- | --- | --- |
| Exit 1, `IBMNotAuthorizedError` in log | Missing or invalid `IBM_QUANTUM_TOKEN` | Regenerate the token at quantum.cloud.ibm.com and update `.env`. |
| Exit 1, channel error | `IBM_QUANTUM_CHANNEL` does not match account | Try `ibm_quantum_platform` (default) or `ibm_quantum` (legacy). |
| Snapshot skipped, `NotImplementedError` | Access tier rejects historical queries | Set `IBM_QUANTUM_INSTANCE` to your hub/group/project, or omit `--historical`. |
| Backend unavailable | Backend not in your allow-list | Check your IBM Quantum account's available backends. |
| Exit 1, retries exhausted | Transient HTTP failure beyond retry budget | Re-run; if persistent, raise `SUPERCONDUCTED_HTTP_RETRIES`. |

Never commit a real token: `.env` is gitignored, and `.env.example` is the template.

## Documentation

| Document | What it holds |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | The canonical design: the pipeline, the Aer integration, the no-per-shot-hook invariant |
| [docs/decisions.md](docs/decisions.md) | The ADR ledger: every architectural decision and its status |
| [docs/numerical-claims.md](docs/numerical-claims.md) | The register every number in the project's public documents traces to |
| [docs/team.md](docs/team.md) | The team, module ownership and review rules |
| [docs/implementations/](docs/implementations/) | One record per change: what, why, how it was verified |
| [superconducted.github.io](https://superconducted.github.io/) | The website, in English and Turkish |

## Team

SuperconducTED is built by undergraduate students at TED University in Ankara, with a faculty
advisor. The roster and the module ownership table are in [docs/team.md](docs/team.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Ask questions in
[Discussions, Q&A](https://github.com/SuperconducTED/superconducted-noise-engine/discussions/categories/q-a);
report security problems privately, as the
[security policy](https://github.com/SuperconducTED/.github/blob/main/SECURITY.md)
describes. Everyone taking part follows the organisation's
[code of conduct](https://github.com/SuperconducTED/.github/blob/main/CODE_OF_CONDUCT.md).

## Citing

If you use the engine in research, please cite it: GitHub's "Cite this repository" button reads
[`CITATION.cff`](CITATION.cff).

## Licence

The code is under the MIT License: see [LICENSE](LICENSE). The SuperconducTED name, mark and
brand files are covered by the organisation's
[brand licence](https://github.com/SuperconducTED/.github/blob/main/brand/LICENSE-BRAND.md).
IBM, IBM Quantum, Qiskit and Qiskit Aer are trademarks of IBM; SuperconducTED is an independent
student project, not affiliated with or endorsed by IBM.
