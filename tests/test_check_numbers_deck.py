"""Signs in the deck's number check (docs/advisor/2026-10-28-akba-phase-4-experiment-deck).

A numeral with the wrong sign must not count as found, which is what Baha asked about and Burak
reproduced on PR #133. The script is a document's tool and not a package module, so it is loaded
by path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "advisor"
    / "2026-10-28-akba-phase-4-experiment-deck"
    / "check_numbers.py"
)
# The Turkish deck's thousands separator, built from its code so the file stays plain ASCII.
NNBSP = chr(0x202F)


@pytest.fixture(scope="module")
def check_numbers() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_numbers", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_numbers"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("token", "source"),
    [
        ("0.5", "autocorrelation of -0.5 here"),
        ("0.5", "the value +0.5 here"),
        ("0.5", "(-0.5) in brackets"),
        ("0.5", "-0.5 at the very start"),
        ("-0.5", "the value 0.5 here"),
        ("-0.5", "the value +0.5 here"),
        ("+0.5", "the value -0.5 here"),
        ("+0.5", "the value 0.5 here"),
        ("-1,234", "the value 1,234 here"),
    ],
)
def test_a_numeral_with_the_wrong_sign_is_not_found(
    check_numbers: ModuleType, token: str, source: str
) -> None:
    assert check_numbers.found_in(token, source) is None


@pytest.mark.parametrize(
    ("token", "source"),
    [
        ("0.5", "the value 0.5 here"),
        ("0.5", "the value: 0.5 here"),
        ("-0.5", "the value -0.5 here"),
        ("+0.5", "the value +0.5 here"),
        ("-0.5", "(-0.5) in brackets"),
        ("0.5", "0.5 at the very start"),
        ("1.0", "a range of 0.5-1.0 days"),
        ("3", "the mode-3 block"),
        ("24", "over a 24-hour horizon"),
        ("-1,234", "the value -1,234 here"),
        (f"-1{NNBSP}234", "the value -1,234 here"),
    ],
)
def test_a_numeral_with_the_right_sign_is_found(
    check_numbers: ModuleType, token: str, source: str
) -> None:
    assert check_numbers.found_in(token, source) is not None


def test_a_signed_occurrence_does_not_hide_a_later_unsigned_one(check_numbers: ModuleType) -> None:
    found = check_numbers.found_in("0.5", "first -0.5 and later 0.5 too")
    assert found is not None and "later 0.5" in found


@pytest.mark.parametrize(
    ("one", "other", "same"),
    [
        ("-0.5", "0.5", False),
        ("-0.5", "+0.5", False),
        ("+0.5", "0.5", False),
        ("-0.5", "-0.5", True),
        ("-1,234", f"-1{NNBSP}234", True),
        ("%50", "50%", True),
        ("%-5", "-5%", True),
    ],
)
def test_the_parity_key_keeps_the_sign_and_nothing_else(
    check_numbers: ModuleType, one: str, other: str, same: bool
) -> None:
    assert (check_numbers.parity_key(one) == check_numbers.parity_key(other)) is same


def test_the_report_flags_a_sign_that_differs_between_the_two_decks(
    check_numbers: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for lang, body in (("en", "gamma -0.5 here"), ("tr", "gamma 0.5 burada")):
        slides = tmp_path / lang / "slides"
        slides.mkdir(parents=True)
        (slides / "one.html").write_text(f"<p>{body}</p>", encoding="utf-8")
        (tmp_path / lang / "deck.json").write_text(json.dumps({"order": ["one"]}), encoding="utf-8")
    (tmp_path / check_numbers.REGISTER).parent.mkdir(parents=True)
    (tmp_path / check_numbers.REGISTER).write_text("", encoding="utf-8")
    monkeypatch.setattr(check_numbers, "HERE", tmp_path)
    monkeypatch.setattr(check_numbers, "ROOT", tmp_path)
    monkeypatch.setattr(check_numbers, "PROTOCOL_DOCS", ())
    monkeypatch.setattr(check_numbers, "git_rev", lambda ref: ref)
    monkeypatch.setattr(check_numbers, "git_show", lambda ref, path: "")

    assert check_numbers.main() == 1
    assert "FAIL one: only in en ['-0.5']; only in tr ['0.5']" in capsys.readouterr().out
