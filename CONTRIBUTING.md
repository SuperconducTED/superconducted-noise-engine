# Contributing to the noise engine

This guide covers `superconducted-noise-engine`. The organisation's
[general guide](https://github.com/SuperconducTED/.github/blob/main/CONTRIBUTING.md)
covers what every SuperconducTED repository shares: the values, how to find an
issue, the issue-first flow and what a pull request should show. Read it too.
**Where the two differ, this file and the documents it links to take precedence.**

Everyone taking part follows the
[code of conduct](https://github.com/SuperconducTED/.github/blob/main/CODE_OF_CONDUCT.md).
Questions go to [Discussions, Q&A](https://github.com/SuperconducTED/superconducted-noise-engine/discussions/categories/q-a),
or to the Question form if you want them tracked as an issue. Security problems are
never reported in public: follow the
[security policy](https://github.com/SuperconducTED/.github/blob/main/SECURITY.md).

## Read first

| Document | What it settles |
| --- | --- |
| [`docs/architecture.md`](docs/architecture.md) | The pipeline and the interfaces a change has to fit |
| [`docs/decisions.md`](docs/decisions.md) | The decision ledger (ADRs). An Accepted decision is locked; a change that touches one, or an Open one, cites it |
| [`docs/team.md`](docs/team.md) | Who owns and reviews each module, the rules for locked modules and cross-cutting changes, and the repository's documentation conventions |
| [`docs/numerical-claims.md`](docs/numerical-claims.md) | Every specific number in a public-facing document traces to a row here, or is removed before merge |
| [`.github/pull_request_template.md`](.github/pull_request_template.md) | The hard constraints every pull request is checked against |

## Rules specific to this repository

- **Ownership.** Request a review from the primary owner of every module you
  touch, as listed in [`docs/team.md`](docs/team.md). Locked modules and
  cross-cutting changes need the extra sign-offs that file describes.
- **Decisions.** A new architectural decision gets an ADR in
  [`docs/decisions.md`](docs/decisions.md). Allocate ADR and NC identifiers at
  merge time, never in a draft; `python scripts/check_ids.py` (run in CI) fails on
  a colliding identifier.
- **Numbers.** A number you add to a public-facing document gets a row in
  [`docs/numerical-claims.md`](docs/numerical-claims.md) in the same pull request.
- **Implementation document.** Every meaningful change adds
  `docs/implementations/YYYY-MM-DD-<slug>.md`, copied from
  [`docs/implementations/_TEMPLATE.md`](docs/implementations/_TEMPLATE.md).
- **Secrets.** Never commit a real `IBM_QUANTUM_TOKEN`. `.env` is gitignored;
  `.env.example` is the template.

## Checks before you push

Install from the pins, as CI does, then run the same gates CI runs
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)):

```bash
pip install -r requirements.txt -r requirements-dev.txt
pip install -e . --no-deps
ruff check .
ruff format --check .
python scripts/check_ids.py
mypy --strict
pytest tests/
```

Paste their output, or the CI run, into the pull request as evidence.
