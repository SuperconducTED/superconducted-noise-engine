"""
Feature distribution survey script.
Reads every snapshot at a pinned ref and records the distribution of features.

Usage:
    python -m scripts.feature_distribution --repo <path> --ref <ref> --out <path>
"""

import argparse
import csv
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

from scripts.init_error_analysis import list_snapshots, read_snapshot
from superconducted.calibration.features import BasicCalibrationVectorizer, _coerce_finite_float
from superconducted.types import CalibrationSnapshot


@dataclass(frozen=True)
class SnapshotFeatureRow:
    """FR-2: One row per snapshot. Columns in the exact requested order."""

    path: str
    stem: str
    backend: str
    timestamp: str
    last_update_date: str
    n_qubits: int
    rejection_reason: str | None

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


def _compute_stats(
    values: list[float],
) -> tuple[int, float | None, float | None, float | None, float | None]:
    """FR-2: Helper to compute n_usable, std (ddof=1), p10, p50, p90."""
    n_usable = len(values)
    if n_usable == 0:
        return 0, None, None, None, None

    arr = np.array(values, dtype=np.float64)
    std = float(np.std(arr, ddof=1)) if n_usable >= 2 else None

    p10 = float(np.percentile(arr, 10))
    p50 = float(np.percentile(arr, 50))
    p90 = float(np.percentile(arr, 90))

    return n_usable, std, p10, p50, p90


def snapshot_row(path: str, doc: dict[str, Any]) -> SnapshotFeatureRow:
    """FR-3: Importable extraction. The per-document work is a pure function."""
    stem = Path(path).stem

    raw_ts = doc.get("timestamp")
    if isinstance(raw_ts, str):
        ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    else:
        ts = datetime.strptime(stem, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=UTC)

    snapshot = CalibrationSnapshot(
        backend=doc.get("backend", "unknown"),
        timestamp=ts,
        schema_version=doc.get("schema_version", "1.0.0"),
        properties=doc.get("properties", {}),
        target=doc.get("target"),
        configuration=doc.get("configuration"),
    )

    extractor = BasicCalibrationVectorizer()

    mean_t1: float | None
    mean_t2: float | None
    mean_ro: float | None
    rejection_reason: str | None = None

    try:
        means = extractor.extract(snapshot)
        mean_t1, mean_t2, mean_ro = float(means[0]), float(means[1]), float(means[2])
    except ValueError as e:
        mean_t1 = mean_t2 = mean_ro = None
        rejection_reason = str(e)

    qubits_section = snapshot.properties.get("qubits", [])
    t1_vals, t2_vals, ro_vals = [], [], []

    for qubit_props in qubits_section:
        for nduv in qubit_props:
            name = nduv.get("name")
            val = _coerce_finite_float(nduv.get("value"))
            if val is not None:
                if name == "T1":
                    t1_vals.append(val)
                elif name == "T2":
                    t2_vals.append(val)
                elif name == "readout_error":
                    ro_vals.append(val)

    t1_n, t1_std, t1_p10, t1_p50, t1_p90 = _compute_stats(t1_vals)
    t2_n, t2_std, t2_p10, t2_p50, t2_p90 = _compute_stats(t2_vals)
    ro_n, ro_std, ro_p10, ro_p50, ro_p90 = _compute_stats(ro_vals)

    last_update = doc.get("properties", {}).get("last_update_date", "")

    return SnapshotFeatureRow(
        path=path,
        stem=stem,
        backend=snapshot.backend,
        timestamp=snapshot.timestamp.isoformat(),
        last_update_date=last_update,
        n_qubits=len(qubits_section),
        rejection_reason=rejection_reason,
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
    )


def iter_snapshot_rows(
    repo: Path, ref: str, prefix: str = "snapshots/"
) -> Iterator[SnapshotFeatureRow]:
    """Yields parsed snapshot rows one by one. Extracted as a standalone generator
    to allow other modules to traverse the archive without triggering the CLI.
    """
    snapshot_paths = list_snapshots(repo, ref, prefix)
    for path in snapshot_paths:
        doc = read_snapshot(repo, ref, path)
        yield snapshot_row(path, doc)


def summarize(rows: list[SnapshotFeatureRow]) -> dict[str, Any]:
    """FR-4: Returns per-feature p1/p50/p99, median over snapshots of qubit_std, and counts."""
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
            summary[f"{feat_name}_p1"] = summary[f"{feat_name}_p50"] = summary[
                f"{feat_name}_p99"
            ] = None

        valid_stds = [getattr(r, std_attr) for r in rows if getattr(r, std_attr) is not None]
        if valid_stds:
            summary[f"{feat_name}_median_qubit_std"] = float(
                np.median(np.array(valid_stds, dtype=np.float64))
            )
        else:
            summary[f"{feat_name}_median_qubit_std"] = None

    return summary


def main() -> int:
    """FR-1: The walk and the CLI."""
    parser = argparse.ArgumentParser(description="Survey the archive's feature distribution.")
    parser.add_argument("--repo", required=True, help="Path to the git repository")
    parser.add_argument("--ref", required=True, help="Pinned git ref (e.g., FETCH_HEAD)")
    parser.add_argument("--backend", help="Filter by a specific backend (e.g., ibm_fez)")
    parser.add_argument("--limit", type=int, help="Limit the number of processed files")
    parser.add_argument("--out", required=True, help="Output TSV file path")

    args = parser.parse_args()
    start_time = time.time()

    # Reject negative limits to prevent unintended tail-slicing behavior during archive traversal.
    if args.limit is not None and args.limit < 0:
        print("Error: --limit cannot be negative.", file=sys.stderr)
        return 1

    try:
        subprocess.run(
            ["git", "-C", args.repo, "cat-file", "-t", args.ref], check=True, capture_output=True
        )
    except subprocess.CalledProcessError:
        print(f"Error: Ref '{args.ref}' is unreachable in repo '{args.repo}'.", file=sys.stderr)
        print(
            "Requires `git fetch superconducted-noise-engine calibration-data` first.",
            file=sys.stderr,
        )
        return 1

    repo_path = Path(args.repo)
    rows: list[SnapshotFeatureRow] = []

    # Consume the reusable iterator to build the survey data.
    for row in iter_snapshot_rows(repo_path, args.ref):
        if args.backend and args.backend not in row.path:
            continue

        rows.append(row)

        # Halt extraction early if the requested limit is reached,
        # optimizing runtime for partial surveys.
        if args.limit is not None and len(rows) >= args.limit:
            break

    field_names = [f.name for f in fields(SnapshotFeatureRow)]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(field_names)
        for row in rows:
            writer.writerow([getattr(row, name) for name in field_names])

    summary_data = summarize(rows)
    summary_data["runtime_seconds"] = time.time() - start_time

    print("Survey Summary:")
    print(json.dumps(summary_data, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
