"""Write deterministic training evidence from a locally fetched archive commit."""

from __future__ import annotations

import argparse
import csv
import json
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
    parser.add_argument("--weighting", choices=("uniform", "hour_of_day"), default="uniform")
    parser.add_argument("--out", type=Path, default=Path("docs/evidence/training-set"))
    args = parser.parse_args(argv)
    report = BuildReport()
    started = time.perf_counter()
    try:
        dataset = build_training_set(
            args.repo, args.ref, backend=args.backend, weighting=args.weighting, report=report
        )
    except NoUsableRowsError as exc:
        print(exc, file=sys.stderr)
        return 1
    except (ValueError, subprocess.CalledProcessError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 2
    runtime = time.perf_counter() - started
    args.out.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now(UTC):%Y-%m-%d}-{dataset.archive_ref[:8]}.tsv"
    columns = (
        "path",
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
    hours = Counter(stamp.hour for stamp in dataset.timestamps)
    document_skips = {
        name: report.skipped[name]
        for name in ("parse_error", "features_unusable", "target_unusable")
    }
    record = (
        f"## {filename}\n\nArchive commit: `{dataset.archive_ref}`.\n\n"
        f"Builder source revision: `{_source_revision()}`.\n\n"
        "```sh\ngit fetch superconducted-noise-engine calibration-data\n"
        f"{shlex.join(command)}\n```\n\n"
        "NC-012's unit is distinct device states; this file has one row per state.\n\n"
        f"Measured distinct device states: {dataset.n_rows}; documents: {report.documents}; "
        f"duplicates: {report.duplicates}.\n\n"
        "Document skips: "
        f"`{json.dumps(document_skips, sort_keys=True)}`.\n\n"
        f"Target qubit skips: `{json.dumps(dict(report.target_skips), sort_keys=True)}`.\n\n"
        "Kept-document loader missingness: "
        f"`{json.dumps(dict(report.missingness), sort_keys=True)}`.\n\n"
        f"UTC row-hour histogram: `{json.dumps(dict(sorted(hours.items())))}`.\n\n"
        f"Measured runtime: {runtime:.0f} seconds (machine-specific). "
        "Growth estimate: to be measured. These figures are audited by this TSV; "
        "register claim IDs at merge time.\n\n"
        "X uses ArchiveUnitFeatureExtractor: T1/T2 in archive microseconds, "
        "readout error dimensionless. ADR-010's BasicCalibrationVectorizer emits SI; "
        "the wrapper explicitly converts it back to the survey/quantile stack's units. "
        "Y is dimensionless; target inputs use SI seconds (training/targets.py, ADR-027). "
        "Feature spread uses sample standard deviation (ddof=1); "
        "a singleton has an empty std cell. "
        "Target gamma spread follows snapshot_target's population standard deviation. "
        "Both weight columns are emitted; uniform is the default. "
        "Digests match the dashboard: parameter dates are normalized away; "
        "measurement names, units and values remain. Parameter date bounds are retained "
        "as provenance columns.\n\n"
        f"Fixed column order: `{', '.join(columns)}`.\n\n"
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
