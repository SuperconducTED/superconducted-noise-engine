"""IBM Quantum calibration polling — Phase 0 deliverable.

Cron-friendly: one invocation = one polling round. Idempotent: existing
snapshot files on disk are skipped (race-safe via ``O_CREAT|O_EXCL`` in
:mod:`storage`). Handles ``NotImplementedError`` (historical access tier
denied), ``properties()`` returning ``None``, and transient ``RuntimeError``
with exponential-backoff retries.

Logs to a rotating file (default: ``data/logs/poller.log``). The CLI
``superconducted-poll`` is bound in ``pyproject.toml``.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import logging.handlers
import os
import sys
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..types import CalibrationSnapshot
from .storage import CalibrationStorage

SCHEMA_VERSION: str = "1.0.0"
LOG_NAME: str = "superconducted.calibration"
DEFAULT_CHANNEL: str = "ibm_quantum_platform"


def configure_logging(log_dir: Path) -> logging.Logger:
    """Configure a rotating-file + stderr logger named ``superconducted.calibration``.

    Creates ``log_dir`` if missing. The rotating file caps at 5 MB with 5
    backups so the cron host doesn't fill its disk over months of polling.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOG_NAME)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        rotating = logging.handlers.RotatingFileHandler(
            log_dir / "poller.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        rotating.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(rotating)
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(stream)
    return logger


def serialize_target(target: Any) -> dict[str, Any] | None:
    """JSON-safe reduced projection of a Qiskit transpiler ``Target`` object.

    Captures operation names, qargs, durations, errors, and physical qubit
    list. Does NOT call ``Target.to_dict()`` — that method is not stable
    across Qiskit versions per the Codex review.
    """
    if target is None:
        return None
    out: dict[str, Any] = {
        "num_qubits": getattr(target, "num_qubits", None),
        "physical_qubits": list(getattr(target, "physical_qubits", []) or []),
        "operations": [],
    }
    op_names = getattr(target, "operation_names", None) or []
    for name in op_names:
        try:
            qargs_iter = list(target.qargs_for_operation_name(name) or [])
        except Exception:
            qargs_iter = []
        for qargs in qargs_iter:
            qargs_tuple = tuple(qargs) if qargs is not None else ()
            entry: dict[str, Any] = {"name": name, "qargs": list(qargs_tuple)}
            instr_props: Any = None
            try:
                instr_props = target[name, qargs_tuple]
            except Exception:
                instr_props = None
            if instr_props is not None:
                duration = getattr(instr_props, "duration", None)
                error = getattr(instr_props, "error", None)
                if duration is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        entry["duration"] = float(duration)
                if error is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        entry["error"] = float(error)
            out["operations"].append(entry)
    return out


def serialize_configuration(config: Any) -> dict[str, Any] | None:
    """JSON-safe projection of a ``BackendConfiguration`` object."""
    if config is None:
        return None
    to_dict = getattr(config, "to_dict", None)
    if callable(to_dict):
        try:
            return dict(to_dict())
        except Exception:
            pass
    fallback: dict[str, Any] = {}
    for attr in (
        "backend_name",
        "backend_version",
        "n_qubits",
        "basis_gates",
        "coupling_map",
        "max_shots",
        "max_experiments",
    ):
        if hasattr(config, attr):
            try:
                fallback[attr] = getattr(config, attr)
            except Exception:
                continue
    return fallback


def _coerce_utc(ts: Any) -> datetime | None:
    """Coerce an arbitrary timestamp (datetime, ISO str) to tz-aware UTC."""
    if ts is None:
        return None
    if isinstance(ts, str):
        s = ts.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            ts = datetime.fromisoformat(s)
        except ValueError:
            return None
    if not isinstance(ts, datetime):
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _fetch_properties_with_retry(
    backend: Any,
    historical_at: datetime | None,
    retries: int,
    logger: logging.Logger,
) -> Any:
    """Call ``backend.properties()`` (optionally with ``datetime=...``) with
    exponential-backoff retries on :class:`RuntimeError`.

    :class:`NotImplementedError` is propagated immediately (historical
    access tier denied) — retry would not help.
    """
    last_exc: RuntimeError | None = None
    for attempt in range(retries + 1):
        try:
            if historical_at is not None:
                return backend.properties(datetime=historical_at)
            return backend.properties()
        except NotImplementedError:
            raise
        except RuntimeError as exc:
            last_exc = exc
            if attempt < retries:
                wait = 2.0**attempt
                logger.warning(
                    "properties() attempt %d/%d failed: %s; retrying in %.1fs",
                    attempt + 1,
                    retries + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def fetch_snapshot(
    service: Any,
    backend_name: str,
    *,
    historical_at: datetime | None = None,
    retries: int = 3,
    logger: logging.Logger | None = None,
) -> CalibrationSnapshot | None:
    """Fetch a single :class:`CalibrationSnapshot` from the IBM runtime service.

    Returns ``None`` (logged) when:

    - ``backend.properties()`` returns ``None``.
    - Historical query raises :class:`NotImplementedError`.

    Raises the underlying :class:`RuntimeError` if ``retries`` are exhausted.

    For *current* snapshots, the function also captures ``backend.target``
    and ``backend.configuration()``. For *historical* snapshots, target
    capture goes through ``backend.target_history(datetime=...)`` if the
    SDK exposes it; otherwise ``target`` and ``configuration`` are stored
    as ``None`` to avoid pairing current target with historical properties.
    """
    log = logger or logging.getLogger(LOG_NAME)
    backend = service.backend(backend_name)

    try:
        properties = _fetch_properties_with_retry(backend, historical_at, retries, log)
    except NotImplementedError as exc:
        log.warning(
            "Historical properties not available for %s at %s: %s",
            backend_name,
            historical_at.isoformat() if historical_at else "current",
            exc,
        )
        return None

    if properties is None:
        log.warning(
            "backend.properties() returned None for %s (%s)",
            backend_name,
            historical_at.isoformat() if historical_at else "current",
        )
        return None

    properties_dict = properties.to_dict()
    timestamp = _coerce_utc(getattr(properties, "last_update_date", None))
    if timestamp is None:
        timestamp = _coerce_utc(properties_dict.get("last_update_date"))
    if timestamp is None:
        log.error(
            "Could not determine timestamp for %s snapshot (no last_update_date)",
            backend_name,
        )
        return None

    target_dict: dict[str, Any] | None = None
    config_dict: dict[str, Any] | None = None
    if historical_at is None:
        try:
            target_obj = getattr(backend, "target", None)
            target_dict = serialize_target(target_obj)
        except Exception as exc:
            log.warning("Failed to serialize current target for %s: %s", backend_name, exc)
        configuration_method = getattr(backend, "configuration", None)
        if callable(configuration_method):
            try:
                config_dict = serialize_configuration(configuration_method())
            except Exception as exc:
                log.warning("Failed to serialize configuration for %s: %s", backend_name, exc)
    else:
        target_history = getattr(backend, "target_history", None)
        if callable(target_history):
            try:
                target_obj = target_history(datetime=historical_at)
                target_dict = serialize_target(target_obj)
            except (NotImplementedError, AttributeError) as exc:
                log.debug("target_history unavailable for %s: %s", backend_name, exc)
            except Exception as exc:
                log.warning("target_history call failed for %s: %s", backend_name, exc)

    return CalibrationSnapshot(
        backend=backend_name,
        timestamp=timestamp,
        schema_version=SCHEMA_VERSION,
        properties=properties_dict,
        target=target_dict,
        configuration=config_dict,
    )


def _default_service_factory(
    *,
    token: str | None,
    instance: str | None,
    channel: str | None,
) -> Any:
    """Build a :class:`QiskitRuntimeService`, lazy-imported so unit tests
    that monkeypatch this function don't need ``qiskit-ibm-runtime`` installed.
    """
    from qiskit_ibm_runtime import QiskitRuntimeService

    kwargs: dict[str, Any] = {
        "channel": channel or os.environ.get("IBM_QUANTUM_CHANNEL", DEFAULT_CHANNEL),
    }
    effective_token = token or os.environ.get("IBM_QUANTUM_TOKEN")
    if effective_token:
        kwargs["token"] = effective_token
    effective_instance = instance or os.environ.get("IBM_QUANTUM_INSTANCE")
    if effective_instance:
        kwargs["instance"] = effective_instance
    return QiskitRuntimeService(**kwargs)


def poll_once(
    backends: list[str],
    storage: CalibrationStorage,
    *,
    historical_window: list[datetime] | None = None,
    service_factory: Callable[[], Any] | None = None,
    token: str | None = None,
    instance: str | None = None,
    channel: str | None = None,
    max_historical_days: int = 30,
    retries: int = 3,
    logger: logging.Logger | None = None,
) -> None:
    """Run one polling round across ``backends``.

    For each backend, fetches the current snapshot. If ``historical_window``
    is given, additionally queries each datetime; entries older than
    ``max_historical_days`` are rejected up-front to avoid hammering the
    IBM API for inaccessible windows.

    ``service_factory`` is the test seam: pass a callable that returns a
    mock service to bypass real IBM auth. Default constructs
    :class:`QiskitRuntimeService` from env vars and CLI args.
    """
    log = logger or logging.getLogger(LOG_NAME)

    if historical_window:
        max_age = timedelta(days=max_historical_days)
        now = datetime.now(UTC)
        for ts in historical_window:
            if ts.tzinfo is None:
                raise ValueError(f"historical_window entries must be tz-aware; got naive {ts!r}")
            ts_utc = ts.astimezone(UTC)
            if (now - ts_utc) > max_age:
                raise ValueError(
                    f"historical timestamp {ts_utc.isoformat()} exceeds "
                    f"max_historical_days={max_historical_days} (now={now.isoformat()})"
                )

    if service_factory is None:

        def _factory() -> Any:
            return _default_service_factory(token=token, instance=instance, channel=channel)

        service = _factory()
    else:
        service = service_factory()

    for backend_name in backends:
        snapshot = fetch_snapshot(service, backend_name, retries=retries, logger=log)
        if snapshot is not None:
            saved = storage.save_if_new(snapshot)
            log.info(
                "current %s @ %s: %s",
                backend_name,
                snapshot.timestamp.isoformat(),
                "saved" if saved else "skipped (already archived)",
            )

        if historical_window:
            for ts in historical_window:
                h_snapshot = fetch_snapshot(
                    service,
                    backend_name,
                    historical_at=ts,
                    retries=retries,
                    logger=log,
                )
                if h_snapshot is None:
                    continue
                saved = storage.save_if_new(h_snapshot)
                log.info(
                    "historical %s @ %s (requested %s): %s",
                    backend_name,
                    h_snapshot.timestamp.isoformat(),
                    ts.isoformat(),
                    "saved" if saved else "skipped (already archived)",
                )


def _parse_iso_utc(s: str) -> datetime:
    """Parse an ISO-8601 string and return tz-aware UTC; naive → assumed UTC."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _build_historical_window(start_str: str, end_str: str, step_hours_str: str) -> list[datetime]:
    start = _parse_iso_utc(start_str)
    end = _parse_iso_utc(end_str)
    step_hours = int(step_hours_str)
    if step_hours <= 0:
        raise ValueError(f"step_hours must be positive; got {step_hours}")
    if start >= end:
        raise ValueError(f"start ({start}) must be before end ({end})")
    step = timedelta(hours=step_hours)
    out: list[datetime] = []
    t = start
    while t < end:
        out.append(t)
        t += step
    return out


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="superconducted-poll",
        description="Archive IBM Quantum backend calibration snapshots.",
    )
    parser.add_argument(
        "--backend",
        action="append",
        required=True,
        metavar="NAME",
        help="Backend name (repeatable). Example: --backend ibm_brisbane",
    )
    parser.add_argument(
        "--historical",
        nargs=3,
        metavar=("START_ISO", "END_ISO", "STEP_HOURS"),
        default=None,
        help="Optional historical sweep, e.g. --historical 2026-04-01T00:00:00Z "
        "2026-05-01T00:00:00Z 24",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Override SUPERCONDUCTED_DATA_DIR (default ./data/calibration).",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="Override SUPERCONDUCTED_LOG_DIR (default ./data/logs).",
    )
    parser.add_argument(
        "--channel",
        default=None,
        help="Override IBM_QUANTUM_CHANNEL (default ibm_quantum_platform).",
    )
    parser.add_argument(
        "--max-historical-days",
        type=int,
        default=None,
        help="Override SUPERCONDUCTED_HISTORICAL_MAX_DAYS (default 30).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=None,
        help="Override SUPERCONDUCTED_HTTP_RETRIES (default 3).",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    """Console-script entry point for ``superconducted-poll``.

    Returns 0 on a clean run (including soft-skipped snapshots) and 1 on
    any unhandled exception (logged with full traceback). Loads ``.env``
    via :func:`dotenv.load_dotenv` before reading environment variables so
    a freshly cloned repo with a populated ``.env`` Just Works.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    data_dir = Path(args.data_dir or os.environ.get("SUPERCONDUCTED_DATA_DIR", "data/calibration"))
    log_dir = Path(args.log_dir or os.environ.get("SUPERCONDUCTED_LOG_DIR", "data/logs"))
    max_historical_days = (
        args.max_historical_days
        if args.max_historical_days is not None
        else int(os.environ.get("SUPERCONDUCTED_HISTORICAL_MAX_DAYS", "30"))
    )
    retries = (
        args.retries
        if args.retries is not None
        else int(os.environ.get("SUPERCONDUCTED_HTTP_RETRIES", "3"))
    )

    logger = configure_logging(log_dir)
    storage = CalibrationStorage(data_dir)

    historical_window: list[datetime] | None = None
    if args.historical:
        try:
            historical_window = _build_historical_window(*args.historical)
        except ValueError as exc:
            logger.error("Invalid --historical argument: %s", exc)
            return 1

    try:
        poll_once(
            backends=list(args.backend),
            storage=storage,
            historical_window=historical_window,
            channel=args.channel,
            max_historical_days=max_historical_days,
            retries=retries,
            logger=logger,
        )
    except Exception as exc:
        logger.exception("Polling failed: %s", exc)
        return 1
    return 0
