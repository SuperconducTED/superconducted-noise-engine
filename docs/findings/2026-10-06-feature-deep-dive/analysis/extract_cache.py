"""Extract every field of every ``ibm_fez`` snapshot at one pinned ref into a field cache.

This is the shared data layer of the 2026-10-06 feature deep dive. It reads each snapshot
blob once, through one ``git cat-file --batch`` process (one request written and its answer
read before the next, so neither pipe can fill), and never checks the archive out.

Output (a directory, one ``.npy`` per array so a reader can memory-map one field at a time):

- ``<field>__v.npy`` values, ``<field>__d.npy`` stamped dates (ms since the epoch), both of
  shape ``(n_files, n_entities)``, NaN where the record is absent. Field names:

  - ``q.<name>``: per-qubit records in ``properties.qubits`` (156 columns);
  - ``g1.<gate>.<param>``: one-qubit gate parameters in ``properties.gates`` (156 columns);
  - ``g2.<gate>.<param>``: two-qubit gate parameters, one column per DIRECTED coupler;
  - ``gen.jq``, ``gen.zz``: ``properties.general`` per coupler (name parsed against the
    coupling map, one column per undirected coupler);
  - ``gen.lf``: layer fidelity ``lf_<N>`` (one column per name), with ``gen.lf_chain__v.npy``
    holding the index of the qubit chain (``properties.general_qlists``) in ``meta.json``.

- ``file.<name>.npy``: one value per file (stamps, provenance flags, digest ids).
- ``meta.json``: stems, entity lists, unique configuration values, target operation sets,
  lf chains, the state index, the ledger, the collision list, the inventory and the checks.

Files are ordered by ``properties.last_update_date``.

Usage::

    python extract_cache.py --repo <repo> --ref <sha> --out <cache dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
N_QUBITS = 156
BACKEND = "ibm_fez"
# Generous widths; arrays are trimmed to the entities actually seen.
MAX_DIRECTED = 512
MAX_COUPLERS = 256
MAX_LF = 160
# A configuration value larger than this (JSON characters) is kept as a digest only.
MAX_CONFIG_VALUE_CHARS = 400_000

_STAMP_MS: dict[str, float] = {}


def stamp_ms(stamp: str) -> float:
    """Milliseconds since the epoch for an ISO-8601 stamp with an explicit offset (memoised)."""
    hit = _STAMP_MS.get(stamp)
    if hit is None:
        hit = datetime.fromisoformat(stamp).timestamp() * 1000.0
        _STAMP_MS[stamp] = hit
    return hit


def git_text(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=True
    ).stdout.decode("utf-8")


def list_tree(repo: Path, ref: str) -> list[tuple[str, str]]:
    """``(path, blob sha)`` of every blob at ``ref``."""
    rows = []
    for line in git_text(repo, "ls-tree", "-r", ref).splitlines():
        meta, path = line.split("\t", 1)
        rows.append((path, meta.split()[2]))
    return rows


def iter_blobs(repo: Path, shas: Sequence[str]) -> Iterator[bytes]:
    """Blob contents in order; one request is written and its answer read before the next."""
    proc = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        for sha in shas:
            proc.stdin.write(f"{sha}\n".encode("ascii"))
            proc.stdin.flush()
            header = proc.stdout.readline().decode("ascii").split()
            if len(header) != 3 or header[1] != "blob":
                raise RuntimeError(f"git cat-file: no blob for {sha}: {header}")
            body = proc.stdout.read(int(header[2]))
            proc.stdout.read(1)
            yield body
    finally:
        proc.stdin.close()
        proc.wait()


def digest(value: Any) -> str:
    return hashlib.sha1(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def parse_pair(digits: str, edges: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """Every split of ``digits`` into two qubit indices that is an edge of the coupling map."""
    out = []
    for cut in range(1, len(digits)):
        left, right = digits[:cut], digits[cut:]
        if (left != "0" and left.startswith("0")) or (right != "0" and right.startswith("0")):
            continue
        a, b = int(left), int(right)
        if a < N_QUBITS and b < N_QUBITS and ((a, b) in edges or (b, a) in edges):
            out.append((a, b))
    return out


class Grid:
    """Value and date arrays of one field, with columns allocated as entities appear."""

    def __init__(self, n_files: int, width: int, fixed: bool) -> None:
        self.v: FloatArray = np.full((n_files, width), np.nan)
        self.d: FloatArray = np.full((n_files, width), np.nan)
        self.fixed = fixed
        self.units: dict[str, int] = {}
        self.records = 0

    def put(self, i: int, col: int, rec: dict[str, Any]) -> bool:
        """Store one record; return False when ``col`` already held a record in this file."""
        self.records += 1
        unit = str(rec.get("unit", ""))
        self.units[unit] = self.units.get(unit, 0) + 1
        clash = not np.isnan(self.d[i, col]) or not np.isnan(self.v[i, col])
        value = rec.get("value")
        self.v[i, col] = float(value) if isinstance(value, (int, float)) else np.nan
        date = rec.get("date")
        self.d[i, col] = stamp_ms(date) if isinstance(date, str) else np.nan
        return not clash


class Extractor:
    def __init__(self, n_files: int, coupling: set[tuple[int, int]]) -> None:
        self.n = n_files
        self.coupling = coupling
        self.grids: dict[str, Grid] = {}
        self.directed: dict[tuple[int, int], int] = {}
        self.couplers: dict[tuple[int, int], int] = {}
        self.lf_names: dict[str, int] = {}
        self.lf_chains: dict[tuple[int, ...], int] = {}
        self.lf_chain = np.full((n_files, MAX_LF), -1, dtype=np.int32)
        self.name_parse: dict[str, dict[str, Any]] = {}
        self.inventory: dict[str, dict[str, Any]] = {}
        self.checks: dict[str, int] = {
            "duplicate_record_in_file": 0,
            "pair_name_ambiguous": 0,
            "pair_name_unparsed": 0,
            "pair_both_orientations": 0,
            "qubit_record_unexpected_keys": 0,
            "non_numeric_value": 0,
        }

    def grid(self, field: str, width: int, fixed: bool) -> Grid:
        g = self.grids.get(field)
        if g is None:
            g = Grid(self.n, width, fixed)
            self.grids[field] = g
        return g

    def seen(self, key: str, stem: str, unit: str | None = None) -> None:
        e = self.inventory.setdefault(key, {"records": 0, "first": stem, "last": stem, "units": {}})
        e["records"] += 1
        e["last"] = stem
        if unit is not None:
            e["units"][unit] = e["units"].get(unit, 0) + 1

    def put(
        self, field: str, width: int, fixed: bool, i: int, col: int, rec: dict[str, Any]
    ) -> None:
        if not isinstance(rec.get("value"), (int, float)):
            self.checks["non_numeric_value"] += 1
        if not self.grid(field, width, fixed).put(i, col, rec):
            self.checks["duplicate_record_in_file"] += 1

    def coupler_col(self, name: str) -> int | None:
        """Column of an undirected coupler named like ``jq_7273`` (parsed once per name)."""
        hit = self.name_parse.get(name)
        if hit is None:
            prefix, digits = name.split("_", 1)
            pairs = parse_pair(digits, self.coupling)
            hit = {"prefix": prefix, "candidates": pairs}
            if len(pairs) != 1:
                self.checks["pair_name_ambiguous" if pairs else "pair_name_unparsed"] += 1
            self.name_parse[name] = hit
        pairs = hit["candidates"]
        if len(pairs) != 1:
            return None
        a, b = pairs[0]
        key = (min(a, b), max(a, b))
        return self.couplers.setdefault(key, len(self.couplers))

    def file(self, i: int, stem: str, props: dict[str, Any]) -> None:
        for q, records in enumerate(props.get("qubits") or []):
            for rec in records:
                name = str(rec.get("name"))
                self.seen(f"qubit:{name}", stem, str(rec.get("unit", "")))
                if set(rec) - {"date", "name", "unit", "value"}:
                    self.checks["qubit_record_unexpected_keys"] += 1
                self.put(f"q.{name}", N_QUBITS, True, i, q, rec)
        for gate in props.get("gates") or []:
            kind = str(gate.get("gate"))
            qubits = [int(x) for x in gate.get("qubits") or []]
            for rec in gate.get("parameters") or []:
                pname = str(rec.get("name"))
                self.seen(f"gate:{kind}:{pname}:{len(qubits)}q", stem, str(rec.get("unit", "")))
                if len(qubits) == 1:
                    self.put(f"g1.{kind}.{pname}", N_QUBITS, True, i, qubits[0], rec)
                elif len(qubits) == 2:
                    col = self.directed.setdefault((qubits[0], qubits[1]), len(self.directed))
                    self.put(f"g2.{kind}.{pname}", MAX_DIRECTED, False, i, col, rec)
        chains = {str(r.get("name")): r.get("qubits") for r in props.get("general_qlists") or []}
        orient: dict[tuple[str, tuple[int, int]], str] = {}
        for rec in props.get("general") or []:
            name = str(rec.get("name"))
            prefix = name.split("_", 1)[0]
            self.seen(f"general:{prefix}", stem, str(rec.get("unit", "")))
            if prefix in ("jq", "zz"):
                col = self.coupler_col(name)
                if col is None:
                    continue
                key = (prefix, self.name_parse[name]["candidates"][0])
                canon = (prefix, (min(key[1]), max(key[1])))
                if canon in orient and orient[canon] != name:
                    self.checks["pair_both_orientations"] += 1
                orient[canon] = name
                self.put(f"gen.{prefix}", MAX_COUPLERS, False, i, col, rec)
            elif prefix == "lf":
                col = self.lf_names.setdefault(name, len(self.lf_names))
                self.put("gen.lf", MAX_LF, False, i, col, rec)
                chain = chains.get(name)
                if chain is not None:
                    key_chain = tuple(int(x) for x in chain)
                    chain_id = self.lf_chains.setdefault(key_chain, len(self.lf_chains))
                    self.lf_chain[i, col] = chain_id
            else:
                self.put(f"gen.other.{prefix}", MAX_COUPLERS, False, i, 0, rec)
        for name in chains:
            self.seen(f"general_qlists:{name.split('_', 1)[0]}", stem)


def read_tsv(text: str) -> list[dict[str, str]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    head = lines[0].split("\t")
    return [dict(zip(head, ln.split("\t"), strict=False)) for ln in lines[1:]]


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None, help="first N files only (smoke test)")
    args = ap.parse_args(argv)
    t0 = time.time()
    tree = list_tree(args.repo, args.ref)
    snaps = sorted(
        (p, s)
        for p, s in tree
        if p.startswith("snapshots/") and f"/{BACKEND}/" in p and p.endswith(".json")
    )
    snaps.sort(key=lambda row: row[0].rsplit("/", 1)[1])
    snaps = snaps[: args.limit]
    stems = [p.rsplit("/", 1)[1] for p, _ in snaps]
    n = len(snaps)

    # The coupling map from the first live document parses coupler names such as jq_717.
    coupling: set[tuple[int, int]] = set()
    for body in iter_blobs(args.repo, [s for _, s in snaps]):
        conf = json.loads(body).get("configuration")
        if conf:
            coupling = {(int(a), int(b)) for a, b in conf["coupling_map"]}
            break
    if not coupling:
        raise RuntimeError("no document with a configuration: cannot parse coupler names")

    ex = Extractor(n, coupling)
    file_arrays: dict[str, npt.NDArray[Any]] = {
        "last_update_ms": np.full(n, np.nan),
        "timestamp_ms": np.full(n, np.nan),
        "has_configuration": np.zeros(n, dtype=np.int8),
        "target_ops_id": np.full(n, -1, dtype=np.int32),
        "n_target_ops": np.zeros(n, dtype=np.int32),
        "n_qubit_records": np.zeros(n, dtype=np.int32),
        "n_gate_records": np.zeros(n, dtype=np.int32),
        "n_general_records": np.zeros(n, dtype=np.int32),
        "backend_version_id": np.full(n, -1, dtype=np.int32),
    }
    config_ids: dict[str, npt.NDArray[np.int32]] = {}
    config_values: dict[str, dict[str, Any]] = {}
    target_sets: dict[str, int] = {}
    target_union: set[tuple[str, tuple[int, ...]]] = set()
    target_listing: list[set[tuple[str, tuple[int, ...]]]] = []
    versions: dict[str, int] = {}
    top_keys: dict[str, int] = {}
    schema: dict[str, int] = {}

    for i, body in enumerate(iter_blobs(args.repo, [s for _, s in snaps])):
        if i % 200 == 0:
            print(f"  {i}/{n}  {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
        doc = json.loads(body)
        for k in doc:
            top_keys[k] = top_keys.get(k, 0) + 1
        schema[str(doc.get("schema_version"))] = schema.get(str(doc.get("schema_version")), 0) + 1
        props = doc["properties"]
        file_arrays["last_update_ms"][i] = stamp_ms(props["last_update_date"])
        if isinstance(doc.get("timestamp"), str):
            file_arrays["timestamp_ms"][i] = stamp_ms(doc["timestamp"])
        ver = str(props.get("backend_version"))
        file_arrays["backend_version_id"][i] = versions.setdefault(ver, len(versions))
        file_arrays["n_qubit_records"][i] = sum(len(r) for r in props.get("qubits") or [])
        file_arrays["n_gate_records"][i] = len(props.get("gates") or [])
        file_arrays["n_general_records"][i] = len(props.get("general") or [])
        conf = doc.get("configuration")
        if isinstance(conf, dict):
            file_arrays["has_configuration"][i] = 1
            for key, value in conf.items():
                ids = config_ids.setdefault(key, np.full(n, -1, dtype=np.int32))
                store = config_values.setdefault(key, {})
                h = digest(value)
                if h not in store:
                    text = json.dumps(value, sort_keys=True)
                    store[h] = {
                        "id": len(store),
                        "first": stems[i],
                        "chars": len(text),
                        "value": value if len(text) <= MAX_CONFIG_VALUE_CHARS else None,
                    }
                store[h]["last"] = stems[i]
                store[h]["files"] = store[h].get("files", 0) + 1
                ids[i] = store[h]["id"]
        target = doc.get("target") or {}
        ops = {
            (str(o.get("name")), tuple(int(x) for x in o.get("qargs") or []))
            for o in target.get("operations") or []
        }
        file_arrays["n_target_ops"][i] = len(ops)
        h = digest(sorted([name, list(q)] for name, q in ops))
        if h not in target_sets:
            target_sets[h] = len(target_sets)
            target_listing.append(ops)
            target_union |= ops
        file_arrays["target_ops_id"][i] = target_sets[h]
        ex.file(i, stems[i], props)

    order = np.argsort(file_arrays["last_update_ms"], kind="stable")
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Any] = {}
    widths = {
        **{f: N_QUBITS for f in ex.grids if f.startswith(("q.", "g1."))},
        **{f: len(ex.directed) for f in ex.grids if f.startswith("g2.")},
        "gen.jq": len(ex.couplers),
        "gen.zz": len(ex.couplers),
        "gen.lf": len(ex.lf_names),
    }
    for field, g in sorted(ex.grids.items()):
        w = widths.get(field, g.v.shape[1])
        np.save(out / f"{field}__v.npy", g.v[order, :w])
        np.save(out / f"{field}__d.npy", g.d[order, :w])
        saved[field] = {"width": w, "records": g.records, "units": g.units}
    np.save(out / "gen.lf_chain__v.npy", ex.lf_chain[order, : len(ex.lf_names)])
    for name, arr in file_arrays.items():
        np.save(out / f"file.{name}.npy", arr[order])
    for key, ids in config_ids.items():
        np.save(out / f"file.config.{key}.npy", ids[order])

    union_sorted = sorted(target_union)
    target_meta = []
    for h, k in sorted(target_sets.items(), key=lambda kv: kv[1]):
        ops = target_listing[k]
        target_meta.append(
            {
                "id": k,
                "digest": h,
                "n_ops": len(ops),
                "missing_from_union": sorted([name, list(q)] for name, q in target_union - ops),
            }
        )
    sorted_stems = [stems[k] for k in order]
    files_by_stem = {s: j for j, s in enumerate(sorted_stems)}
    state_rows = read_tsv(git_text(args.repo, "show", f"{args.ref}:health/state-index.tsv"))
    state_ids: dict[str, int] = {}
    state_id = np.full(n, -1, dtype=np.int32)
    is_new = np.full(n, -1, dtype=np.int8)
    for row in state_rows:
        j = files_by_stem.get(row["snapshot_filename"])
        if j is None:
            continue
        state_id[j] = state_ids.setdefault(row["qubit_digest"], len(state_ids))
        is_new[j] = int(row["is_new_state"])
    np.save(out / "file.state_id.npy", state_id)
    np.save(out / "file.is_new_state.npy", is_new)
    ledger: list[dict[str, str]] = []
    for path, _ in sorted(p for p in tree if p[0].startswith("ledger/") and p[0].endswith(".tsv")):
        ledger.extend(read_tsv(git_text(args.repo, "show", f"{args.ref}:{path}")))
    meta = {
        "ref": args.ref,
        "backend": BACKEND,
        "n_files": n,
        "stems": sorted_stems,
        "fields": saved,
        "qubits": list(range(N_QUBITS)),
        "directed_edges": [list(e) for e, _ in sorted(ex.directed.items(), key=lambda kv: kv[1])],
        "couplers": [list(e) for e, _ in sorted(ex.couplers.items(), key=lambda kv: kv[1])],
        "lf_names": [nm for nm, _ in sorted(ex.lf_names.items(), key=lambda kv: kv[1])],
        "lf_chains": [list(c) for c, _ in sorted(ex.lf_chains.items(), key=lambda kv: kv[1])],
        "coupler_name_parse": ex.name_parse,
        "coupling_map": sorted([a, b] for a, b in coupling),
        "config_values": config_values,
        "target_union": [[name, list(q)] for name, q in union_sorted],
        "target_sets": target_meta,
        "backend_versions": versions,
        "state_digests": [d for d, _ in sorted(state_ids.items(), key=lambda kv: kv[1])],
        "state_index_rows": len(state_rows),
        "ledger": ledger,
        "collisions": sorted(
            p for p, _ in tree if p.startswith("collisions/") and p.endswith(".json")
        ),
        "top_level_keys": top_keys,
        "schema_versions": schema,
        "inventory": ex.inventory,
        "checks": ex.checks,
        "seconds": round(time.time() - t0, 1),
    }
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"done: {n} files, {len(saved)} fields, {meta['seconds']}s -> {out}", file=sys.stderr)
    print(json.dumps(ex.checks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
