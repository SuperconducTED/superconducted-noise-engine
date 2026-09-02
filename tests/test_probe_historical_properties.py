"""Tests for the historical-properties probe.

The probe exists because a denied historical read is not an exception on the
current SDK — it is a *current* document handed back in answer to a historical
request. Its whole value is telling "honoured" apart from "ignored", so the
verdict table is the thing worth pinning: if `_probe_one` says OK when the
service ignored or clamped the request, NC-026's retention-depth claim is
unfounded and a backfill built on it silently recovers nothing.

Two further properties come from PR #50's review and are pinned here as well:
a verdict the probe could not reach (ERROR, MALFORMED) must never be reported
as a definitive refusal, and a sweep answered with documents newer than the
instants it asked for must not come back as a clean "nothing in the window".

Everything here runs against a stub backend, so there is no network and no
credential.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from scripts import probe_historical_properties as probe
from scripts.probe_historical_properties import Verdict

NOW = datetime(2026, 8, 29, 14, 6, 21, tzinfo=UTC)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries back off for real; the tests must not."""
    monkeypatch.setattr(probe.time, "sleep", lambda _: None)


class _Props:
    """Minimal stand-in for BackendProperties."""

    def __init__(self, stamp: datetime | None, *, via_dict: bool = False) -> None:
        self._stamp = stamp
        if not via_dict:
            self.last_update_date = stamp

    def to_dict(self) -> dict[str, Any]:
        return {"last_update_date": self._stamp}


class _StubBackend:
    """Serves whatever the policy says, recording what it was asked for."""

    def __init__(self, policy: Any) -> None:
        self._policy = policy
        self.requests: list[datetime | None] = []

    def properties(self, *, datetime: datetime | None = None) -> Any:
        self.requests.append(datetime)
        if callable(self._policy):
            return self._policy(datetime)
        return self._policy


class TestLastUpdateDate:
    def test_reads_the_attribute(self) -> None:
        assert probe._last_update_date(_Props(NOW)) == NOW

    def test_falls_back_to_to_dict(self) -> None:
        assert probe._last_update_date(_Props(NOW, via_dict=True)) == NOW

    def test_none_when_absent(self) -> None:
        assert probe._last_update_date(_Props(None)) is None


class TestVerdict:
    def test_only_error_and_malformed_are_not_definitive(self) -> None:
        """The exit-code split in `main` rests on exactly this partition."""
        undecided = {v for v in Verdict if not v.definitive}
        assert undecided == {Verdict.ERROR, Verdict.MALFORMED}


class TestProbeOneVerdicts:
    """The verdict table. Each row is a distinct way the service can answer."""

    def test_older_than_the_request_is_ok(self) -> None:
        served = NOW - timedelta(days=7, minutes=15)
        result = probe._probe_one(_StubBackend(_Props(served)), NOW, 7)
        assert result.verdict is Verdict.OK
        assert result.requested == NOW - timedelta(days=7)
        assert result.stamp == served

    def test_current_document_is_ignored_not_ok(self) -> None:
        result = probe._probe_one(_StubBackend(_Props(NOW)), NOW, 7)
        assert result.verdict is Verdict.IGNORED
        assert result.stamp == NOW

    def test_clamped_to_a_shallower_depth_is_not_ok(self) -> None:
        """A 30-day-old document answering a 60-day request must not score OK.

        This is the failure mode that would make a retention-depth claim
        unfounded: the stamp is older than *now*, so a naive check passes,
        but it is newer than the instant requested, so the depth was not served.
        """
        served = NOW - timedelta(days=30)
        result = probe._probe_one(_StubBackend(_Props(served)), NOW, 60)
        assert result.verdict is Verdict.CLAMPED
        assert result.stamp == served
        assert result.stamp > result.requested

    def test_boundary_equal_to_the_request_is_ok(self) -> None:
        served = NOW - timedelta(days=7)
        assert probe._probe_one(_StubBackend(_Props(served)), NOW, 7).verdict is Verdict.OK

    def test_not_implemented_is_denied_and_not_retried(self) -> None:
        def policy(_: datetime | None) -> Any:
            raise NotImplementedError("cloud runtime")

        backend = _StubBackend(policy)
        result = probe._probe_one(backend, NOW, 7)
        assert result.verdict is Verdict.DENIED
        assert result.stamp is None
        assert len(backend.requests) == 1  # a refusal is not a transient

    def test_persistent_exception_is_an_error_not_a_verdict(self) -> None:
        def policy(_: datetime | None) -> Any:
            raise RuntimeError("boom")

        backend = _StubBackend(policy)
        result = probe._probe_one(backend, NOW, 7)
        assert result.verdict is Verdict.ERROR
        assert not result.verdict.definitive
        assert result.stamp is None
        assert len(backend.requests) == probe._RETRIES + 1  # retried, then gave up

    def test_a_transient_that_clears_on_retry_is_judged_normally(self) -> None:
        calls = {"n": 0}

        def policy(_: datetime | None) -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient HTTP 503")
            return _Props(NOW - timedelta(days=7, hours=1))

        result = probe._probe_one(_StubBackend(policy), NOW, 7)
        assert result.verdict is Verdict.OK
        assert calls["n"] == 2

    def test_none_response_is_unavailable(self) -> None:
        result = probe._probe_one(_StubBackend(None), NOW, 7)
        assert result.verdict is Verdict.UNAVAILABLE
        assert result.stamp is None

    def test_missing_stamp_is_malformed(self) -> None:
        result = probe._probe_one(_StubBackend(_Props(None)), NOW, 7)
        assert result.verdict is Verdict.MALFORMED
        assert not result.verdict.definitive
        assert result.stamp is None


class TestEnumerateWindow:
    def test_steps_the_window_and_dedups(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Two documents published inside the window, seen by six queries, report as two.

        The stub honours the contract — the newest document *older than* the
        request — so the query at the window's start is answered with the
        document published before it, which is outside the window.
        """
        start = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)
        before = start - timedelta(hours=2)
        first = start + timedelta(minutes=30)
        second = start + timedelta(hours=3, minutes=30)

        def policy(at: datetime | None) -> Any:
            assert at is not None
            if at >= second:
                return _Props(second)
            return _Props(first if at >= first else before)

        backend = _StubBackend(policy)
        rc = probe._enumerate_window(
            backend, start.isoformat(), (start + timedelta(hours=5)).isoformat(), "1"
        )

        assert rc == 0
        assert len(backend.requests) == 6  # 0..5h inclusive at 1h
        out = capsys.readouterr().out
        assert "honoured: 6   not honoured: 0" in out
        assert "distinct documents returned : 3  (2 inside the window)" in out
        assert first.strftime("%Y%m%dT%H%M%S%f") in out
        assert second.strftime("%Y%m%dT%H%M%S%f") in out
        assert before.strftime("%Y%m%dT%H%M%S%f") not in out  # listed only if inside

    def test_rejects_non_positive_step(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = probe._enumerate_window(
            _StubBackend(_Props(NOW)), NOW.isoformat(), (NOW + timedelta(hours=1)).isoformat(), "0"
        )
        assert rc == 1
        assert "step must be positive" in capsys.readouterr().out

    def test_rejects_reversed_window(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = probe._enumerate_window(
            _StubBackend(_Props(NOW)), NOW.isoformat(), (NOW - timedelta(hours=1)).isoformat(), "1"
        )
        assert rc == 1
        assert "start must be before end" in capsys.readouterr().out

    def test_partial_sweep_still_prints_what_it_found(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A transient must not discard the stamps already collected.

        A 30-day sweep is ~720 calls; throwing all of them away on one failure
        would make the sweep unusable in exactly the case it is needed.
        """
        start = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)
        served = start + timedelta(minutes=1)
        calls = {"n": 0}

        def policy(_: datetime | None) -> Any:
            calls["n"] += 1
            if calls["n"] > 2:
                raise RuntimeError("transient")
            return _Props(served)

        rc = probe._enumerate_window(
            _StubBackend(policy), start.isoformat(), (start + timedelta(hours=5)).isoformat(), "1"
        )
        out = capsys.readouterr().out
        assert rc == 1
        assert served.strftime("%Y%m%dT%H%M%S%f") in out  # evidence survived
        assert "INCOMPLETE" in out

    def test_retries_a_transient_before_giving_up(self) -> None:
        start = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)
        calls = {"n": 0}

        def policy(_: datetime | None) -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient")
            return _Props(start - timedelta(minutes=1))

        rc = probe._enumerate_window(
            _StubBackend(policy), start.isoformat(), (start + timedelta(hours=1)).isoformat(), "1"
        )
        assert rc == 0
        assert calls["n"] > 1  # it retried rather than aborting

    def test_the_current_document_for_every_query_is_not_a_clean_sweep(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """PR #50 review, finding 3: an ignored filter must not read as "0 missed".

        Every step is answered with a document newer than the window's end.
        Before the honour check this printed "0 inside the window" and exited
        0 -- a sweep that found nothing to recover, when it had found nothing
        at all.
        """
        start = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)
        rc = probe._enumerate_window(
            _StubBackend(_Props(NOW)),
            start.isoformat(),
            (start + timedelta(hours=5)).isoformat(),
            "1",
        )
        out = capsys.readouterr().out
        assert rc == 1
        assert "not honoured: 6" in out
        assert "NEWER than the instant requested" in out
        assert "INCOMPLETE" in out
        assert "distinct documents returned : 0" in out

    def test_an_answer_newer_than_its_request_is_excluded_even_inside_the_window(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """One dishonoured step poisons the sweep, and its stamp is not "served"."""
        start = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)
        honest = start - timedelta(minutes=10)
        bad_step = start + timedelta(hours=2)
        too_new = bad_step + timedelta(minutes=5)  # inside the window, but newer than asked

        def policy(at: datetime | None) -> Any:
            assert at is not None
            return _Props(too_new if at == bad_step else honest)

        rc = probe._enumerate_window(
            _StubBackend(policy), start.isoformat(), (start + timedelta(hours=5)).isoformat(), "1"
        )
        out = capsys.readouterr().out
        assert rc == 1
        assert "not honoured: 1" in out
        assert too_new.strftime("%Y%m%dT%H%M%S%f") not in out.split("PROBE FAILED")[0]
        assert f"asked {bad_step.isoformat()}, got {too_new.isoformat()}" in out

    def test_an_unusable_answer_fails_the_sweep_but_keeps_the_evidence(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        start = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)
        served = start + timedelta(minutes=1)

        def policy(at: datetime | None) -> Any:
            assert at is not None
            return None if at == start + timedelta(hours=3) else _Props(served)

        rc = probe._enumerate_window(
            _StubBackend(policy), start.isoformat(), (start + timedelta(hours=5)).isoformat(), "1"
        )
        out = capsys.readouterr().out
        assert rc == 1
        assert "unusable: 1" in out
        assert "no usable document" in out
        assert served.strftime("%Y%m%dT%H%M%S%f") in out  # evidence survived


class _StubService:
    """Stands in for QiskitRuntimeService; hands back one prepared backend."""

    def __init__(self, backend: _StubBackend) -> None:
        self._backend = backend

    def backend(self, name: str) -> _StubBackend:
        return self._backend


class TestMainExitCodes:
    """`main`'s exit code is what calibration-historical-probe.yml gates on.

    The workflow treats 0 and 2 as successful probes and only 1 as "the probe
    broke", so two things must hold. An all-CLAMPED table must come back 2
    rather than 0, or a service that quietly stopped serving the requested
    depth would still report HISTORICAL ACCESS WORKS. And a table with no OK
    and any ERROR/MALFORMED row must come back 1 rather than 2, or a transient
    HTTP failure would be reported as "the gaps are unrecoverable" -- a
    successful negative finding the workflow would accept (PR #50 review).
    """

    @pytest.fixture
    def install_backend(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        def _install(policy: Any) -> _StubBackend:
            import qiskit_ibm_runtime

            backend = _StubBackend(policy)
            monkeypatch.setattr(
                qiskit_ibm_runtime,
                "QiskitRuntimeService",
                lambda **kwargs: _StubService(backend),
            )
            return backend

        return _install

    @staticmethod
    def _policy(historical: Any) -> Any:
        """Serve NOW for the current call, `historical` for a dated one."""

        def policy(at: datetime | None) -> Any:
            if at is None:
                return _Props(NOW)
            return historical(at) if callable(historical) else historical

        return policy

    def test_served_depth_exits_zero(self, install_backend: Any) -> None:
        install_backend(self._policy(_Props(NOW - timedelta(days=90))))
        assert probe.main(["--days-back", "60"]) == 0

    def test_all_clamped_exits_two(self, install_backend: Any) -> None:
        # 30-day-old document answering a 60-day request: older than now, but
        # newer than the request, so the depth was not served.
        install_backend(self._policy(_Props(NOW - timedelta(days=30))))
        assert probe.main(["--days-back", "60"]) == 2

    def test_ignored_exits_two(self, install_backend: Any) -> None:
        install_backend(self._policy(_Props(NOW)))
        assert probe.main(["--days-back", "7"]) == 2

    def test_denied_exits_two(self, install_backend: Any) -> None:
        def deny(_: datetime | None) -> Any:
            raise NotImplementedError("cloud runtime")

        install_backend(self._policy(deny))
        assert probe.main(["--days-back", "7"]) == 2

    def test_unavailable_exits_two(self, install_backend: Any) -> None:
        """None is the service's answer for that instant, so it counts as one."""
        install_backend(self._policy(lambda _: None))
        assert probe.main(["--days-back", "7"]) == 2

    def test_mixed_table_exits_zero_if_any_depth_is_served(self, install_backend: Any) -> None:
        """One genuinely served depth is enough to prove access exists."""

        def historical(at: datetime | None) -> Any:
            assert at is not None
            # Serves 7 d honestly; clamps anything deeper.
            return _Props(min(at - timedelta(minutes=5), NOW - timedelta(days=30)))

        install_backend(self._policy(historical))
        assert probe.main(["--days-back", "7", "60"]) == 0

    def test_transient_errors_at_every_depth_exit_one_not_two(
        self, install_backend: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """PR #50 review, finding 2, reproduced exactly.

        The current document is fine; every historical query raises. Before the
        fix this printed "NO HISTORICAL ACCESS ... the gaps are unrecoverable"
        and exited 2, which the workflow accepts as a successful negative result.
        """

        def historical(_: datetime | None) -> Any:
            raise RuntimeError("transient HTTP 503")

        install_backend(self._policy(historical))
        rc = probe.main(["--days-back", "1", "7", "30"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "INDETERMINATE" in out
        assert "3 of 3 depths" in out
        assert "unrecoverable" not in out

    def test_malformed_at_every_depth_exits_one(self, install_backend: Any) -> None:
        install_backend(self._policy(_Props(None)))
        assert probe.main(["--days-back", "7"]) == 1

    def test_an_error_beside_a_refusal_still_exits_one(self, install_backend: Any) -> None:
        """Refused at 7 d, unreachable at 60 d: access was not shown to be denied."""

        def historical(at: datetime | None) -> Any:
            assert at is not None
            if at < NOW - timedelta(days=30):
                raise RuntimeError("transient HTTP 503")
            return _Props(NOW)  # ignored

        install_backend(self._policy(historical))
        assert probe.main(["--days-back", "7", "60"]) == 1

    def test_an_error_beside_a_served_depth_exits_zero(self, install_backend: Any) -> None:
        def historical(at: datetime | None) -> Any:
            assert at is not None
            if at < NOW - timedelta(days=30):
                raise RuntimeError("transient HTTP 503")
            return _Props(at - timedelta(hours=1))

        install_backend(self._policy(historical))
        assert probe.main(["--days-back", "7", "60"]) == 0

    def test_no_current_properties_exits_one(self, install_backend: Any) -> None:
        """A broken probe must not be reported as a definitive answer."""
        install_backend(lambda _: None)
        assert probe.main(["--days-back", "7"]) == 1

    def test_current_fetch_failing_after_retries_exits_one(self, install_backend: Any) -> None:
        def policy(_: datetime | None) -> Any:
            raise RuntimeError("transient HTTP 503")

        backend = install_backend(policy)
        assert probe.main(["--days-back", "7"]) == 1
        assert len(backend.requests) == probe._RETRIES + 1  # only the current fetch, retried

    def test_current_fetch_transient_is_retried(self, install_backend: Any) -> None:
        calls = {"n": 0}

        def policy(at: datetime | None) -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient HTTP 503")
            return _Props(NOW if at is None else at - timedelta(hours=1))

        install_backend(policy)
        assert probe.main(["--days-back", "7"]) == 0
