"""Thermal-relaxation reference models derived from calibration snapshots.

The builder converts IBM calibration units at the module boundary, applies
ADR-017's non-imputing skip rule, and returns a plain Aer ``NoiseModel``.
Provenance is available separately through :func:`build_reference_report`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from qiskit_aer.noise import NoiseModel, ReadoutError, thermal_relaxation_error

from ..types import CalibrationSnapshot

ReferenceScope = Literal["single_qubit_relaxation", "full_device"]

_NON_UNITARY_GATE_NAMES = frozenset({"measure", "measure_2", "reset"})
_TIME_UNIT_SCALE = {"us": 1e-6, "ns": 1e-9}
_SKIP_REASONS = ("missing_t1_t2", "t2_exceeds_2t1")


@dataclass(frozen=True)
class ReferenceReport:
    """Auditable provenance for one reference-model build.

    ``gate_lengths_s`` includes considered zero-duration gates even though
    their identity channels are deliberately not installed. ``dead_pairs``
    records directed ``cz`` entries with ``gate_error == 1``; ADR-017 still
    prevents installation when either endpoint lacks usable T1/T2 data.
    """

    scope: str
    qubits_used: tuple[int, ...]
    skipped: Mapping[str, tuple[int, ...]]
    gate_lengths_s: Mapping[tuple[str, tuple[int, ...]], float]
    overridden_gate_lengths: tuple[str, ...]
    dead_pairs: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class _QubitParameters:
    t1_s: float
    t2_s: float
    prob_meas0_prep1: float | None
    prob_meas1_prep0: float | None


def _validate_scope(scope: str) -> ReferenceScope:
    if scope not in ("single_qubit_relaxation", "full_device"):
        raise ValueError(f"scope must be 'single_qubit_relaxation' or 'full_device'; got {scope!r}")
    return scope  # type: ignore[return-value]


def _named_entries(raw_entries: Any, *, context: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(raw_entries, list):
        raise ValueError(f"{context} must be a list; got {type(raw_entries).__name__}")
    by_name: dict[str, Mapping[str, Any]] = {}
    for position, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, Mapping):
            raise ValueError(f"{context}[{position}] must be a mapping")
        name = raw_entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{context}[{position}] has no non-empty name")
        if name in by_name:
            raise ValueError(f"{context} contains duplicate field {name!r}")
        by_name[name] = raw_entry
    return by_name


def _read_quantity(
    entries: Mapping[str, Mapping[str, Any]],
    name: str,
    expected_unit: str,
    *,
    context: str,
    missing_ok: bool,
) -> float | None:
    entry = entries.get(name)
    if entry is None:
        if missing_ok:
            return None
        raise ValueError(f"{context} is missing required field {name!r}")
    actual_unit = entry.get("unit")
    if actual_unit != expected_unit:
        raise ValueError(
            f"{context} field {name!r}: expected unit {expected_unit!r}, got {actual_unit!r}"
        )
    raw_value = entry.get("value")
    if raw_value is None:
        if missing_ok:
            return None
        raise ValueError(f"{context} field {name!r} has null value")
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} field {name!r} is not numeric: {raw_value!r}") from exc
    if not math.isfinite(value):
        if missing_ok:
            return None
        raise ValueError(f"{context} field {name!r} must be finite; got {value}")
    return value * _TIME_UNIT_SCALE.get(expected_unit, 1.0)


def _selected_qubits(raw_qubits: list[Any], qubits: Sequence[int] | None) -> tuple[int, ...]:
    selected = tuple(range(len(raw_qubits))) if qubits is None else tuple(qubits)
    if len(set(selected)) != len(selected):
        raise ValueError(f"qubits must not contain duplicates; got {selected}")
    invalid = [q for q in selected if not isinstance(q, int) or q < 0 or q >= len(raw_qubits)]
    if invalid:
        raise ValueError(
            f"qubits contains indices outside [0, {len(raw_qubits)}): {tuple(invalid)}"
        )
    return selected


def _qubit_parameters(
    raw_qubits: list[Any], selected: tuple[int, ...]
) -> tuple[dict[int, _QubitParameters], dict[str, tuple[int, ...]]]:
    usable: dict[int, _QubitParameters] = {}
    skipped: dict[str, list[int]] = {reason: [] for reason in _SKIP_REASONS}
    for q in selected:
        entries = _named_entries(raw_qubits[q], context=f"properties.qubits[{q}]")
        t1_s = _read_quantity(
            entries, "T1", "us", context=f"properties.qubits[{q}]", missing_ok=True
        )
        t2_s = _read_quantity(
            entries, "T2", "us", context=f"properties.qubits[{q}]", missing_ok=True
        )
        if t1_s is None or t2_s is None:
            skipped["missing_t1_t2"].append(q)
            continue
        if t1_s <= 0.0 or t2_s <= 0.0:
            raise ValueError(f"qubit {q} requires positive T1 and T2; got {t1_s}, {t2_s}")
        if t2_s > 2.0 * t1_s:
            skipped["t2_exceeds_2t1"].append(q)
            continue
        p01 = _read_quantity(
            entries,
            "prob_meas0_prep1",
            "",
            context=f"properties.qubits[{q}]",
            missing_ok=True,
        )
        p10 = _read_quantity(
            entries,
            "prob_meas1_prep0",
            "",
            context=f"properties.qubits[{q}]",
            missing_ok=True,
        )
        usable[q] = _QubitParameters(
            t1_s=t1_s,
            t2_s=t2_s,
            prob_meas0_prep1=p01,
            prob_meas1_prep0=p10,
        )
    return usable, {reason: tuple(indices) for reason, indices in skipped.items()}


def _gate_entries(snapshot: CalibrationSnapshot) -> list[Mapping[str, Any]]:
    raw_gates = snapshot.properties.get("gates")
    if not isinstance(raw_gates, list):
        raise ValueError("snapshot.properties['gates'] must be a list")
    gates: list[Mapping[str, Any]] = []
    for position, entry in enumerate(raw_gates):
        if not isinstance(entry, Mapping):
            raise ValueError(f"properties.gates[{position}] must be a mapping")
        gates.append(entry)
    return gates


def _basis_gates(gates: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    names = {
        name
        for gate in gates
        if isinstance((name := gate.get("gate")), str)
        and name
        and name not in _NON_UNITARY_GATE_NAMES
    }
    if not names:
        raise ValueError("snapshot.properties['gates'] contains no unitary gate names")
    return tuple(sorted(names))


def _validated_overrides(gate_lengths: Mapping[str, float] | None) -> dict[str, float]:
    if gate_lengths is None:
        return {}
    overrides: dict[str, float] = {}
    for name, raw_value in gate_lengths.items():
        if not isinstance(name, str) or not name:
            raise ValueError("gate_lengths keys must be non-empty strings")
        value = float(raw_value)
        if not math.isfinite(value) or value < 0.0:
            raise ValueError(
                f"gate_lengths[{name!r}] must be a finite, non-negative number of seconds; "
                f"got {raw_value!r}"
            )
        overrides[name] = value
    return overrides


def _gate_qubits(entry: Mapping[str, Any], *, context: str) -> tuple[int, ...]:
    raw_qubits = entry.get("qubits")
    if not isinstance(raw_qubits, list) or not raw_qubits:
        raise ValueError(f"{context}.qubits must be a non-empty list")
    if any(not isinstance(q, int) or q < 0 for q in raw_qubits):
        raise ValueError(f"{context}.qubits must contain non-negative integers")
    return tuple(raw_qubits)


def _gate_length_s(
    entry: Mapping[str, Any], gate_name: str, overrides: Mapping[str, float], *, context: str
) -> float:
    if gate_name in overrides:
        return overrides[gate_name]
    parameters = _named_entries(entry.get("parameters"), context=f"{context}.parameters")
    length = _read_quantity(
        parameters, "gate_length", "ns", context=f"{context}.parameters", missing_ok=False
    )
    assert length is not None
    if length < 0.0:
        raise ValueError(f"{context} gate_length must be non-negative; got {length}")
    return length


def _is_dead_cz(entry: Mapping[str, Any], *, context: str) -> bool:
    if entry.get("gate") != "cz":
        return False
    parameters = _named_entries(entry.get("parameters"), context=f"{context}.parameters")
    error = _read_quantity(
        parameters, "gate_error", "", context=f"{context}.parameters", missing_ok=True
    )
    return error == 1.0


def _readout_error(params: _QubitParameters, q: int) -> ReadoutError:
    p01 = params.prob_meas0_prep1
    p10 = params.prob_meas1_prep0
    if p01 is None or p10 is None:
        raise ValueError(
            f"full_device scope requires prob_meas0_prep1 and prob_meas1_prep0 for qubit {q}"
        )
    if not (0.0 <= p01 <= 1.0 and 0.0 <= p10 <= 1.0):
        raise ValueError(f"qubit {q} readout probabilities must lie in [0, 1]; got {p01}, {p10}")
    return ReadoutError([[1.0 - p10, p10], [p01, 1.0 - p01]])


def _build(
    snapshot: CalibrationSnapshot,
    *,
    scope: ReferenceScope,
    gate_lengths: Mapping[str, float] | None,
    qubits: Sequence[int] | None,
) -> tuple[NoiseModel, ReferenceReport]:
    raw_qubits = snapshot.properties.get("qubits")
    if not isinstance(raw_qubits, list):
        raise ValueError("snapshot.properties['qubits'] must be a list")
    selected = _selected_qubits(raw_qubits, qubits)
    selected_set = set(selected)
    usable, skipped = _qubit_parameters(raw_qubits, selected)
    gates = _gate_entries(snapshot)
    basis = _basis_gates(gates)
    overrides = _validated_overrides(gate_lengths)
    model = NoiseModel(basis_gates=list(basis))
    lengths: dict[tuple[str, tuple[int, ...]], float] = {}
    dead_pairs: list[tuple[int, int]] = []
    override_names_used: set[str] = set()
    seen_gate_keys: set[tuple[str, tuple[int, ...]]] = set()
    used_qubits: set[int] = set()

    for position, entry in enumerate(gates):
        context = f"properties.gates[{position}]"
        gate_name = entry.get("gate")
        if not isinstance(gate_name, str) or not gate_name:
            raise ValueError(f"{context}.gate must be a non-empty string")
        if gate_name in _NON_UNITARY_GATE_NAMES:
            continue
        gate_qubits = _gate_qubits(entry, context=context)
        if not set(gate_qubits).issubset(selected_set):
            continue
        if len(gate_qubits) > 2:
            raise ValueError(
                f"{context} gate {gate_name!r} acts on {len(gate_qubits)} qubits; "
                "the reference builder supports at most two"
            )
        if scope == "single_qubit_relaxation" and len(gate_qubits) != 1:
            continue
        key = (gate_name, gate_qubits)
        if key in seen_gate_keys:
            raise ValueError(f"snapshot contains duplicate gate calibration for {key!r}")
        seen_gate_keys.add(key)
        if scope == "full_device" and len(gate_qubits) == 2 and _is_dead_cz(entry, context=context):
            dead_pairs.append((gate_qubits[0], gate_qubits[1]))
        if any(q not in usable for q in gate_qubits):
            continue
        length_s = _gate_length_s(entry, gate_name, overrides, context=context)
        lengths[key] = length_s
        if gate_name in overrides:
            override_names_used.add(gate_name)
        if length_s == 0.0:
            continue
        if len(gate_qubits) == 1:
            q = gate_qubits[0]
            params = usable[q]
            error = thermal_relaxation_error(params.t1_s, params.t2_s, length_s)
        else:
            qa, qb = gate_qubits
            params_a = usable[qa]
            params_b = usable[qb]
            error_a = thermal_relaxation_error(params_a.t1_s, params_a.t2_s, length_s)
            error_b = thermal_relaxation_error(params_b.t1_s, params_b.t2_s, length_s)
            error = error_a.expand(error_b)
        model.add_quantum_error(error, gate_name, list(gate_qubits))
        used_qubits.update(gate_qubits)

    if scope == "full_device":
        for q, params in usable.items():
            model.add_readout_error(_readout_error(params, q), [q])
            used_qubits.add(q)

    report = ReferenceReport(
        scope=scope,
        qubits_used=tuple(sorted(used_qubits)),
        skipped=skipped,
        gate_lengths_s=dict(sorted(lengths.items())),
        overridden_gate_lengths=tuple(sorted(override_names_used)),
        dead_pairs=tuple(sorted(dead_pairs)),
    )
    return model, report


def build_reference(
    snapshot: CalibrationSnapshot,
    *,
    scope: ReferenceScope,
    gate_lengths: Mapping[str, float] | None = None,
    qubits: Sequence[int] | None = None,
) -> NoiseModel:
    """Build a plain thermal-relaxation ``NoiseModel`` from ``snapshot``.

    ``single_qubit_relaxation`` installs only positive-duration one-qubit
    gate errors. ``full_device`` additionally installs two-qubit product
    channels and per-qubit readout errors. ``gate_lengths`` overrides are in
    SI seconds. Missing or unphysical T1/T2 values are never imputed.
    """
    checked_scope = _validate_scope(scope)
    model, _report = _build(
        snapshot,
        scope=checked_scope,
        gate_lengths=gate_lengths,
        qubits=qubits,
    )
    return model


def build_reference_report(
    snapshot: CalibrationSnapshot,
    *,
    scope: ReferenceScope,
    gate_lengths: Mapping[str, float] | None = None,
    qubits: Sequence[int] | None = None,
) -> ReferenceReport:
    """Return deterministic provenance for :func:`build_reference`.

    The arguments and filtering rules are identical to the model builder;
    this separate return type keeps ``run_benchmark``'s reference parameter a
    plain Aer ``NoiseModel``.
    """
    checked_scope = _validate_scope(scope)
    _model, report = _build(
        snapshot,
        scope=checked_scope,
        gate_lengths=gate_lengths,
        qubits=qubits,
    )
    return report
