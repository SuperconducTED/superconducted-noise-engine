# Decisions from Dr. Akba

The single location where an advisor decision is recorded. Every phase-3 ticket cites
this path; none proposes another (Issue #56 FR-12).

Dr. Fırat Akba has no GitHub account and is not a repository collaborator (#25's
2026-08-28 comment). His sign-off cannot be a review request and must not be written as
one. It is obtained out of band via @mertefesensoy and recorded here.

> **NOTE · This file is append-only.** One dated entry per decision, appended below the
> previous. Nothing above a new entry is edited. A decision that has not been answered by
> its decision-by date is recorded as outstanding with the date it was asked, because a
> recorded gap is a record and a silence is not.

> **NOTE · Two tickets claim this file.** Issue #56 (FR-12) and Issue #84 (§5) both own
> creating it. Issue #56 created it on 2026-09-09. Issue #84 appends its ADR-027 entries
> below rather than re-creating the file. `scripts/check_ids.py` checks identifiers, not
> file creation, so it would not have caught a double create.

---

## Starting position, as of 2026-09-09

This is a verified fact, not an estimate.

**None of the ten questions in `docs/advisor/2026-05-25-questions-for-akba.md` has a
recorded answer anywhere in this repository or on GitHub.** The advisor loop has never
closed once in this project.

The only recorded advisor inputs on `main` are:

| Input | Where |
| --- | --- |
| "Advisor sign-off obtained" | `docs/decisions.md`, ADR-001 |
| The April-2026 tanh membership-function recommendation | Issue #2's body; `docs/decisions.md` ADR-006 and ADR-019 Context |

Nothing else. Every other statement about what the advisor thinks is inference.

---

## Outstanding items

The 2026-09-09 batch (`docs/advisor/2026-09-09-akba-brief/`) is the single message that
carries these. It was batched deliberately: thirteen separate asks to someone with no
GitHub account is how the 2026-05-25 set went unanswered for three months.

Items are triaged. **Ask** means the answer is his to give and we cannot get it by
measuring. **Ratify** means we have measured or will measure it and need his confirmation,
not his design. **Withdrawn** means Issue #56 listed it and this record removes it from the
ask, with the reason stated, because sending a question we can settle ourselves wastes the
one advisor channel this project has.

| # | Item | Class | Decision-by | Status |
| --- | --- | --- | --- | --- |
| 1 | ADR-027 target, decisions D1, D3, D4 (Issue #57 / #84) | Ratify | 2026-09-16 | Outstanding |
| 1b | ADR-027 decision D2 (where gate lengths are parsed) | Withdrawn | n/a | Internal ownership question between @mertefesensoy and @BahaJarad. Not an architectural decision. |
| 2 | ADR-025 `duplicate-partial` amendment (owed on PR #55) | Ask | 2026-09-16 | Outstanding |
| 3 | ADR-009, T1 vs Interval Type-2 | Ask (scope) + Ratify (evidence) | 2026-09-23 | Outstanding, evidence pending #60 / #62 |
| 4 | ADR-011, Nie-Tan vs Karnik-Mendel | Ratify | 2026-09-23 | Outstanding, measurement pending #61 |
| 5 | ADR-014 status flip, Deferred to Accepted | Ratify | 2026-09-30 | Outstanding, pending #60 |
| 6 | ADR-015, ensemble sampling mechanism | Ask | 2026-09-23 | Outstanding |
| 7 | ADR-016, interval aggregation semantics | Ask | 2026-09-30 | Outstanding, pending #64 |
| 8 | ADR-019 closure, ablation winner | Ratify | 2026-09-23 | Outstanding, measurement pending #62 |
| 9 | ADR-013 revisit, richer feature extractors | Withdrawn | n/a | Deferred by its own text until the floor is met; NC-025 records 504 distinct states against a floor this phase re-derives. Nothing to decide yet. |
| 10 | `interfaces.py` `TSKTrainer` owner read | Ask (authority) | 2026-09-16 | Outstanding |
| 11 | `interfaces.py` `MemberPerturbation` owner read | Withdrawn | n/a | **The contract does not exist.** `grep -rn MemberPerturbation src/ tests/ docs/` at `5f935ea` returns nothing. It is a planned ABC for ADR-015 and folds into item 6. |
| 12 | `MembershipFunction` docstring correction owner read | Ask (authority) | 2026-09-16 | Outstanding |
| 13 | The ten 2026-05-25 questions | Mixed, see below | 2026-09-23 | Outstanding |

### Item 13, the ten 2026-05-25 questions

Four are answered in practice by `docs/roadmap/2026-09-03-phase-3-plan.md` and are marked
as such in the brief rather than left hanging. Six remain genuinely open, and five of those
six are the questions only he can answer, because they are about what the field and its
reviewers expect rather than about anything this repository can measure.

| Q | Subject | Class |
| --- | --- | --- |
| Q1 | Is the ensemble architecturally sufficient, or is an escape hatch needed | Ask |
| Q2 | Which variance-injection mechanism to prioritize | Answered by the plan (folds into item 6) |
| Q3 | Metric ordering and the benchmark circuit suite | Ask |
| Q4 | Aggregation contract, mean versus sum | Answered by the plan (ADR-016 aligned 2026-09-07) |
| Q5 | Missing calibration data: skip versus fuzzy maximum entropy | Ask |
| Q6 | Realistic paper submission target and venue | Ask |
| Q7 | Resolve Type-1 versus Type-2 before or after the trainer | Answered by the plan (folds into item 3) |
| Q8 | Expand beyond a single backend before the paper | Ask |
| Q9 | Required level of real-hardware validation | Ask |
| Q10 | Division of cycle-2 work across the team | Answered by the plan (§4) |

---

## Decisions

*No decision has been recorded yet. Entries are appended below as answers arrive, each
naming the question, the answer, the date it was given, the medium it came through, and
the PR or ADR it unblocks.*

<!-- Append one dated entry per decision below this line. Do not edit anything above it. -->
