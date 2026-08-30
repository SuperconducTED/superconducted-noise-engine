"""Tests for the historical-properties probe.

The probe exists because a denied historical read is not an exception on the
current SDK — it is a *current* document handed back in answer to a historical
request. Its whole value is telling "honoured" apart from "ignored", so the
verdict table is the thing worth pinning: if `_probe_one` says OK when the
service ignored or clamped the request, NC-024's retention-depth claim is
unfounded and a backfill built on it silently recovers nothing.

Everything here runs against a stub backend, so there is no network and no
credential.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from scripts import probe_historical_properties as probe

NOW = datetime(2026, 8, 29, 14, 6, 21, tzinfo=UTC)


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


class TestProbeOneVerdicts:
    """The verdict table. Each row is a distinct way the service can answer."""

    def test_older_than_the_request_is_ok(self) -> None:
        served = NOW - timedelta(days=7, minutes=15)
        verdict, requested, stamp = probe._probe_one(_StubBackend(_Props(served)), NOW, 7)
        assert verdict == "OK"
        assert requested == NOW - timedelta(days=7)
        assert stamp == served

    def test_current_document_is_ignored_not_ok(self) -> None:
        verdict, _, stamp = probe._probe_one(_StubBackend(_Props(NOW)), NOW, 7)
        assert verdict.startswith("IGNORED")
        assert stamp == NOW

    def test_clamped_to_a_shallower_depth_is_not_ok(self) -> None:
        """A 30-day-old document answering a 60-day request must not score OK.

        This is the failure mode that would make a retention-depth claim
        unfounded: the stamp is older than *now*, so a naive check passes,
        but it is newer than the instant requested, so the depth was not served.
        """
        served = NOW - timedelta(days=30)
        verdict, requested, stamp = probe._probe_one(_StubBackend(_Props(served)), NOW, 60)
        assert verdict.startswith("CLAMPED")
        assert stamp == served
        assert stamp > requested

    def test_boundary_equal_to_the_request_is_ok(self) -> None:
        served = NOW - timedelta(days=7)
        verdict, _, _ = probe._probe_one(_StubBackend(_Props(served)), NOW, 7)
        assert verdict == "OK"

    def test_not_implemented_is_denied(self) -> None:
        def policy(_: datetime | None) -> Any:
            raise NotImplementedError("cloud runtime")

        verdict, _, stamp = probe._probe_one(_StubBackend(policy), NOW, 7)
        assert verdict.startswith("DENIED")
        assert stamp is None

    def test_other_exception_is_an_error_not_a_verdict(self) -> None:
        def policy(_: datetime | None) -> Any:
            raise RuntimeError("boom")

        verdict, _, stamp = probe._probe_one(_StubBackend(policy), NOW, 7)
        assert verdict.startswith("ERROR")
        assert stamp is None

    def test_none_response_is_unavailable(self) -> None:
        verdict, _, stamp = probe._probe_one(_StubBackend(None), NOW, 7)
        assert verdict.startswith("UNAVAILABLE")
        assert stamp is None

    def test_missing_stamp_is_malformed(self) -> None:
        verdict, _, stamp = probe._probe_one(_StubBackend(_Props(None)), NOW, 7)
        assert verdict.startswith("MALFORMED")
        assert stamp is None


class TestEnumerateWindow:
    def test_steps_the_window_and_dedups(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Two published documents seen by six queries must report as two."""
        start = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)
        first = start + timedelta(minutes=30)
        second = start + timedelta(hours=3, minutes=30)

        def policy(at: datetime | None) -> Any:
            assert at is not None
            return _Props(second if at >= second else first)

        backend = _StubBackend(policy)
        rc = probe._enumerate_window(
            backend, start.isoformat(), (start + timedelta(hours=5)).isoformat(), "1"
        )

        assert rc == 0
        assert len(backend.requests) == 6  # 0..5h inclusive at 1h
        out = capsys.readouterr().out
        assert "distinct documents returned : 2" in out
        assert first.strftime("%Y%m%dT%H%M%S%f") in out
        assert second.strftime("%Y%m%dT%H%M%S%f") in out

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
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A transient must not discard the stamps already collected.

        A 30-day sweep is ~720 calls; throwing all of them away on one failure
        would make the sweep unusable in exactly the case it is needed.
        """
        monkeypatch.setattr(probe.time, "sleep", lambda _: None)
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

    def test_retries_a_transient_before_giving_up(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(probe.time, "sleep", lambda _: None)
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


class _StubService:
    """Stands in for QiskitRuntimeService; hands back one prepared backend."""

    def __init__(self, backend: _StubBackend) -> None:
        self._backend = backend

    def backend(self, name: str) -> _StubBackend:
        return self._backend


class TestMainExitCodes:
    """`main`'s exit code is what calibration-historical-probe.yml gates on.

    The workflow treats 0 and 2 as successful probes and only 1 as "the probe
    broke", so an all-CLAMPED table must come back 2 rather than 0 — otherwise
    a service that quietly stopped serving the requested depth would still
    report HISTORICAL ACCESS WORKS.
    """

    @pytest.fixture
    def install_backend(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        def _install(policy: Any) -> None:
            import qiskit_ibm_runtime

            backend = _StubBackend(policy)
            monkeypatch.setattr(
                qiskit_ibm_runtime,
                "QiskitRuntimeService",
                lambda **kwargs: _StubService(backend),
            )

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

    def test_mixed_table_exits_zero_if_any_depth_is_served(self, install_backend: Any) -> None:
        """One genuinely served depth is enough to prove access exists."""

        def historical(at: datetime | None) -> Any:
            assert at is not None
            # Serves 7 d honestly; clamps anything deeper.
            return _Props(min(at - timedelta(minutes=5), NOW - timedelta(days=30)))

        install_backend(self._policy(historical))
        assert probe.main(["--days-back", "7", "60"]) == 0

    def test_no_current_properties_exits_one(self, install_backend: Any) -> None:
        """A broken probe must not be reported as a definitive answer."""
        install_backend(lambda _: None)
        assert probe.main(["--days-back", "7"]) == 1
