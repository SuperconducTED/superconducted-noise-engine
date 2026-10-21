"""Fail a pull request that introduces a colliding ADR or NC identifier.

Why this exists
---------------
Identifier collisions in this repository do not surface as merge conflicts.
Two branches that each append "the next free id" to a *different* decision
touch different regions of the file, so git merges both cleanly and the
duplicate is found later by a reader rather than by CI. Three instances were
live on 2026-09-06:

- PR #69 added a second ``NC-021`` row instead of updating the existing one, so
  the stale value kept reading as current (numerical-claims register Rule 6).
- PR #52 and PR #69 both claimed ``NC-031`` through ``NC-034`` for unrelated
  claims. ``git merge-tree`` on the two heads reports zero conflict markers.
- PR #69 added ``docs/decisions/drafts/ADR-024-calibration-training-target.md``
  while ``docs/decisions.md`` already used ADR-024 for "Degeneracy of random
  TSK consequent initialization" -- a new file, so not even a text conflict.

The draft/ledger rule
---------------------
Six draft files legitimately share an id with a ledger entry today, because a
promoted draft stays in ``drafts/`` as the authoring record. The ledger states
the distinguishing condition itself, in its drafts paragraph: "A draft that has
been promoted stays in ``drafts/`` as the authoring record, and the promoted
entry says so."

Rule A4 below is exactly that sentence: an id present in both places is legal
only when the ledger's own section for that id references the draft's path.
This needs no title comparison and no similarity threshold -- ADR-018's draft
and ledger titles already differ in wording while describing one decision, so
a title match would be both wrong and fitted.

What is deliberately not checked
--------------------------------
- **Gaps in a sequence.** Ids are claimed and then abandoned when a PR closes.
  A gap is not a defect.
- **Citations in prose.** Only *definitions* are collected: ledger headings,
  draft files, and the first cell of a claims-table row. A ``see ADR-014`` in a
  sentence is a reference, not a claim on the id.
- **Whether an id is the next free one across unmerged branches.** CI cannot
  see a sibling branch. This check catches a collision once both sides reach
  ``main``: the second PR to merge goes red instead of merging silently.

Exit status is 0 when clean and 1 when any violation is found. ``--next``
reports the next free ADR and NC id and always exits 0.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Final

LEDGER: Final = pathlib.Path("docs/decisions.md")
DRAFTS: Final = pathlib.Path("docs/decisions/drafts")
CLAIMS: Final = pathlib.Path("docs/numerical-claims.md")

_LEDGER_HEADING: Final = re.compile(r"^##\s+(ADR-\d+)\b")
_DRAFT_HEADING: Final = re.compile(r"^#\s+(ADR-\d+)\b")
_DRAFT_FILENAME: Final = re.compile(r"^(ADR-\d+)-")
_CLAIM_ROW: Final = re.compile(r"^\|\s*(NC-R?\d+)\s*\|")
_SECTION: Final = re.compile(r"^##\s+(.*?)\s*$")


@dataclass(frozen=True, slots=True)
class Definition:
    """One place an identifier is defined, for reporting and duplicate checks."""

    identifier: str
    path: pathlib.Path
    line: int


@dataclass(frozen=True, slots=True)
class Violation:
    """One rule failure, rendered as a single reviewable line."""

    rule: str
    path: pathlib.Path
    line: int
    message: str

    def render(self) -> str:
        """Format as ``path:line: [rule] message`` for CI logs."""
        return f"{self.path.as_posix()}:{self.line}: [{self.rule}] {self.message}"


def _lines(path: pathlib.Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def ledger_definitions(root: pathlib.Path) -> list[Definition]:
    """Collect every ``## ADR-NNN`` heading in the canonical ledger."""
    path = root / LEDGER
    if not path.is_file():
        return []
    return [
        Definition(match.group(1), LEDGER, number)
        for number, line in enumerate(_lines(path), start=1)
        if (match := _LEDGER_HEADING.match(line)) is not None
    ]


def ledger_sections(root: pathlib.Path) -> dict[str, str]:
    """Map each ADR id to its ledger section text, heading to next heading."""
    path = root / LEDGER
    if not path.is_file():
        return {}
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in _lines(path):
        match = _LEDGER_HEADING.match(line)
        if match is not None:
            if current is not None:
                sections[current] = "\n".join(buffer)
            current = match.group(1)
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer)
    return sections


def draft_definitions(root: pathlib.Path) -> list[Definition]:
    """Collect the id each ``drafts/ADR-NNN-*.md`` file claims via its heading.

    Falls back to the filename when a draft carries no ``# ADR-NNN`` heading,
    so a malformed draft still occupies its id rather than vanishing from the
    duplicate check.
    """
    directory = root / DRAFTS
    if not directory.is_dir():
        return []
    definitions: list[Definition] = []
    for path in sorted(directory.glob("ADR-*.md")):
        relative = DRAFTS / path.name
        heading = next(
            (
                (match.group(1), number)
                for number, line in enumerate(_lines(path), start=1)
                if (match := _DRAFT_HEADING.match(line)) is not None
            ),
            None,
        )
        if heading is None:
            name_match = _DRAFT_FILENAME.match(path.name)
            if name_match is not None:
                definitions.append(Definition(name_match.group(1), relative, 1))
            continue
        definitions.append(Definition(heading[0], relative, heading[1]))
    return definitions


def claim_definitions(root: pathlib.Path, section: str) -> list[Definition]:
    """Collect claim-table row ids under one ``## <section>`` heading."""
    path = root / CLAIMS
    if not path.is_file():
        return []
    definitions: list[Definition] = []
    inside = False
    for number, line in enumerate(_lines(path), start=1):
        heading = _SECTION.match(line)
        if heading is not None:
            inside = heading.group(1) == section
            continue
        if not inside:
            continue
        match = _CLAIM_ROW.match(line)
        if match is not None:
            definitions.append(Definition(match.group(1), CLAIMS, number))
    return definitions


def _duplicates(definitions: list[Definition], rule: str, scope: str) -> list[Violation]:
    """Report every definition after the first for any repeated identifier."""
    by_id: dict[str, list[Definition]] = defaultdict(list)
    for definition in definitions:
        by_id[definition.identifier].append(definition)
    violations: list[Violation] = []
    for identifier, found in sorted(by_id.items()):
        if len(found) < 2:
            continue
        first = found[0]
        violations.extend(
            Violation(
                rule,
                duplicate.path,
                duplicate.line,
                f"{identifier} is already defined in {scope} at "
                f"{first.path.as_posix()}:{first.line}. Claim the next free id "
                f"(see --next) and renumber this one.",
            )
            for duplicate in found[1:]
        )
    return violations


def _draft_filename_violations(drafts: list[Definition]) -> list[Violation]:
    """Rule A2: a draft's filename id must match the id in its heading."""
    violations: list[Violation] = []
    for draft in drafts:
        name_match = _DRAFT_FILENAME.match(draft.path.name)
        if name_match is None or name_match.group(1) == draft.identifier:
            continue
        violations.append(
            Violation(
                "A2",
                draft.path,
                draft.line,
                f"filename claims {name_match.group(1)} but the heading claims "
                f"{draft.identifier}. Make the two agree.",
            )
        )
    return violations


def _draft_ledger_violations(drafts: list[Definition], sections: dict[str, str]) -> list[Violation]:
    """Rule A4: a shared id is legal only if the ledger names the draft."""
    violations: list[Violation] = []
    for draft in drafts:
        section = sections.get(draft.identifier)
        if section is None or draft.path.as_posix() in section:
            continue
        violations.append(
            Violation(
                "A4",
                draft.path,
                draft.line,
                f"{draft.identifier} is also a decided entry in "
                f"{LEDGER.as_posix()}, whose section does not reference this "
                f"draft. Either this is an id collision and the draft must "
                f"renumber (see --next), or the draft was promoted and the "
                f"ledger entry must say so by naming {draft.path.as_posix()}.",
            )
        )
    return violations


def check(root: pathlib.Path) -> list[Violation]:
    """Run every rule against a repository root and return sorted violations."""
    ledger = ledger_definitions(root)
    drafts = draft_definitions(root)
    active = claim_definitions(root, "Active claims")
    retired = claim_definitions(root, "Retired claims")

    violations: list[Violation] = []
    violations += _duplicates(ledger, "A1", "the ledger")
    violations += _duplicates(drafts, "A3", "drafts/")
    violations += _duplicates(active, "N1", "Active claims")
    violations += _duplicates(retired, "N2", "Retired claims")
    violations += _draft_filename_violations(drafts)
    violations += _draft_ledger_violations(drafts, ledger_sections(root))

    retired_ids = {definition.identifier for definition in retired}
    violations.extend(
        Violation(
            "N3",
            definition.path,
            definition.line,
            f"{definition.identifier} appears in both Active and Retired claims. "
            f"A retirement moves the row; it does not copy it.",
        )
        for definition in active
        if definition.identifier in retired_ids
    )

    return sorted(violations, key=lambda item: (item.path.as_posix(), item.line, item.rule))


def _next_free(identifiers: list[str], prefix: str) -> str:
    """Return the lowest unused ``<prefix>NNN`` above every id seen."""
    numbers = [
        int(identifier.removeprefix(prefix))
        for identifier in identifiers
        if identifier.startswith(prefix) and identifier.removeprefix(prefix).isdigit()
    ]
    width = max((len(identifier) - len(prefix) for identifier in identifiers), default=3)
    return f"{prefix}{max(numbers, default=0) + 1:0{width}d}"


def next_free_ids(root: pathlib.Path) -> tuple[str, str]:
    """Return the next free ADR id and the next free active NC id."""
    adr = [definition.identifier for definition in ledger_definitions(root)]
    adr += [definition.identifier for definition in draft_definitions(root)]
    claims = [definition.identifier for definition in claim_definitions(root, "Active claims")]
    return _next_free(adr, "ADR-"), _next_free(claims, "NC-")


def main(argv: list[str] | None = None) -> int:
    """Print violations and return the process exit status."""
    parser = argparse.ArgumentParser(
        prog="python scripts/check_ids.py",
        description="Detect duplicate or colliding ADR and NC identifiers.",
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parents[1],
        help="Repository root to check (default: the repository this script lives in).",
    )
    parser.add_argument(
        "--next",
        action="store_true",
        help="Print the next free ADR and NC id, then exit 0 without checking.",
    )
    args = parser.parse_args(argv)
    root: pathlib.Path = args.root

    if args.next:
        adr, claim = next_free_ids(root)
        print(f"next free ADR id: {adr}")
        print(f"next free NC id:  {claim}")
        return 0

    violations = check(root)
    for violation in violations:
        print(violation.render())
    if violations:
        plural = "s" if len(violations) != 1 else ""
        print(f"\n{len(violations)} identifier violation{plural}.", file=sys.stderr)
        return 1
    print("No duplicate or colliding ADR / NC identifiers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
