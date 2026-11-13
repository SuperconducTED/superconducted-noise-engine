"""Read-only, pinned public event replay for ADR-029's proposed second source.

Only explicitly named CC-BY columns are decoded; SN is never requested.
Synthetic documents stay in memory and are never admitted to calibration-data.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..calibration.loader import EXPECTED_UNITS

PUBLIC_REVISION = "0c298c2ba07f9b230a81a0e5fa8d993dcd2cf37d"
PUBLIC_SHA256 = "dbb53131a6c2c96732e5be070c6ad1621b7d90cb052298975d78d6bbd86fcc73"
PUBLIC_START = datetime(2026, 1, 31, tzinfo=UTC)
# NC-078's exact boundary: the first IBM document, not midnight on that day.
PUBLIC_END = datetime(2026, 5, 13, 12, 13, 22, tzinfo=UTC)
PUBLIC_SOURCE = "phanerozoic/qiskit-calibration-drift"
# A complete replay can still have only one gate duration initialized. Require
# broad target coverage separately; never change NC-078's completeness count.
PUBLIC_MIN_TARGET_QUBITS = 100
QUBIT_PROPERTIES = tuple(EXPECTED_UNITS)
COMPLETE = ("T1", "T2", "readout_error", "prob_meas0_prep1", "prob_meas1_prep0")
EXCLUDE = frozenset({(72, "T1"), (72, "T2")})
COLUMNS = (
    "backend",
    "scope",
    "property",
    "qubit_a",
    "qubit_b",
    "calibrated_time",
    "observed_time",
    "value",
    "unit",
)


@dataclass
class PublicReplayReport:
    """Completeness counts precede target admissibility and cross-source overlap."""

    revision: str = PUBLIC_REVISION
    sha256: str = PUBLIC_SHA256
    marks: int = 0
    incomplete_marks: int = 0
    distinct_states: int = 0
    overlap_states: int = 0
    minimum_target_qubits: int = PUBLIC_MIN_TARGET_QUBITS
    target_coverage_skips: int = 0
    rescaled_events: dict[str, int] = field(default_factory=dict)
    excluded_rescale_events: dict[str, int] = field(default_factory=dict)


def projected_digest(doc: dict[str, Any]) -> str:
    """NC-078 all7 projection; separate from the IBM document's own digest."""
    entries = sorted(
        (q, entry["name"], float(entry["value"]))
        for q, qubit in enumerate(doc["properties"]["qubits"])
        for entry in qubit
        if entry["name"] in QUBIT_PROPERTIES and (q, entry["name"]) not in EXCLUDE
    )
    return hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()


def verify_public_parquet(path: Path) -> None:
    """Reject anything other than the exact revision's registered bytes."""
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != PUBLIC_SHA256:
        raise ValueError(f"Public parquet SHA-256 mismatch: expected {PUBLIC_SHA256}, got {actual}")


def _events(path: Path, report: PublicReplayReport) -> list[tuple[Any, ...]]:
    try:
        import pyarrow.dataset as ds
    except ImportError as exc:
        raise ValueError(
            "Public archive requires the optional 'public-archive' dependencies"
        ) from exc
    events = []
    selection = (
        (ds.field("backend") == "ibm_fez")
        & ds.field("property").isin([*QUBIT_PROPERTIES, "sx_gate_length"])
        & (ds.field("calibrated_time") < PUBLIC_END)
    )
    scanner = ds.dataset(path, format="parquet").scanner(columns=list(COLUMNS), filter=selection)
    for batch in scanner.to_batches():
        for row in batch.to_pylist():
            if row["backend"] != "ibm_fez":
                continue
            prop, scope = row["property"], row["scope"]
            if not (
                (scope == "qubit" and prop in QUBIT_PROPERTIES)
                or (scope == "gate1q" and prop == "sx_gate_length")
            ):
                continue
            stamp = row["calibrated_time"]
            observed = row["observed_time"]
            if stamp is None or stamp.tzinfo is None or observed is None or observed.tzinfo is None:
                raise ValueError("Public event timestamps must be timezone aware")
            if stamp >= PUBLIC_END:
                continue
            q = row["qubit_a"]
            if not isinstance(q, int) or not 0 <= q < 156:
                raise ValueError(f"Invalid ibm_fez qubit: {q!r}")
            if (q, prop) in EXCLUDE:
                if float(row["value"]) < 0.01:
                    report.excluded_rescale_events[prop] = (
                        report.excluded_rescale_events.get(prop, 0) + 1
                    )
                continue
            expected = "ns" if prop == "sx_gate_length" else EXPECTED_UNITS[prop]
            if row["unit"] != expected:
                raise ValueError(f"Public {prop} expected unit {expected!r}, got {row['unit']!r}")
            value = float(row["value"])
            if not math.isfinite(value):
                raise ValueError(f"Non-finite public {prop} value")
            if prop in ("T1", "T2") and value < 0.01:
                value *= 1e6
                report.rescaled_events[prop] = report.rescaled_events.get(prop, 0) + 1
            events.append((stamp, observed, q, prop, value))
    # First observed value per calibrated stamp wins. Sorting is stable even
    # when duplicate source rows share observed_time.
    events.sort(key=lambda event: event[:2])
    return events


def iter_public_archive(
    path: Path,
    report: PublicReplayReport,
    *,
    end: datetime = PUBLIC_END,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield earliest hourly complete representative of each all7 state.

    The fixed NC-078 grid stops at the first IBM document, or earlier when
    the selected archive starts earlier. Target skips are counted separately
    by the builder; gate changes do not create new qubit states.
    """
    verify_public_parquet(path)
    events = _events(path, report)
    required = {(q, p) for q in range(156) for p in COMPLETE if (q, p) not in EXCLUDE}
    state: dict[tuple[int, str], tuple[float, datetime]] = {}
    seen_events: set[tuple[datetime, int, str]] = set()
    seen_states: set[str] = set()
    index = 0
    mark = PUBLIC_START
    while mark < min(end, PUBLIC_END):
        report.marks += 1
        while index < len(events) and events[index][0] <= mark:
            stamp, _, q, prop, value = events[index]
            key = (stamp, q, prop)
            if key not in seen_events:
                state[q, prop] = value, stamp
                seen_events.add(key)
            index += 1
        if not required <= state.keys():
            report.incomplete_marks += 1
            mark += timedelta(hours=1)
            continue
        qubits: list[list[dict[str, Any]]] = [[] for _ in range(156)]
        gates = []
        for (q, prop), (value, stamp) in sorted(state.items()):
            entry = {
                "name": prop,
                "value": value,
                "date": stamp.isoformat(),
                "unit": "ns" if prop == "sx_gate_length" else EXPECTED_UNITS[prop],
            }
            if prop == "sx_gate_length":
                entry["name"] = "gate_length"
                gates.append({"gate": "sx", "qubits": [q], "parameters": [entry]})
            else:
                qubits[q].append(entry)
        doc = {
            "backend": "ibm_fez",
            "schema_version": "1.0.0",
            "timestamp": mark.isoformat(),
            "properties": {"last_update_date": mark.isoformat(), "qubits": qubits, "gates": gates},
        }
        digest = projected_digest(doc)
        if digest not in seen_states:
            seen_states.add(digest)
            report.distinct_states += 1
            yield f"public/ibm_fez/{mark:%Y%m%dT%H%M%S%fZ}.json", doc
        mark += timedelta(hours=1)
