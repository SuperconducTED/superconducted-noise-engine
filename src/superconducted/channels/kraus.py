"""LOCKED. Kraus operator construction with CPTP guarantees.

Maps crisp parameter vectors (output of the TSK pipeline) to
:class:`qiskit_aer.noise.QuantumError` via Kraus-operator decomposition.
The supplied :class:`NormalizationStrategy` is applied to the candidate
Kraus set before wrapping in a :class:`QuantumError`.

Bootstrap status:

- :class:`KrausChannelProjector` — full for single-qubit gates with the
  composed amplitude+phase damping channel.
- :class:`NoOpNormalization` — full.
- :class:`CPTPProjectionNormalization` — stub (deferred to ADR-008; needs
  an SDP-solver dependency decision).
- :class:`DerivativeBasedNormalization` — stub (deferred to ADR-008).

Mathematical reference (CPTP condition: ``sum_i K_i^dagger K_i = I``):

The composed amplitude+phase damping channel uses parameters
``gamma in [0, 1]`` (amplitude damping) and ``lambda in [0, 1]`` (phase
damping). Single-qubit Kraus operators::

    K_amp_0 = [[1, 0], [0, sqrt(1 - gamma)]]
    K_amp_1 = [[0, sqrt(gamma)], [0, 0]]
    K_phs_0 = [[1, 0], [0, sqrt(1 - lambda)]]
    K_phs_1 = [[0, 0], [0, sqrt(lambda)]]

Composition produces 4 Kraus operators ``K_amp_i @ K_phs_j`` whose sum of
``K^dagger K`` is the identity by direct algebra (verified in tests).
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
from qiskit.quantum_info import Kraus
from qiskit_aer.noise import QuantumError

from ..interfaces import ChannelProjector, NormalizationStrategy

_SINGLE_QUBIT_GATES: frozenset[str] = frozenset(
    {
        "id",
        "x",
        "y",
        "z",
        "h",
        "s",
        "sdg",
        "sx",
        "sxdg",
        "t",
        "tdg",
        "rx",
        "ry",
        "rz",
        "u",
        "u1",
        "u2",
        "u3",
        "p",
    }
)


def _amplitude_damping_kraus(gamma: float) -> list[npt.NDArray[np.complex128]]:
    """Single-qubit amplitude-damping Kraus operators for parameter ``gamma``."""
    g = max(0.0, min(1.0, float(gamma)))
    sqrt_g = math.sqrt(g)
    sqrt_1mg = math.sqrt(1.0 - g)
    k0 = np.array([[1.0, 0.0], [0.0, sqrt_1mg]], dtype=np.complex128)
    k1 = np.array([[0.0, sqrt_g], [0.0, 0.0]], dtype=np.complex128)
    return [k0, k1]


def _phase_damping_kraus(lam: float) -> list[npt.NDArray[np.complex128]]:
    """Single-qubit phase-damping Kraus operators for parameter ``lambda``."""
    lam_c = max(0.0, min(1.0, float(lam)))
    sqrt_l = math.sqrt(lam_c)
    sqrt_1ml = math.sqrt(1.0 - lam_c)
    k0 = np.array([[1.0, 0.0], [0.0, sqrt_1ml]], dtype=np.complex128)
    k1 = np.array([[0.0, 0.0], [0.0, sqrt_l]], dtype=np.complex128)
    return [k0, k1]


def _compose_channels(
    kraus_a: list[npt.NDArray[np.complex128]],
    kraus_b: list[npt.NDArray[np.complex128]],
) -> list[npt.NDArray[np.complex128]]:
    """Sequential composition of two Kraus channels.

    For independent channels A then B, the composite Kraus set is the
    matrix-product Cartesian product ``{A_i @ B_j : i, j}``.
    """
    return [np.asarray(a @ b, dtype=np.complex128) for a in kraus_a for b in kraus_b]


class KrausChannelProjector(ChannelProjector):
    """Build single-qubit composed amplitude+phase damping noise channels.

    The crisp parameter vector is interpreted as ``[p_amp, p_phase, ...]``;
    additional entries are ignored at bootstrap. Two-qubit gates raise
    :class:`NotImplementedError` until ADR-008 lands a multi-qubit
    extension.

    The supplied normalization is applied to the candidate Kraus set
    before wrapping in :class:`QuantumError`.
    """

    def __init__(self, normalization: NormalizationStrategy) -> None:
        self._normalization = normalization

    def project(
        self,
        crisp_params: npt.NDArray[np.float64],
        gate_name: str,
        qubits: tuple[int, ...],
    ) -> QuantumError:
        if len(qubits) != 1:
            raise NotImplementedError(
                f"KrausChannelProjector currently supports single-qubit gates only; "
                f"got gate {gate_name!r} on qubits {qubits}. Multi-qubit channels "
                f"are deferred to ADR-008."
            )
        if crisp_params.size < 2:
            raise ValueError(
                f"crisp_params must contain at least 2 entries (p_amp, p_phase); "
                f"got shape {crisp_params.shape}"
            )
        gamma = float(crisp_params.flat[0])
        lam = float(crisp_params.flat[1])
        amp_kraus = _amplitude_damping_kraus(gamma)
        phase_kraus = _phase_damping_kraus(lam)
        composed = _compose_channels(amp_kraus, phase_kraus)
        normalized = self._normalization.normalize(composed)
        return QuantumError(Kraus(normalized))


class NoOpNormalization(NormalizationStrategy):
    """Pass-through normalization. Caller MUST guarantee CPTP."""

    def normalize(
        self,
        kraus_ops: list[npt.NDArray[np.complex128]],
    ) -> list[npt.NDArray[np.complex128]]:
        return [np.asarray(k, dtype=np.complex128) for k in kraus_ops]


class CPTPProjectionNormalization(NormalizationStrategy):
    """Project a candidate Kraus set onto the CPTP cone via Choi SDP.

    Bootstrap status: stub. Raises :class:`NotImplementedError`. The
    implementation will require an SDP solver (cvxpy or a hand-rolled
    scipy-based projection) — that dependency choice is itself ADR-008.
    """

    def normalize(
        self,
        kraus_ops: list[npt.NDArray[np.complex128]],
    ) -> list[npt.NDArray[np.complex128]]:
        raise NotImplementedError(
            "CPTPProjectionNormalization is deferred to ADR-008. Use "
            "NoOpNormalization while the bootstrap channel construction is "
            "CPTP-by-construction."
        )


class DerivativeBasedNormalization(NormalizationStrategy):
    """Derivative-based CPTP normalization with tunable damping coefficient.

    Bootstrap status: stub. Raises :class:`NotImplementedError`.
    """

    def __init__(self, lambda_coeff: float = 1.0) -> None:
        self._lambda_coeff = float(lambda_coeff)

    def normalize(
        self,
        kraus_ops: list[npt.NDArray[np.complex128]],
    ) -> list[npt.NDArray[np.complex128]]:
        raise NotImplementedError("DerivativeBasedNormalization is deferred to ADR-008.")
