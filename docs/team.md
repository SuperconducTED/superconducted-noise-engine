# Team

## Roster

| Name | Role | Primary modules |
| --- | --- | --- |
| Dr. Fırat Akba | Faculty advisor | Reviews `docs/architecture.md` and architectural ADRs |
| Mert Efe Şensoy | CS junior | `interfaces.py`, `types.py`, CI / pyproject, ADR ledger |
| Burak Öztekin | CS&EE senior | `fuzzy/tsk.py` (LOCKED), `fuzzy/fuzzification.py`, `integration/aer_factory.py`, `benchmarks/harness.py` |
| Baha Jarad | CS&EE junior | `calibration/poller.py`, `calibration/storage.py`, `calibration/features.py` |
| Yiğit Arda Kaderoğlu | CS sophomore | `fuzzy/membership.py`, `fuzzy/squashing.py`, `benchmarks/circuits.py` |
| Bengisu | Math junior | `fuzzy/defuzzification.py`, `channels/kraus.py` (LOCKED, co-owned), `benchmarks/metrics.py` |

## Module ownership

| Module | Primary owner | Secondary reviewer |
| --- | --- | --- |
| `interfaces.py`, `types.py` | Dr. Fırat Akba | Mert Efe Şensoy |
| `calibration/poller.py` | Baha Jarad | Mert Efe Şensoy |
| `calibration/storage.py` | Baha Jarad | Mert Efe Şensoy |
| `calibration/features.py` | Baha Jarad | Bengisu |
| `fuzzy/membership.py` | Yiğit Arda Kaderoğlu | Burak Öztekin |
| `fuzzy/tsk.py` (LOCKED) | Burak Öztekin | Mert Efe Şensoy + Bengisu |
| `fuzzy/defuzzification.py` | Bengisu | Burak Öztekin |
| `fuzzy/fuzzification.py` | Burak Öztekin | Mert Efe Şensoy |
| `fuzzy/squashing.py` | Yiğit Arda Kaderoğlu | Bengisu |
| `channels/kraus.py` (LOCKED) | Bengisu | Burak Öztekin |
| `integration/aer_factory.py` | Burak Öztekin | Mert Efe Şensoy |
| `benchmarks/circuits.py` | Yiğit Arda Kaderoğlu | Burak Öztekin |
| `benchmarks/metrics.py` | Bengisu | Mert Efe Şensoy |
| `benchmarks/harness.py` | Burak Öztekin | Mert Efe Şensoy |
| `tests/*` | Owner of the implementation under test | — |
| `docs/architecture.md` | Dr. Fırat Akba | Mert Efe Şensoy |
| `docs/decisions.md` (ADR ledger) | Dr. Fırat Akba | Mert Efe Şensoy |
| CI / pyproject / requirements | Dr. Fırat Akba | Mert Efe Şensoy |

## How ownership works

- **Primary owner** reviews every PR that touches their files. They are
  the default reviewer requested on a draft PR.
- **Secondary reviewer** stands in when the primary owner is unavailable.
- **Locked modules** (`fuzzy/tsk.py`, `channels/kraus.py`) require BOTH
  the primary owner and the secondary reviewer to sign off, plus a
  reference to an ADR in `docs/decisions.md` if the change touches the
  locked math.
- **Cross-cutting changes** (CI, pyproject, requirements, ABCs in
  `interfaces.py`) need both Dr. Fırat Akba' and Mert Efe Şensoy's approval.
- If you're unsure who owns a file, look in this table or ask in chat
  before opening a PR.

## Updating this file

Update this file when:
- A team member joins or leaves.
- Module ownership shifts (record the date in the PR description).
- A new module appears in the source tree — add a row before merging.
