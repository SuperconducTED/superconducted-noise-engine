# 2026-09-09: conventions and the advisor decision record

## Problem / Motivation

Issue #56's M0 conventions carve-out (FR-12, FR-14, FR-6 Part 3 items d and g)
was the one part of the phase-3 queue work that nothing else could route around,
and it had not been done. Three separate gaps:

1. **There was no place to record an advisor decision.** `docs/advisor/` held
   exactly one file, the ten questions of 2026-05-25, none of which has a
   recorded answer anywhere in this repository or on GitHub. Every phase-3 ticket
   that needs Dr. Akba (FR-2's ADR-025 sign-off, FR-15's ADR-009 flip, FR-16's
   ADR-011 closure, FR-11's ADR-014 read, and Issue #84's four ADR-027 decisions)
   cites a path that did not exist. Issue #84 §5 flags the hazard explicitly:
   two tickets claim the same file, `scripts/check_ids.py` checks identifiers
   rather than file creation, and two independent creations would merge cleanly
   into a mess.
2. **There was no rule for how many `docs/numerical-claims.md` rows a results
   table is worth,** which is why the ADR-019 ablation ticket priced itself at
   500-600 register rows.
3. **`docs/team.md` carried three of the five conventions FR-6 Part 3 lists.**
   PR #81 landed the dated-doc rule, the live label set and the ASCII-callout
   rule on 2026-09-08. The identifier-allocation rule and the batched
   desktop-verification convention were not landed, and other tickets cite both.

## What changed

| File | One-sentence description |
| --- | --- |
| `docs/advisor/2026-09-03-decisions-from-akba.md` | *New.* The append-only record for every out-of-band advisor decision, opening with the verified starting position and a triaged table of outstanding items. |
| `docs/advisor/2026-09-09-akba-brief/index.html` | *New.* Turkish cover page for the single batched request: what is being asked, what is deliberately not being asked, and the per-item decision-by dates. |
| `docs/advisor/2026-09-09-akba-brief/01-egitim-hedefi.html` | *New.* ADR-027's four decisions plus the module-owner read, with the derivation and the Aer pin that is the whole argument for the target. |
| `docs/advisor/2026-09-09-akba-brief/02-tip-sistemi.html` | *New.* ADR-009 and ADR-011, with the newly measured per-shape parameter counts that undercut the standard "IT2 doubles the parameters" objection. |
| `docs/advisor/2026-09-09-akba-brief/03-topluluk-ve-varyans.html` | *New.* ADR-015 and ADR-016, the Aer no-per-shot-hook constraint, and the fact that today's ensemble members are identical. |
| `docs/advisor/2026-09-09-akba-brief/04-veri-durustlugu.html` | *New.* The ADR-025 amendment, missing-calibration-field policy, backend breadth, and the correction to the training floor. |
| `docs/advisor/2026-09-09-akba-brief/05-yayin-stratejisi.html` | *New.* Venue and timeline, real-hardware validation depth, and metric ordering: the three questions no measurement in this repository can answer. |
| `docs/team.md` | Adds the identifier-allocation rule and the batched desktop-verification convention to `## Documentation conventions`, and points Dr. Akba's roster cell at the advisor record. |
| `docs/numerical-claims.md` | Adds the one-row-per-conclusion granularity sub-section to `## Adding a claim`, with its three citation requirements and the counter-rule for prose figures. |

No executable line changed. No new module, no new dependency.

## Implementation approach

**The advisor record is a ledger, not a mailbox.** It is append-only in the same
sense `docs/decisions.md` is: one dated entry per decision, each naming the
question, the answer, the date it was given, the medium it came through, and the
PR or ADR it unblocks. The file opens with a statement of the starting position
because the alternative, an empty file, reads as "no decisions yet" when the true
state is "the advisor loop has never closed once in this project."

Two structural choices are worth naming:

- **The outstanding-items table carries a class column, not just a list.** Every
  item is `Ask`, `Ratify`, or `Withdrawn`. `Ask` means the answer is his to give
  and no measurement produces it. `Ratify` means we have measured or will measure
  it and want confirmation rather than design. `Withdrawn` means Issue #56 listed
  the item and this record removes it, with the reason recorded in the table.
- **The file names Issue #84 as co-claimant in a callout at the top.** Whichever
  ticket had landed first would have created it; this one did, so #84 appends.

**The brief is one document per thematic cluster, not one per question.** Issue
#56's FR-12 lists thirteen items and Issue #84 expands item 1 into five, which is
roughly twenty-six asks once the ten 2026-05-25 questions are counted. Sending
twenty-six cards to a reader with no GitHub account reproduces exactly the
failure mode that left the 2026-05-25 set unanswered for three months. Clustering
by the decision served (target, type system, ensemble, data, publication) also
lets each document show how its decisions constrain each other, which is most of
the actual content.

Each question carries the same five fields: background, the question, why we are
asking, what the answer buys, and why it needs him rather than an experiment.
Each cluster closes with a "what we are not asking and why" appendix.

**The triage shrinks the ask.** Four items were withdrawn, each for a stated
reason recorded in the advisor record and in the relevant cluster's appendix:

| Withdrawn | Reason |
| --- | --- |
| ADR-027 decision D2 (where gate lengths are parsed) | An internal ownership question between the lead and @BahaJarad. Both options produce the same number and neither is visible outside the repository. |
| ADR-013 revisit | Deferred by its own text until the training floor is met. NC-025 records 504 distinct states against a floor this phase re-derives upward, so there is nothing yet to decide. |
| `MemberPerturbation` owner read | **The contract does not exist.** `grep -rn MemberPerturbation src/ tests/ docs/` at `5f935ea` returns nothing. It is a planned ABC for ADR-015 and folds into the ADR-015 question. |
| 2026-05-25 questions Q2, Q4, Q7, Q10 | Answered in practice by `docs/roadmap/2026-09-03-phase-3-plan.md` and by the 2026-09-07 ADR-016 alignment. Marked as answered in the brief rather than left hanging. |

**The HTML is self-contained by requirement.** Dr. Akba receives these as email
attachments, so every file inlines its own CSS and SVG and loads nothing
external. There is no shared stylesheet: a detached `brief.css` would break the
moment one file is forwarded on its own.

## Mathematical / Statistical details

One measurement was taken to write the type-system cluster honestly, and it is
the input to Issue #56 FR-10's floor derivation.

For a `TSKRuleBase.from_grid` rule base with `R` rules, input dimension `d`,
output dimension `k`, and `U` unique membership-function objects each carrying
`p` parameters, the trainable-parameter count is

```
count = k * R * (d + 1) + U * p
```

The `d + 1` is the affine consequent per rule per output: one coefficient per
input plus a bias. `U` is the count of **unique** membership-function objects,
not antecedent references: `from_grid` iterates the Cartesian product and reuses
one object across every rule naming it, so a 3x3x3 grid has 27 rules and 81
antecedent references over only 9 distinct objects.

Measured at `5f935ea` with `count_trainable_parameters` on a 3x3x3 grid at
`output_dim = 2`, so `R = 27`, `d = 3`, `k = 2`, `U = 9`, and the consequent term
is fixed at `2 * 27 * 4 = 216`:

| Shape | `p` | Premise `U*p` | Consequent | Total | Floor (x5) |
| --- | --- | --- | --- | --- | --- |
| `GaussianMF` | 2 | 18 | 216 | 234 | 1170 |
| `TanhSigmoidMF` | 2 | 18 | 216 | 234 | 1170 |
| `TriangularMF` | 3 | 27 | 216 | 243 | 1215 |
| `TanhBellMF` | 3 | 27 | 216 | 243 | 1215 |
| `IntervalGaussianMF` | 3 | 27 | 216 | 243 | 1215 |
| `TrapezoidalMF` | 4 | 36 | 216 | 252 | 1260 |
| `TanhMF` | 4 | 36 | 216 | 252 | 1260 |

The `GaussianMF` row reproduces NC-037 (234 at candidate `37e1ba0`) exactly,
which is the check that the measurement procedure is the same one the registered
row used. **The other six rows are not registered here.** They are registered by
Issue #56's M3 PR alongside the derived floor, per FR-10.1 and the
next-free-id-at-merge-time rule this PR writes into `docs/team.md`. The brief
states this in the paragraph under the table rather than presenting the figures
as though they were already in the register.

The consequence that matters for ADR-009: moving from `GaussianMF` to
`IntervalGaussianMF` costs `9 * (3 - 2) = 9` parameters, which is 3.8% of 234,
not the doubling the standard objection to IT2 assumes. The consequent term
dominates at 216 of 234, and IT2 touches only the premise term.

## Design decisions

**Why the record shrinks the ask instead of forwarding all thirteen items.**
The alternative considered was to send everything, labelled by class, and let the
advisor triage. It was rejected because it hands him work already done and it
misrepresents our own position: for ADR-011 and ADR-019 we are not asking him to
choose, we are asking him to confirm a measurement that #61 and #62 produce. A
question phrased as open when it is not invites an answer we would then have to
argue with. The withdrawn items are recorded rather than silently dropped, so the
next reader can see that the list went from thirteen to nine and why.

**Why the brief lives in the repository rather than as a hosted page.** Chosen
by the lead. The trade-off is that the advisor cannot click a link and the HTML
sits in git history; the gain is that what was circulated is versioned with the
project, which is the property FR-12 needs for an unanswered item to read as a
record rather than a silence.

**Why the granularity rule is a sub-section of `## Adding a claim` rather than a
new top-level section.** It is a refinement of step 3, not a parallel procedure.
Placing it under the existing numbered list keeps one entry point for "how do I
register something", which is the question the rule exists to answer.

**Why the verification convention names the batch record as the source of truth
rather than deprecating laptop runs.** Laptop runs are still how a PR author
checks their own work before requesting review, and forbidding them would just
mean they happen unrecorded. The rule that carries weight is the one about
*claiming*: a number is verified when it appears in a batch record, and a
provisional run is cited as provisional with the machine named.

## Verification

Run from the repository root at the PR's head.

```bash
# 1. Every HTML file parses, is UTF-8, and declares Turkish.
python - <<'PY'
import glob
from html.parser import HTMLParser
VOID={"area","base","br","col","embed","hr","img","input","link","meta","source",
      "track","wbr","path","rect","circle","line","polygon","text","use","stop"}
class P(HTMLParser):
    def __init__(s): super().__init__(convert_charrefs=True); s.st=[]; s.e=[]
    def handle_starttag(s,t,a):
        if t not in VOID: s.st.append((t,s.getpos()[0]))
    def handle_endtag(s,t):
        if t in VOID: return
        if not s.st: s.e.append(f"stray </{t}> line {s.getpos()[0]}"); return
        top,ln=s.st.pop()
        if top!=t: s.e.append(f"</{t}> closes <{top}> from line {ln}")
for f in sorted(glob.glob("docs/advisor/2026-09-09-akba-brief/*.html")):
    p=P(); p.feed(open(f,encoding="utf-8").read()); p.close()
    print(("FAIL " if p.e or p.st else "OK   ")+f, p.e[:3])
PY

# 2. No emoji anywhere in the brief (NFR-5).
python -c "import glob,re; pat=re.compile('[\U0001F300-\U0001FAFF☀-➿]'); \
print([f for f in glob.glob('docs/advisor/2026-09-09-akba-brief/*.html') \
if pat.search(open(f,encoding='utf-8').read())] or 'no emoji')"

# 3. The handle warning holds: no bare @bengisu anywhere in the change.
grep -rn '@bengisu\b' docs/advisor docs/team.md docs/numerical-claims.md || echo "clean"

# 4. The parameter-count table in cluster 02 reproduces from the code.
python -c "
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.fuzzy.membership import GaussianMF, IntervalGaussianMF
from superconducted.training.parameters import count_trainable_parameters
for cls,kw in ((GaussianMF,dict(sigma=0.15)),(IntervalGaussianMF,dict(sigma_low=0.12,sigma_high=0.18))):
    g=[[cls(center=c,**kw) for c in (0.2,0.5,0.8)] for _ in range(3)]
    print(cls.__name__, count_trainable_parameters(TSKRuleBase.from_grid(g,output_dim=2)))
"
# Expect: GaussianMF total=234 (reproduces NC-037), IntervalGaussianMF total=243.

# 5. No executable line changed, and no dated document lost a line.
git diff main --stat -- src/ scripts/            # expect empty
git diff main -- docs/roadmap/ docs/state-of-the-project/ | grep '^-[^-]' || echo "append-only clean"

# 6. Unchanged against main.
ruff check && ruff format --check && mypy --strict
python -m pytest tests/ --collect-only -q -o addopts="" | tail -1
```

Step 6's collection count is stated differentially against NC-021 in the PR
description, citing the row rather than recalling a number, and is a
**provisional** laptop run per the convention this PR writes into
`docs/team.md`. This PR originates no number that needs canonical verification:
the parameter counts in the mathematics section above are registered by the M3
PR, not here.

## Related docs

- Issue #56 FR-6 Part 3, FR-12, FR-14; NFR-3, NFR-4, NFR-5, NFR-9
- Issue #84 §3, §4, §5 (the ADR-027 decisions and the co-claimed file)
- `docs/advisor/2026-05-25-questions-for-akba.md` (the ten questions the record opens against)
- `docs/decisions.md` ADR-009, ADR-011, ADR-013, ADR-015, ADR-016, ADR-025, ADR-027
- `docs/numerical-claims.md` NC-012, NC-025, NC-037, NC-R001, NC-R002
- `docs/implementations/2026-08-31-adr-nc-collision-and-branch-reissue.md` (why identifiers are allocated at merge time)
- `docs/verification/2026-08-20-pr33-burak-desktop.md` and siblings (the per-PR shape the batch convention replaces)
- `docs/roadmap/2026-09-03-phase-3-plan.md` (the M0-M4 gate text these records cite rather than restate)
