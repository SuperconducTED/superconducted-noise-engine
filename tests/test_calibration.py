"""Polling + storage + features without real IBM API calls."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from superconducted.calibration import poller as poller_module
from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.calibration.poller import (
    fetch_snapshot,
    main,
    poll_once,
    serialize_target,
)
from superconducted.calibration.storage import (
    CalibrationStorage,
    _decode_filename_stem,
    _SnapshotJSONEncoder,
)
from superconducted.types import CalibrationSnapshot

UTC = UTC


# --- Storage --------------------------------------------------------------


class TestCalibrationStorage:
    def test_save_if_new_idempotent(
        self, tmp_storage: CalibrationStorage, dummy_snapshot: CalibrationSnapshot
    ) -> None:
        assert tmp_storage.save_if_new(dummy_snapshot) is True
        assert tmp_storage.save_if_new(dummy_snapshot) is False

    def test_path_for_no_colon(
        self, tmp_storage: CalibrationStorage, dummy_snapshot: CalibrationSnapshot
    ) -> None:
        path = tmp_storage.path_for(dummy_snapshot.backend, dummy_snapshot.timestamp)
        assert ":" not in path.name

    def test_filename_round_trips(self, dummy_snapshot: CalibrationSnapshot) -> None:
        stem = dummy_snapshot.storage_filename().removesuffix(".json")
        decoded = _decode_filename_stem(stem)
        assert decoded == dummy_snapshot.timestamp

    def test_list_timestamps_sorted(self, tmp_storage: CalibrationStorage) -> None:
        ts1 = datetime(2026, 5, 1, tzinfo=UTC)
        ts2 = datetime(2026, 5, 7, tzinfo=UTC)
        ts3 = datetime(2026, 5, 4, tzinfo=UTC)
        for ts in (ts1, ts2, ts3):
            snap = CalibrationSnapshot(
                backend="b",
                timestamp=ts,
                schema_version="1.0.0",
                properties={"qubits": []},
                target=None,
                configuration=None,
            )
            tmp_storage.save_if_new(snap)
        result = tmp_storage.list_timestamps("b")
        assert result == [ts1, ts3, ts2]

    def test_list_timestamps_missing_dir(self, tmp_storage: CalibrationStorage) -> None:
        assert tmp_storage.list_timestamps("not_a_real_backend") == []

    def test_save_if_new_race_safe(
        self,
        tmp_storage: CalibrationStorage,
        dummy_snapshot: CalibrationSnapshot,
    ) -> None:
        results: list[bool] = []
        barrier = threading.Barrier(8)

        def worker() -> None:
            barrier.wait()
            results.append(tmp_storage.save_if_new(dummy_snapshot))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sum(results) == 1
        assert results.count(False) == 7

    def test_load_round_trip(
        self, tmp_storage: CalibrationStorage, dummy_snapshot: CalibrationSnapshot
    ) -> None:
        tmp_storage.save_if_new(dummy_snapshot)
        loaded = tmp_storage.load(dummy_snapshot.backend, dummy_snapshot.timestamp)
        assert loaded.backend == dummy_snapshot.backend
        assert loaded.timestamp == dummy_snapshot.timestamp
        assert loaded.properties == dummy_snapshot.properties


class TestSnapshotJSONEncoder:
    def test_datetime_to_iso(self) -> None:
        ts = datetime(2026, 5, 7, 12, 0, 0, tzinfo=UTC)
        out = json.dumps({"ts": ts}, cls=_SnapshotJSONEncoder)
        assert "2026-05-07T12:00:00+00:00" in out

    def test_complex(self) -> None:
        out = json.dumps({"z": 1.0 + 2.0j}, cls=_SnapshotJSONEncoder)
        assert "__complex__" in out

    def test_numpy_scalar(self) -> None:
        out = json.dumps({"x": np.float64(3.14), "y": np.int64(42)}, cls=_SnapshotJSONEncoder)
        decoded = json.loads(out)
        assert decoded["x"] == pytest.approx(3.14)
        assert decoded["y"] == 42


# --- Features -------------------------------------------------------------


class TestBasicCalibrationVectorizer:
    def test_extract_shape(self, dummy_snapshot: CalibrationSnapshot) -> None:
        vec = BasicCalibrationVectorizer()
        result = vec.extract(dummy_snapshot)
        assert result.shape == (3,)
        assert vec.output_dim == 3

    def test_feature_names(self) -> None:
        assert BasicCalibrationVectorizer().feature_names == (
            "mean_T1",
            "mean_T2",
            "mean_readout_error",
        )

    def test_extract_is_mean(self, dummy_snapshot: CalibrationSnapshot) -> None:
        result = BasicCalibrationVectorizer().extract(dummy_snapshot)
        # Two qubits with T1 = 100e-6 and 110e-6 → mean 105e-6
        assert result[0] == pytest.approx(105e-6)
        # T2 = 80e-6 and 90e-6 → mean 85e-6
        assert result[1] == pytest.approx(85e-6)
        # readout = 0.01 and 0.012 → mean 0.011
        assert result[2] == pytest.approx(0.011)

    def test_extract_skips_missing(self) -> None:
        snapshot = CalibrationSnapshot(
            backend="b",
            timestamp=datetime(2026, 5, 7, tzinfo=UTC),
            schema_version="1.0.0",
            properties={
                "qubits": [
                    [
                        {"name": "T1", "value": 100e-6},
                        {"name": "T2", "value": float("nan")},
                        {"name": "readout_error", "value": 0.01},
                    ],
                    [
                        {"name": "T1", "value": 90e-6},
                        {"name": "T2", "value": 80e-6},
                        {"name": "readout_error", "value": 0.02},
                    ],
                ]
            },
            target=None,
            configuration=None,
        )
        result = BasicCalibrationVectorizer().extract(snapshot)
        assert result[1] == pytest.approx(80e-6)  # NaN skipped

    def test_extract_raises_on_empty(self) -> None:
        snapshot = CalibrationSnapshot(
            backend="b",
            timestamp=datetime(2026, 5, 7, tzinfo=UTC),
            schema_version="1.0.0",
            properties={"qubits": []},
            target=None,
            configuration=None,
        )
        with pytest.raises(ValueError):
            BasicCalibrationVectorizer().extract(snapshot)


# --- serialize_target -----------------------------------------------------


class TestSerializeTarget:
    def test_none_returns_none(self) -> None:
        assert serialize_target(None) is None

    def test_minimal_target_shape(self) -> None:
        target = MagicMock()
        target.num_qubits = 2
        target.physical_qubits = [0, 1]
        target.operation_names = ["x", "cx"]

        def qargs_for(name: str) -> list[tuple[int, ...]]:
            if name == "x":
                return [(0,), (1,)]
            return [(0, 1)]

        target.qargs_for_operation_name.side_effect = qargs_for

        instr_props = MagicMock()
        instr_props.duration = 35.6e-9
        instr_props.error = 1e-3
        target.__getitem__.return_value = instr_props

        result = serialize_target(target)
        assert result is not None
        assert result["num_qubits"] == 2
        assert result["physical_qubits"] == [0, 1]
        assert isinstance(result["operations"], list)
        assert len(result["operations"]) == 3


# --- CalibrationSnapshot validation --------------------------------------


class TestCalibrationSnapshotValidation:
    def test_naive_timestamp_rejected(self) -> None:
        with pytest.raises(ValueError):
            CalibrationSnapshot(
                backend="b",
                timestamp=datetime(2026, 5, 7, 12, 0, 0),
                schema_version="1.0.0",
                properties={},
                target=None,
                configuration=None,
            )

    def test_non_utc_normalized(self) -> None:
        tz_plus_3 = timezone(timedelta(hours=3))
        snap = CalibrationSnapshot(
            backend="b",
            timestamp=datetime(2026, 5, 7, 15, 0, 0, tzinfo=tz_plus_3),
            schema_version="1.0.0",
            properties={},
            target=None,
            configuration=None,
        )
        assert snap.timestamp.tzinfo == UTC
        assert snap.timestamp.hour == 12  # 15:00 +03:00 → 12:00 UTC


# --- fetch_snapshot -------------------------------------------------------


class TestFetchSnapshot:
    def test_happy_path(
        self,
        make_mock_service: Callable[..., MagicMock],
        dummy_snapshot: CalibrationSnapshot,
    ) -> None:
        service = make_mock_service()
        snap = fetch_snapshot(service, "ibm_test")
        assert snap is not None
        assert snap.backend == "ibm_test"
        assert snap.timestamp == dummy_snapshot.timestamp

    def test_properties_returns_none(self, make_mock_service: Callable[..., MagicMock]) -> None:
        service = make_mock_service(properties_value=None)
        # backend.properties returns None → fetch should return None
        service.backend.return_value.properties.return_value = None
        snap = fetch_snapshot(service, "ibm_test")
        assert snap is None

    def test_not_implemented_historical(self, make_mock_service: Callable[..., MagicMock]) -> None:
        service = make_mock_service(properties_side_effect=[NotImplementedError("nope")])
        snap = fetch_snapshot(service, "ibm_test", historical_at=datetime(2026, 4, 1, tzinfo=UTC))
        assert snap is None

    def test_retries_on_runtime_error(
        self,
        make_mock_service: Callable[..., MagicMock],
        make_mock_properties: Callable[..., MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Avoid real sleeping
        monkeypatch.setattr(poller_module.time, "sleep", lambda _: None)
        good = make_mock_properties()
        service = make_mock_service(
            properties_side_effect=[
                RuntimeError("transient 1"),
                RuntimeError("transient 2"),
                good,
            ]
        )
        snap = fetch_snapshot(service, "ibm_test", retries=3)
        assert snap is not None

    def test_gives_up_after_retries(
        self,
        make_mock_service: Callable[..., MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(poller_module.time, "sleep", lambda _: None)
        service = make_mock_service(properties_side_effect=[RuntimeError("fail")] * 5)
        with pytest.raises(RuntimeError):
            fetch_snapshot(service, "ibm_test", retries=3)

    def test_timestamp_from_properties(
        self,
        make_mock_service: Callable[..., MagicMock],
        make_mock_properties: Callable[..., MagicMock],
    ) -> None:
        # The historical_at requested differs from what properties report.
        actual_ts = datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC)
        props = make_mock_properties(last_update_date=actual_ts)
        service = make_mock_service(properties_value=props)
        snap = fetch_snapshot(
            service,
            "ibm_test",
            historical_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
        assert snap is not None
        # Snapshot's timestamp comes from properties.last_update_date,
        # NOT the historical_at argument.
        assert snap.timestamp == actual_ts


# --- poll_once ------------------------------------------------------------


class TestPollOnce:
    def test_happy_path_persists(
        self,
        tmp_storage: CalibrationStorage,
        make_mock_service: Callable[..., MagicMock],
    ) -> None:
        service = make_mock_service()
        poll_once(
            ["ibm_test"],
            tmp_storage,
            service_factory=lambda: service,
        )
        timestamps = tmp_storage.list_timestamps("ibm_test")
        assert len(timestamps) == 1

    def test_idempotent_across_invocations(
        self,
        tmp_storage: CalibrationStorage,
        make_mock_service: Callable[..., MagicMock],
    ) -> None:
        service = make_mock_service()
        poll_once(["ibm_test"], tmp_storage, service_factory=lambda: service)
        poll_once(["ibm_test"], tmp_storage, service_factory=lambda: service)
        # Second invocation should not duplicate the snapshot.
        assert len(tmp_storage.list_timestamps("ibm_test")) == 1

    def test_historical_window_too_old_rejected(
        self,
        tmp_storage: CalibrationStorage,
        make_mock_service: Callable[..., MagicMock],
    ) -> None:
        service = make_mock_service()
        far_past = datetime.now(UTC) - timedelta(days=365)
        with pytest.raises(ValueError):
            poll_once(
                ["ibm_test"],
                tmp_storage,
                historical_window=[far_past],
                service_factory=lambda: service,
                max_historical_days=30,
            )


# --- main / CLI -----------------------------------------------------------


class TestMain:
    def test_happy_path_returns_zero(
        self,
        tmp_path: Path,
        make_mock_service: Callable[..., MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        service = make_mock_service()
        monkeypatch.setattr(
            poller_module,
            "_default_service_factory",
            lambda **kwargs: service,
        )
        rc = main(
            [
                "--backend",
                "ibm_test",
                "--data-dir",
                str(tmp_path / "data"),
                "--log-dir",
                str(tmp_path / "logs"),
            ]
        )
        assert rc == 0

    def test_returns_one_on_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def failing_factory(**kwargs: Any) -> MagicMock:
            raise RuntimeError("auth failed")

        monkeypatch.setattr(poller_module, "_default_service_factory", failing_factory)
        rc = main(
            [
                "--backend",
                "ibm_test",
                "--data-dir",
                str(tmp_path / "data"),
                "--log-dir",
                str(tmp_path / "logs"),
            ]
        )
        assert rc == 1

    def test_invalid_historical_returns_one(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        make_mock_service: Callable[..., MagicMock],
    ) -> None:
        service = make_mock_service()
        monkeypatch.setattr(
            poller_module,
            "_default_service_factory",
            lambda **kwargs: service,
        )
        rc = main(
            [
                "--backend",
                "ibm_test",
                "--data-dir",
                str(tmp_path / "data"),
                "--log-dir",
                str(tmp_path / "logs"),
                "--historical",
                "2026-05-07T00:00:00Z",
                "2026-05-01T00:00:00Z",
                "24",
            ]
        )
        assert rc == 1
