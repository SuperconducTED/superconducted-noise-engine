# Team

## Roster

| Name | Role | Primary modules |
| --- | --- | --- |
| Two leads | Project leads | `interfaces.py`, `types.py`, CI / pyproject, ADR ledger |
| Burak Öztekin | CS&EE senior | `fuzzy/tsk.py` (LOCKED), `fuzzy/fuzzification.py`, `integration/aer_factory.py`, `benchmarks/harness.py` |
| Baha Jarad | CS&EE junior | `calibration/poller.py`, `calibration/storage.py`, `calibration/features.py` |
| Yiğit Arda Kaderoğlu | CS sophomore | `fuzzy/membership.py`, `fuzzy/squashing.py`, `benchmarks/circuits.py` |
| Bengisu | Math junior | `fuzzy/defuzzification.py`, `channels/kraus.py` (LOCKED, co-owned), `benchmarks/metrics.py` |
| Fırat Akba | Faculty advisor | Reviews `docs/architecture.md` and architectural ADRs |

## Module ownership

| Module | Primary owner | Secondary reviewer |
| --- | --- | --- |
| `interfaces.py`, `types.py` | Two leads (joint) | — |
| `calibration/poller.py` | Baha Jarad | Two leads |
| `calibration/storage.py` | Baha Jarad | Two leads |
| `calibration/features.py` | Baha Jarad | Bengisu |
| `fuzzy/membership.py` | Yiğit Arda Kaderoğlu | Burak Öztekin |
| `fuzzy/tsk.py` (LOCKED) | Burak Öztekin | Two leads + Bengisu |
| `fuzzy/defuzzification.py` | Bengisu | Burak Öztekin |
| `fuzzy/fuzzification.py` | Burak Öztekin | Two leads |
| `fuzzy/squashing.py` | Yiğit Arda Kaderoğlu | Bengisu |
| `channels/kraus.py` (LOCKED) | Bengisu | Burak Öztekin |
| `integration/aer_factory.py` | Burak Öztekin | Two leads |
| `benchmarks/circuits.py` | Yiğit Arda Kaderoğlu | Burak Öztekin |
| `benchmarks/metrics.py` | Bengisu | Two leads |
| `benchmarks/harness.py` | Burak Öztekin | Two leads |
| `tests/*` | Owner of the implementation under test | — |
| `docs/architecture.md` | Two leads | Fırat Akba |
| `docs/decisions.md` (ADR ledger) | Two leads | — |
| CI / pyproject / requirements | Two leads | — |

## How ownership works

- **Primary owner** reviews every PR that touches their files. They are
  the default reviewer requested on a draft PR.
- **Secondary reviewer** stands in when the primary owner is unavailable.
- **Locked modules** (`fuzzy/tsk.py`, `channels/kraus.py`) require BOTH
  the primary owner and the secondary reviewer to sign off, plus a
  reference to an ADR in `docs/decisions.md` if the change touches the
  locked math.
- **Cross-cutting changes** (CI, pyproject, requirements, ABCs in
  `interfaces.py`) need both leads' approval.
- If you're unsure who owns a file, look in this table or ask in chat
  before opening a PR.

## Updating this file

Update this file when:
- A team member joins or leaves.
- Module ownership shifts (record the date in the PR description).
- A new module appears in the source tree — add a row before merging.
