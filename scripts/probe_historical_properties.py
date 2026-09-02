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

The only sound test therefore compares ``last_update_date`` values. For a
request at ``T_req`` made when the current document is stamped ``T_now``:

    ==================================  ==========================================
    observation                         verdict
    ==================================  ==========================================
    ``T_hist <= T_req``                 OK — the depth was served
    ``T_req < T_hist < T_now``          CLAMPED — served, but not the depth asked
    ``T_hist >= T_now``                 IGNORED — the parameter was ignored
    ``NotImplementedError``             DENIED — refused outright
    ``None``                            UNAVAILABLE — no document for that time
    other exception (after retries)     ERROR — the probe could not ask
    document without a stamp            MALFORMED — the probe could not judge
    ==================================  ==========================================

The first five rows are *answers from the service*; the last two are
*non-answers*, and that distinction decides the exit code. Exit **0** =
historical access works at some probed depth; **2** = every probed depth was
definitively refused (a successful probe with a negative answer); **1** = no
depth was served AND at least one depth could not be judged, so the question
remains open. The probe workflow treats 2 as a successful negative result, so
2 must never be reachable through an ERROR or MALFORMED row — reporting a
transient HTTP failure as "the gaps are unrecoverable" was PR #50's second
review finding.

Contract: read-only, writes nothing, prints no credentials. One call per probed
depth plus one for the current document, each retried up to
``SUPERCONDUCTED_HTTP_RETRIES`` times with the poller's backoff.

Run in CI via ``.github/workflows/calibration-historical-probe.yml``, which is
where ``IBM_QUANTUM_TOKEN`` already lives. See #45 Phase 2.
"""

from __future__ import annotations

import argparse
import enum
import os
import sys
import time
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any, NamedTuple, Protocol

# Reused rather than reimplemented so the probe coerces timestamps exactly the
# way the poller does; a divergence here would make the comparison meaningless.
from superconducted.calibration.poller import DEFAULT_CHANNEL, coerce_utc, parse_iso_utc


class _PropertiesBackend(Protocol):
    """The one backend method this probe uses, as a structural type.

    Typed here rather than as ``object`` so the module can be checked under
    ``mypy --strict`` without a blanket ``type: ignore`` on every call.
    """

    def properties(self, *, datetime: datetime | None = None) -> Any:
        """Backend properties; with ``datetime``, the newest document older than it."""


# Reads the same knob as the poller, so raising it when transients persist
# affects every path here -- the sweep (~720 calls) needs it most, but a single
# transient on a depth probe would otherwise turn a definitive run into an
# open question.
_RETRIES = int(os.environ.get("SUPERCONDUCTED_HTTP_RETRIES", "3"))


class Verdict(enum.Enum):
    """How one historical request was answered, and whether that is an answer.

    ``definitive`` verdicts come from the service: it served the depth (OK) or
    observably did not (DENIED, IGNORED, CLAMPED, UNAVAILABLE). ERROR and
    MALFORMED are failures of the transport or of the document, and prove
    nothing either way -- ``main`` must not let them reach exit code 2.
    """

    OK = "OK"
    DENIED = "DENIED"
    IGNORED = "IGNORED"
    CLAMPED = "CLAMPED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    MALFORMED = "MALFORMED"

    @property
    def definitive(self) -> bool:
        """True when the verdict is the service's answer, not a probe failure."""
        return self not in (Verdict.ERROR, Verdict.MALFORMED)


class ProbeResult(NamedTuple):
    """One row of the verdict table."""

    verdict: Verdict
    detail: str
    requested: datetime
    stamp: datetime | None

    def render(self) -> str:
        """``VERDICT — detail`` as printed in the table."""
        return f"{self.verdict.value} — {self.detail}" if self.detail else self.verdict.value


def _last_update_date(properties: Any) -> datetime | None:
    """Extract ``last_update_date`` as tz-aware UTC, attribute first then dict."""
    stamp = coerce_utc(getattr(properties, "last_update_date", None))
    if stamp is not None:
        return stamp
    to_dict = getattr(properties, "to_dict", None)
    if callable(to_dict):
        return coerce_utc(to_dict().get("last_update_date"))
    return None


def _properties_with_retry(backend: _PropertiesBackend, at: datetime | None) -> Any:
    """``backend.properties(datetime=at)`` with the poller's exponential backoff.

    :class:`NotImplementedError` is the SDK's documented "denied" signal and is
    propagated immediately; retrying a refusal would not change it. Any other
    exception is retried ``_RETRIES`` times and then re-raised, so the caller
    sees a transient only once it has persisted.
    """
    last: Exception | None = None
    for attempt in range(_RETRIES + 1):
        try:
            return backend.properties(datetime=at)
        except NotImplementedError:
            raise
        except Exception as exc:
            last = exc
            if attempt < _RETRIES:
                time.sleep(2.0**attempt)
    assert last is not None
    raise last


def _probe_one(backend: _PropertiesBackend, t_now: datetime, days: float) -> ProbeResult:
    """Query one depth and judge the answer against the *request*.

    Judged against the request, not against "is it older than now": a service
    that silently clamps to a retention floor -- serving a 30-day-old document
    for a 60-day request -- returns something older than now and would
    otherwise score OK, which is exactly the claim a retention-depth
    measurement is supposed to establish. ``CLAMPED`` separates "served the
    window" from "served something, but not the window asked for".
    """
    requested = t_now - timedelta(days=days)
    try:
        historical = _properties_with_retry(backend, requested)
    except NotImplementedError as exc:
        return ProbeResult(Verdict.DENIED, f"NotImplementedError: {exc}", requested, None)
    except Exception as exc:  # persisted past the retries; a non-answer
        detail = f"{type(exc).__name__}: {exc} (after {_RETRIES} retries)"
        return ProbeResult(Verdict.ERROR, detail, requested, None)
    if historical is None:
        return ProbeResult(Verdict.UNAVAILABLE, "returned None", requested, None)
    stamp = _last_update_date(historical)
    if stamp is None:
        return ProbeResult(Verdict.MALFORMED, "no last_update_date", requested, None)
    if stamp >= t_now:
        return ProbeResult(Verdict.IGNORED, "returned the current document", requested, stamp)
    if stamp > requested:
        detail = "newer than the request; depth not served"
        return ProbeResult(Verdict.CLAMPED, detail, requested, stamp)
    detail = f"document is {requested - stamp} older than the request"
    return ProbeResult(Verdict.OK, detail, requested, stamp)


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

    That reasoning holds only for queries the service actually honoured. An
    answer stamped *newer* than its request means the filter was ignored or
    clamped for that step, so the answer says nothing about the window; the
    poller refuses such a document (``fetch_snapshot``) and so does the sweep.
    Those answers are counted, excluded from the served list, and fail the
    sweep -- a service that ignores ``datetime`` throughout must not come back
    as a clean "0 documents in the window" (PR #50's third review finding).
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
    not_honoured: list[tuple[datetime, datetime]] = []
    unusable: list[datetime] = []
    queries = 0
    failed_at: str | None = None
    t = start
    while t <= end:
        queries += 1
        try:
            doc = _properties_with_retry(backend, t)
        except Exception as exc:  # persisted past the retries
            failed_at = f"{t.isoformat()}: {type(exc).__name__}: {exc}"
            break
        stamp = _last_update_date(doc) if doc is not None else None
        if stamp is None:
            unusable.append(t)
        elif stamp > t:
            not_honoured.append((t, stamp))
        else:
            seen[stamp] = seen.get(stamp, 0) + 1
        t += step

    in_window = sorted(s for s in seen if start <= s <= end)
    honoured = queries - len(not_honoured) - len(unusable) - (1 if failed_at else 0)
    print(f"window   : {start.isoformat()} .. {end.isoformat()}")
    print(
        f"step     : {step_hours_s}h   queries: {queries}   honoured: {honoured}   "
        f"not honoured: {len(not_honoured)}   unusable: {len(unusable)}"
    )
    print(f"distinct documents returned : {len(seen)}  ({len(in_window)} inside the window)")
    print("\nlast_update_date values IBM will serve for this window:")
    for s in in_window:
        print(f"  {s.strftime('%Y%m%dT%H%M%S%f')}Z   {s.isoformat()}")
    print(
        "\nDiff these stamps against the archived filenames on calibration-data; "
        "any listed here and absent there is a document the poller missed and can "
        "still recover."
    )

    # Everything above is printed before any failure is reported, so a partial
    # sweep's evidence is never wasted -- but each failure below makes the
    # list INCOMPLETE, and the exit code says so.
    rc = 0
    if not_honoured:
        first_t, first_s = not_honoured[0]
        print(
            f"\nPROBE FAILED: {len(not_honoured)} of {queries} queries were answered with a "
            f"document NEWER than the instant requested (first: asked {first_t.isoformat()}, "
            f"got {first_s.isoformat()}). The datetime filter was not honoured for those "
            "steps; they are excluded above and the list is INCOMPLETE."
        )
        rc = 1
    if unusable:
        print(
            f"\nPROBE FAILED: {len(unusable)} of {queries} queries returned no usable document "
            f"(None, or no last_update_date; first at {unusable[0].isoformat()}). "
            "The list above is INCOMPLETE."
        )
        rc = 1
    if failed_at is not None:
        print(f"\nPROBE FAILED at {failed_at}")
        print(f"Sweep stopped early at {t.isoformat()}; the window above is INCOMPLETE.")
        rc = 1
    return rc


def main(argv: Iterable[str] | None = None) -> int:
    """Parse arguments, build the service, and run the requested probe mode.

    Returns 0 when historical access is demonstrated, 2 when every probed
    depth was definitively refused, and 1 when the probe itself failed or
    could not judge every depth, so the question is still open.
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

    try:
        current = _properties_with_retry(backend, None)
    except Exception as exc:
        print(f"PROBE FAILED: backend.properties() raised {type(exc).__name__}: {exc}")
        return 1
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

    results = [_probe_one(backend, t_now, days) for days in sorted(args.days_back)]
    for days, result in zip(sorted(args.days_back), results, strict=True):
        returned = result.stamp.isoformat() if result.stamp else "-"
        requested = result.requested.isoformat()
        print(f"{days:>7.1f}d  {requested:<25}  {returned:<25}  {result.render()}")

    if any(r.verdict is Verdict.OK for r in results):
        print("\nRESULT: HISTORICAL ACCESS WORKS — backfill is feasible at the depths marked OK.")
        return 0
    undecided = [r for r in results if not r.verdict.definitive]
    if undecided:
        print(
            f"\nRESULT: INDETERMINATE — {len(undecided)} of {len(results)} depths could not be "
            "judged (ERROR/MALFORMED) and none was served. This is not evidence that access "
            "is denied; re-run before concluding anything about recoverability."
        )
        return 1
    print("\nRESULT: NO HISTORICAL ACCESS at any probed depth — the gaps are unrecoverable.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
