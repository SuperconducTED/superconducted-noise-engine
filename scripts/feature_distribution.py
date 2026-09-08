"""Survey the calibration archive's own feature distribution (Issue #59, Part A).

Reads every ``snapshots/**/*.json`` at a pinned ref through ``git show`` and
writes one TSV row per snapshot: the three ``BasicCalibrationVectorizer``
features, plus the per-qubit spread of the values each feature averages over.
``scripts/feature_distribution.py::summarize`` reduces those rows to the
quantiles ``superconducted.fuzzy.parameterization`` consumes.

Units are the vectorizer's own (NFR-8): **microseconds** for ``mean_T1`` and
``mean_T2``, dimensionless for ``mean_readout_error``. That is the raw Nduv
value with no scaling. ``scripts/first_ensemble_run.py::FEATURE_SCALES`` is in
seconds and is **not** a source of truth for anything here.

``*_qubit_std`` is the **sample** standard deviation, ``numpy.std(v, ddof=1)``,
written empty when fewer than two values are usable -- a spread over one value
is not a measurement. ``ddof=1`` matches ``calibration/features.py::per_qubit_spread``
(#64), which becomes the single home for this statistic; on the committed
fixture ``ibm_fez_20260513T121322Z_q72_missing_t1t2.json`` the T1 spread is
45.4847 with ``ddof=1`` and 45.3377 with ``ddof=0``.

Read-only: the archive is never checked out, never written to, and the network
is never touched. Requires ``git fetch superconducted-noise-engine
calibration-data`` first -- the remote is not ``origin``.

Usage::

    python -m scripts.feature_distribution --repo <path> --ref <sha> \\
        [--backend ibm_fez] [--limit N] --out <tsv>

``--ref`` should be a commit sha, not ``FETCH_HEAD``: the committed TSV's
provenance has to survive the next fetch.
"""

import argparse
import csv
import itertools
import json
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from scripts.init_error_analysis import _git, list_snapshots, read_snapshot

# `_coerce_finite_float` is private on purpose and imported anyway, on purpose:
# FR-2 requires the per-qubit columns to walk `properties.qubits` with *exactly*
# the Nduv filter `BasicCalibrationVectorizer.extract` averages over, so
# `*_n_usable` is the count `extract` used. Re-implementing the filter here
# would let the two drift silently, which is the one failure this column exists
# to rule out. #64 makes `calibration/features.py::per_qubit_spread` the single
# home for this loop; when it lands, import that instead.
from superconducted.calibration.features import BasicCalibrationVectorizer, _coerce_finite_float
from superconducted.types import CalibrationSnapshot

_STEM_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%S%fZ"


@dataclass(frozen=True)
class SnapshotFeatureRow:
    """One archived snapshot's features and per-qubit spread (FR-2).

    Field order is the TSV column order. FR-2's stated columns come first, so
    they are a strict prefix; ``rejection_reason`` is appended last and is
    non-empty exactly when ``mean_*`` are empty.
    """

    path: str
    stem: str
    backend: str
    timestamp: str
    last_update_date: str
    n_qubits: int

    mean_T1: float | None  # noqa: N815
    mean_T2: float | None  # noqa: N815
    mean_readout_error: float | None

    T1_n_usable: int
    T1_qubit_std: float | None
    T1_qubit_p10: float | None
    T1_qubit_p50: float | None
    T1_qubit_p90: float | None

    T2_n_usable: int
    T2_qubit_std: float | None
    T2_qubit_p10: float | None
    T2_qubit_p50: float | None
    T2_qubit_p90: float | None

    readout_error_n_usable: int
    readout_error_qubit_std: float | None
    readout_error_qubit_p10: float | None
    readout_error_qubit_p50: float | None
    readout_error_qubit_p90: float | None

    rejection_reason: str | None


def _compute_stats(
    values: list[float],
) -> tuple[int, float | None, float | None, float | None, float | None]:
    """Return ``(n_usable, std, p10, p50, p90)`` over one feature's qubit values.

    ``std`` is the **sample** standard deviation (``ddof=1``) and is ``None``
    when fewer than two values are usable, rather than NaN (FR-2).
    """
    n_usable = len(values)
    if n_usable == 0:
        return 0, None, None, None, None

    arr = np.array(values, dtype=np.float64)
    std = float(np.std(arr, ddof=1)) if n_usable >= 2 else None

    p10 = float(np.percentile(arr, 10))
    p50 = float(np.percentile(arr, 50))
    p90 = float(np.percentile(arr, 90))

    return n_usable, std, p10, p50, p90


def _as_str(value: Any) -> str:
    """A TSV cell for a JSON value that ought to be a string but need not be.

    Empty for anything that is not one, rather than ``"None"`` or a repr: an
    absent or malformed ``last_update_date`` is missing provenance, and writing
    a plausible-looking placeholder into a committed evidence file is worse than
    writing nothing.
    """
    return value if isinstance(value, str) else ""


def _parse_timestamp(doc: dict[str, Any], stem: str) -> datetime:
    """Snapshot timestamp, parsed exactly as ``first_ensemble_run._load_snapshot`` does.

    Falls back to the filename stem for a document with no ``timestamp`` field.
    Raises ``ValueError`` if neither parses; :func:`snapshot_row` turns that into
    a rejection rather than letting it escape.
    """
    raw_ts = doc.get("timestamp")
    if isinstance(raw_ts, str):
        return datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    return datetime.strptime(stem, _STEM_TIMESTAMP_FORMAT).replace(tzinfo=UTC)


def snapshot_row(path: str, doc: dict[str, Any]) -> SnapshotFeatureRow:
    """Reduce one parsed archive document to its survey row (FR-3).

    Pure: no I/O, no mutation of ``doc``. Never raises -- a document the
    vectorizer rejects, or one whose timestamp will not parse, comes back with
    empty ``mean_*`` and a ``rejection_reason``, and is counted rather than
    dropped. That promise covers a **malformed** document too, not only a
    rejected one: ``doc`` is parsed JSON from an external archive, so every
    container this walks is shape-checked before it is iterated. #63 imports
    this function to build the training set and must not have to pre-validate.
    The per-qubit statistics walk ``properties.qubits`` with the same Nduv
    filter ``BasicCalibrationVectorizer.extract`` uses, so ``*_n_usable`` is the
    count ``extract`` averaged over and ``n_usable <= n_qubits``.
    """
    stem = Path(path).stem
    rejection_reason: str | None = None

    try:
        timestamp = _parse_timestamp(doc, stem)
    except ValueError as exc:
        timestamp = datetime.min.replace(tzinfo=UTC)
        rejection_reason = f"unparseable timestamp: {exc}"

    raw_properties = doc.get("properties")
    properties: dict[str, Any] = raw_properties if isinstance(raw_properties, dict) else {}

    snapshot = CalibrationSnapshot(
        backend=doc.get("backend", "unknown"),
        timestamp=timestamp,
        schema_version=doc.get("schema_version", "1.0.0"),
        properties=properties,
        target=doc.get("target"),
        configuration=doc.get("configuration"),
    )

    mean_t1: float | None = None
    mean_t2: float | None = None
    mean_ro: float | None = None
    if rejection_reason is None:
        try:
            means = BasicCalibrationVectorizer().extract(snapshot)
            mean_t1, mean_t2, mean_ro = float(means[0]), float(means[1]), float(means[2])
        except ValueError as exc:
            # The documented rejection: a feature with no usable value.
            rejection_reason = str(exc)
        except (AttributeError, TypeError) as exc:
            # A malformed document, caught here rather than fixed upstream.
            # `BasicCalibrationVectorizer.extract` assumes `properties.qubits`
            # is a list of lists of dicts and raises `AttributeError` when the
            # archive disagrees; `calibration/features.py` is Baha's and Issue
            # #59 consumes it without editing it, so widening the guard at the
            # call site is this script's only option. Recorded as its own
            # reason so a malformed row is never read as a legitimate rejection.
            rejection_reason = f"malformed document: {type(exc).__name__}: {exc}"

    raw_qubits = properties.get("qubits", [])
    qubits_section: list[Any] = raw_qubits if isinstance(raw_qubits, list) else []
    t1_vals: list[float] = []
    t2_vals: list[float] = []
    ro_vals: list[float] = []

    for qubit_props in qubits_section:
        if not isinstance(qubit_props, list):
            continue
        for nduv in qubit_props:
            if not isinstance(nduv, dict):
                continue
            name = nduv.get("name")
            val = _coerce_finite_float(nduv.get("value"))
            if val is None:
                continue
            if name == "T1":
                t1_vals.append(val)
            elif name == "T2":
                t2_vals.append(val)
            elif name == "readout_error":
                ro_vals.append(val)

    t1_n, t1_std, t1_p10, t1_p50, t1_p90 = _compute_stats(t1_vals)
    t2_n, t2_std, t2_p10, t2_p50, t2_p90 = _compute_stats(t2_vals)
    ro_n, ro_std, ro_p10, ro_p50, ro_p90 = _compute_stats(ro_vals)

    return SnapshotFeatureRow(
        path=path,
        stem=stem,
        backend=snapshot.backend,
        timestamp=snapshot.timestamp.isoformat(),
        last_update_date=_as_str(properties.get("last_update_date")),
        n_qubits=len(qubits_section),
        mean_T1=mean_t1,
        mean_T2=mean_t2,
        mean_readout_error=mean_ro,
        T1_n_usable=t1_n,
        T1_qubit_std=t1_std,
        T1_qubit_p10=t1_p10,
        T1_qubit_p50=t1_p50,
        T1_qubit_p90=t1_p90,
        T2_n_usable=t2_n,
        T2_qubit_std=t2_std,
        T2_qubit_p10=t2_p10,
        T2_qubit_p50=t2_p50,
        T2_qubit_p90=t2_p90,
        readout_error_n_usable=ro_n,
        readout_error_qubit_std=ro_std,
        readout_error_qubit_p10=ro_p10,
        readout_error_qubit_p50=ro_p50,
        readout_error_qubit_p90=ro_p90,
        rejection_reason=rejection_reason,
    )


def iter_snapshot_rows(
    repo: Path, ref: str, prefix: str = "snapshots/", *, backend: str | None = None
) -> Iterator[SnapshotFeatureRow]:
    """Walk every ``*.json`` under ``prefix`` at ``ref``, newest path last (FR-3).

    Importable so the training-set builder (#63) reuses the extraction loop
    instead of rewriting the archive walk. ``backend`` filters on the path
    segment *before* any document is read, so it saves the ``git show`` too.
    """
    paths = list_snapshots(repo, ref, prefix)
    if backend is not None:
        paths = [p for p in paths if f"/{backend}/" in p]
    for path in paths:
        yield snapshot_row(path, read_snapshot(repo, ref, path))


def summarize(rows: list[SnapshotFeatureRow]) -> dict[str, Any]:
    """Reduce survey rows to the per-feature figures the partition consumes (FR-4).

    Per feature: p1/p50/p99 of the snapshot values, the median over snapshots of
    ``*_qubit_std``, and how many rows carry a usable mean. Rows with empty
    ``mean_*`` are excluded from the quantiles but still counted in
    ``file_count``; rows whose std is empty are skipped by the median.

    ``file_count`` counts **files**, never samples and never distinct device
    states -- the archive holds byte-identical repeats, and NC-025's distinct
    count is #63's job.
    """
    summary: dict[str, Any] = {"file_count": len(rows)}

    features = {
        "T1": ("mean_T1", "T1_qubit_std"),
        "T2": ("mean_T2", "T2_qubit_std"),
        "readout_error": ("mean_readout_error", "readout_error_qubit_std"),
    }

    for feat_name, (mean_attr, std_attr) in features.items():
        valid_means = [getattr(r, mean_attr) for r in rows if getattr(r, mean_attr) is not None]
        summary[f"{feat_name}_present_rows"] = len(valid_means)

        if valid_means:
            arr_means = np.array(valid_means, dtype=np.float64)
            summary[f"{feat_name}_p1"] = float(np.percentile(arr_means, 1))
            summary[f"{feat_name}_p50"] = float(np.percentile(arr_means, 50))
            summary[f"{feat_name}_p99"] = float(np.percentile(arr_means, 99))
        else:
            summary[f"{feat_name}_p1"] = None
            summary[f"{feat_name}_p50"] = None
            summary[f"{feat_name}_p99"] = None

        valid_stds = [getattr(r, std_attr) for r in rows if getattr(r, std_attr) is not None]
        summary[f"{feat_name}_median_qubit_std"] = (
            float(np.median(np.array(valid_stds, dtype=np.float64))) if valid_stds else None
        )

    summary["rejected_rows"] = sum(1 for r in rows if r.rejection_reason)
    return summary


def write_tsv(rows: list[SnapshotFeatureRow], out: Path) -> None:
    """Write the survey rows as a TSV, byte-identically for identical input (FR-10).

    ``lineterminator="\\n"`` rather than ``csv``'s default ``\\r\\n``: the repo's
    ``.gitattributes`` normalises every text file to LF, so a CRLF writer would
    make the script's output differ from its own committed artifact on every
    platform and no determinism check could ever pass.
    """
    field_names = [f.name for f in fields(SnapshotFeatureRow)]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(field_names)
        for row in rows:
            writer.writerow([getattr(row, name) for name in field_names])


def main() -> int:
    """Run the archive walk and write the TSV, printing the FR-4 summary (FR-1)."""
    parser = argparse.ArgumentParser(description="Survey the archive's feature distribution.")
    parser.add_argument("--repo", required=True, help="Path to the git repository")
    parser.add_argument("--ref", required=True, help="Pinned git ref; use a commit sha")
    parser.add_argument("--backend", help="Filter by a specific backend (e.g., ibm_fez)")
    parser.add_argument("--limit", type=int, help="Stop after this many rows")
    parser.add_argument("--out", required=True, help="Output TSV file path")

    args = parser.parse_args()
    start_time = time.monotonic()

    if args.limit is not None and args.limit < 0:
        print("Error: --limit cannot be negative.", file=sys.stderr)
        return 1

    repo_path = Path(args.repo)
    try:
        _git(repo_path, "cat-file", "-t", args.ref)
    except (subprocess.CalledProcessError, OSError):
        print(f"Error: Ref '{args.ref}' is unreachable in repo '{args.repo}'.", file=sys.stderr)
        print(
            "Run `git fetch superconducted-noise-engine calibration-data` first; "
            "the archive remote is not `origin`.",
            file=sys.stderr,
        )
        return 1

    walk = iter_snapshot_rows(repo_path, args.ref, backend=args.backend)
    if args.limit is not None:
        walk = itertools.islice(walk, args.limit)
    rows = list(walk)

    write_tsv(rows, Path(args.out))

    summary_data = summarize(rows)
    summary_data["runtime_seconds"] = time.monotonic() - start_time

    print("Survey Summary:")
    print(json.dumps(summary_data, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
