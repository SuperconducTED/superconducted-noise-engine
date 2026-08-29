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
from superconducted.calibration.poller import DEFAULT_CHANNEL, _coerce_utc


def _last_update_date(properties: Any) -> datetime | None:
    """Extract ``last_update_date`` as tz-aware UTC, attribute first then dict."""
    stamp = _coerce_utc(getattr(properties, "last_update_date", None))
    if stamp is not None:
        return stamp
    to_dict = getattr(properties, "to_dict", None)
    if callable(to_dict):
        return _coerce_utc(to_dict().get("last_update_date"))
    return None


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="probe-historical-properties",
        description="Determine whether historical calibration properties are readable.",
    )
    parser.add_argument("--backend", default="ibm_fez", help="Backend name (default ibm_fez).")
    parser.add_argument(
        "--days-back",
        type=float,
        default=7.0,
        help="How far back to request, in days. Keep under max_historical_days (30).",
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

    current = backend.properties()
    if current is None:
        print("PROBE FAILED: backend.properties() returned None")
        return 1
    t_now = _last_update_date(current)
    if t_now is None:
        print("PROBE FAILED: current properties carry no last_update_date")
        return 1
    print(f"current last_update_date    : {t_now.isoformat()}")

    requested = t_now - timedelta(days=args.days_back)
    print(f"requesting datetime=        : {requested.isoformat()}")

    try:
        historical = backend.properties(datetime=requested)
    except NotImplementedError as exc:
        print(f"RESULT: DENIED — NotImplementedError: {exc}")
        return 2
    except Exception as exc:  # any failure is itself a probe result
        print(f"PROBE FAILED: {type(exc).__name__}: {exc}")
        return 1

    if historical is None:
        print("RESULT: UNAVAILABLE — properties(datetime=...) returned None")
        return 2

    t_hist = _last_update_date(historical)
    if t_hist is None:
        print("PROBE FAILED: historical properties carry no last_update_date")
        return 1
    print(f"historical last_update_date : {t_hist.isoformat()}")
    print(f"moved back by               : {t_now - t_hist}")

    if t_hist < t_now:
        print("RESULT: HISTORICAL ACCESS WORKS — backfill is feasible.")
        return 0
    print("RESULT: PARAMETER IGNORED — same document returned; backfill is impossible.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
