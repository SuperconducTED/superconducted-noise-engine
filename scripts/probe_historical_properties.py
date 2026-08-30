"""Probe whether this IBM account can read *historical* calibration properties.

Answers one question definitively: does ``backend.properties(datetime=...)``
return an older document, or does the service ignore the request and hand back
the current one?

Why a probe is needed at all
----------------------------
``poller.fetch_snapshot`` catches :class:`NotImplementedError` and logs
"historical access tier denied". In ``qiskit-ibm-runtime==0.46.1`` that
exception is never raised. The call path

    IBMBackend.properties      (ibm_backend.py)
      -> RuntimeClient.backend_properties   (api/clients/runtime.py)
        -> CloudBackend.properties          (api/rest/cloud_backend.py)

turns ``datetime`` into an ``updated_before`` query parameter and sends it;
only the *docstrings* mention ``NotImplementedError``. So the denial the
poller anticipates cannot be observed as an exception.

That matters because the silent-failure mode is indistinguishable from
success at a glance: if the service ignores ``updated_before`` it returns the
*current* document, the poller stores it under a timestamp it already has, and
a backfill sweep logs "skipped (already archived)" at every step — doing
nothing while reporting green.

The only sound test therefore compares ``last_update_date`` values:

    ==================================  ==========================================
    observation                         conclusion
    ==================================  ==========================================
    ``T_hist <  T_now``                 historical access works; backfill feasible
    ``T_hist == T_now``                 parameter ignored; backfill impossible
    ``NotImplementedError`` / ``None``  denied outright
    ==================================  ==========================================

Contract: makes exactly two read-only API calls, writes nothing, and prints no
credentials. Exit code 0 = historical access works, 2 = definitively
unavailable (a successful probe with a negative answer), 1 = the probe itself
failed and the question remains open.

Run in CI via ``.github/workflows/calibration-historical-probe.yml``, which is
where ``IBM_QUANTUM_TOKEN`` already lives. See #45 Phase 2.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

# Reused rather than reimplemented so the probe coerces timestamps exactly the
# way the poller does; a divergence here would make the comparison meaningless.
from superconducted.calibration.poller import DEFAULT_CHANNEL, _coerce_utc, _parse_iso_utc


def _last_update_date(properties: Any) -> datetime | None:
    """Extract ``last_update_date`` as tz-aware UTC, attribute first then dict."""
    stamp = _coerce_utc(getattr(properties, "last_update_date", None))
    if stamp is not None:
        return stamp
    to_dict = getattr(properties, "to_dict", None)
    if callable(to_dict):
        return _coerce_utc(to_dict().get("last_update_date"))
    return None


def _probe_one(backend: object, t_now: datetime, days: float) -> tuple[str, datetime | None]:
    """Query one depth. Returns (verdict, returned stamp or None)."""
    requested = t_now - timedelta(days=days)
    try:
        historical = backend.properties(datetime=requested)  # type: ignore[attr-defined]
    except NotImplementedError as exc:
        return f"DENIED — NotImplementedError: {exc}", None
    except Exception as exc:  # any failure is itself a probe result
        return f"ERROR — {type(exc).__name__}: {exc}", None
    if historical is None:
        return "UNAVAILABLE — returned None", None
    stamp = _last_update_date(historical)
    if stamp is None:
        return "MALFORMED — no last_update_date", None
    if stamp >= t_now:
        return "IGNORED — returned the current document", stamp
    return "OK", stamp


def _enumerate_window(backend: object, start_iso: str, end_iso: str, step_hours_s: str) -> int:
    """Walk a window and report every distinct document the service will serve.

    Because ``properties(datetime=T)`` returns the newest document *older than*
    ``T``, stepping finer than the publish cadence enumerates the window: each
    published document is the answer for at least one step. Distinct
    ``last_update_date`` values are therefore the ground truth of what IBM
    retains, and differencing them against the archived filenames says exactly
    what a polling gap cost — no estimation from a median.
    """
    start = _parse_iso_utc(start_iso)
    end = _parse_iso_utc(end_iso)
    step = timedelta(hours=float(step_hours_s))
    if step <= timedelta(0):
        print("PROBE FAILED: step must be positive")
        return 1
    if start >= end:
        print("PROBE FAILED: start must be before end")
        return 1

    seen: dict[datetime, int] = {}
    queries = 0
    t = start
    while t <= end:
        queries += 1
        try:
            doc = backend.properties(datetime=t)  # type: ignore[attr-defined]
        except Exception as exc:  # any failure is itself a probe result
            print(f"PROBE FAILED at {t.isoformat()}: {type(exc).__name__}: {exc}")
            return 1
        stamp = _last_update_date(doc) if doc is not None else None
        if stamp is not None:
            seen[stamp] = seen.get(stamp, 0) + 1
        t += step

    in_window = sorted(s for s in seen if start <= s <= end)
    print(f"window   : {start.isoformat()} .. {end.isoformat()}")
    print(f"step     : {step_hours_s}h   queries: {queries}")
    print(f"distinct documents returned : {len(seen)}  ({len(in_window)} inside the window)")
    print("\nlast_update_date values IBM will serve for this window:")
    for s in in_window:
        print(f"  {s.strftime('%Y%m%dT%H%M%S%f')}Z   {s.isoformat()}")
    print(
        "\nDiff these stamps against the archived filenames on calibration-data; "
        "any listed here and absent there is a document the poller missed and can "
        "still recover."
    )
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="probe-historical-properties",
        description="Determine whether historical calibration properties are readable.",
    )
    parser.add_argument("--backend", default="ibm_fez", help="Backend name (default ibm_fez).")
    parser.add_argument(
        "--days-back",
        type=float,
        nargs="+",
        default=[7.0],
        metavar="DAYS",
        help="Depths to probe, in days. Several values map the retention window, "
        "which is what decides how far a backfill sweep can reach.",
    )
    parser.add_argument(
        "--enumerate",
        nargs=3,
        metavar=("START_ISO", "END_ISO", "STEP_HOURS"),
        default=None,
        help="Instead of probing depths, walk a window and list every distinct "
        "last_update_date the service returns. Read-only: this is how you find out "
        "exactly which documents a polling gap missed, before deciding to backfill.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    from qiskit_ibm_runtime import QiskitRuntimeService

    kwargs: dict[str, Any] = {
        "channel": os.environ.get("IBM_QUANTUM_CHANNEL", DEFAULT_CHANNEL),
    }
    if os.environ.get("IBM_QUANTUM_TOKEN"):
        kwargs["token"] = os.environ["IBM_QUANTUM_TOKEN"]
    if os.environ.get("IBM_QUANTUM_INSTANCE"):
        kwargs["instance"] = os.environ["IBM_QUANTUM_INSTANCE"]

    print(f"channel : {kwargs['channel']}")
    print(f"backend : {args.backend}")

    backend = QiskitRuntimeService(**kwargs).backend(args.backend)

    if args.enumerate:
        return _enumerate_window(backend, *args.enumerate)

    current = backend.properties()
    if current is None:
        print("PROBE FAILED: backend.properties() returned None")
        return 1
    t_now = _last_update_date(current)
    if t_now is None:
        print("PROBE FAILED: current properties carry no last_update_date")
        return 1
    print(f"current last_update_date : {t_now.isoformat()}\n")

    header = f"{'depth':>8}  {'requested':<25}  {'returned':<25}  verdict"
    print(header)
    print("-" * len(header))

    any_ok = False
    for days in sorted(args.days_back):
        requested = t_now - timedelta(days=days)
        verdict, stamp = _probe_one(backend, t_now, days)
        if verdict == "OK":
            any_ok = True
            lag = requested - stamp if stamp else None
            verdict = f"OK (document is {lag} older than the request)"
        print(
            f"{days:>7.1f}d  {requested.isoformat():<25}  "
            f"{(stamp.isoformat() if stamp else '-'):<25}  {verdict}"
        )

    if any_ok:
        print("\nRESULT: HISTORICAL ACCESS WORKS — backfill is feasible at the depths marked OK.")
        return 0
    print("\nRESULT: NO HISTORICAL ACCESS at any probed depth — the gaps are unrecoverable.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
