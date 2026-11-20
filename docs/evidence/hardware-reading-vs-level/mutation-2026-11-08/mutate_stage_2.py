# ruff: noqa: E501
"""Criterion 25: mutate every line stage 2 added to the scripts and confirm a test fails.

    python mutate_stage_2.py <repo root> <base commit> <out folder> [--list]
        [--run-root <copy>] [--shard <i>/<n>] [--only <n,n,...>] [--group <name>]
    python mutate_stage_2.py <repo root> <base commit> <out folder> --merge <n> [--rerun]

The lines come from ``git diff <base>..HEAD`` (added lines only), so a line cannot be missed by
hand. Docstrings, comments and blank lines are left out. Each remaining line gets every mutant
below that still compiles:

- **delete**: a simple statement starting on the line becomes ``pass``; an ``if`` or ``while``
  test is negated; a ``for`` loop becomes ``pass``; any other line (an entry of a literal or a
  call spread over lines) is deleted;
- **operator**: ``<`` and ``<=``, ``>`` and ``>=``, ``==`` and ``!=``, ``and`` and ``or`` swap;
  ``not`` is dropped and ``is`` becomes ``is not``; between two operands ``+`` and ``-`` swap and
  ``*`` and ``/`` swap;
- **constant**: an integer ``n`` becomes ``n + 1``, a float is multiplied by 1.01, ``True`` and
  ``False`` swap.

Each mutant records the line's text and asserts it is still there before mutating, so a stale
mutant cannot pass as caught. The test command depends on the function the line is in. Every run
has its own time limit, kills its process tree when the limit passes, and writes one status line,
because a hung run looks exactly like a working one. What killed each mutant is recorded: the
first failing test and its message, and whether that was an assertion or a crash.

Files are restored from a copy taken here, never via git, and checked byte for byte. With
``--run-root`` the mutants are generated from the repository's diff but applied and tested in a
plain copy, whose scripts and tests must equal the repository's byte for byte; ``--shard i/n``
runs every n-th mutant from the i-th, so two copies can run at once. ``--merge n`` joins the
shards' tables into ``mutation.tsv``.
"""

from __future__ import annotations

import ast
import csv
import io
import os
import re
import subprocess
import sys
import time
import tokenize
from dataclasses import dataclass
from pathlib import Path

SUBMIT = "scripts/hardware_submit.py"
T1 = "scripts/hardware_t1_check.py"
DAILY = "scripts/hardware_daily.py"
FILES = (SUBMIT, T1, DAILY)
SUBMIT_TESTS = "tests/test_hardware_submit.py"

# Functions of hardware_submit.py whose lines the score command's tests exercise; every other
# new line in that file belongs to the report and its statistics.
SCORE_FUNCTIONS = {
    "run_score",
    "refuse_sealed_inside",
    "main",
    "run_build",
    "_record_unusable_live",
}
SCORE_TESTS_FIRST = [
    "test_a_scored_day_leaves_no_score_in_the_jobs_folder_or_on_stdout",
    "test_score_refuses_a_sealed_folder_inside_the_jobs_folder_before_the_network",
    "test_score_and_report_need_a_sealed_folder",
    "test_report_command_writes_the_file_and_marks_it_interim",
    "test_report_command_exits_refused_without_a_traceback",
    "test_report_refuses_a_sealed_folder_inside_the_jobs_folder",
    "test_the_score_command_hands_its_sealed_folder_to_the_scoring",
    "test_report_makes_a_sealed_folder_that_is_not_there_yet",
    "test_a_bad_live_document_is_a_missed_morning",
    "test_a_day_recorded_missed_is_not_built_again",
    "test_score_adds_the_control_from_the_archive_and_scores_both_arms",
    "test_a_job_with_a_control_left_out_scores_on_the_rest",
    "test_job_one_scores_arm_a_only",
]
LIMIT_S = {"report": 180, "score": 420, "t1": 180, "daily": 180}
CRASHES_EXPECTED = ("delete",)


@dataclass
class Mutant:
    file: str
    line: int
    group: str
    kind: str
    label: str
    original: str
    source: str


def added_lines(root: Path, base: str, name: str) -> set[int]:
    diff = subprocess.run(
        ["git", "diff", "-U0", f"{base}..HEAD", "--", name],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    ).stdout
    out: set[int] = set()
    line = 0
    for row in diff.splitlines():
        hunk = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", row)
        if hunk:
            line = int(hunk.group(1))
            continue
        if row.startswith("+++") or row.startswith("---"):
            continue
        if row.startswith("+"):
            out.add(line)
            line += 1
        elif not row.startswith("-") and not row.startswith("\\"):
            line += 1
    return out


def docstring_lines(tree: ast.Module) -> set[int]:
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                out |= set(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return out


def enclosing_function(tree: ast.Module, line: int) -> str:
    best, size = "<module>", 10**9
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            end = node.end_lineno or node.lineno
            if node.lineno <= line <= end and end - node.lineno < size:
                best, size = node.name, end - node.lineno
    return best


def group_of(name: str, function: str) -> str:
    if name == T1:
        return "t1"
    if name == DAILY:
        return "daily"
    return "score" if function in SCORE_FUNCTIONS else "report"


def compiles(source: str) -> bool:
    try:
        compile(source, "<mutant>", "exec")
    except SyntaxError:
        return False
    return True


def splice(lines: list[str], line: int, col: int, end_col: int, new: str) -> str:
    out = list(lines)
    text = out[line - 1]
    out[line - 1] = text[:col] + new + text[end_col:]
    return "".join(out)


def mutants_for(root: Path, base: str, name: str) -> tuple[list[Mutant], list[tuple[int, str]]]:
    text = (root / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    skip = docstring_lines(tree)
    targets = sorted(
        n
        for n in added_lines(root, base, name)
        if n not in skip and lines[n - 1].strip() and not lines[n - 1].strip().startswith("#")
    )
    starts: dict[int, ast.stmt] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and node.lineno not in starts:
            starts[node.lineno] = node
    tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    out: list[Mutant] = []
    bare: list[tuple[int, str]] = []
    seen: set[str] = set()

    def add(line: int, kind: str, label: str, source: str) -> None:
        if source == text or source in seen or not compiles(source):
            return
        seen.add(source)
        function = enclosing_function(tree, line)
        out.append(
            Mutant(
                name,
                line,
                group_of(name, function),
                kind,
                label,
                lines[line - 1].rstrip("\n"),
                source,
            )
        )

    for n in targets:
        before = len(out)
        indent = re.match(r"\s*", lines[n - 1]).group(0)  # type: ignore[union-attr]
        node = starts.get(n)
        if isinstance(node, ast.If | ast.While):
            test = node.test
            if test.lineno == test.end_lineno == n:
                seg = lines[n - 1][test.col_offset : test.end_col_offset]
                add(
                    n,
                    "delete",
                    "test negated",
                    splice(lines, n, test.col_offset, test.end_col_offset or 0, f"not ({seg})"),
                )
        elif isinstance(node, ast.For):
            end = node.end_lineno or n
            add(
                n,
                "delete",
                "loop removed",
                "".join([*lines[: n - 1], indent + "pass\n", *lines[end:]]),
            )
        elif isinstance(node, ast.FunctionDef | ast.ClassDef | ast.Try | ast.With):
            pass
        elif node is not None:
            end = node.end_lineno or n
            add(
                n,
                "delete",
                "statement removed",
                "".join([*lines[: n - 1], indent + "pass\n", *lines[end:]]),
            )
        else:
            add(n, "delete", "line removed", "".join(lines[: n - 1] + lines[n:]))
        line_tokens = [t for t in tokens if t.start[0] == n == t.end[0]]
        for i, tok in enumerate(line_tokens):
            col, end_col = tok.start[1], tok.end[1]
            swaps = {"<": "<=", "<=": "<", ">": ">=", ">=": ">", "==": "!=", "!=": "=="}
            if tok.type == tokenize.OP and tok.string in swaps:
                add(
                    n,
                    "operator",
                    f"{tok.string} -> {swaps[tok.string]}",
                    splice(lines, n, col, end_col, swaps[tok.string]),
                )
            elif tok.type == tokenize.NAME and tok.string in ("and", "or"):
                new = "or" if tok.string == "and" else "and"
                add(n, "operator", f"{tok.string} -> {new}", splice(lines, n, col, end_col, new))
            elif tok.type == tokenize.NAME and tok.string == "not":
                nxt = line_tokens[i + 1] if i + 1 < len(line_tokens) else None
                prev = line_tokens[i - 1] if i > 0 else None
                if prev is not None and prev.string == "is":
                    add(n, "operator", "is not -> is", splice(lines, n, prev.end[1], end_col, ""))
                elif nxt is not None:
                    add(n, "operator", "not dropped", splice(lines, n, col, nxt.start[1], ""))
            elif tok.type == tokenize.NAME and tok.string == "is":
                nxt = line_tokens[i + 1] if i + 1 < len(line_tokens) else None
                if nxt is not None and nxt.string != "not":
                    add(n, "operator", "is -> is not", splice(lines, n, col, end_col, "is not"))
            elif tok.type == tokenize.OP and tok.string in ("+", "-", "*", "/"):
                prev = line_tokens[i - 1] if i > 0 else None
                nxt = line_tokens[i + 1] if i + 1 < len(line_tokens) else None
                operand_before = (
                    prev is not None
                    and (
                        prev.type in (tokenize.NAME, tokenize.NUMBER, tokenize.STRING)
                        or prev.string in (")", "]")
                    )
                    and prev.string
                    not in ("and", "or", "not", "in", "is", "return", "else", "if", "lambda")
                )
                operand_after = nxt is not None and (
                    nxt.type in (tokenize.NAME, tokenize.NUMBER, tokenize.STRING)
                    or nxt.string in ("(", "[")
                )
                if operand_before and operand_after:
                    new = {"+": "-", "-": "+", "*": "/", "/": "*"}[tok.string]
                    add(
                        n, "operator", f"{tok.string} -> {new}", splice(lines, n, col, end_col, new)
                    )
            elif tok.type == tokenize.NAME and tok.string in ("True", "False"):
                new = "False" if tok.string == "True" else "True"
                add(n, "constant", f"{tok.string} -> {new}", splice(lines, n, col, end_col, new))
            elif tok.type == tokenize.NUMBER:
                try:
                    value = int(tok.string.replace("_", ""), 0)
                    new = str(value + 1)
                except ValueError:
                    new = repr(float(tok.string) * 1.01)
                add(n, "constant", f"{tok.string} -> {new}", splice(lines, n, col, end_col, new))
        if len(out) == before:
            bare.append((n, lines[n - 1].rstrip("\n")))
    return out, bare


def report_test_ids(root: Path) -> list[str]:
    tree = ast.parse((root / SUBMIT_TESTS).read_text(encoding="utf-8"))
    start = next(
        n.lineno for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_scored_day"
    )
    return [
        f"{SUBMIT_TESTS}::{n.name}"
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_") and n.lineno > start
    ]


def commands(root: Path) -> dict[str, list[str]]:
    base = [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "--no-header"]
    report = ["tests/test_hardware_report_rule.py", *report_test_ids(root)]
    score = [f"{SUBMIT_TESTS}::{name}" for name in SCORE_TESTS_FIRST]
    return {
        "report": [*base, *report],
        "score": [*base, *score],
        "t1": [*base, "tests/test_hardware_t1_check.py"],
        "daily": [*base, "tests/test_hardware_daily.py"],
    }


def run(command: list[str], root: Path, limit: float) -> tuple[int | None, str]:
    # A wide terminal: at pytest's default 80 columns a long test id leaves no room for the
    # failure's message in the summary line, and the message is what tells an assertion from a crash.
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([".", "src"]),
        "PYTHONIOENCODING": "utf-8",
        "COLUMNS": "1000",
    }
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        command,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    try:
        out, _ = proc.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False
            )
        else:
            proc.kill()
        proc.communicate()
        return None, ""
    return proc.returncode, out


def killer(output: str) -> tuple[str, str, str]:
    for row in output.splitlines():
        # A parametrized test id can hold spaces, so the id runs to the first " - ".
        match = re.match(r"^(FAILED|ERROR) (.+?)(?: - (.*))?$", row)
        if match:
            message = (match.group(3) or "").strip()
            how = (
                "assert" if message.startswith(("AssertionError", "assert", "Failed:")) else "crash"
            )
            if how == "crash" and match.group(1) == "ERROR":
                how = "crash"
            return match.group(2).split("::")[-1], how, message[:160]
    return "", "crash", output.strip().splitlines()[-1][:160] if output.strip() else ""


def merge(out_dir: Path, shards: int, stem: str = "mutation") -> int:
    rows: list[dict[str, str]] = []
    for i in range(shards):
        with (out_dir / f"{stem}.{i}.tsv").open(encoding="utf-8", newline="") as handle:
            rows += list(csv.DictReader(handle, delimiter="\t"))
    rows.sort(key=lambda r: int(r["n"]))
    with (out_dir / f"{stem}.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    counts: dict[str, int] = {}
    for r in rows:
        key = r["outcome"] if r["outcome"] != "caught" else f"caught by {r['how']}"
        counts[key] = counts.get(key, 0) + 1
    print(f"{len(rows)} mutants: {dict(sorted(counts.items()))}")
    return 0


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    base = sys.argv[2]
    out_dir = Path(sys.argv[3])
    rest = sys.argv[4:]
    if "--merge" in rest:
        stem = "mutation.rerun" if "--rerun" in rest else "mutation"
        return merge(out_dir, int(rest[rest.index("--merge") + 1]), stem)
    listing = "--list" in rest
    run_root = Path(rest[rest.index("--run-root") + 1]).resolve() if "--run-root" in rest else root
    shard, shards = (
        tuple(int(x) for x in rest[rest.index("--shard") + 1].split("/"))
        if "--shard" in rest
        else (0, 1)
    )
    only = {int(x) for x in rest[rest.index("--only") + 1].split(",")} if "--only" in rest else None
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = (".rerun" if only is not None else "") + (f".{shard}" if shards > 1 else "")
    status = out_dir / f"mutation.out{suffix}.txt"
    table = out_dir / f"mutation{suffix}.tsv"
    head = subprocess.run(
        ["git", "rev-parse", "--short=8", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    every: list[Mutant] = []
    bare: list[tuple[str, int, str]] = []
    for name in FILES:
        found, none = mutants_for(root, base, name)
        every += found
        bare += [(name, n, t) for n, t in none]
    if "--group" in rest:
        # One test command for every mutant, for a pass over a few lines whose tests are known.
        forced = rest[rest.index("--group") + 1]
        assert forced in LIMIT_S, forced
        for m in every:
            m.group = forced
    groups = {g: sum(m.group == g for m in every) for g in LIMIT_S}

    def line(text: str) -> None:
        with status.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')} {text}\n")

    if listing:
        print(f"{len(every)} mutants at {head} from {base}: {groups}")
        for name, n, text in bare:
            print(f"no mutant: {name}:{n}: {text.strip()}")
        return 0

    tests = [
        "tests/test_hardware_submit.py",
        "tests/test_hardware_t1_check.py",
        "tests/test_hardware_daily.py",
        "tests/test_hardware_report_rule.py",
    ]
    for name in (*FILES, *tests):
        assert (run_root / name).read_bytes() == (root / name).read_bytes(), (
            f"{name} differs in the copy"
        )
    numbered = list(enumerate(every, 1))
    mine = [(i, m) for i, m in numbered if (i - 1) % shards == shard]
    if only is not None:
        # A re-run of named mutants after tests were added; the numbering is the full list's, so
        # it is stable while the scripts are unchanged.
        named = [(i, m) for i, m in numbered if i in only]
        assert len(named) == len(only), f"no such mutant: {sorted(only - {i for i, _ in named})}"
        mine = [x for k, x in enumerate(named) if k % shards == shard]
    root = run_root
    backup = {name: (root / name).read_bytes() for name in FILES}
    cmds = commands(root)
    results: list[dict[str, str]] = []
    try:
        line(
            f"start at {head} from {base}: {len(every)} mutants {groups}; {len(bare)} new lines with no mutant; "
            f"shard {shard} of {shards}: {len(mine)} mutants, run in {run_root}"
        )
        for name, n, text in bare:
            line(f"no mutant  {name}:{n}: {text.strip()}")
        for group, command in cmds.items():
            code, output = run(command, root, LIMIT_S[group])
            line(
                f"baseline {group}: exit {code}; {output.strip().splitlines()[-1] if output.strip() else ''}"
            )
            assert code == 0, output[-3000:]
        for i, m in mine:
            text = backup[m.file].decode("utf-8")
            crlf = "\r\n" in text
            current = text.replace("\r\n", "\n").splitlines()
            assert current[m.line - 1] == m.original, f"{m.file}:{m.line}: pattern not found"
            data = m.source.replace("\n", "\r\n") if crlf else m.source
            (root / m.file).write_bytes(data.encode("utf-8"))
            started = time.monotonic()
            try:
                code, output = run(cmds[m.group], root, LIMIT_S[m.group])
            finally:
                (root / m.file).write_bytes(backup[m.file])
                assert (root / m.file).read_bytes() == backup[m.file]
            seconds = time.monotonic() - started
            if code is None:
                outcome, test, how, message = "TIMEOUT", "", "", ""
            elif code == 0:
                outcome, test, how, message = "SURVIVED", "", "", ""
            else:
                test, how, message = killer(output)
                outcome = "caught"
            results.append(
                {
                    "n": str(i),
                    "file": m.file,
                    "line": str(m.line),
                    "group": m.group,
                    "kind": m.kind,
                    "mutant": m.label,
                    "outcome": outcome,
                    "how": how,
                    "test": test,
                    "message": message,
                    "seconds": f"{seconds:.1f}",
                    "code": m.original.strip(),
                }
            )
            line(
                f"{outcome:<8} {i:>3}/{len(every)} {m.file}:{m.line} {m.kind}: {m.label} [{how}] {test}"
            )
    finally:
        for name, data in backup.items():
            (root / name).write_bytes(data)
        if results:
            with table.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=list(results[0]), delimiter="\t", lineterminator="\n"
                )
                writer.writeheader()
                writer.writerows(results)
    survived = sum(r["outcome"] == "SURVIVED" for r in results)
    timed_out = sum(r["outcome"] == "TIMEOUT" for r in results)
    crash = sum(r["how"] == "crash" for r in results)
    line(
        f"RUN END: {len(results)} of {len(mine)} mutants run, {survived} survived, {timed_out} timed out, "
        f"{crash} caught by a crash rather than an assertion"
    )
    return 1 if survived or timed_out or len(results) != len(mine) else 0


if __name__ == "__main__":
    sys.exit(main())
