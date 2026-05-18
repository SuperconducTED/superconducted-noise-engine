"""Concrete :class:`FuzzificationStrategy` implementations.

Bootstrap status:

- :class:`PostGateFuzzification` is fully implemented (Aer-default
  placement; errors fire after target gates).
- :class:`PreGateFuzzification` and :class:`BetweenGatesFuzzification`
  are stubs — they raise :class:`NotImplementedError` until ADR-007 picks
  one (or both) and lands an implementation.
"""

from __future__ import annotations

from collections.abc import Callable

from qiskit.circuit import Instruction, QuantumCircuit
from qiskit_aer.noise import NoiseModel, QuantumError

from ..interfaces import FuzzificationStrategy

_NOISELESS_INSTRUCTIONS: frozenset[str] = frozenset({"barrier", "measure", "reset"})


class PostGateFuzzification(FuzzificationStrategy):
    """Aer-default placement: errors fire AFTER target gates.

    Walks the circuit's instructions; for each (gate, qubits) pair that
    has not already been registered, calls ``error_provider`` and adds
    the resulting :class:`QuantumError` to the noise model via
    :meth:`NoiseModel.add_quantum_error`. Returns the original circuit
    unchanged and the augmented noise model.
    """

    def install(
        self,
        circuit: QuantumCircuit,
        noise_model: NoiseModel,
        error_provider: Callable[[Instruction, tuple[int, ...]], QuantumError],
    ) -> tuple[QuantumCircuit, NoiseModel]:
        qubit_index = {q: i for i, q in enumerate(circuit.qubits)}
        registered: set[tuple[str, tuple[int, ...]]] = set()
        for instr in circuit.data:
            gate = instr.operation
            name = gate.name
            if not name or name in _NOISELESS_INSTRUCTIONS:
                continue
            qubits = tuple(qubit_index[q] for q in instr.qubits)
            key = (name, qubits)
            if key in registered:
                continue
            registered.add(key)
            error = error_provider(gate, qubits)
            if error is None:
                continue
            noise_model.add_quantum_error(error, name, list(qubits))
        return circuit, noise_model


class PreGateFuzzification(FuzzificationStrategy):
    """Pre-gate placement: errors fire BEFORE target gates.

    Bootstrap status: stub. Raises :class:`NotImplementedError` until
    ADR-007.
    """

    def install(
        self,
        circuit: QuantumCircuit,
        noise_model: NoiseModel,
        error_provider: Callable[[Instruction, tuple[int, ...]], QuantumError],
    ) -> tuple[QuantumCircuit, NoiseModel]:
        raise NotImplementedError(
            "PreGateFuzzification is deferred to ADR-007. Use PostGateFuzzification "
            "for the bootstrap experiments."
        )


class BetweenGatesFuzzification(FuzzificationStrategy):
    """Between-gates placement: decompose target gates and interleave errors.

    Bootstrap status: stub. Raises :class:`NotImplementedError` until
    ADR-007.
    """

    def install(
        self,
        circuit: QuantumCircuit,
        noise_model: NoiseModel,
        error_provider: Callable[[Instruction, tuple[int, ...]], QuantumError],
    ) -> tuple[QuantumCircuit, NoiseModel]:
        raise NotImplementedError(
            "BetweenGatesFuzzification is deferred to ADR-007. Use "
            "PostGateFuzzification for the bootstrap experiments."
        )
