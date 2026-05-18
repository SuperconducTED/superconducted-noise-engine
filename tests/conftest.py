"""Shared pytest fixtures.

Use absolute imports — relative imports from a top-level ``tests/``
package can break under newer pytest collection rules.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from superconducted.calibration.storage import CalibrationStorage
from superconducted.types import CalibrationSnapshot

DEFAULT_TIMESTAMP = datetime(2026, 5, 7, 12, 0, 0, tzinfo=UTC)
DEFAULT_PROPERTIES: dict[str, Any] = {
    "last_update_date": DEFAULT_TIMESTAMP.isoformat(),
    "qubits": [
        [
            {"name": "T1", "value": 100e-6, "unit": "s"},
            {"name": "T2", "value": 80e-6, "unit": "s"},
            {"name": "readout_error", "value": 0.01, "unit": ""},
        ],
        [
            {"name": "T1", "value": 110e-6, "unit": "s"},
            {"name": "T2", "value": 90e-6, "unit": "s"},
            {"name": "readout_error", "value": 0.012, "unit": ""},
        ],
    ],
    "gates": [],
    "general": [],
}


@pytest.fixture
def tmp_storage(tmp_path: Any) -> CalibrationStorage:
    return CalibrationStorage(tmp_path)


@pytest.fixture
def dummy_snapshot() -> CalibrationSnapshot:
    return CalibrationSnapshot(
        backend="ibm_test",
        timestamp=DEFAULT_TIMESTAMP,
        schema_version="1.0.0",
        properties=DEFAULT_PROPERTIES,
        target=None,
        configuration=None,
    )


@pytest.fixture
def make_mock_properties() -> Callable[..., MagicMock]:
    """Factory for a mock ``BackendProperties``-shaped object."""

    def _factory(
        *,
        last_update_date: datetime | None = None,
        properties_dict: dict[str, Any] | None = None,
    ) -> MagicMock:
        m = MagicMock()
        m.last_update_date = last_update_date or DEFAULT_TIMESTAMP
        m.to_dict.return_value = properties_dict or DEFAULT_PROPERTIES
        return m

    return _factory


@pytest.fixture
def make_mock_service(
    make_mock_properties: Callable[..., MagicMock],
) -> Callable[..., MagicMock]:
    """Factory for a mock ``QiskitRuntimeService``.

    Pass ``properties_side_effect`` to control retry / error behavior:
    a list of values where each element is either a ``BackendProperties``
    mock, ``None``, or an exception instance/class to raise on that call.
    """

    def _factory(
        *,
        properties_side_effect: list[Any] | None = None,
        properties_value: MagicMock | None = None,
    ) -> MagicMock:
        service = MagicMock()
        backend = MagicMock()
        backend.target = None
        backend.configuration.return_value = None
        if properties_side_effect is not None:
            backend.properties.side_effect = properties_side_effect
        else:
            backend.properties.return_value = properties_value or make_mock_properties()
        service.backend.return_value = backend
        return service

    return _factory
