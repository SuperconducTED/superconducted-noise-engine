# <YYYY-MM-DD>: <slug>

> Copy this template to `docs/implementations/YYYY-MM-DD-<slug>.md` for
> every meaningful change. The global engineering convention requires
> one of these per non-trivial PR — the PR description can summarize,
> but the durable record lives here.

## Problem / Motivation

What gap or risk did this change address? Cite the upstream issue, ADR,
or external bug that triggered the work. One paragraph.

## What changed

| File | One-sentence description |
| --- | --- |
| `path/to/file.py` | What it does after this change. |

## Implementation approach

The "how." Describe the pattern, algorithm, or strategy. If the change
swaps a piece behind an existing ABC in `interfaces.py`, name the ABC
and the concrete class. If a new ABC is introduced, justify it.

## Mathematical / Statistical details

Required if the change involves any formula, statistical test, or
numeric algorithm. Describe in plain English with notation a future
reader can audit without re-reading the code.

Skip this section only for purely structural changes. If you skip it,
say "N/A — purely structural" so the next reader knows the omission was
deliberate.

## Design decisions

What alternatives were considered and why was this approach chosen
over them? Cite the relevant ADR (`docs/decisions.md`) if the decision
touches a locked or open architectural question.

## Verification

Concrete, runnable steps. Examples:

- `pytest tests/test_my_module.py -v`
- `mypy --strict src/superconducted/my_module.py`
- `superconducted-poll --backend ibm_fez --data-dir /tmp/test`

## Related docs

- ADR-### in `docs/decisions.md`
- Section X in `docs/architecture.md`
- Linked GitHub issues / PRs
