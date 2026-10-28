"""Check every numeral on the 2026-10-28 deck for Dr. Akba against its sources.

For each slide of ``en/`` and ``tr/`` (body, footer and speaker notes), every numeral is looked
up in this order and the first hit is reported:

1. ``ROW``: a register row the same slide cites (``NC-xxx``, ranges such as ``NC-077 to NC-079``
   expanded). Rows NC-087 to NC-091 are read from the pre-registration branch's register,
   every other row from ``docs/numerical-claims.md`` in the working tree.
2. ``PROTOCOL``: a decided protocol value, found in one of the three protocol documents named in
   ``PROTOCOL_DOCS`` (the design, the pre-registration draft, the phase-4 plan's section 8),
   each read at a pinned commit. A single-digit integer found only here is marked ``weak``,
   since any long document contains one.
3. ``FAIL uncited-row``: the numeral is in some register row, but not in a row the slide cites.
4. ``FAIL missing``: the numeral is in none of the above.

Structural numerals are excluded before the lookup and listed per slide: dates, issue and PR
numbers, section references, register and decision ids, commit and asset hashes, arXiv ids,
review ids, years, the slide's page number, and identifiers with digits (``T1``, ``p_1``,
``S1``, ``N0``, ``L1``, ``lag-1``). Thousands separators (comma, or the narrow no-break space of
the Turkish deck) and a leading or trailing percent sign are normalised before matching.

A second check compares, per slide, the numerals of the Turkish body with the English body;
the two decks are meant to carry identical numbers.

From the repository root, with the ``origin`` branches fetched:

    python docs/advisor/2026-10-28-akba-phase-4-experiment-deck/check_numbers.py

Prints the report and exits 1 if any numeral fails or the parity check finds a difference.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REGISTER = "docs/numerical-claims.md"
PREREG_REF = "821f6781"  # tip of origin/mert/issue-125-preregistration read for the deck
BUILDER_REF = "e5c75c3b"  # tip of origin/mert/phase-4-builder-order read for the deck
PREREG_ROWS = {"NC-087", "NC-088", "NC-089", "NC-090", "NC-091"}
PROTOCOL_DOCS = (
    ("design", "HEAD", "docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md"),
    ("pre-registration", PREREG_REF, "docs/roadmap/2026-10-24-issue-125-preregistration.md"),
    ("phase-4 plan s8", BUILDER_REF, "docs/roadmap/2026-10-23-phase-4-plan.md"),
)
LANGS = ("en", "tr")

SEP = ",\u202f"
NUMERAL = re.compile(
    r"(?<![\w.:%])(?:\d{2}:\d{2})"
    r"|(?<![\w.,\u202f])%?[+-]?\d{1,3}(?:[,\u202f]\d{3})+(?:\.\d+)?%?(?![\w])"
    r"|(?<![\w.,\u202f])%?[+-]?\d+(?:\.\d+)?%?(?![\w])"
)
STRUCTURAL = (
    ("date", re.compile(r"\b\d{4}-\d{2}-\d{2}(?:T[\d:]+Z)?\b")),
    ("rule reference", re.compile(r"\bRule \d+\b")),
    ("arXiv id", re.compile(r"(?<=arXiv )\d{4}\.\d{4,5}")),
    ("register or decision id", re.compile(r"\b(?:NC|ADR|PR|SHA|L)-\d+\w*")),
    ("issue or PR number", re.compile(r"#\d+")),
    ("section reference", re.compile(r"§\s?\d+(?:\.\d+)*")),
    ("hash", re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b")),
    ("review id", re.compile(r"\b\d{10}\b")),
    ("phase number", re.compile(r"\b(?:[Pp]hase|[Ff]az)[ -]\d+\b")),
    ("identifier", re.compile(r"\b[A-Za-z]+-\d+\w*")),
    ("identifier", re.compile(r"\b\w*[^\W\d]\w*?\d\w*|\b\d+[^\W\d_]\w*")),
    ("year", re.compile(r"\b20\d\d\b")),
)
FOOTER_PAGE = re.compile(r"^\s*\d+\s·\s")
NC_ID = re.compile(r"NC-(\d{3})(?:\s+(?:to|ile)\s+NC-(\d{3}))?")


def git_show(ref: str, path: str) -> str:
    """Return a file's text at a commit."""
    out = subprocess.run(
        ["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, check=True
    )
    return out.stdout.decode("utf-8")


def git_rev(ref: str) -> str:
    """Return the full commit id a ref names."""
    out = subprocess.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return out.stdout.decode("ascii").strip()


def register_rows(text: str) -> dict[str, str]:
    """Map each active register row's id to its full line."""
    rows: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"\| (NC-\d{3}) \|", line)
        if match:
            rows[match.group(1)] = line
    return rows


@dataclass
class SlideText:
    """The text of one slide, split into zones."""

    body: list[str] = field(default_factory=list)
    footer: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class SlideParser(HTMLParser):
    """Collect a slide's text by zone: the pinned footer, the aside, everything else."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text = SlideText()
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        style = dict(attrs).get("style") or ""
        if tag == "aside":
            zone = "notes"
        elif "bottom:64px" in style.replace(" ", ""):
            zone = "footer"
        else:
            zone = self.stack[-1] if self.stack else "body"
        if tag == "img":
            alt = dict(attrs).get("alt") or ""
            self._add(zone, alt)
            return
        if tag in ("br", "hr"):
            return
        self.stack.append(zone)

    def handle_endtag(self, tag: str) -> None:
        if tag not in ("img", "br", "hr") and self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        self._add(self.stack[-1] if self.stack else "body", data)

    def _add(self, zone: str, data: str) -> None:
        # Collapse ASCII whitespace only: str.split() would also eat the narrow no-break
        # space the Turkish deck uses as its thousands separator.
        if data.strip():
            getattr(self.text, zone).append(re.sub(r"[ \t\r\n]+", " ", data).strip())


def parse_slide(path: Path) -> SlideText:
    """Parse one slide file."""
    parser = SlideParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.text


def strip_structural(text: str) -> tuple[str, list[str]]:
    """Blank out structural numerals; return the remaining text and what was excluded."""
    excluded: list[str] = []
    for name, pattern in STRUCTURAL:

        def blank(match: re.Match[str], name: str = name) -> str:
            excluded.append(f"{name} {match.group(0)}")
            return " " * len(match.group(0))

        text = pattern.sub(blank, text)
    return text, excluded


def normalise(token: str) -> str:
    """Drop thousands separators, signs and percent signs; keep the digits and the point."""
    core = token.strip("%+-")
    for sep in SEP:
        core = core.replace(sep, "")
    return core


def search_forms(token: str) -> list[str]:
    """The literal forms a numeral may take in a source, a signed form first if it has one."""
    if re.fullmatch(r"\d{2}:\d{2}", token):
        return [token]
    core = normalise(token)
    whole, _, frac = core.partition(".")
    bare = [core]
    if len(whole) > 3:
        bare.append(f"{int(whole):,}" + (f".{frac}" if frac else ""))
    sign = token.lstrip("%")[:1]
    signed = [sign + form for form in bare] if sign in "+-" else []
    return signed + bare


MD_HEADING_NUMBER = re.compile(r"^(#+ )\d+(?:\.\d+)*\.?", flags=re.MULTILINE)
MAX_SNIPPETS = 2


def clean_source(text: str) -> str:
    """Blank a source's structural numerals, so a slide numeral only meets a source numeral.

    Markdown heading numbers (``## 3.``) go too: they are section labels, not values.
    """
    text = MD_HEADING_NUMBER.sub(lambda m: m.group(1) + " " * (len(m.group(0)) - 3), text)
    return strip_structural(text)[0]


def found_in(token: str, text: str) -> str | None:
    """Return context snippets of the numeral's first occurrences in ``text``, or None.

    ``text`` must already have passed through ``clean_source``. A whole number only: no digit,
    letter, point, comma or colon may touch it, so ``0.5`` does not meet ``0.50`` or ``10.5``,
    and ``14`` does not meet ``14:45``.
    """
    for form in search_forms(token):
        lead = r"(?<![\w.,+-])(?<!\d:)" if form[0] in "+-" else r"(?<![\w.,])(?<!\d:)"
        pattern = rf"{lead}{re.escape(form)}(?![\w]|[.,:]\d)"
        snippets = []
        for match in re.finditer(pattern, text):
            start, end = max(0, match.start() - 28), min(len(text), match.end() + 28)
            snippets.append("..." + " ".join(text[start:end].split()) + "...")
            if len(snippets) == MAX_SNIPPETS:
                break
        if snippets:
            return " / ".join(snippets)
    return None


def cited_rows(text: str) -> set[str]:
    """Every NC id a slide names, with ranges expanded."""
    ids: set[str] = set()
    for first, last in NC_ID.findall(text):
        lo = int(first)
        hi = int(last) if last else lo
        ids.update(f"NC-{n:03d}" for n in range(lo, hi + 1))
    return ids


def verdict(
    token: str,
    cited: set[str],
    rows: dict[str, str],
    protocol: dict[str, str],
) -> tuple[bool, str]:
    """Look a numeral up in the cited rows, the protocol documents, then the whole register.

    Every cited row that holds the numeral is listed, so a match on the wrong quantity in one
    row is visible beside the intended one.
    """
    hits = [
        f"{row_id}: {snippet}"
        for row_id in sorted(cited)
        if row_id in rows and (snippet := found_in(token, rows[row_id]))
    ]
    if hits:
        return True, "ROW " + " | ".join(hits)
    docs = [
        f"{name}: {snippet}"
        for name, text in protocol.items()
        if (snippet := found_in(token, text))
    ]
    if docs:
        weak = " (weak: single digit)" if re.fullmatch(r"\d", normalise(token)) else ""
        return True, f"PROTOCOL{weak} " + " | ".join(docs)
    elsewhere = [row_id for row_id, text in rows.items() if found_in(token, text)]
    if elsewhere:
        return False, f"FAIL uncited-row: in {', '.join(elsewhere[:6])} only"
    return False, "FAIL missing: in no cited row, protocol document or register row"


def numerals(text: str) -> list[str]:
    """Every numeral left in a text once structural ones are blanked."""
    return [m.group(0) for m in NUMERAL.finditer(text)]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # the report quotes non-ASCII source text
    head = git_rev("HEAD")
    prereg = git_rev(PREREG_REF)
    builder = git_rev(BUILDER_REF)
    rows = register_rows((ROOT / REGISTER).read_text(encoding="utf-8"))
    for row_id, line in register_rows(git_show(prereg, REGISTER)).items():
        if row_id in PREREG_ROWS:
            rows[row_id] = line
    rows = {row_id: clean_source(line) for row_id, line in rows.items()}
    protocol = {
        name: clean_source(
            (ROOT / path).read_text(encoding="utf-8")
            if ref == "HEAD"
            else git_show(git_rev(ref), path)
        )
        for name, ref, path in PROTOCOL_DOCS
    }

    out: list[str] = [
        "check_numbers.py: every numeral on the deck's slides against its sources",
        f"working tree HEAD {head}",
        f"register: {REGISTER} in the working tree, every row except NC-087 to NC-091",
        f"register: {prereg}:{REGISTER}, rows NC-087 to NC-091 only",
    ]
    for name, ref, path in PROTOCOL_DOCS:
        commit = head if ref == "HEAD" else git_rev(ref)
        out.append(f"protocol document '{name}': {commit}:{path}")
    out.append(f"phase-4 plan section 8 branch tip: {builder}")
    out.append("")

    failures = 0
    per_slide_body: dict[str, dict[str, Counter[str]]] = {}
    totals: Counter[str] = Counter()
    for lang in LANGS:
        if not (HERE / lang / "deck.json").exists():
            out.append(f"== {lang}: no deck.json, skipped")
            failures += 1
            continue
        deck = json.loads((HERE / lang / "deck.json").read_text(encoding="utf-8"))
        per_slide_body[lang] = {}
        for page, slide_id in enumerate(deck["order"], start=1):
            text = parse_slide(HERE / lang / "slides" / f"{slide_id}.html")
            whole = " ".join(text.body + text.footer + text.notes)
            cited = cited_rows(whole)
            out.append(
                f"== {lang}/{slide_id} (page {page}); rows cited: "
                + (", ".join(sorted(cited)) or "none")
            )
            body_tokens: Counter[str] = Counter()
            excluded_all: list[str] = []
            for zone in ("body", "footer", "notes"):
                zone_text = " | ".join(getattr(text, zone))
                if zone == "footer":
                    page_match = FOOTER_PAGE.match(zone_text)
                    if page_match:
                        excluded_all.append(f"page number {page_match.group(0).split()[0]}")
                        zone_text = zone_text[page_match.end() :]
                zone_text = html.unescape(zone_text)
                stripped, excluded = strip_structural(zone_text)
                excluded_all.extend(excluded)
                for token in numerals(stripped):
                    ok, why = verdict(token, cited, rows, protocol)
                    totals["pass" if ok else "fail"] += 1
                    if not ok:
                        failures += 1
                    out.append(f"  [{zone}] {token}: {why}")
                    if zone == "body":
                        body_tokens[normalise(token)] += 1
            per_slide_body[lang][slide_id] = body_tokens
            if excluded_all:
                out.append("  excluded as structural: " + "; ".join(excluded_all))
        out.append("")

    out.append("== parity: numerals in each slide body, Turkish against English")
    parity_failures = 0
    for slide_id, en_tokens in per_slide_body.get("en", {}).items():
        tr_tokens = per_slide_body.get("tr", {}).get(slide_id, Counter())
        if en_tokens != tr_tokens:
            parity_failures += 1
            only_en = sorted((en_tokens - tr_tokens).elements())
            only_tr = sorted((tr_tokens - en_tokens).elements())
            out.append(f"  FAIL {slide_id}: only in en {only_en}; only in tr {only_tr}")
    if not parity_failures:
        out.append("  every slide body carries the same numerals in both languages")
    out.append("")
    out.append(
        f"summary: {totals['pass']} numerals pass, {totals['fail']} fail; "
        f"{parity_failures} parity differences"
    )
    print("\n".join(out))
    return 1 if failures or parity_failures else 0


if __name__ == "__main__":
    sys.exit(main())
