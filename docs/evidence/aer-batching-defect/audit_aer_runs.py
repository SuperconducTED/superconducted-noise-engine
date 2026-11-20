"""Static audit: where could this repository run more than one circuit in one Aer run?

Run from the repository root:  python -I audit_aer_runs.py [--refs ref ...]

Standard library only. Reads tracked `.py` and `.ipynb` blobs from git, so it covers branches
without checking them out, and lists every call to a `run`, `execute` or `_run_circuits` attribute
except `subprocess.run`, with its first argument and whether the file imports a Qiskit package. It
classifies nothing: every site is read by hand in the findings doc.

With no --refs it scans `main` and every other local and origin branch, except `calibration-data`.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass

ATTRIBUTES = {"run", "execute", "_run_circuits", "run_circuits"}
EXECUTORS = {"subprocess", "sp"}
PACKAGES = {
    "qiskit_aer": "aer",
    "qiskit.primitives": "primitives",
    "qiskit_ibm_runtime": "runtime",
    "qiskit_experiments": "experiments",
    "mthree": "mthree",
}
PRIMARY = "main"


@dataclass(frozen=True)
class Site:
    path: str
    call: str
    first_argument: str
    imports: str


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, encoding="utf-8", errors="replace"
    ).stdout


def all_refs() -> list[str]:
    names = git(
        "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes/origin"
    ).split()
    return [
        name
        for name in names
        if "calibration-data" not in name and name not in ("origin", "origin/HEAD", PRIMARY)
    ]


def tracked_blobs(ref: str) -> dict[str, str]:
    """Path to blob id, for tracked Python files and notebooks of a ref."""
    out = {}
    for line in git("ls-tree", "-r", ref).splitlines():
        meta, path = line.split("\t", 1)
        path = path.strip('"')
        if path.endswith((".py", ".ipynb")):
            out[path] = meta.split()[2]
    return out


def read_blobs(blob_ids: set[str]) -> tuple[dict[str, str], set[str]]:
    """Blob id to text, through one `git cat-file --batch`; unreadable ids come back apart."""
    ordered = sorted(blob_ids)
    process = subprocess.run(
        ["git", "cat-file", "--batch"],
        input=("\n".join(ordered) + "\n").encode(),
        capture_output=True,
        check=True,
    )
    data = process.stdout
    texts: dict[str, str] = {}
    unread: set[str] = set()
    position = 0
    for blob in ordered:
        end = data.index(b"\n", position)
        header = data[position:end].decode().split()
        position = end + 1
        if len(header) < 3 or header[1] == "missing":
            unread.add(blob)
            continue
        size = int(header[2])
        texts[blob] = data[position : position + size].decode("utf-8", errors="replace")
        position += size + 1
    return texts, unread


def python_source(path: str, text: str) -> str:
    if not path.endswith(".ipynb"):
        return text
    cells = json.loads(text).get("cells", [])
    lines: list[str] = []
    for cell in cells:
        if cell.get("cell_type") == "code":
            source = cell.get("source", "")
            source = source if isinstance(source, str) else "".join(source)
            lines.extend(
                line for line in source.splitlines() if not line.lstrip().startswith(("%", "!"))
            )
    return "\n".join(lines)


def file_imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for package, tag in PACKAGES.items():
                if name == package or name.startswith(package + "."):
                    found.add(tag)
    return found


def scan(path: str, text: str) -> tuple[list[tuple[int, Site]], set[str], list[str]]:
    """Call sites with line numbers, the file's Qiskit imports, python subprocess calls."""
    tree = ast.parse(python_source(path, text))
    imports = file_imports(tree)
    tag = ",".join(sorted(imports)) or "-"
    sites: list[tuple[int, Site]] = []
    children: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        receiver = ast.unparse(node.func.value)
        first = ast.unparse(node.args[0]) if node.args else "(keywords only)"
        if receiver in EXECUTORS:
            if "executable" in ast.unparse(node) or "python" in first:
                children.append(f"{path}:{node.lineno}: {ast.unparse(node)[:150]}")
            continue
        if node.func.attr in ATTRIBUTES:
            site = Site(path, f"{receiver}.{node.func.attr}", first[:90], tag)
            sites.append((node.lineno, site))
    return sites, imports, children


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refs", nargs="*", default=None)
    args = parser.parse_args()
    others = all_refs() if args.refs is None else args.refs

    head = git("rev-parse", "--short=8", PRIMARY).strip()
    print(f"primary ref {PRIMARY} at {head}; other refs scanned: {len(others)}")

    per_ref = {ref: tracked_blobs(ref) for ref in [PRIMARY, *others]}
    blobs = {blob for mapping in per_ref.values() for blob in mapping.values()}
    texts, unread = read_blobs(blobs)
    print(f"distinct blobs {len(blobs)}, unreadable {len(unread)}")

    parsed: dict[tuple[str, str], tuple[list[tuple[int, Site]], set[str], list[str]]] = {}
    syntax_errors: list[str] = []
    for mapping in per_ref.values():
        for path, blob in mapping.items():
            if (path, blob) in parsed or blob not in texts:
                continue
            try:
                parsed[(path, blob)] = scan(path, texts[blob])
            except (SyntaxError, ValueError, json.JSONDecodeError) as error:
                syntax_errors.append(f"{path} ({blob[:8]}): {error}")
                parsed[(path, blob)] = ([], set(), [])

    print(f"\n1. Files on {PRIMARY} importing a Qiskit execution package")
    main_map = per_ref[PRIMARY]
    importing = defaultdict(list)
    for path, blob in sorted(main_map.items()):
        for tag in sorted(parsed.get((path, blob), ([], set(), []))[1]):
            importing[tag].append(path)
    for tag in sorted(PACKAGES.values()):
        print(f"  {tag}: {len(importing[tag])}")
        for path in importing[tag]:
            print(f"    {path}")

    print(f"\n2. Call sites on {PRIMARY}: line, call, first argument, file's Qiskit imports")
    main_sites = set()
    for path, blob in sorted(main_map.items()):
        for line, site in sorted(parsed.get((path, blob), ([], set(), []))[0], key=lambda x: x[0]):
            main_sites.add(site)
            print(f"  {path}:{line}  {site.call}({site.first_argument})  [{site.imports}]")

    print(f"\n3. Call sites on other refs and not on {PRIMARY}, deduplicated")
    elsewhere: dict[Site, set[str]] = defaultdict(set)
    for ref in others:
        for path, blob in per_ref[ref].items():
            for _, site in parsed.get((path, blob), ([], set(), []))[0]:
                if site not in main_sites:
                    elsewhere[site].add(ref)
    for site in sorted(elsewhere, key=lambda s: (s.path, s.call, s.first_argument)):
        refs = sorted(elsewhere[site])
        print(
            f"  {site.path}  {site.call}({site.first_argument})  [{site.imports}]  "
            f"on {len(refs)} refs, e.g. {refs[0]}"
        )

    print(
        f"\n4. Calls on {PRIMARY} that start a Python subprocess (outside the pytest spy's reach)"
    )
    for path, blob in sorted(main_map.items()):
        for child in parsed.get((path, blob), ([], set(), []))[2]:
            print(f"  {child}")

    print(f"\n5. Files that could not be parsed: {len(syntax_errors)}")
    for line in syntax_errors:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
