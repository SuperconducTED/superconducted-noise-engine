"""Boundary contract of the LOCKED ``channels/kraus.py`` projector (#75).

Two decisions are pinned here:

* the projector is gate-name agnostic; gate eligibility belongs to
  ``FuzzyNoiseModel.prepare()`` (#73);
* ``gamma`` / ``lambda`` outside ``[0, 1]`` or non-finite are rejected, never
  clipped. Clipping is the pipeline's job (``ProbabilityClip``, ADR-012), and a
  channel-level clamp turned NaN into maximal damping while
  ``is_identity_damping`` called the same vector the identity.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
import pytest
from qiskit.quantum_info import Kraus, SuperOp

from superconducted.channels import kraus as kraus_module
from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization


def _reference_superop(gamma: float, lam: float) -> SuperOp:
    """Independent re-derivation of the composed channel (pre-#75 behavior)."""
    amp = [
        np.array([[1.0, 0.0], [0.0, math.sqrt(1.0 - gamma)]], dtype=np.complex128),
        np.array([[0.0, math.sqrt(gamma)], [0.0, 0.0]], dtype=np.complex128),
    ]
    phs = [
        np.array([[1.0, 0.0], [0.0, math.sqrt(1.0 - lam)]], dtype=np.complex128),
        np.array([[0.0, 0.0], [0.0, math.sqrt(lam)]], dtype=np.complex128),
    ]
    return SuperOp(Kraus([a @ p for a in amp for p in phs]))


def _project(params: list[float], gate: str = "sx") -> npt.NDArray[np.complex128]:
    projector = KrausChannelProjector(NoOpNormalization())
    error = projector.project(np.asarray(params, dtype=np.float64), gate, (0,))
    return np.asarray(SuperOp(error.to_quantumchannel()).data)


@pytest.mark.parametrize(
    ("gamma", "lam"),
    [(0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0), (0.2, 0.1), (0.37, 0.91), (1e-9, 0.5)],
)
def test_in_range_channels_are_unchanged(gamma: float, lam: float) -> None:
    got = _project([gamma, lam])
    assert np.abs(got - _reference_superop(gamma, lam).data).max() < 1e-12


@pytest.mark.parametrize("gate", ["id", "x", "sx", "rz", "u3", "cx", "measure", "anything"])
def test_projector_is_gate_name_agnostic(gate: str) -> None:
    baseline = _project([0.2, 0.1], "sx")
    assert np.abs(_project([0.2, 0.1], gate) - baseline).max() == 0.0


def test_unused_gate_allowlist_is_removed() -> None:
    assert not hasattr(kraus_module, "_SINGLE_QUBIT_GATES")


@pytest.mark.parametrize("bad", [-0.1, -1e-12, 1.0 + 1e-12, 1.5, np.nan, np.inf, -np.inf])
@pytest.mark.parametrize("position", [0, 1])
def test_out_of_domain_parameters_are_rejected(bad: float, position: int) -> None:
    params = [0.2, 0.1]
    params[position] = bad
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        _project(params)


def test_extra_entries_are_still_ignored() -> None:
    assert np.abs(_project([0.2, 0.1, 99.0, np.nan]) - _project([0.2, 0.1])).max() == 0.0
