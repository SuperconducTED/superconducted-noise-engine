# 2026-10-16: community-files-and-readme-header

> Branch `docs/community-files`. Companion to the organisation-wide community
> health files in `SuperconducTED/.github` (branch `docs/community-health`,
> record `docs/implementations/2026-10-16-community-health-files.md` there).
> Prose style: no em or en dashes.

## Problem / Motivation

On 2026-10-16 GitHub's community profile scored this repository at 37%: it had a
README, an MIT `LICENSE` and a pull request template, but no code of conduct,
contributing guide, security policy or support guide, no description and no
topics. The organisation is adding those files as defaults in its `.github`
repository, and GitHub shows a default in every repository that has no file of
that type of its own. Two of this repository's own files decide how much of that
reaches it:

- **Issue templates are all or nothing.** This repository has its own
  `.github/ISSUE_TEMPLATE/` (`bug.md`, `feature.md`), so none of the default issue
  forms and no default contact links appear on its new-issue page. Without a
  change here, a newcomer would see no route to Discussions, the security policy
  or the code of conduct when opening an issue, and no way to file a question.
- **It has no `CONTRIBUTING.md`.** The organisation's general guide would be shown
  instead, and that guide cannot carry this repository's rules (module ownership,
  the ADR ledger, the numerical claims register, the CI gates) in full.

The repository also had no visual link to the brand adopted on 2026-10-16
(`SuperconducTED/.github`, `brand/`). The owner chose, on 2026-10-16, the four
changes below for this repository.

## What changed

| File | One-sentence description |
| --- | --- |
| `README.md` | Adds the brand README header at the top (loaded by absolute URL from the `.github` repository's `main`, linking to the organisation) and a short "Contributing" section before "License". |
| `CONTRIBUTING.md` | A thin guide: it defers the shared parts to the organisation's guide and points at this repository's own rules in `docs/team.md`, `docs/decisions.md`, `docs/numerical-claims.md`, the pull request template and the CI gates; it takes precedence over the organisation's guide. |
| `.github/ISSUE_TEMPLATE/config.yml` | Contact links on the new-issue page: Discussions Q&A, the security policy, the code of conduct; blank issues stay enabled. |
| `.github/ISSUE_TEMPLATE/question.yml` | A Question issue form, labelled `question`, that points first at Discussions Q&A. |
| `docs/implementations/2026-10-16-community-files-and-readme-header.md` | This record. |

`bug.md`, `feature.md` and `.github/pull_request_template.md` are unchanged.

## Implementation approach

**What this repository shows after both pull requests merge,** file type by file
type:

| File type | Source |
| --- | --- |
| Code of conduct, security policy, support guide | The organisation's defaults in `SuperconducTED/.github` |
| Contributing guide | This repository's `CONTRIBUTING.md` (overrides the default) |
| Issue templates and chooser | This repository's `bug.md`, `feature.md`, `question.yml` and `config.yml` (the default forms never apply here) |
| Pull request template | This repository's own (unchanged) |

**README header.** The header is `brand/kit/web/readme-header-noise-engine.svg`
from the brand kit: a 1280 by 320 banner on its own dark ground (`#0A1B24`), so
one image serves both light and dark mode and needs no `<picture>` switch. It is
loaded from `https://raw.githubusercontent.com/SuperconducTED/.github/main/...`,
which serves SVG as `image/svg+xml` (checked with `curl -I` on the brand branch),
the same way the Cassandra Collective's project READMEs load their marks. The
`# SuperconducTED` heading and the one-line description stay below it, so the
page keeps its text title and anchor for search and screen readers; the image
carries the same sentence as its alt text.

**Forms.** `question.yml` uses only the documented form schema and the existing
`question` label. GitHub shows Markdown templates and YAML forms side by side in
one chooser, so the legacy templates keep working.

**Links.** Links to other repositories are absolute; links inside this repository
are relative, as elsewhere in this README.

## Mathematical / Statistical details

N/A · purely structural (documentation and repository configuration).

## Design decisions

| Decision | Alternatives | Why | Who |
| --- | --- | --- | --- |
| The four changes above | The README header only | Without `config.yml` the defaults' contact links never reach this repository; without a `CONTRIBUTING.md` the general guide would stand in for this repository's rules | Owner, 2026-10-16 |
| Blank issues stay enabled | Disabling them, as the organisation's default `config.yml` does | Leaves the team's existing way of filing issues unchanged; the option the owner chose kept blank issues on | Owner, 2026-10-16 |
| `CONTRIBUTING.md` points at `docs/team.md` and the ledger rather than restating them | Copying the ownership table and rules | One source of truth; `docs/team.md` is updated whenever ownership shifts | Engineering |
| The header loads from the `.github` repository by URL | A copy of the SVG in this repository | One source for the brand; the cost is that the header depends on `.github` staying public, and shows a broken image until the brand pull request (`SuperconducTED/.github#1`) merges | Engineering, following the Cassandra Collective |
| The H1 and one-line description stay under the header | Replacing them with the image | Text stays searchable and readable without images | Engineering |

## Verification

- `question.yml` and `config.yml` pass the issue-form validator described in the
  `.github` record (`validate_forms.py`, PyYAML 6.0.3): `OK: 2 files, every check
  passed (question.yml 3 fields)`. The same validator caught 9 of 9 injected
  faults there.
- No em or en dash in any added line: `git diff origin/main -- . | grep '^+' |
  LC_ALL=C grep -c $'\xe2\x80[\x93\x94]'` gives 0.
- `python scripts/check_ids.py` passes (no ADR or NC identifier is added).
- The test suite does not read any of the changed files:
  `grep -rn -E 'CONTRIBUTING|config\.yml|README' tests/` matches only other
  READMEs (a fixture README, an evidence README, the calibration-data branch
  README and the fixture `test_file_snapshots.py` writes for itself), never the
  root `README.md`, `CONTRIBUTING.md` or `.github/ISSUE_TEMPLATE/`.
- After `SuperconducTED/.github#1` and the `.github` community-health pull request
  merge: open this repository's README on GitHub in light and dark mode and
  confirm the header loads; open "New issue" and confirm the chooser lists Bug
  report, Feature request and Question plus the three contact links; confirm the
  "Contributing" link on the issue page opens this repository's
  `CONTRIBUTING.md`.

**Not tested before merge:** how GitHub renders the header and the chooser (both
depend on the `.github` repository's `main` and this repository's default
branch).

## Related docs

- `SuperconducTED/.github`: `docs/implementations/2026-10-16-community-health-files.md`,
  `2026-10-16-repository-presence.md`, `brand/README.md` ("Digital applications")
- [`docs/team.md`](../team.md), [`docs/decisions.md`](../decisions.md),
  [`docs/numerical-claims.md`](../numerical-claims.md)

## As of 2026-10-16, later

Cherry-picked unchanged onto `main` @ `fec055c1` as branch `mert/readme-citation-community`,
where the README is then rewritten from the beginning and gains a `CITATION.cff`
(`2026-10-16-readme-and-citation.md`). The header now loads
`brand/web/readme-header-noise-engine.svg`: `SuperconducTED/.github` PR #5 moves the kit from
`brand/kit/` to `brand/`.
