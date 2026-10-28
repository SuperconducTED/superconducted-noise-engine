"""Archive side of the #125 hardware test: four predictors per qubit at submission time.

For each qubit and each of ``T1``, ``T2``, ``readout_error``, ``prob_meas0_prep1`` and
``prob_meas1_prep0`` this emits, from a pinned ``calibration-data`` ref and nothing else:

- ``reading``: the value in the latest archived *file* at or before ``t_s`` (files, not
  states; a state is a first occurrence), or the live ``backend.properties()`` document
  captured at ``t_s`` when one is supplied;
- ``level``: the geometric mean over the distinct device *states* in the trailing 30 days,
  finite positive values only, at least five states;
- ``band_lo``, ``band_hi``: the 10th and 90th percentiles of the same window (NumPy's default
  linear interpolation, NC-081's rolling-band object);
- ``n_window``, ``n_distinct`` (whole archive up to ``t_s``), ``log_disagreement =
  log(reading) - log(level)`` and ``n_window_distinct`` (distinct values inside the window).

``--mode controls`` freezes the four control qubits once, at the freezing ref, before any job
(proposal D of the #125 pre-registration). ``--mode submission`` then takes that file, keeps its
qubits out of the discriminating stratum, and selects the eight discriminating qubits by sign
(proposals A and B). ``--mode execution`` emits only ``reading`` as of a later time: the
``reading_at_execution`` control of the design. Units are SI seconds for ``T1`` and ``T2`` and
dimensionless for the readout quantities, exactly as ``calibration/loader.py`` parses them.

This half builds no channel and submits nothing. Design:
``docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md``; plan:
``docs/roadmap/2026-10-23-hardware-test-archive-side-plan.md``; selection rules:
``docs/implementations/2026-10-28-hardware-test-selection-rules.md``.

Usage::

    python -m scripts.hardware_test_predictors --repo . --ref <sha> --at <freezing instant> \\
        --mode controls --out <dir>
    python -m scripts.hardware_test_predictors --repo . --ref <sha> --at 2026-11-03T03:45:00Z \\
        --controls <dir>/controls.json [--live-properties live.json] --out <job dir>
    python -m scripts.hardware_test_predictors --repo . --ref <sha> --at <t> \\
        --mode execution [--live-properties live.json] --out <dir>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from superconducted.calibration.loader import (
    CalibrationParseError,
    ParsedCalibrationSnapshot,
    parse_snapshot,
)
from superconducted.training.dataset import (
    ArchiveRefError,
    iter_archive,
    qubit_block_digest,
    resolve_archive_ref,
)

QUANTITIES: tuple[str, ...] = (
    "T1",
    "T2",
    "readout_error",
    "prob_meas0_prep1",
    "prob_meas1_prep0",
)
_FIELDS: dict[str, str] = {
    "T1": "t1_seconds",
    "T2": "t2_seconds",
    "readout_error": "readout_error",
    "prob_meas0_prep1": "prob_meas0_prep1",
    "prob_meas1_prep0": "prob_meas1_prep0",
}
WINDOW_DAYS = 30.0
MIN_WINDOW_STATES = 5
MIN_DISTINCT_VALUES = 20
# Proposal A: the discriminating stratum's floor, counted inside the window (NC-088).
MIN_WINDOW_DISTINCT = 15
BAND_QUANTILES = (0.10, 0.90)
TSV_COLUMNS: tuple[str, ...] = (
    "qubit",
    "quantity",
    "reading",
    "level",
    "band_lo",
    "band_hi",
    "n_window",
    "n_distinct",
    "log_disagreement",
    "reading_time",
    "n_window_distinct",
)


@dataclass(frozen=True)
class FileRecord:
    """One archived document, parsed: its time, its qubit-block digest and its values."""

    path: str
    time: datetime
    digest: str
    values: npt.NDArray[np.float64]  # (n_qubits, len(QUANTITIES)), NaN where missing


@dataclass
class Collected:
    """Every usable document up to ``until`` (``files``) and the first file per state.

    ``backend`` is the backend the archive was filtered on; a live document must name the same
    one (``LiveDocumentError`` otherwise), so two physical devices never share a window.
    """

    backend: str = ""
    files: list[FileRecord] = field(default_factory=list)
    states: list[FileRecord] = field(default_factory=list)
    skipped: Counter[str] = field(default_factory=Counter)


class LiveDocumentError(ValueError):
    """A ``--live-properties`` payload that cannot be used: wrong shape or wrong backend.

    Distinct from ``CalibrationParseError`` on purpose: an archive document that fails to parse
    is counted and skipped, while a bad live document stops the run, because it would otherwise
    replace every reading.
    """


@dataclass(frozen=True)
class PredictorRow:
    qubit: int
    quantity: str
    reading: float
    level: float
    band_lo: float
    band_hi: float
    n_window: int
    n_distinct: int
    log_disagreement: float
    reading_time: str
    # Last, with a default, so positional constructors written before it keep working.
    n_window_distinct: int = 0


class ControlsFileError(ValueError):
    """A ``--controls`` file that cannot be used: unreadable, wrong shape or wrong backend."""


def _timestamp(doc: dict[str, Any]) -> datetime:
    stamp = datetime.fromisoformat(
        str(doc["properties"]["last_update_date"]).replace("Z", "+00:00")
    )
    if stamp.tzinfo is None:
        raise ValueError("last_update_date must be timezone aware")
    return stamp.astimezone(UTC)


def _values(parsed: ParsedCalibrationSnapshot) -> npt.NDArray[np.float64]:
    out = np.full((len(parsed.qubits), len(QUANTITIES)), np.nan, dtype=np.float64)
    for pos, qubit in enumerate(parsed.qubits):
        for j, name in enumerate(QUANTITIES):
            value = getattr(qubit, _FIELDS[name])
            if value is not None and math.isfinite(value):
                out[pos, j] = float(value)
    return out


def _check_qubit_shapes(doc: dict[str, Any], source: str) -> None:
    """Raise ``CalibrationParseError`` unless every ``properties.qubits[q]`` is a list of objects.

    The loader and the digest both call ``.get`` on each Nduv entry, so a JSON ``null`` (or any
    non-object) there raises ``AttributeError``, which is not a parse error and would abort the
    run. Checked here, at the script boundary, so ``src/`` stays untouched by this PR.
    """
    properties = doc.get("properties")
    if not isinstance(properties, dict):
        return  # the loader reports a missing or non-dict ``properties`` itself
    qubits = properties.get("qubits")
    if not isinstance(qubits, list):
        return  # likewise for a non-list ``qubits``
    for index, entries in enumerate(qubits):
        if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
            raise CalibrationParseError(
                f"{source}: properties.qubits[{index}] must be a list of objects"
            )


def _record(path: str, doc: dict[str, Any]) -> FileRecord:
    _check_qubit_shapes(doc, path)
    parsed = parse_snapshot(doc, source=path)
    return FileRecord(path, _timestamp(doc), qubit_block_digest(doc), _values(parsed))


def collect(
    docs: Iterable[tuple[str, dict[str, Any]]], *, backend: str, until: datetime
) -> Collected:
    """Filter on backend and time, parse, sort by (time, path), and dedup into states."""
    out = Collected(backend=backend)
    records: list[FileRecord] = []
    for path, doc in docs:
        if not doc or doc.get("backend") != backend:
            out.skipped["other_backend"] += 1
            continue
        try:
            record = _record(path, doc)
        except (CalibrationParseError, KeyError, TypeError, ValueError):
            out.skipped["parse_error"] += 1
            continue
        if record.time > until:
            out.skipped["after_until"] += 1
            continue
        records.append(record)
    records.sort(key=lambda r: (r.time, r.path))
    seen: set[str] = set()
    for record in records:
        if record.digest not in seen:
            seen.add(record.digest)
            out.states.append(record)
    out.files = records
    return out


def normalise_live(live: dict[str, Any], *, backend: str) -> dict[str, Any]:
    """Return ``live`` in the archive envelope, after checking it names ``backend`` only.

    Two input shapes are accepted:

    - the archive envelope ``{backend, timestamp, properties: {backend_name, ...}}``, returned
      as is;
    - the raw ``BackendProperties.to_dict()`` body, with ``backend_name``, ``last_update_date``
      and ``qubits`` at the top level (what ``json.dump(props.to_dict(), default=str)`` writes),
      wrapped as ``{backend, timestamp, properties: live}``. The archive stores exactly that
      body under ``properties``, so the wrapped document digests the way an archived one does.

    Every backend identity present (top-level ``backend``, ``properties.backend_name``, raw
    ``backend_name``) must equal ``backend``; none present is also rejected, since the device
    cannot then be verified. The input is not mutated, and the caller keeps the original bytes
    for the provenance hash and the copied document.
    """
    properties = live.get("properties")
    if isinstance(properties, dict):
        doc = live
        identities = [live.get("backend"), properties.get("backend_name")]
    elif "qubits" in live and "last_update_date" in live:
        doc = {
            "backend": live.get("backend_name"),
            "timestamp": live.get("last_update_date"),
            "properties": live,
        }
        identities = [live.get("backend_name")]
    else:
        raise LiveDocumentError(
            "live properties must be the archive envelope (with 'properties') or a "
            "BackendProperties.to_dict() body (with 'qubits' and 'last_update_date')"
        )
    named = {str(i) for i in identities if i is not None}
    if not named:
        raise LiveDocumentError(f"live properties name no backend; expected {backend!r}")
    if named != {backend}:
        raise LiveDocumentError(
            f"live properties name {sorted(named)}; the archive was filtered on {backend!r}"
        )
    return doc


def _live_record(live: dict[str, Any], at: datetime, backend: str) -> FileRecord:
    doc = normalise_live(live, backend=backend)
    try:
        _check_qubit_shapes(doc, "<live>")
        parsed = parse_snapshot(doc, source="<live>")
        digest = qubit_block_digest(doc)
    except (CalibrationParseError, KeyError, TypeError, ValueError) as exc:
        raise LiveDocumentError(f"live properties do not parse: {exc}") from exc
    return FileRecord("<live>", at, digest, _values(parsed))


def _latest_file(files: Sequence[FileRecord], at: datetime) -> FileRecord | None:
    latest: FileRecord | None = None
    for record in files:
        if record.time <= at:
            latest = record
    return latest


def _log_positive(values: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    finite = values[np.isfinite(values) & (values > 0.0)]
    return np.log(finite)


def predictor_rows(
    collected: Collected,
    *,
    at: datetime,
    live: dict[str, Any] | None,
    window_days: float = WINDOW_DAYS,
    min_states: int = MIN_WINDOW_STATES,
) -> list[PredictorRow]:
    """Reading, level, band and disagreement per qubit and quantity at ``at``."""
    reading_rec = _latest_file(collected.files, at)
    window = [s for s in collected.states if at - timedelta(days=window_days) < s.time <= at]
    all_states = [s for s in collected.states if s.time <= at]
    if live is not None:
        live_rec = _live_record(live, at, collected.backend)
        reading_rec = live_rec
        # A state is its first occurrence (``collect``). A live document whose qubit block was
        # already seen at any time up to ``at`` adds no state: it overrides the reading, and the
        # original state's time alone decides window membership.
        if live_rec.digest not in {s.digest for s in all_states}:
            window.append(live_rec)
            all_states.append(live_rec)
    n_qubits = max((r.values.shape[0] for r in collected.files), default=0)
    if live is not None and reading_rec is not None:
        n_qubits = max(n_qubits, reading_rec.values.shape[0])
    rows: list[PredictorRow] = []
    for q in range(n_qubits):
        for j, quantity in enumerate(QUANTITIES):
            reading = math.nan
            reading_time = ""
            if reading_rec is not None and q < reading_rec.values.shape[0]:
                reading = float(reading_rec.values[q, j])
                reading_time = reading_rec.time.isoformat()
            window_vals = np.array([s.values[q, j] for s in window if q < s.values.shape[0]])
            logs = _log_positive(window_vals) if window_vals.size else np.array([])
            n_window = int(logs.size)
            n_window_distinct = len(
                {float(v) for v in window_vals if math.isfinite(float(v)) and v > 0.0}
            )
            level = band_lo = band_hi = math.nan
            if n_window >= min_states:
                level = float(math.exp(float(np.mean(logs))))
                lo, hi = np.quantile(logs, BAND_QUANTILES)
                band_lo, band_hi = float(math.exp(lo)), float(math.exp(hi))
            distinct = {
                float(s.values[q, j])
                for s in all_states
                if q < s.values.shape[0] and math.isfinite(float(s.values[q, j]))
            }
            disagreement = math.nan
            if math.isfinite(reading) and reading > 0.0 and math.isfinite(level):
                disagreement = math.log(reading) - math.log(level)
            rows.append(
                PredictorRow(
                    q,
                    quantity,
                    reading,
                    level,
                    band_lo,
                    band_hi,
                    n_window,
                    len(distinct),
                    disagreement,
                    reading_time,
                    n_window_distinct,
                )
            )
    return rows


def execution_rows(
    collected: Collected, *, at: datetime, live: dict[str, Any] | None
) -> list[PredictorRow]:
    """The ``reading_at_execution`` control: readings only, window and level left empty."""
    reading_rec = (
        _live_record(live, at, collected.backend)
        if live is not None
        else _latest_file(collected.files, at)
    )
    rows: list[PredictorRow] = []
    if reading_rec is None:
        return rows
    for q in range(reading_rec.values.shape[0]):
        for j, quantity in enumerate(QUANTITIES):
            rows.append(
                PredictorRow(
                    q,
                    quantity,
                    float(reading_rec.values[q, j]),
                    math.nan,
                    math.nan,
                    math.nan,
                    0,
                    0,
                    math.nan,
                    reading_rec.time.isoformat(),
                )
            )
    return rows


def select_discriminating(
    rows: Sequence[PredictorRow], *, k: int, min_distinct: int = MIN_DISTINCT_VALUES
) -> list[dict[str, Any]]:
    """The ``k`` qubits whose ``T1`` reading and level disagree most, above the distinct floor."""
    candidates = [
        r
        for r in rows
        if r.quantity == "T1" and math.isfinite(r.log_disagreement) and r.n_distinct >= min_distinct
    ]
    candidates.sort(key=lambda r: -abs(r.log_disagreement))
    return [
        {
            "qubit": r.qubit,
            "log_disagreement": r.log_disagreement,
            "abs_log_disagreement": abs(r.log_disagreement),
            "n_distinct": r.n_distinct,
            "n_window": r.n_window,
        }
        for r in candidates[:k]
    ]


def propose_controls(
    collected: Collected,
    *,
    k: int,
    exclude: set[int],
    min_distinct: int = MIN_DISTINCT_VALUES,
) -> list[dict[str, Any]]:
    """The ``k`` qubits whose whole-archive scatter of ``log T1`` is nearest the median."""
    j = QUANTITIES.index("T1")
    n_qubits = max((s.values.shape[0] for s in collected.states), default=0)
    scatter: dict[int, tuple[float, int]] = {}
    for q in range(n_qubits):
        vals = np.array([s.values[q, j] for s in collected.states if q < s.values.shape[0]])
        logs = _log_positive(vals) if vals.size else np.array([])
        distinct = len({float(v) for v in vals if math.isfinite(float(v))})
        if q in exclude or distinct < min_distinct or logs.size < 2:
            continue
        scatter[q] = (float(np.std(logs, ddof=1)), distinct)
    if not scatter:
        return []
    median = float(np.median([s for s, _ in scatter.values()]))
    ranked = sorted(scatter.items(), key=lambda item: (abs(item[1][0] - median), item[0]))
    return [
        {"qubit": q, "log_t1_scatter": s, "median_scatter": median, "n_distinct": d}
        for q, (s, d) in ranked[:k]
    ]


def _below_window_floor(rows: Sequence[PredictorRow], min_window_distinct: int) -> list[int]:
    """Qubits whose in-window distinct ``T1`` count is below the floor (no ``T1`` row: below)."""
    t1 = {r.qubit: r for r in rows if r.quantity == "T1"}
    n_qubits = max((r.qubit + 1 for r in rows), default=0)
    return [
        q for q in range(n_qubits) if q not in t1 or t1[q].n_window_distinct < min_window_distinct
    ]


def freeze_controls(
    collected: Collected,
    rows: Sequence[PredictorRow],
    *,
    k: int,
    min_window_distinct: int = MIN_WINDOW_DISTINCT,
) -> dict[str, Any]:
    """Proposal D: the ``k`` controls, chosen before any discriminating selection.

    The only exclusion is the discriminating stratum's window floor; ``propose_controls`` keeps
    its own whole-archive floor underneath. No reading enters: ``rows`` supply only the window
    counts, so the caller passes rows built without a live document.
    """
    below = _below_window_floor(rows, min_window_distinct)
    return {
        "below_window_floor": below,
        "controls": propose_controls(collected, k=k, exclude=set(below)),
    }


def select_balanced(
    rows: Sequence[PredictorRow],
    *,
    k: int,
    controls: set[int],
    min_window_distinct: int = MIN_WINDOW_DISTINCT,
) -> dict[str, Any]:
    """Proposals A and B: ``k/2`` qubits below their level and ``k/2`` above, by ``|d|``.

    Candidates are ``T1`` rows with a finite disagreement ``d``, at least
    ``min_window_distinct`` distinct values inside the window, and a qubit outside ``controls``.
    Each side is ranked by ``|d|`` descending, ties by qubit index. A side with fewer than
    ``k/2`` candidates leaves its places to the other side's next-largest ``|d|``; ``d == 0``
    belongs to neither side and is never selected. Fewer than ``k`` qubits come out when fewer
    are admitted. The returned log names every such event.
    """
    if k <= 0 or k % 2:
        raise ValueError(f"k must be a positive even number, got {k}")
    half = k // 2
    candidates = [
        r
        for r in rows
        if r.quantity == "T1"
        and math.isfinite(r.log_disagreement)
        and r.n_window_distinct >= min_window_distinct
        and r.qubit not in controls
    ]

    def ranked(side: list[PredictorRow]) -> list[PredictorRow]:
        return sorted(side, key=lambda r: (-abs(r.log_disagreement), r.qubit))

    below = ranked([r for r in candidates if r.log_disagreement < 0.0])
    above = ranked([r for r in candidates if r.log_disagreement > 0.0])
    zero = sorted(r.qubit for r in candidates if r.log_disagreement == 0.0)
    take_below, take_above = below[:half], above[:half]
    short_side: str | None = None
    filled_from: str | None = None
    n_filled = 0
    if len(take_below) < half and len(take_above) == half:
        short_side, filled_from = "below", "above"
        extra = above[half : half + half - len(take_below)]
        n_filled = len(extra)
        take_above = take_above + extra
    elif len(take_above) < half and len(take_below) == half:
        short_side, filled_from = "above", "below"
        extra = below[half : half + half - len(take_above)]
        n_filled = len(extra)
        take_below = take_below + extra
    elif len(take_below) < half and len(take_above) < half:
        short_side = "both"

    def entry(r: PredictorRow, side: str, filled: bool) -> dict[str, Any]:
        return {
            "qubit": r.qubit,
            "side": side,
            "filled": filled,
            "log_disagreement": r.log_disagreement,
            "abs_log_disagreement": abs(r.log_disagreement),
            "n_window_distinct": r.n_window_distinct,
            "n_distinct": r.n_distinct,
            "n_window": r.n_window,
        }

    picked = [entry(r, "below", i >= half) for i, r in enumerate(take_below)]
    picked += [entry(r, "above", i >= half) for i, r in enumerate(take_above)]
    return {
        "discriminating": picked,
        "n_selected": len(picked),
        "admitted": {"below": len(below), "above": len(above), "zero": len(zero)},
        "zero_disagreement": zero,
        "below_window_floor": _below_window_floor(rows, min_window_distinct),
        "excluded_controls": sorted(controls),
        "short_side": short_side,
        "filled_from": filled_from,
        "n_filled": n_filled,
    }


def load_controls(path: Path, *, backend: str) -> tuple[dict[str, Any], str]:
    """Read a ``controls.json`` written by ``--mode controls``; return it and its SHA-256."""
    try:
        raw = path.read_bytes()
        loaded = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise ControlsFileError(f"cannot read controls file {path}: {exc}") from exc
    if not isinstance(loaded, dict) or not isinstance(loaded.get("controls"), list):
        raise ControlsFileError("controls file must be an object with a 'controls' list")
    if loaded.get("backend") != backend:
        raise ControlsFileError(
            f"controls file names backend {loaded.get('backend')!r}; expected {backend!r}"
        )
    qubits = [c.get("qubit") if isinstance(c, dict) else None for c in loaded["controls"]]
    if not qubits or not all(isinstance(q, int) and not isinstance(q, bool) for q in qubits):
        raise ControlsFileError("every control must be an object with an integer 'qubit'")
    return loaded, hashlib.sha256(raw).hexdigest()


def write_outputs(
    out: Path,
    *,
    rows: Sequence[PredictorRow],
    selection: dict[str, Any] | None,
    manifest: dict[str, Any],
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "predictors.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(TSV_COLUMNS), delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    if selection is not None:
        (out / "selection.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _parse_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise argparse.ArgumentTypeError("--at must carry a time zone")
    return stamp.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--ref", required=True, help="pinned calibration-data commit")
    parser.add_argument("--backend", default="ibm_fez")
    parser.add_argument(
        "--at",
        type=_parse_at,
        default=None,
        help="submission (or execution) time, ISO 8601 with zone",
    )
    parser.add_argument(
        "--mode", choices=("submission", "execution", "controls"), default="submission"
    )
    parser.add_argument("--live-properties", type=Path, default=None)
    parser.add_argument("--window-days", type=float, default=WINDOW_DAYS)
    parser.add_argument("--select-discriminating", type=int, default=8)
    parser.add_argument("--propose-controls", type=int, default=4, help="controls mode: how many")
    parser.add_argument(
        "--controls", type=Path, default=None, help="submission: controls.json from controls mode"
    )
    parser.add_argument(
        "--no-frozen-controls",
        action="store_true",
        help="submission without frozen controls; archive dry runs only, recorded as null",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    at: datetime = args.at if args.at is not None else _parse_at(None)

    if args.mode == "controls" and args.live_properties is not None:
        print("error: controls are frozen from the archive; no --live-properties", file=sys.stderr)
        return 2
    if args.mode == "submission":
        if args.select_discriminating <= 0 or args.select_discriminating % 2:
            print("error: --select-discriminating must be a positive even number", file=sys.stderr)
            return 2
        if args.controls is not None and args.no_frozen_controls:
            print("error: --controls and --no-frozen-controls exclude each other", file=sys.stderr)
            return 2
        if args.controls is None and not args.no_frozen_controls:
            print(
                "error: submission needs the frozen controls (--controls controls.json from "
                "--mode controls); --no-frozen-controls is for archive dry runs only",
                file=sys.stderr,
            )
            return 2
    controls_doc: dict[str, Any] | None = None
    controls_sha: str | None = None
    if args.mode == "submission" and args.controls is not None:
        try:
            controls_doc, controls_sha = load_controls(args.controls, backend=args.backend)
        except ControlsFileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    try:
        sha = resolve_archive_ref(args.repo, args.ref)
    except ArchiveRefError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    live: dict[str, Any] | None = None
    live_sha: str | None = None
    if args.live_properties is not None:
        raw = args.live_properties.read_bytes()
        live_sha = hashlib.sha256(raw).hexdigest()
        loaded = json.loads(raw)
        live = loaded if isinstance(loaded, dict) else None
        if live is None:
            print("error: --live-properties must hold one JSON object", file=sys.stderr)
            return 2

    collected = collect(iter_archive(args.repo, sha), backend=args.backend, until=at)
    selection: dict[str, Any] | None = None
    frozen: dict[str, Any] | None = None
    control_qubits: list[int] | None = None
    try:
        if args.mode == "submission":
            rows = predictor_rows(collected, at=at, live=live, window_days=args.window_days)
            if controls_doc is not None:
                control_qubits = [int(c["qubit"]) for c in controls_doc["controls"]]
            selection = select_balanced(
                rows, k=args.select_discriminating, controls=set(control_qubits or [])
            )
            selection["controls"] = control_qubits
            if selection["short_side"] is not None:
                print(
                    f"note: short side {selection['short_side']}, {selection['n_filled']} "
                    f"place(s) filled from {selection['filled_from']}, "
                    f"{selection['n_selected']} selected",
                    file=sys.stderr,
                )
        elif args.mode == "controls":
            rows = predictor_rows(collected, at=at, live=None, window_days=args.window_days)
            frozen = freeze_controls(collected, rows, k=args.propose_controls)
        else:
            rows = execution_rows(collected, at=at, live=live)
    except LiveDocumentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    manifest: dict[str, Any] = {
        "mode": args.mode,
        "ref": args.ref,
        "ref_sha": sha,
        "backend": args.backend,
        "at": at.isoformat(),
        "window_days": args.window_days,
        "min_window_states": MIN_WINDOW_STATES,
        "min_distinct_values": MIN_DISTINCT_VALUES,
        "min_window_distinct": MIN_WINDOW_DISTINCT,
        "files_used": len(collected.files),
        "states_used": len(collected.states),
        "skipped": dict(collected.skipped),
        "live_properties_sha256": live_sha,
        "python": sys.version.split()[0],
        "numpy": np.__version__,
    }
    if args.mode == "submission":
        manifest["controls"] = control_qubits
        manifest["controls_file_sha256"] = controls_sha
        manifest["controls_ref_sha"] = (controls_doc or {}).get("ref_sha")
        manifest["controls_at"] = (controls_doc or {}).get("at")
    write_outputs(args.out, rows=rows, selection=selection, manifest=manifest)
    if frozen is not None:
        controls_out = {
            "backend": args.backend,
            "ref": args.ref,
            "ref_sha": sha,
            "at": at.isoformat(),
            "min_window_distinct": MIN_WINDOW_DISTINCT,
            "min_distinct_values": MIN_DISTINCT_VALUES,
            **frozen,
        }
        (args.out / "controls.json").write_text(
            json.dumps(controls_out, indent=2), encoding="utf-8"
        )
    if args.live_properties is not None:
        shutil.copyfile(
            args.live_properties, args.out / f"live-properties-{at:%Y%m%dT%H%M%SZ}.json"
        )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
