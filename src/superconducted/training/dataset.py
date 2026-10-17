"""Pinned, read-only archive extraction with one row per distinct qubit block.

Documents are streamed through git show. Only digests and numeric row summaries
are retained; selection uses (last_update_date, full path), never iteration order.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from ..calibration.features import ArchiveUnitFeatureExtractor, _coerce_finite_float
from ..calibration.loader import parse_snapshot
from ..calibration.storage import _decode_filename_stem
from ..interfaces import CalibrationFeatureExtractor
from ..types import CalibrationSnapshot, TrainingSet
from .targets import gate_lengths, qubit_targets, snapshot_target

# Fixed TSV columns: usable count, sample std and quantiles in archive units
# (T1/T2 microseconds, readout_error dimensionless). No I/O or X columns added.
SPREAD_NAMES: tuple[str, ...] = tuple(
    f"{name}_{stat}"
    for name in ("T1", "T2", "readout_error")
    for stat in ("n_usable", "qubit_std", "qubit_p10", "qubit_p50", "qubit_p90")
)
# Fixed TSV columns for dimensionless gamma summaries from snapshot_target.
TARGET_SPREAD_NAMES: tuple[str, ...] = tuple(
    f"gamma_{stat}" for stat in ("std", "p10", "p50", "p90")
)


class ArchiveRefError(ValueError):
    """The requested local archive commit cannot be resolved."""


class NoUsableRowsError(ValueError):
    """The archive was read successfully, but no usable training rows remain."""


class ArchiveTimestampError(ValueError):
    """Distinct device states share a row timestamp; the archive is ambiguous."""


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def resolve_archive_ref(repo: Path, ref: str) -> str:
    """Resolve ``ref`` in local ``repo`` to its full commit SHA.

    Invokes git rev-parse only; never fetches or checks out data. Any ref spelling
    is accepted, but the returned identifier always names an immutable commit.
    Raise ArchiveRefError if git is absent or the ref is unreachable.
    """
    try:
        return (
            _git(repo, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ArchiveRefError(f"Unreachable archive ref: {ref}") from exc


def iter_archive(
    repo: Path, ref: str, *, prefix: str = "snapshots/"
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield JSON documents in path order at a pinned local commit, without checkout.

    One ls-tree covers the entire prefix (all months by default), followed by
    one git show per file. Invalid JSON yields an empty mapping so callers can
    count it as parse_error rather than silently losing an archive document.
    """
    sha = resolve_archive_ref(repo, ref)
    paths = _git(repo, "ls-tree", "-r", "--name-only", sha, "--", prefix).decode().splitlines()
    for path in sorted(paths):
        if path.endswith(".json"):
            try:
                doc = json.loads(_git(repo, "show", f"{sha}:{path}"))
            except (ValueError, UnicodeError):
                doc = {}
            yield path, doc if isinstance(doc, dict) else {}


def _strip_parameter_dates(node: Any) -> Any:
    """Mirror the stdlib dashboard normalizer without importing unshipped scripts."""
    if isinstance(node, list):
        return [_strip_parameter_dates(item) for item in node]
    if not isinstance(node, dict):
        return node
    is_parameter = "value" in node
    return {
        key: _strip_parameter_dates(value)
        for key, value in node.items()
        if not (is_parameter and key == "date")
    }


def qubit_block_digest(doc: dict[str, Any]) -> str:
    """Hash the bare qubit list by dashboard normalization; pure, no I/O.

    Dates on parameters provide provenance and are stripped out only in cases where there is a
    value key. Names, units, values, list order and other metadata are untouched.
    Conformance tests tie this packaged implementation to the stdlib-only
    scripts.canonical_snapshot_digest.qubit_digest implementation.
    """
    properties = doc.get("properties")
    if not isinstance(properties, dict) or not isinstance(properties.get("qubits"), list):
        raise ValueError("properties.qubits must be a list")
    body = json.dumps(
        _strip_parameter_dates(properties["qubits"]), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _timestamp(doc: dict[str, Any]) -> datetime:
    stamp = datetime.fromisoformat(doc["properties"]["last_update_date"].replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("last_update_date must be timezone aware")
    return stamp.astimezone(UTC)


def _parameter_date(value: str) -> str:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC).isoformat()


def dedup_by_qubit_block(
    docs: Iterable[tuple[str, dict[str, Any]]],
) -> list[tuple[str, dict[str, Any]]]:
    """Select earliest document per digest, sorted by UTC timestamp then full path.

    Helper function for small inputs only, as the builder stores summaries
    not entire documents. Incorrect input results in ValueError or KeyError.
    """
    first: dict[str, tuple[str, dict[str, Any]]] = {}
    for path, doc in docs:
        digest = qubit_block_digest(doc)
        previous = first.get(digest)
        if previous is None or (_timestamp(doc), path) < (_timestamp(previous[1]), previous[0]):
            first[digest] = path, doc
    return sorted(first.values(), key=lambda item: (_timestamp(item[1]), item[0]))


def hour_of_day_weights(timestamps: Iterable[datetime]) -> npt.NDArray[np.float64]:
    """Map aware row timestamps to finite positive inverse UTC-hour weights.

    Return one float64 weight per input, with equal total weight per populated
    hour and mean one. Empty input returns an empty array. No I/O or mutations;
    reject naive timestamps rather than depending on the machine's timezone.
    """
    hours = []
    for stamp in timestamps:
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("Hour weighting requires timezone-aware timestamps")
        hours.append(stamp.astimezone(UTC).hour)
    counts = Counter(hours)
    weights = np.array([1.0 / counts[hour] for hour in hours], dtype=np.float64)
    return weights / weights.mean() if hours else weights


@dataclass
class BuildReport:
    """Caller-supplied audit output; reset and populated by build_training_set."""

    documents: int = 0
    duplicates: int = 0
    skipped: Counter[str] = field(default_factory=Counter)
    missingness: Counter[str] = field(default_factory=Counter)
    target_skips: Counter[str] = field(default_factory=Counter)
    rows: list[dict[str, Any]] = field(default_factory=list)


def _row(
    path: str, doc: dict[str, Any], digest: str, extractor: CalibrationFeatureExtractor
) -> tuple[dict[str, Any], Counter[str], Counter[str], str | None]:
    parsed = parse_snapshot(doc, source=path)
    props = doc["properties"]
    stamp = _decode_filename_stem(Path(path).stem)
    raw = CalibrationSnapshot(
        backend=parsed.backend_name,
        timestamp=stamp,
        schema_version=str(doc.get("schema_version", "1.0.0")),
        properties=props,
        target=doc.get("target"),
        configuration=doc.get("configuration"),
    )
    row: dict[str, Any] = {
        "path": path,
        "stem": Path(path).stem,
        "qubit_digest": digest,
        "last_update_date": _timestamp(doc).isoformat(),
        "hour_utc": _timestamp(doc).hour,
    }
    try:
        x = extractor.extract(raw)
        if x.shape != (extractor.output_dim,) or not np.all(np.isfinite(x)):
            raise ValueError("Unusable extractor output")
    except ValueError:
        return row, Counter(), Counter(), "features_unusable"
    row.update(zip(extractor.feature_names, x.tolist(), strict=True))
    for name in ("T1", "T2", "readout_error"):
        values = [
            value
            for qubit in props["qubits"]
            for entry in qubit
            if entry.get("name") == name
            and (value := _coerce_finite_float(entry.get("value"))) is not None
        ]
        row[f"{name}_n_usable"] = len(values)
        row[f"{name}_qubit_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else None
        quantiles = np.quantile(values, (0.1, 0.5, 0.9)).tolist() if values else [None] * 3
        row.update(zip((f"{name}_qubit_p{p}" for p in (10, 50, 90)), quantiles, strict=True))
    dates = sorted(
        _parameter_date(entry["date"])
        for qubit in props["qubits"]
        for entry in qubit
        if isinstance(entry.get("date"), str)
    )
    row.update(qubit_date_min=dates[0] if dates else "", qubit_date_max=dates[-1] if dates else "")
    targets = qubit_targets(parsed, gate_lengths(props, "sx"))
    skipped = Counter(asdict(targets.skipped))
    target = snapshot_target(targets)
    if target is None:
        return row, Counter(), skipped, "target_unusable"
    row.update({"gamma": float(target.mean[0]), "lambda": float(target.mean[1])})
    row["n_usable_qubits_target"] = target.n_usable
    row.update(
        zip(
            TARGET_SPREAD_NAMES,
            [float(target.std[0]), *target.quantiles[:, 0].tolist()],
            strict=True,
        )
    )
    missingness = Counter(
        {
            f"{name}_{kind}": value
            for name, stats in asdict(parsed.missingness).items()
            for kind, value in zip(("absent", "explicit_null", "nan_present"), stats, strict=True)
        }
    )
    return row, missingness, skipped, None


def build_training_set(
    repo: Path,
    ref: str,
    *,
    backend: str | None = None,
    extractor: CalibrationFeatureExtractor | None = None,
    weighting: Literal["uniform", "hour_of_day"] = "uniform",
    report: BuildReport | None = None,
) -> TrainingSet:
    """Load a pinned archive into trainer inputs; mutate an optional audit report.

    Keep only numeric summaries, replacing a representative when a document
    with an earlier (last_update_date, path) arrives. Count duplicates before usability:
    a subsequently usable one cannot replace an unusable first representative.
    The default ArchiveUnitFeatureExtractor explicitly converts ADR-010's SI
    vectorizer output back to archive microseconds, matching the survey and
    quantile stack. Spread columns use archive units too. Injected extractors
    must follow this unit contract. ADR-027 owns the dimensionless targets.
    Raise NoUsableRowsError for zero rows and ArchiveTimestampError for ties.
    No network, archive writes, or checkouts; subprocess side effects are git reads.
    """
    if weighting not in ("uniform", "hour_of_day"):
        raise ValueError("Unknown weighting")
    extractor = extractor or ArchiveUnitFeatureExtractor()
    if any("init_error" in name for name in extractor.feature_names):
        raise ValueError("init_error is excluded from training features")
    sha = resolve_archive_ref(repo, ref)
    audit = report if report is not None else BuildReport()
    audit.documents = audit.duplicates = 0
    audit.skipped.clear()
    audit.missingness.clear()
    audit.target_skips.clear()
    audit.rows.clear()
    first: dict[
        str, tuple[datetime, str, dict[str, Any], Counter[str], Counter[str], str | None]
    ] = {}
    for path, doc in iter_archive(repo, sha):
        if backend is not None and Path(path).parent.name != backend:
            continue
        audit.documents += 1
        try:
            digest, timestamp = qubit_block_digest(doc), _timestamp(doc)
        except (ValueError, KeyError, TypeError, AttributeError):
            audit.skipped["parse_error"] += 1
            continue
        previous = first.get(digest)
        if previous is not None:
            audit.duplicates += 1
            if (timestamp, path) >= previous[:2]:
                continue
        try:
            row, missingness, target_skips, reason = _row(path, doc, digest, extractor)
        except (ValueError, KeyError, TypeError, AttributeError):
            row, missingness, target_skips, reason = {}, Counter(), Counter(), "parse_error"
        first[digest] = timestamp, path, row, missingness, target_skips, reason
    ordered = sorted(first.values(), key=lambda item: item[:2])
    for previous, current in pairwise(ordered):
        if previous[0] == current[0]:
            raise ArchiveTimestampError(
                f"Distinct states share last_update_date: {previous[1]} and {current[1]}"
            )
    timestamps = []
    for timestamp, _, row, missingness, target_skips, reason in ordered:
        audit.target_skips.update(target_skips)
        if reason:
            audit.skipped[reason] += 1
        else:
            timestamps.append(timestamp)
            audit.rows.append(row)
            audit.missingness.update(missingness)
    assert len(audit.rows) + sum(audit.skipped.values()) + audit.duplicates == audit.documents
    if not audit.rows:
        raise NoUsableRowsError("Archive has no usable rows")
    hourly = hour_of_day_weights(timestamps)
    for row, weight in zip(audit.rows, hourly.tolist(), strict=True):
        row.update(weight_uniform=1.0, weight_hour_of_day=weight)
    return TrainingSet(
        features=np.array([[row[name] for name in extractor.feature_names] for row in audit.rows]),
        targets=np.array([[row["gamma"], row["lambda"]] for row in audit.rows]),
        timestamps=tuple(timestamps),
        provenance=tuple(row["qubit_digest"] for row in audit.rows),
        feature_names=extractor.feature_names,
        target_names=("gamma", "lambda"),
        archive_ref=sha,
        weights=hourly if weighting == "hour_of_day" else np.ones(len(audit.rows)),
    )
