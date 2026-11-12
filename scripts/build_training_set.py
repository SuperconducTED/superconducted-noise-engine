"""Write deterministic training evidence from a locally fetched archive commit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import shlex
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from superconducted.training.dataset import (
    SPREAD_NAMES,
    TARGET_SPREAD_NAMES,
    BuildReport,
    NoUsableRowsError,
    build_training_set,
)


def _source_revision() -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        changed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "status",
                "--porcelain",
                "--untracked-files=normal",
                "--",
                "src",
                "scripts",
                "tests",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return "unavailable (source checkout not accessible)"
    return revision + (" + uncommitted source changes" if changed else "")


def main(argv: Sequence[str] | None = None) -> int:
    """Write evidence; exit 0 success, 1 no usable rows, 2 read/schema failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--ref", required=True)
    parser.add_argument("--backend")
    parser.add_argument(
        "--public-parquet",
        type=Path,
        help="Pinned ADR-029 parquet; ibm_fez only, never downloaded implicitly",
    )
    parser.add_argument("--weighting", choices=("uniform", "hour_of_day"), default="uniform")
    parser.add_argument("--out", type=Path, default=Path("docs/evidence/training-set"))
    args = parser.parse_args(argv)
    report = BuildReport()
    started = time.perf_counter()
    try:
        dataset = build_training_set(
            args.repo,
            args.ref,
            backend=args.backend,
            weighting=args.weighting,
            report=report,
            public_parquet=args.public_parquet,
        )
    except NoUsableRowsError as exc:
        print(exc, file=sys.stderr)
        return 1
    except (ValueError, subprocess.CalledProcessError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 2
    runtime = time.perf_counter() - started
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = "-public" if args.public_parquet else ""
    filename = f"{datetime.now(UTC):%Y-%m-%d}-{dataset.archive_ref[:8]}{suffix}.tsv"
    columns = (
        "path",
        "source",
        "source_revision",
        "source_sha256",
        "stem",
        "qubit_digest",
        "last_update_date",
        "hour_utc",
        *dataset.feature_names,
        "gamma",
        "lambda",
        *SPREAD_NAMES,
        *TARGET_SPREAD_NAMES,
        "qubit_date_min",
        "qubit_date_max",
        "weight_uniform",
        "weight_hour_of_day",
        "n_usable_qubits_target",
    )
    with (args.out / filename).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(columns)
        for row in report.rows:
            writer.writerow(
                [repr(row[name]) if isinstance(row[name], float) else row[name] for name in columns]
            )
    command = [
        "python",
        "scripts/build_training_set.py",
        "--repo",
        args.repo.as_posix(),
        "--ref",
        dataset.archive_ref,
        "--weighting",
        args.weighting,
        "--out",
        args.out.as_posix(),
    ]
    if args.backend:
        command.extend(("--backend", args.backend))
    if args.public_parquet:
        command.extend(("--public-parquet", args.public_parquet.as_posix()))
    hours = Counter(stamp.hour for stamp in dataset.timestamps)
    document_skips = {
        name: report.skipped[name]
        for name in (
            "parse_error",
            "features_unusable",
            "target_unusable",
            "target_coverage_insufficient",
        )
    }
    requirements = Path(__file__).resolve().parents[1] / "requirements-dev.txt"
    requirements_hash = hashlib.sha256(requirements.read_bytes()).hexdigest()
    record = (
        f"## {filename}\n\nArchive commit: `{dataset.archive_ref}`.\n\n"
        f"Builder source revision: `{_source_revision()}`.\n\n"
        f"Python: `{platform.python_version()}`. "
        "Pinned environment: `requirements-dev.txt`, SHA-256 "
        f"`{requirements_hash}`.\n\n"
        "```sh\ngit fetch superconducted-noise-engine calibration-data\n"
        f"{shlex.join(command)}\n```\n\n"
        "NC-012's unit is distinct device states; this file has one row per state.\n\n"
        f"Measured distinct device states: {dataset.n_rows}; documents: {report.documents}; "
        f"duplicates: {report.duplicates}.\n\n"
        "Document skips: "
        f"`{json.dumps(document_skips, sort_keys=True)}`.\n\n"
        f"Target qubit skips: `{json.dumps(dict(report.target_skips), sort_keys=True)}`.\n\n"
        "Target qubit skips by source: "
        f"`{json.dumps(report.target_skips_by_source, sort_keys=True)}`.\n\n"
        "Kept-document loader missingness: "
        f"`{json.dumps(dict(report.missingness), sort_keys=True)}`.\n\n"
        f"UTC row-hour histogram: `{json.dumps(dict(sorted(hours.items())))}`.\n\n"
        f"Measured runtime: {runtime:.0f} seconds (machine-specific). "
        "Growth estimate: to be measured. These figures are audited by this TSV.\n\n"
        "X uses ArchiveUnitFeatureExtractor: T1/T2 in archive microseconds, "
        "readout error dimensionless. ADR-010's BasicCalibrationVectorizer emits SI; "
        "the wrapper explicitly converts it back to the survey/quantile stack's units. "
        "Y is dimensionless; target inputs use SI seconds (training/targets.py, ADR-027). "
        "Feature spread uses sample standard deviation (ddof=1); "
        "a singleton has an empty std cell. "
        "Target gamma spread follows snapshot_target's population standard deviation. "
        "Both weight columns are emitted; uniform is the default. "
        "IBM digests match the dashboard: parameter dates are normalized away; "
        "measurement names, units and values remain. Parameter date bounds are retained "
        "as provenance columns.\n\n"
        f"Fixed column order: `{', '.join(columns)}`.\n\n"
    )
    if report.public is not None:
        from dataclasses import asdict

        record += (
            f"Public replay audit: `{json.dumps(asdict(report.public), sort_keys=True)}`.\n\n"
            "Public source: Charles C. Norton, phanerozoic/qiskit-calibration-drift, "
            "CC-BY-4.0; SN (CC-BY-NC-4.0) never loaded. Neither party has checked "
            "IBM's redistribution terms for backend.properties() output.\n\n"
            "Rules: T1/T2 below 0.01 us multiplied by 1e6; qubit 72 T1/T2 dropped; "
            "first observed value per stamp retained. Completeness uses all five required "
            "fields on every non-excluded qubit before state counting. "
            "Targets from both sources use the factor-1000 NC-041 unit-error guard. "
            "Public states need at least 100 usable target qubits; insufficient coverage "
            "is a separate target_coverage_insufficient skip after NC-078 state counting. "
            "Replay marks stop before the first IBM snapshot and never extend beyond "
            "2026-05-13T12:13:22Z. Public rows never enter calibration-data.\n\n"
        )
    readme = args.out / "README.md"
    previous = (
        readme.read_text(encoding="utf-8") if readme.exists() else "# Training-set evidence\n\n"
    )
    section = re.compile(rf"^## {re.escape(filename)}\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    updated = (
        section.sub(lambda match: record, previous)
        if section.search(previous)
        else previous + record
    )
    readme.write_text(updated, encoding="utf-8")
    print(f"{args.out / filename}: {dataset.n_rows} distinct device states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
