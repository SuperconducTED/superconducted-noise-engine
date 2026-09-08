"""Tests for the ADR / NC identifier collision check.

The synthetic cases build a miniature repository under ``tmp_path`` so each
rule is exercised in isolation. The last group pins the three collisions that
were live on 2026-09-06 and motivated the check, in the shape they actually
took, so a future refactor cannot quietly stop catching them.
"""

from __future__ import annotations

import pathlib

import pytest
from scripts.check_ids import check, main, next_free_ids

_CLEAN_LEDGER = """# Decisions

## ADR-001 — First decision

Body.

---

## ADR-002 — Second decision

Body.
"""

_CLEAN_CLAIMS = """# Numerical Claims Register

## Active claims

| ID | Claim | Value |
|----|-------|-------|
| NC-001 | A claim | 1 |
| NC-002 | Another claim | 2 |

## Retired claims

| ID | Claim | Value |
|----|-------|-------|
| NC-R001 | A retired claim | 3 |
"""


def _repo(
    tmp_path: pathlib.Path,
    *,
    ledger: str = _CLEAN_LEDGER,
    claims: str = _CLEAN_CLAIMS,
    drafts: dict[str, str] | None = None,
) -> pathlib.Path:
    """Build a miniature repository and return its root."""
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "decisions.md").write_text(ledger, encoding="utf-8")
    (tmp_path / "docs" / "numerical-claims.md").write_text(claims, encoding="utf-8")
    draft_dir = tmp_path / "docs" / "decisions" / "drafts"
    draft_dir.mkdir(parents=True, exist_ok=True)
    for name, body in (drafts or {}).items():
        (draft_dir / name).write_text(body, encoding="utf-8")
    return tmp_path


def _rules(root: pathlib.Path) -> list[str]:
    return [violation.rule for violation in check(root)]


def test_a_clean_repository_reports_nothing(tmp_path: pathlib.Path) -> None:
    assert check(_repo(tmp_path)) == []


def test_a1_flags_a_duplicated_ledger_heading(tmp_path: pathlib.Path) -> None:
    ledger = _CLEAN_LEDGER + "\n## ADR-002 — A different second decision\n\nBody.\n"
    violations = check(_repo(tmp_path, ledger=ledger))
    assert [violation.rule for violation in violations] == ["A1"]
    assert "ADR-002 is already defined in the ledger" in violations[0].message


def test_a2_flags_a_filename_that_disagrees_with_its_heading(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path, drafts={"ADR-009-mismatched.md": "# ADR-010 — Mismatched\n"})
    assert "A2" in _rules(root)


def test_a3_flags_two_drafts_claiming_one_id(tmp_path: pathlib.Path) -> None:
    root = _repo(
        tmp_path,
        drafts={
            "ADR-009-first.md": "# ADR-009 — First\n",
            "ADR-009-second.md": "# ADR-009 — Second\n",
        },
    )
    assert _rules(root) == ["A3"]


def test_a4_accepts_a_draft_the_ledger_names_as_promoted(tmp_path: pathlib.Path) -> None:
    ledger = (
        "# Decisions\n\n## ADR-001 — First decision\n\n"
        "> Promoted from draft. The draft at\n"
        "> `docs/decisions/drafts/ADR-001-first.md` is retained as the\n"
        "> authoring record; this ledger entry is canonical.\n"
    )
    root = _repo(tmp_path, ledger=ledger, drafts={"ADR-001-first.md": "# ADR-001 — First\n"})
    assert check(root) == []


def test_a4_flags_a_draft_reusing_a_decided_id(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path, drafts={"ADR-001-unrelated.md": "# ADR-001 — Something else\n"})
    violations = check(root)
    assert [violation.rule for violation in violations] == ["A4"]
    assert "is also a decided entry" in violations[0].message


def test_a4_does_not_leak_a_reference_across_ledger_sections(tmp_path: pathlib.Path) -> None:
    """A path named under ADR-001 must not excuse a collision on ADR-002."""
    ledger = (
        "# Decisions\n\n## ADR-001 — First decision\n\n"
        "See `docs/decisions/drafts/ADR-002-unrelated.md` for background.\n\n"
        "## ADR-002 — Second decision\n\nBody.\n"
    )
    root = _repo(tmp_path, ledger=ledger, drafts={"ADR-002-unrelated.md": "# ADR-002 — Other\n"})
    assert _rules(root) == ["A4"]


def test_a_draft_with_an_unused_id_is_accepted(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path, drafts={"ADR-050-undecided.md": "# ADR-050 — Undecided\n"})
    assert check(root) == []


def test_n1_flags_a_duplicated_active_claim(tmp_path: pathlib.Path) -> None:
    claims = _CLEAN_CLAIMS.replace(
        "| NC-002 | Another claim | 2 |",
        "| NC-002 | Another claim | 2 |\n| NC-001 | A restated claim | 9 |",
    )
    violations = check(_repo(tmp_path, claims=claims))
    assert [violation.rule for violation in violations] == ["N1"]
    assert "NC-001 is already defined in Active claims" in violations[0].message


def test_n2_flags_a_duplicated_retired_claim(tmp_path: pathlib.Path) -> None:
    claims = _CLEAN_CLAIMS + "| NC-R001 | A second retirement | 4 |\n"
    assert _rules(_repo(tmp_path, claims=claims)) == ["N2"]


def test_n3_flags_a_claim_left_in_both_sections(tmp_path: pathlib.Path) -> None:
    claims = _CLEAN_CLAIMS + "| NC-001 | Copied not moved | 1 |\n"
    assert _rules(_repo(tmp_path, claims=claims)) == ["N3"]


def test_prose_citations_are_not_treated_as_definitions(tmp_path: pathlib.Path) -> None:
    """A mention inside a note cell or a sentence does not claim an id."""
    ledger = _CLEAN_LEDGER + "\nSee ADR-001 and ADR-002 for context.\n"
    claims = _CLEAN_CLAIMS.replace(
        "| NC-002 | Another claim | 2 |",
        "| NC-002 | Another claim | 2 · derived from NC-001, see NC-R001 |",
    )
    assert check(_repo(tmp_path, ledger=ledger, claims=claims)) == []


def test_gaps_in_a_sequence_are_not_violations(tmp_path: pathlib.Path) -> None:
    ledger = "# Decisions\n\n## ADR-001 — First\n\n## ADR-007 — Seventh\n"
    claims = _CLEAN_CLAIMS.replace("| NC-002 |", "| NC-044 |")
    assert check(_repo(tmp_path, ledger=ledger, claims=claims)) == []


def test_next_free_ids_skips_past_drafts_and_the_ledger(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path, drafts={"ADR-050-undecided.md": "# ADR-050 — Undecided\n"})
    assert next_free_ids(root) == ("ADR-051", "NC-003")


def test_next_free_ids_ignores_the_retired_namespace(tmp_path: pathlib.Path) -> None:
    """``NC-R001`` must not push the next active id to ``NC-R002``."""
    _, claim = next_free_ids(_repo(tmp_path))
    assert claim == "NC-003"


def test_main_exits_zero_on_a_clean_tree(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--root", str(_repo(tmp_path))]) == 0
    assert "No duplicate or colliding" in capsys.readouterr().out


def test_main_exits_one_and_prints_a_locatable_line(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path, drafts={"ADR-001-unrelated.md": "# ADR-001 — Something else\n"})
    assert main(["--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "docs/decisions/drafts/ADR-001-unrelated.md:1: [A4]" in out


def test_main_next_reports_both_sequences(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--root", str(_repo(tmp_path)), "--next"]) == 0
    out = capsys.readouterr().out
    assert "next free ADR id: ADR-003" in out
    assert "next free NC id:  NC-003" in out


# --- The three collisions live on 2026-09-06, in the shape they took. --------


def test_regression_pr69_duplicate_nc_021_row(tmp_path: pathlib.Path) -> None:
    """A second NC-021 row appended instead of updating the first (Rule 6)."""
    claims = _CLEAN_CLAIMS.replace(
        "| NC-002 | Another claim | 2 |",
        "| NC-002 | Another claim | 2 |\n| NC-001 | Full test-suite size | 352 |",
    )
    violations = check(_repo(tmp_path, claims=claims))
    assert [violation.rule for violation in violations] == ["N1"]


def test_regression_pr52_and_pr69_claim_the_same_nc_ids(tmp_path: pathlib.Path) -> None:
    """Both PRs appended four rows in different regions, so git merged cleanly."""
    claims = _CLEAN_CLAIMS.replace(
        "| NC-002 | Another claim | 2 |",
        "| NC-002 | Another claim | 2 |\n"
        "| NC-031 | Sweep recall | 87.9% |\n"
        "| NC-032 | Capture rate | 70.2% |\n"
        "| NC-031 | sx gate length | 24 ns |\n"
        "| NC-032 | Aer SuperOp difference | 1e-15 |",
    )
    violations = check(_repo(tmp_path, claims=claims))
    assert [violation.rule for violation in violations] == ["N1", "N1"]
    assert all("already defined in Active claims" in v.message for v in violations)


def test_regression_pr69_new_draft_reuses_a_decided_adr_id(tmp_path: pathlib.Path) -> None:
    """A new drafts/ file, so there was not even a text conflict to catch it."""
    ledger = "# Decisions\n\n## ADR-024 — Degeneracy of random TSK consequent initialization\n"
    root = _repo(
        tmp_path,
        ledger=ledger,
        drafts={
            "ADR-024-calibration-training-target.md": "# ADR-024: Calibration training target\n"
        },
    )
    violations = check(root)
    assert [violation.rule for violation in violations] == ["A4"]
    assert "ADR-024" in violations[0].message


def test_this_repository_is_currently_clean() -> None:
    """The check must be green on ``main``, or it will be ignored."""
    root = pathlib.Path(__file__).resolve().parents[1]
    assert [violation.render() for violation in check(root)] == []
