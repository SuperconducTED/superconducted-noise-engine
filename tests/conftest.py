"""Shared pytest fixtures.

Use absolute imports — relative imports from a top-level ``tests/``
package can break under newer pytest collection rules.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from superconducted.calibration.features import BasicCalibrationVectorizer
from superconducted.calibration.storage import CalibrationStorage
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization
from superconducted.fuzzy.defuzzification import WeightedAverageDefuzzifier
from superconducted.fuzzy.fuzzification import PostGateFuzzification
from superconducted.fuzzy.membership import GaussianMF
from superconducted.fuzzy.squashing import ProbabilityClip
from superconducted.fuzzy.tsk import TSKRuleBase
from superconducted.integration.aer_factory import (
    FuzzyNoiseModelEnsemble,
    first_viable_seed,
)
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


@pytest.fixture(scope="session")
def benchmark_snapshot() -> CalibrationSnapshot:
    """Load the committed IBM Fez fixture used by benchmark certification tests."""
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "calibration"
        / "ibm_fez_20260513T121322Z_q72_missing_t1t2.json"
    )
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    timestamp = datetime.fromisoformat(str(data["timestamp"]).replace("Z", "+00:00"))
    return CalibrationSnapshot(
        backend=str(data["backend"]),
        timestamp=timestamp,
        schema_version=str(data["schema_version"]),
        properties=data["properties"],
        target=data.get("target"),
        configuration=data.get("configuration"),
    )


@pytest.fixture(scope="session")
def issue_57_gates_snapshot() -> CalibrationSnapshot:
    """Load #57's sole gates fixture, or skip consumers until that issue lands."""
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "calibration"
        / "ibm_fez_20260513T121322Z_with_gates.json"
    )
    if not fixture_path.exists():
        pytest.skip("Issue #57 has not yet landed ibm_fez_20260513T121322Z_with_gates.json")
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    timestamp = datetime.fromisoformat(str(data["timestamp"]).replace("Z", "+00:00"))
    return CalibrationSnapshot(
        backend=str(data["backend"]),
        timestamp=timestamp,
        schema_version=str(data["schema_version"]),
        properties=data["properties"],
        target=data.get("target"),
        configuration=data.get("configuration"),
    )


def _feature_range(snapshot: CalibrationSnapshot, field: str) -> tuple[float, float]:
    values = [
        float(entry["value"])
        for qubit in snapshot.properties["qubits"]
        for entry in qubit
        if entry.get("name") == field
        and entry.get("value") is not None
        and math.isfinite(float(entry["value"]))
    ]
    if not values:
        raise ValueError(f"benchmark fixture has no finite {field} values")
    lo, hi = min(values), max(values)
    if lo == hi:
        raise ValueError(f"benchmark fixture has no {field} range")
    return lo, hi


def _benchmark_ensemble_for_seed(
    snapshot: CalibrationSnapshot, seed: int, ensemble_size: int = 1
) -> FuzzyNoiseModelEnsemble:
    """Build the issue #58 one-member, 3x3x3 Gaussian test ensemble."""
    vectorizer = BasicCalibrationVectorizer()
    fields = ("T1", "T2", "readout_error")
    per_input_mfs: list[list[GaussianMF]] = []
    for field in fields:
        lo, hi = _feature_range(snapshot, field)
        sigma = (hi - lo) * 0.25
        per_input_mfs.append(
            [GaussianMF(center=float(center), sigma=sigma) for center in np.linspace(lo, hi, 3)]
        )
    return FuzzyNoiseModelEnsemble(
        calibration=snapshot,
        feature_extractor=vectorizer,
        rule_base=TSKRuleBase.from_grid(
            per_input_mfs=per_input_mfs,
            output_dim=2,
            consequent_init="random",
            rng=np.random.default_rng(seed),
        ),
        defuzzifier=WeightedAverageDefuzzifier(),
        squashing=ProbabilityClip(),
        channel_projector=KrausChannelProjector(NoOpNormalization()),
        fuzzification_strategy=PostGateFuzzification(),
        ensemble_size=ensemble_size,
    )


@pytest.fixture(scope="session")
def make_benchmark_ensemble(
    benchmark_snapshot: CalibrationSnapshot,
) -> Callable[..., FuzzyNoiseModelEnsemble]:
    """Build viable issue #58 engines of a requested size from one fixed seed."""
    _members, seed = first_viable_seed(
        lambda candidate: list(_benchmark_ensemble_for_seed(benchmark_snapshot, candidate)),
        context="issue #58 committed-fixture 3x3x3 Gaussian grid",
    )

    def _factory(
        ensemble_size: int = 1,
        *,
        snapshot: CalibrationSnapshot | None = None,
    ) -> FuzzyNoiseModelEnsemble:
        selected_snapshot = benchmark_snapshot if snapshot is None else snapshot
        return _benchmark_ensemble_for_seed(selected_snapshot, seed, ensemble_size)

    return _factory


@pytest.fixture(scope="session")
def benchmark_ensemble(
    make_benchmark_ensemble: Callable[..., FuzzyNoiseModelEnsemble],
) -> FuzzyNoiseModelEnsemble:
    """Return the first viable one-member engine, avoiding ADR-024's identity trap."""
    return make_benchmark_ensemble(1)


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
