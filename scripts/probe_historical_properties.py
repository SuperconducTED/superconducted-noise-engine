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
import time
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any, Protocol

# Reused rather than reimplemented so the probe coerces timestamps exactly the
# way the poller does; a divergence here would make the comparison meaningless.
from superconducted.calibration.poller import DEFAULT_CHANNEL, coerce_utc, parse_iso_utc


class _PropertiesBackend(Protocol):
    """The one backend method this probe uses, as a structural type.

    Typed here rather than as ``object`` so the module can be checked under
    ``mypy --strict`` without a blanket ``type: ignore`` on every call.
    """

    def properties(self, *, datetime: datetime | None = None) -> Any: ...


# Reads the same knob as the poller, so raising it when transients persist
# actually affects the sweep -- the one path (~720 calls) that needs it most.
_RETRIES = int(os.environ.get("SUPERCONDUCTED_HTTP_RETRIES", "3"))


def _last_update_date(properties: Any) -> datetime | None:
    """Extract ``last_update_date`` as tz-aware UTC, attribute first then dict."""
    stamp = coerce_utc(getattr(properties, "last_update_date", None))
    if stamp is not None:
        return stamp
    to_dict = getattr(properties, "to_dict", None)
    if callable(to_dict):
        return coerce_utc(to_dict().get("last_update_date"))
    return None


def _probe_one(
    backend: _PropertiesBackend, t_now: datetime, days: float
) -> tuple[str, datetime, datetime | None]:
    """Query one depth. Returns (verdict, instant requested, stamp returned).

    The verdict must be judged against the *request*, not against "is it older
    than now". A service that silently clamps to a retention floor — serving a
    30-day-old document for a 60-day request — returns something older than now
    and would otherwise score OK, which is exactly the claim a retention-depth
    measurement is supposed to establish. ``CLAMPED`` separates "served the
    window" from "served something, but not the window asked for".
    """
    requested = t_now - timedelta(days=days)
    try:
        historical = backend.properties(datetime=requested)
    except NotImplementedError as exc:
        return f"DENIED — NotImplementedError: {exc}", requested, None
    except Exception as exc:  # any failure is itself a probe result
        return f"ERROR — {type(exc).__name__}: {exc}", requested, None
    if historical is None:
        return "UNAVAILABLE — returned None", requested, None
    stamp = _last_update_date(historical)
    if stamp is None:
        return "MALFORMED — no last_update_date", requested, None
    if stamp >= t_now:
        return "IGNORED — returned the current document", requested, stamp
    if stamp > requested:
        return "CLAMPED — newer than the request; depth not served", requested, stamp
    return "OK", requested, stamp


def _enumerate_window(
    backend: _PropertiesBackend, start_iso: str, end_iso: str, step_hours_s: str
) -> int:
    """Walk a window and report every distinct document the service will serve.

    Because ``properties(datetime=T)`` returns the newest document *older than*
    ``T``, stepping finer than the publish cadence enumerates the window: each
    published document is the answer for at least one step. Distinct
    ``last_update_date`` values are therefore the ground truth of what IBM
    retains, and differencing them against the archived filenames says exactly
    what a polling gap cost — no estimation from a median.
    """
    start = parse_iso_utc(start_iso)
    end = parse_iso_utc(end_iso)
    step = timedelta(hours=float(step_hours_s))
    if step <= timedelta(0):
        print("PROBE FAILED: step must be positive")
        return 1
    if start >= end:
        print("PROBE FAILED: start must be before end")
        return 1

    seen: dict[datetime, int] = {}
    queries = 0
    failed_at: str | None = None
    t = start
    while t <= end:
        queries += 1
        doc: Any = None
        # A 30-day sweep is ~720 calls; losing all of them to one transient is
        # not acceptable, so retry with the same backoff shape the poller uses.
        for attempt in range(_RETRIES + 1):
            try:
                doc = backend.properties(datetime=t)
                break
            except Exception as exc:  # any failure is itself a probe result
                if attempt == _RETRIES:
                    failed_at = f"{t.isoformat()}: {type(exc).__name__}: {exc}"
                    break
                time.sleep(2.0**attempt)
        if failed_at is not None:
            break
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
    if failed_at is not None:
        # The stamps above are still valid evidence — they are printed before
        # this return precisely so a partial sweep is not wasted.
        print(f"\nPROBE FAILED at {failed_at}")
        print(f"Sweep stopped early at {t.isoformat()}; the window above is INCOMPLETE.")
        return 1
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    """Parse arguments, build the service, and run the requested probe mode.

    Returns 0 when historical access is demonstrated, 2 when it is definitively
    unavailable, and 1 when the probe itself failed and the question is still open.
    """
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
        verdict, requested, stamp = _probe_one(backend, t_now, days)
        if verdict == "OK" and stamp is not None:
            any_ok = True
            verdict = f"OK (document is {requested - stamp} older than the request)"
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
