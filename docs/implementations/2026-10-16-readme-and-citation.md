# 2026-10-16: readme-and-citation

Status: **plan, written before the changes it describes**; results go in an as-of section
appended at the end.

## Problem / Motivation

Mert asked on 2026-10-16 for the organisation to be set up "like CASSANDRA", with the READMEs
"written from the beginning properly". Measured against `Cassandra-Collective/CASSANDRA`, the
flagship lacked a branded README, a contributing guide and a `CITATION.cff` (community health
37% against CASSANDRA's 87%). Its README also stated two things that are no longer true:

- "the ≥630 historical records needed for ANFIS training": NC-012 has said at least 1,170
  distinct device states since 2026-09-09 (NC-045: 234 trainable parameters times 5);
- "Five contributors plus a faculty advisor": one contributor has left the team (2026-10-16).

## What will change (planned)

| File | Change |
| --- | --- |
| `README.md` | Rewritten from the beginning: the brand header (from `SuperconducTED/.github`'s `brand/web/`), what the engine is and why, where it stands, how it works, quick start, calibration polling with its failure-mode table, documentation, team, contributing, citing, licence. |
| `CITATION.cff` | New: the software citation GitHub turns into a "Cite this repository" button. |
| `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/config.yml`, `.github/ISSUE_TEMPLATE/question.yml` | From the prepared branch `docs/community-files` (`1efa9fd5`), cherry-picked unchanged: the guide, the chooser's contact links and a Question form. |
| `docs/implementations/2026-10-16-community-files-and-readme-header.md` | From the same commit; one appended as-of section (the header's path moved). |
| `docs/implementations/2026-10-16-readme-and-citation.md` | This record. |

## Implementation approach

- **Every number in the README traces to the register.** The rewrite keeps only figures with a row
  on `main`: the 1,170-state floor and the 234 parameters (NC-012, NC-045), and the hourly polling
  target (NC-008). The proposed NC-067 to NC-069 (PR #116) are not cited until they merge.
- **No team count and no names in the README.** The roster lives in `docs/team.md`, which another
  branch is updating; the README links to it, so it cannot go stale or conflict.
- **The polling failure-mode table stays**: the website's Get started page sends readers to it.
- **The header** loads `brand/web/readme-header-noise-engine.svg` from `.github`'s `main` by raw
  URL; it renders once `SuperconducTED/.github` PR #5 (which moves the kit to `brand/web/`) is
  merged, so this pull request opens after that merge.
- **`CITATION.cff`** follows the Citation File Format 1.2.0: `cff-version`, `message`, `title`,
  `type: software`, `authors`, `version` (0.1.0, from `pyproject.toml`), `license: MIT`,
  `repository-code`, `url`, `abstract`, `keywords`. Authors (Mert's decision, 2026-10-16): Mert
  Efe Şensoy, Burak Öztekin, Baha Jarad, Bengisu Cıvdı and Dr. Fırat Akba, each affiliated with TED
  University. No ORCID iDs are given (none were provided), and no release date (nothing is
  released).

## Mathematical / Statistical details

N/A: documentation and metadata only.

## Design decisions

- **CITATION.cff authors are the current students plus the advisor**, per Mert. A contributor who
  has left is not listed there; the git history credits every commit.
- **The README states status as aims** (the ensemble's sampling and interval aggregation are
  deferred under ADR-015 and ADR-016), matching the website.

## Verification (planned)

- `cffconvert --validate` on `CITATION.cff` (in a scratch environment), and GitHub's "Cite this
  repository" box on the branch.
- Every relative link in `README.md` and `CONTRIBUTING.md` resolves; no em dashes; every number in
  `README.md` maps to a register row.
- After `.github` PR #5 merges: the header image loads on the rendered README.
- The engine's CI passes (docs only, so `NC-021` is unaffected under Rule 6).

## Related docs

- `SuperconducTED/.github` `docs/implementations/2026-10-16-organisation-home.md`
- `docs/numerical-claims.md` (NC-008, NC-012, NC-045)
- `docs/implementations/2026-10-16-community-files-and-readme-header.md`
