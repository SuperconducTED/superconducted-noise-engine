"""Offline half of the #125 hardware test: circuits, predictions, scoring and the Aer dry run.

Arm A (decay): per qubit, ``x``, ``delay(tau)``, measure, on the seven-slot union grid
``{0} U {0.5, 1, 2} x T1_level U {0.5, 1, 2} x T1_reading`` (proposal C), every qubit of a job in
one circuit per slot, predicted by the design's closed form. Arm B (layout):
``ghz_state_circuit(3)`` plus an idle block of half the layout's median ``T1_level``, on six
connected triples spanning the ``level`` prediction, predicted by one Aer noise-model builder
shared by every predictor.
Scoring follows design section 3 and 4; the decision rule itself is the pre-registration's.

The predictors' predictions all come from one builder; the dry run's truth comes from a
different path, ``NoiseModel.from_backend`` on a backend rebuilt from an archived snapshot.
Plan, protocol and the dry run's acceptance criteria:
``docs/implementations/2026-10-28-hardware-test-offline-half.md``. Design:
``docs/roadmap/2026-10-23-hardware-reading-vs-level-test.md``.

This script submits nothing and never reads the IBM token. Usage::

    python -m scripts.hardware_reading_vs_level --repo . --ref <sha> --at <t_s> \\
        --controls controls.json --execution-ref <sha> --execution-at <t_execute> \\
        --out <dir>
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from itertools import combinations, pairwise
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import qiskit
import qiskit_aer
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Delay
from qiskit.providers import BackendV2, Options
from qiskit.transpiler import Target
from qiskit_aer import AerSimulator
from qiskit_aer.noise import (
    NoiseModel,
    RelaxationNoisePass,
    depolarizing_error,
    thermal_relaxation_error,
)
from qiskit_ibm_runtime.models import BackendConfiguration, BackendProperties
from qiskit_ibm_runtime.utils.backend_converter import convert_to_target

from scripts.hardware_test_predictors import (
    MIN_WINDOW_DISTINCT,
    Collected,
    PredictorRow,
    collect,
    execution_rows,
    load_controls,
    predictor_rows,
    select_balanced,
)
from superconducted.benchmarks.circuits import ghz_state_circuit
from superconducted.training.dataset import iter_archive, resolve_archive_ref

# (slot name, T1 source, factor); the zero slot first so a rounded zero is never a duplicate.
SLOTS: tuple[tuple[str, str | None, float], ...] = (
    ("zero", None, 0.0),
    ("level_x0.5", "level", 0.5),
    ("level_x1", "level", 1.0),
    ("level_x2", "level", 2.0),
    ("reading_x0.5", "reading", 0.5),
    ("reading_x1", "reading", 1.0),
    ("reading_x2", "reading", 2.0),
)
ARM_A_SHOTS = 2048
ARM_B_SHOTS = 4096
N_LAYOUTS = 6
IDLE_FRACTION = 0.5
SEED = 125
POINT_PREDICTORS: tuple[str, ...] = ("reading", "level", "reading_at_execution")
SOURCES: tuple[str, ...] = (*POINT_PREDICTORS, "band_lo", "band_hi")
_UNIT_SCALE = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "µs": 1e-6, "ns": 1e-9}


class UnusableSourceError(ValueError):
    """A predictor has no usable value for a qubit (missing, non-positive, or ``T2 > 2 T1``)."""


@dataclass(frozen=True)
class QubitSource:
    """One predictor's values for one qubit: ``T1``, ``T2`` in seconds, assignment errors.

    ``e10`` is ``prob_meas0_prep1`` (prepared 1, read 0) and ``e01`` is ``prob_meas1_prep0``.
    """

    t1: float
    t2: float
    e10: float
    e01: float

    def usable_for_decay(self) -> bool:
        return (
            math.isfinite(self.t1)
            and self.t1 > 0.0
            and all(math.isfinite(e) and 0.0 <= e <= 1.0 for e in (self.e10, self.e01))
        )

    def usable_for_relaxation(self) -> bool:
        """ADR-027's rule: positive finite ``T1`` and ``T2``, and ``T2 <= 2 T1`` (no capping)."""
        return self.usable_for_decay() and math.isfinite(self.t2) and 0.0 < self.t2 <= 2.0 * self.t1


def sources_from_rows(
    rows: Sequence[PredictorRow], execution: Sequence[PredictorRow]
) -> dict[str, dict[int, QubitSource]]:
    """Per predictor, per qubit: the values each predictor carries (design section 2).

    The band's two ends take ``T1`` and ``T2`` from the band and readout from the level.
    """
    table: dict[tuple[int, str], PredictorRow] = {(r.qubit, r.quantity): r for r in rows}
    later: dict[tuple[int, str], PredictorRow] = {(r.qubit, r.quantity): r for r in execution}
    qubits = sorted({r.qubit for r in rows})
    out: dict[str, dict[int, QubitSource]] = {name: {} for name in SOURCES}
    nan = math.nan

    def get(tab: Mapping[tuple[int, str], PredictorRow], q: int, quantity: str, attr: str) -> float:
        row = tab.get((q, quantity))
        return float(getattr(row, attr)) if row is not None else nan

    for q in qubits:
        for name, attr in (("reading", "reading"), ("level", "level")):
            out[name][q] = QubitSource(
                get(table, q, "T1", attr),
                get(table, q, "T2", attr),
                get(table, q, "prob_meas0_prep1", attr),
                get(table, q, "prob_meas1_prep0", attr),
            )
        e10 = get(table, q, "prob_meas0_prep1", "level")
        e01 = get(table, q, "prob_meas1_prep0", "level")
        for name, attr in (("band_lo", "band_lo"), ("band_hi", "band_hi")):
            out[name][q] = QubitSource(
                get(table, q, "T1", attr), get(table, q, "T2", attr), e10, e01
            )
        out["reading_at_execution"][q] = QubitSource(
            get(later, q, "T1", "reading"),
            get(later, q, "T2", "reading"),
            get(later, q, "prob_meas0_prep1", "reading"),
            get(later, q, "prob_meas1_prep0", "reading"),
        )
    return out


# ---------------------------------------------------------------------------------------------
# Arm A


def delay_slots(
    t1_level: float, t1_reading: float, *, dt: float, min_length: int = 2
) -> list[int | None]:
    """The seven slots in ``dt`` units; a slot that repeats an earlier one of the qubit is None.

    Rounded to the nearest ``dt``; a non-zero delay below ``min_length`` is raised to it.
    """
    for value in (t1_level, t1_reading):
        if not (math.isfinite(value) and value > 0.0):
            raise UnusableSourceError(f"delay grid needs positive finite T1, got {value!r}")
    out: list[int | None] = []
    seen: set[int] = set()
    for _name, source, factor in SLOTS:
        tau = 0.0 if source is None else factor * (t1_level if source == "level" else t1_reading)
        n = round(tau / dt)
        if 0 < n < min_length:
            n = min_length
        if n in seen:
            out.append(None)
        else:
            seen.add(n)
            out.append(n)
    return out


def arm_a_circuit(
    slot: int,
    durations: Mapping[int, int | None],
    x_lengths_dt: Mapping[int, int],
    n_qubits: int,
) -> QuantumCircuit:
    """One slot's circuit: every active qubit ends ``x`` then ``delay(tau)`` at one measurement.

    The backend measures every qubit at once (one ``meas_map`` group), so a lead delay before
    each ``x`` makes ``x + tau`` end at the same instant for all qubits, and a barrier holds
    the measurement there: no qubit idles between its delay and its measurement. Clbit ``i``
    belongs to ``metadata["qubits"][i]``.
    """
    active = [q for q in sorted(durations) if durations[q] is not None]
    if not active:
        raise ValueError(f"slot {slot} has no active qubit")
    total = {q: x_lengths_dt[q] + int(durations[q] or 0) for q in active}
    horizon = max(total.values())
    qc = QuantumCircuit(n_qubits, len(active), name=f"arm_a_{SLOTS[slot][0]}")
    for q in active:
        lead = horizon - total[q]
        if lead > 0:
            qc.delay(lead, q, unit="dt")
        qc.x(q)
        tau = int(durations[q] or 0)
        if tau > 0:
            qc.delay(tau, q, unit="dt")
    qc.barrier(active)
    for i, q in enumerate(active):
        qc.measure(q, i)
    qc.metadata = {"arm": "A", "slot": slot, "slot_name": SLOTS[slot][0], "qubits": active}
    return qc


def p1_closed_form(tau_s: float, source: QubitSource) -> float:
    """Design section 3: ``p_1 = (1 - e_10) s + e_01 (1 - s)``, ``s = exp(-tau / T1)``."""
    if not source.usable_for_decay():
        raise UnusableSourceError("closed form needs a positive T1 and assignment errors in [0, 1]")
    s = math.exp(-tau_s / source.t1)
    return (1.0 - source.e10) * s + source.e01 * (1.0 - s)


def x_to_measure_intervals(circuit: QuantumCircuit, target: Target) -> dict[int, int]:
    """Schedule ``circuit`` on ``target`` (ASAP) and return, per qubit, ``measure`` start minus
    the end of its last ``x``, in ``dt``. Criterion 5 of the dry run compares this with tau."""
    scheduled = transpile(
        circuit,
        target=target,
        optimization_level=0,
        layout_method="trivial",
        scheduling_method="asap",
    )
    durations = target.durations()
    starts = scheduled.op_start_times
    x_end: dict[int, int] = {}
    measure_start: dict[int, int] = {}
    for instruction, start in zip(scheduled.data, starts, strict=True):
        name = instruction.operation.name
        if name not in ("x", "measure"):
            continue
        q = scheduled.find_bit(instruction.qubits[0]).index
        if name == "x":
            x_end[q] = int(start) + int(durations.get("x", [q], unit="dt"))
        else:
            measure_start[q] = int(start)
    return {q: measure_start[q] - x_end[q] for q in x_end}


# ---------------------------------------------------------------------------------------------
# Arm B


def coupled_pairs(coupling_map: Iterable[Sequence[int]]) -> set[frozenset[int]]:
    return {frozenset((int(a), int(b))) for a, b in coupling_map if int(a) != int(b)}


def connected_triples(pairs: set[frozenset[int]], eligible: set[int]) -> list[tuple[int, int, int]]:
    """Triples ``(b, a, c)`` with ``b`` coupled to both ``a < c``; ``b`` is the GHZ control."""
    out: list[tuple[int, int, int]] = []
    for b in sorted(eligible):
        neighbours = sorted(n for n in eligible if n != b and frozenset((b, n)) in pairs)
        out.extend((b, a, c) for a, c in combinations(neighbours, 2))
    return out


def ghz_idle_circuit(idle_dt: int) -> QuantumCircuit:
    """``ghz_state_circuit(3)``, then ``delay(idle_dt)`` on each qubit, then measurement."""
    qc = ghz_state_circuit(3).remove_final_measurements(inplace=False)
    if idle_dt > 0:
        for i in range(3):
            qc.delay(idle_dt, i, unit="dt")
    qc.measure_all()
    return qc


def transpile_layout(
    circuit: QuantumCircuit, layout: Sequence[int], target: Target, *, seed: int = SEED
) -> QuantumCircuit:
    """Transpile once onto ``layout`` (logical ``i`` on ``layout[i]``); the circuit predicted is
    the circuit submitted. Raises if the transpiler touches any other physical qubit."""
    out = transpile(
        circuit,
        target=target,
        initial_layout=list(layout),
        optimization_level=1,
        seed_transpiler=seed,
    )
    touched = {
        out.find_bit(q).index
        for instruction in out.data
        if instruction.operation.name != "barrier"
        for q in instruction.qubits
    }
    if not touched <= set(layout):
        raise ValueError(f"transpiled circuit leaves the layout {list(layout)}: {sorted(touched)}")
    return out


@dataclass(frozen=True)
class GateTable:
    """From the latest snapshot: single-qubit gate lengths (s) and ``cz`` errors per pair."""

    lengths: dict[tuple[str, int], float]
    cz_error: dict[frozenset[int], float]


def gate_table(properties: Mapping[str, Any]) -> GateTable:
    lengths: dict[tuple[str, int], float] = {}
    cz: dict[frozenset[int], float] = {}
    for entry in properties.get("gates", []):
        params = {p["name"]: p for p in entry.get("parameters", [])}
        qubits = [int(q) for q in entry.get("qubits", [])]
        name = entry.get("gate")
        if name in ("sx", "x") and len(qubits) == 1 and "gate_length" in params:
            p = params["gate_length"]
            lengths[(name, qubits[0])] = float(p["value"]) * _UNIT_SCALE[p.get("unit", "ns")]
        if name == "cz" and len(qubits) == 2 and "gate_error" in params:
            value = params["gate_error"]["value"]
            if value is not None and math.isfinite(float(value)):
                cz[frozenset(qubits)] = float(value)
    return GateTable(lengths, cz)


def usable_cz_error(r: float | None) -> bool:
    """A ``cz`` error the depolarizing form can carry: ``0 <= 4 r / 3 <= 1``."""
    return r is not None and math.isfinite(r) and 0.0 <= 4.0 * r / 3.0 <= 1.0


def build_predictor_noise(
    sources: Mapping[int, QubitSource],
    *,
    qubits: Sequence[int],
    gates: GateTable,
    dt: float,
    n_qubits: int,
) -> NoiseModel:
    """The one Arm B builder, the same for every predictor; only ``sources`` differ.

    Per qubit, ``thermal_relaxation_error`` on ``sx`` and ``x`` with the snapshot's gate
    lengths; ``RelaxationNoisePass`` with the predictor's ``T1``, ``T2`` on ``delay``; on each
    ``cz`` among ``qubits`` a two-qubit depolarizing channel with ``p = 4 r / 3`` from the
    snapshot's ``gate_error`` ``r``, identical across predictors. No readout error here:
    readout is applied afterwards from the predictor's own assignment errors.
    """
    model = NoiseModel(basis_gates=["cz", "id", "rz", "sx", "x"])
    t1s = [math.inf] * n_qubits
    t2s = [math.inf] * n_qubits
    for q in qubits:
        src = sources.get(q)
        if src is None or not src.usable_for_relaxation():
            raise UnusableSourceError(f"qubit {q}: no usable T1, T2 (ADR-027) in {src}")
        t1s[q], t2s[q] = src.t1, src.t2
        for gate in ("sx", "x"):
            length = gates.lengths.get((gate, q), 0.0)
            if length > 0.0:
                model.add_quantum_error(thermal_relaxation_error(src.t1, src.t2, length), gate, [q])
    for a, b in combinations(sorted(qubits), 2):
        r = gates.cz_error.get(frozenset((a, b)))
        if r is None:
            continue
        if not usable_cz_error(r):
            raise UnusableSourceError(f"cz ({a}, {b}) gate_error {r} is not a usable error")
        error = depolarizing_error(4.0 * r / 3.0, 2)
        model.add_quantum_error(error, "cz", [a, b])
        model.add_quantum_error(error, "cz", [b, a])
    # Aer 0.17.2 has no public hook for a custom pass; from_backend appends to this list itself.
    model._custom_noise_passes.append(RelaxationNoisePass(t1s, t2s, dt=dt, op_types=Delay))
    return model


def apply_readout(
    probabilities: npt.NDArray[np.float64], e10: Sequence[float], e01: Sequence[float]
) -> npt.NDArray[np.float64]:
    """Apply per-qubit assignment matrices to a little-endian distribution over ``n`` qubits.

    Qubit ``i`` is bit ``i`` of the index. Its matrix maps true to read:
    ``[[1 - e01, e10], [e01, 1 - e10]]`` (columns: true 0, true 1).
    """
    n = len(e10)
    if len(e01) != n or probabilities.shape != (2**n,):
        raise ValueError("one (e10, e01) pair per qubit and 2**n probabilities")
    tensor = probabilities.reshape([2] * n)  # axis 0 is the most significant qubit, n - 1
    for i in range(n):
        matrix = np.array([[1.0 - e01[i], e10[i]], [e01[i], 1.0 - e10[i]]])
        axis = n - 1 - i
        tensor = np.moveaxis(np.tensordot(matrix, tensor, axes=([1], [axis])), 0, axis)
    return np.asarray(tensor.reshape(-1), dtype=np.float64)


GHZ_IDEAL = np.array([0.5, 0, 0, 0, 0, 0, 0, 0.5], dtype=np.float64)


def hellinger_fidelity(p: npt.NDArray[np.float64], q: npt.NDArray[np.float64]) -> float:
    """``(sum_i sqrt(p_i q_i))^2``, which equals ``(1 - H^2)^2`` with ``benchmarks.metrics``' H."""
    return float(np.sum(np.sqrt(np.clip(p, 0, None) * np.clip(q, 0, None))) ** 2)


def shot_free_distribution(
    circuit: QuantumCircuit, model: NoiseModel, layout: Sequence[int]
) -> npt.NDArray[np.float64]:
    """Exact outcome probabilities before readout: density matrix, final measurements removed."""
    state = circuit.remove_final_measurements(inplace=False)
    state.save_probabilities(qubits=list(layout))
    result = AerSimulator(method="density_matrix", noise_model=model).run(state).result()
    return np.asarray(result.data()["probabilities"], dtype=np.float64)


def choose_layouts(
    predicted: Sequence[tuple[tuple[int, int, int], float]], k: int = N_LAYOUTS
) -> list[tuple[int, int, int]]:
    """``k`` triples spanning best to worst: ranks ``floor(i (n - 1) / (k - 1) + 1/2)``."""
    ranked = sorted(predicted, key=lambda item: (-item[1], tuple(sorted(item[0]))))
    n = len(ranked)
    if n == 0:
        return []
    picks: list[int] = []
    for i in range(k):
        index = math.floor(i * (n - 1) / (k - 1) + 0.5) if k > 1 else 0
        if index not in picks:
            picks.append(index)
    return [ranked[i][0] for i in picks]


# ---------------------------------------------------------------------------------------------
# Scoring


def binomial_log_score(k: int, n: int, p: float) -> float:
    p = min(max(p, 1e-12), 1.0 - 1e-12)
    return k * math.log(p) + (n - k) * math.log(1.0 - p)


def binomial_se(p: float, n: int) -> float:
    return math.sqrt(max(p * (1.0 - p), 0.0) / n)


def paired_bootstrap(
    diffs: Sequence[float],
    groups: Sequence[Any] | None = None,
    *,
    n_boot: int = 10_000,
    seed: int = SEED,
    level: float = 0.90,
) -> tuple[float, float]:
    """Percentile interval of the mean of ``diffs``, resampling rows or whole groups (jobs).

    With groups, each draw takes groups with replacement and averages over all their rows
    (row-weighted).
    """
    values = np.asarray(diffs, dtype=np.float64)
    if values.size == 0:
        raise ValueError("no rows to bootstrap")
    rng = np.random.default_rng(seed)
    if groups is None:
        draws = rng.integers(0, values.size, size=(n_boot, values.size))
        means = values[draws].mean(axis=1)
    else:
        keys = sorted(set(groups), key=str)
        sums = np.array(
            [sum(v for v, g in zip(values, groups, strict=True) if g == k) for k in keys]
        )
        counts = np.array([sum(1 for g in groups if g == k) for k in keys], dtype=np.float64)
        picks = rng.integers(0, len(keys), size=(n_boot, len(keys)))
        means = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    alpha = (1.0 - level) / 2.0
    lo, hi = np.quantile(means, [alpha, 1.0 - alpha])
    return float(lo), float(hi)


def _calendar_axis(dates: Sequence[date]) -> tuple[date, int]:
    """The first date and the number of calendar days to the last, both ends included."""
    first = min(dates)
    return first, (max(dates) - first).days + 1


def calendar_block_bootstrap(
    diffs: Sequence[float],
    dates: Sequence[date],
    *,
    block_days: int,
    n_boot: int = 10_000,
    seed: int = SEED,
    level: float = 0.90,
) -> tuple[float, float]:
    """Circular block bootstrap on the complete calendar axis, empty dates kept at zero rows.

    The axis runs from the first to the last date, every day included, so a block of
    ``block_days`` is that many calendar days, not that many observed days (Bengisu's PR #128
    lesson). Each draw takes ``ceil(n_days / block_days)`` blocks and averages over all rows
    in them (row-weighted); a draw with no rows is redrawn.
    """
    values = np.asarray(diffs, dtype=np.float64)
    if values.size == 0 or len(dates) != values.size:
        raise ValueError("one date per row, at least one row")
    first, n_days = _calendar_axis(dates)
    day_sum = np.zeros(n_days)
    day_count = np.zeros(n_days)
    for v, d in zip(values, dates, strict=True):
        day_sum[(d - first).days] += v
        day_count[(d - first).days] += 1
    n_blocks = math.ceil(n_days / block_days)
    rng = np.random.default_rng(seed)
    means: list[float] = []
    offsets = np.arange(block_days)
    while len(means) < n_boot:
        starts = rng.integers(0, n_days, size=n_blocks)
        days = ((starts[:, None] + offsets[None, :]) % n_days).reshape(-1)
        count = day_count[days].sum()
        if count == 0:
            continue
        means.append(float(day_sum[days].sum() / count))
    alpha = (1.0 - level) / 2.0
    lo, hi = np.quantile(np.asarray(means), [alpha, 1.0 - alpha])
    return float(lo), float(hi)


def spearman(predicted: Sequence[float], measured: Sequence[float]) -> float:
    if len(predicted) < 2:
        return math.nan
    """Pearson correlation of the average ranks (ties share the mean rank); NaN if constant."""
    a, b = _average_ranks(predicted), _average_ranks(measured)
    if np.std(a) == 0.0 or np.std(b) == 0.0:
        return math.nan
    return float(np.corrcoef(a, b)[0, 1])


def _average_ranks(values: Sequence[float]) -> npt.NDArray[np.float64]:
    data = np.asarray(values, dtype=np.float64)
    ranks = np.empty(data.size)
    ranks[np.argsort(data, kind="stable")] = np.arange(1, data.size + 1)
    for value in np.unique(data):
        tied = data == value
        ranks[tied] = ranks[tied].mean()
    return ranks


# ---------------------------------------------------------------------------------------------
# Archived backends and the dry run's truths


class ArchivedBackend(BackendV2):  # type: ignore[misc]
    """A ``BackendV2`` that only carries a ``Target`` rebuilt from an archived snapshot."""

    def __init__(self, target: Target, name: str) -> None:
        super().__init__(name=name)
        self._archived_target = target

    @property
    def target(self) -> Target:
        return self._archived_target

    @property
    def max_circuits(self) -> None:
        return None

    @classmethod
    def _default_options(cls) -> Options:
        return Options()

    def run(self, run_input: Any, **options: Any) -> Any:
        raise NotImplementedError("an archived backend cannot run anything")


def archived_backend(doc: Mapping[str, Any], name: str = "archived") -> ArchivedBackend:
    """Rebuild a backend from an archived ``{configuration, properties}`` document.

    ``from_backend_properties`` cannot read the archive (no qubit ``frequency``), so the target
    goes through ``qiskit_ibm_runtime``'s ``convert_to_target``.
    """
    conf = BackendConfiguration.from_dict(copy.deepcopy(dict(doc["configuration"])))
    props = BackendProperties.from_dict(copy.deepcopy(dict(doc["properties"])))
    return ArchivedBackend(convert_to_target(conf, props), name)


def substitute_level(
    doc: Mapping[str, Any], level: Mapping[int, QubitSource]
) -> tuple[dict[str, Any], list[int]]:
    """Truth 2: the snapshot with each qubit's ``T1``, ``T2``, assignment errors and
    ``readout_error = (e10 + e01) / 2`` replaced by the level, in each entry's own unit.

    Returns the new document and the qubits left at their reading (no usable level).
    """
    out = copy.deepcopy(dict(doc))
    kept: list[int] = []
    for q, entries in enumerate(out["properties"]["qubits"]):
        src = level.get(q)
        if src is None or not (src.usable_for_decay() and math.isfinite(src.t2) and src.t2 > 0.0):
            kept.append(q)
            continue
        values = {
            "T1": src.t1,
            "T2": src.t2,
            "prob_meas0_prep1": src.e10,
            "prob_meas1_prep0": src.e01,
            "readout_error": (src.e10 + src.e01) / 2.0,
        }
        for entry in entries:
            name = entry.get("name")
            if name in ("T1", "T2"):
                entry["value"] = values[name] / _UNIT_SCALE[entry.get("unit") or "s"]
            elif name in values:
                entry["value"] = values[name]
    return out, kept


def truth_readout(model: NoiseModel, qubits: Sequence[int]) -> tuple[list[float], list[float]]:
    """The truth model's own per-qubit assignment errors ``(e10, e01)`` from its readout errors."""
    e10: list[float] = []
    e01: list[float] = []
    for q in qubits:
        error = model._local_readout_errors.get((q,))
        if error is None:
            e10.append(0.0)
            e01.append(0.0)
            continue
        matrix = np.asarray(error.probabilities)  # rows: prepared, columns: read
        e01.append(float(matrix[0, 1]))
        e10.append(float(matrix[1, 0]))
    return e10, e01


def _git_json(repo: Path, sha: str, path: str) -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "-C", str(repo), "show", f"{sha}:{path}"], check=True, capture_output=True
    ).stdout
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} is not a JSON object")
    return loaded


# ---------------------------------------------------------------------------------------------
# One job: build, simulate (dry run), score


@dataclass
class Job:
    """Everything one job needs, all fixed at ``t_s``."""

    t_s: datetime
    n_qubits: int
    dt: float
    discriminating: list[int]
    controls: list[int]
    sources: dict[str, dict[int, QubitSource]]
    slots: dict[int, list[int | None]]
    arm_a: list[QuantumCircuit]
    layouts: list[tuple[int, int, int]]
    arm_b: list[QuantumCircuit]
    arm_b_predicted: dict[str, list[float | None]]
    layout_log: dict[str, Any] = field(default_factory=dict)


def build_job(
    *,
    rows: Sequence[PredictorRow],
    execution: Sequence[PredictorRow],
    selection: Mapping[str, Any],
    controls: Sequence[int],
    snapshot: Mapping[str, Any],
    t_s: datetime,
    seed: int = SEED,
) -> Job:
    """Arm A and Arm B circuits and predictions for one job, from the archive side's outputs."""
    backend = archived_backend(snapshot, "reading_snapshot")
    target = backend.target
    dt = float(backend.dt)
    n_qubits = int(backend.num_qubits)
    min_length = int(snapshot["configuration"].get("timing_constraints", {}).get("min_length", 2))
    sources = sources_from_rows(rows, execution)
    discriminating = [int(p["qubit"]) for p in selection["discriminating"]]
    arm_a_qubits = sorted(set(discriminating) | set(controls))
    slots = {
        q: delay_slots(
            sources["level"][q].t1, sources["reading"][q].t1, dt=dt, min_length=min_length
        )
        for q in arm_a_qubits
    }
    x_len = {q: round(float(target["x"][(q,)].duration) / dt) for q in arm_a_qubits}
    arm_a = [
        arm_a_circuit(k, {q: slots[q][k] for q in arm_a_qubits}, x_len, n_qubits)
        for k in range(len(SLOTS))
    ]

    gates = gate_table(snapshot["properties"])
    window = {r.qubit: r.n_window_distinct for r in rows if r.quantity == "T1"}
    eligible = {
        q
        for q, w in window.items()
        if w >= MIN_WINDOW_DISTINCT and sources["level"][q].usable_for_relaxation()
    }
    # A pair whose cz has no usable error (gate_error 1 marks a dead pair) is not a link.
    pairs = {
        pair
        for pair in coupled_pairs(snapshot["configuration"]["coupling_map"])
        if usable_cz_error(gates.cz_error.get(pair))
    }
    triples = connected_triples(pairs, eligible)
    level_fidelity: list[tuple[tuple[int, int, int], float]] = []
    compiled: dict[tuple[int, int, int], QuantumCircuit] = {}
    for triple in triples:
        idle = round(
            IDLE_FRACTION * float(np.median([sources["level"][q].t1 for q in triple])) / dt
        )
        circuit = transpile_layout(ghz_idle_circuit(idle), triple, target, seed=seed)
        compiled[triple] = circuit
        level_fidelity.append(
            (triple, _predict_layout(circuit, triple, sources["level"], gates, dt, n_qubits))
        )
    layouts = choose_layouts(level_fidelity)
    arm_b: list[QuantumCircuit] = []
    for triple in layouts:
        circuit = compiled[triple]
        circuit.name = f"arm_b_{'_'.join(map(str, triple))}"
        circuit.metadata = {"arm": "B", "layout": list(triple)}
        arm_b.append(circuit)
    predicted: dict[str, list[float | None]] = {}
    for name in SOURCES:
        predicted[name] = []
        for triple, circuit in zip(layouts, arm_b, strict=True):
            try:
                predicted[name].append(
                    _predict_layout(circuit, triple, sources[name], gates, dt, n_qubits)
                )
            except UnusableSourceError:
                predicted[name].append(None)
    return Job(
        t_s=t_s,
        n_qubits=n_qubits,
        dt=dt,
        discriminating=discriminating,
        controls=list(controls),
        sources=sources,
        slots=slots,
        arm_a=arm_a,
        layouts=layouts,
        arm_b=arm_b,
        arm_b_predicted=predicted,
        layout_log={"eligible_qubits": len(eligible), "triples": len(triples)},
    )


def _predict_layout(
    circuit: QuantumCircuit,
    triple: Sequence[int],
    sources: Mapping[int, QubitSource],
    gates: GateTable,
    dt: float,
    n_qubits: int,
) -> float:
    model = build_predictor_noise(sources, qubits=triple, gates=gates, dt=dt, n_qubits=n_qubits)
    probabilities = shot_free_distribution(circuit, model, triple)
    read = apply_readout(
        probabilities, [sources[q].e10 for q in triple], [sources[q].e01 for q in triple]
    )
    return hellinger_fidelity(read, GHZ_IDEAL)


def _counts_vector(counts: Mapping[str, int], n_bits: int) -> npt.NDArray[np.float64]:
    out = np.zeros(2**n_bits)
    for key, value in counts.items():
        out[int(key.replace(" ", ""), 2)] += value
    return out


def score_arm_a(
    job: Job,
    counts: Sequence[Mapping[str, int]],
    *,
    shots: int = ARM_A_SHOTS,
    truth_p: Mapping[tuple[int, int], float] | None = None,
) -> list[dict[str, Any]]:
    """One row per (qubit, slot): ``p_hat``, each point predictor's error and log score, the
    band's coverage at nominal and widened by one binomial standard error, the band's width.
    In the dry run ``truth_p`` adds the truth's shot-free probability per row."""
    rows: list[dict[str, Any]] = []
    for circuit, slot_counts in zip(job.arm_a, counts, strict=True):
        slot = int(circuit.metadata["slot"])
        qubits: list[int] = list(circuit.metadata["qubits"])
        vector = _counts_vector(slot_counts, len(qubits))
        for i, q in enumerate(qubits):
            ones = int(sum(v for idx, v in enumerate(vector) if (idx >> i) & 1))
            p_hat = ones / shots
            tau_dt = int(job.slots[q][slot] or 0)
            tau_s = tau_dt * job.dt
            row: dict[str, Any] = {
                "stratum": "control" if q in job.controls else "discriminating",
                "qubit": q,
                "slot": SLOTS[slot][0],
                "tau_dt": tau_dt,
                "tau_s": tau_s,
                "shots": shots,
                "ones": ones,
                "p_hat": p_hat,
            }
            for name in POINT_PREDICTORS:
                try:
                    p = p1_closed_form(tau_s, job.sources[name][q])
                    row[f"p_{name}"] = p
                    row[f"abs_err_{name}"] = abs(p_hat - p)
                    row[f"log_score_{name}"] = binomial_log_score(ones, shots, p)
                except UnusableSourceError:
                    row[f"p_{name}"] = row[f"abs_err_{name}"] = row[f"log_score_{name}"] = math.nan
            try:
                ends = sorted(
                    p1_closed_form(tau_s, job.sources[end][q]) for end in ("band_lo", "band_hi")
                )
                widen = binomial_se(p_hat, shots)
                row["band_p_lo"], row["band_p_hi"] = ends
                row["band_covered"] = int(ends[0] <= p_hat <= ends[1])
                row["band_covered_widened"] = int(ends[0] - widen <= p_hat <= ends[1] + widen)
                row["band_width"] = ends[1] - ends[0]
            except UnusableSourceError:
                row["band_p_lo"] = row["band_p_hi"] = row["band_width"] = math.nan
                row["band_covered"] = row["band_covered_widened"] = -1
            if truth_p is not None:
                row["p_truth"] = truth_p[(q, slot)]
            rows.append(row)
    return rows


def score_arm_b(
    job: Job, counts: Sequence[Mapping[str, int]], *, shots: int = ARM_B_SHOTS
) -> dict[str, Any]:
    """Measured fidelity per layout; per predictor Spearman, best-pick and mean absolute error."""
    measured = [hellinger_fidelity(_counts_vector(c, 3) / shots, GHZ_IDEAL) for c in counts]
    best = int(np.argmax(measured))
    out: dict[str, Any] = {"layouts": [list(t) for t in job.layouts], "measured": measured}
    for name in SOURCES:
        pairs = [
            (p, m)
            for p, m in zip(job.arm_b_predicted[name], measured, strict=True)
            if p is not None
        ]
        preds = job.arm_b_predicted[name]
        picks = [i for i, p in enumerate(preds) if p is not None]
        out[name] = {
            "predicted": preds,
            "n_predicted": len(pairs),
            "spearman": spearman([p for p, _ in pairs], [m for _, m in pairs]),
            "best_pick_hit": (
                int(max(picks, key=lambda i: preds[i] or 0.0) == best) if picks else None
            ),
            "mean_abs_error": (
                float(np.mean([abs(p - m) for p, m in pairs])) if pairs else math.nan
            ),
        }
    return out


# ---------------------------------------------------------------------------------------------
# Dry run


SEED_GAP = 10 * max(ARM_A_SHOTS, ARM_B_SHOTS)


def circuit_seeds(seed: int, n_arm_a: int, n_arm_b: int) -> tuple[list[int], list[int]]:
    """One simulator seed per circuit, drawn from ``numpy``'s ``SeedSequence(seed)``.

    When Aer 0.17.2 simulates shots one by one (no measure sampling, as with per-shot noise on
    Arm A's circuits), it seeds shot ``j`` of a run with seed ``s`` as ``s + j``
    (``circuit_executor.hpp``, ``rng.set_seed(circ.seed + shot_index)``; Qiskit/qiskit-aer#1916),
    whatever the thread count: seeds ``500`` and ``501`` give the same shots shifted by one
    (checked 2026-10-28 on an Arm A circuit). Seeds closer than the shot count therefore share
    most of their draws. These are spread over 32 bits and checked to lie at least ``SEED_GAP``
    apart. Each circuit is a run of its own, so Aer's ``seed + 2113 k`` offset between circuits
    of one run never applies here.
    """
    drawn = np.random.SeedSequence(seed).generate_state(n_arm_a + n_arm_b, dtype=np.uint32)
    seeds = [int(v) for v in drawn]
    ordered = sorted(seeds)
    if any(b - a < SEED_GAP for a, b in pairwise(ordered)):
        raise ValueError(f"seed {seed} draws two circuit seeds closer than {SEED_GAP}")
    return seeds[:n_arm_a], seeds[n_arm_a:]


def simulate_truth(job: Job, truth: NoiseModel, *, seed: int = SEED) -> dict[str, Any]:
    """Counts for every circuit from the truth model, and the truth's shot-free probabilities
    with its own readout applied analytically (criterion 1).

    Every circuit gets its own seed, far from every other (``circuit_seeds``): seeds that are
    equal or close replay the same shots, so a qubit's sampling errors would repeat across its
    slots and the rows would not be independent draws.
    """
    sim = AerSimulator(noise_model=truth)
    seeds_a, seeds_b = circuit_seeds(seed, len(job.arm_a), len(job.arm_b))
    arm_a_counts = [
        sim.run(c, shots=ARM_A_SHOTS, seed_simulator=s).result().get_counts()
        for c, s in zip(job.arm_a, seeds_a, strict=True)
    ]
    arm_b_counts = [
        sim.run(c, shots=ARM_B_SHOTS, seed_simulator=s).result().get_counts()
        for c, s in zip(job.arm_b, seeds_b, strict=True)
    ]
    truth_p: dict[tuple[int, int], float] = {}
    for circuit in job.arm_a:
        slot = int(circuit.metadata["slot"])
        for q in circuit.metadata["qubits"]:
            single = _single_qubit_part(circuit, q)
            p = shot_free_distribution(single, truth, [q])
            e10, e01 = truth_readout(truth, [q])
            truth_p[(q, slot)] = float(apply_readout(p, e10, e01)[1])
    arm_b_truth: list[list[float]] = []
    for circuit, triple in zip(job.arm_b, job.layouts, strict=True):
        p = shot_free_distribution(circuit, truth, triple)
        e10, e01 = truth_readout(truth, triple)
        arm_b_truth.append([float(v) for v in apply_readout(p, e10, e01)])
    return {
        "arm_a_counts": arm_a_counts,
        "arm_b_counts": arm_b_counts,
        "arm_a_truth_p": truth_p,
        "arm_b_truth_p": arm_b_truth,
    }


def _single_qubit_part(circuit: QuantumCircuit, qubit: int) -> QuantumCircuit:
    """The instructions of ``circuit`` acting on ``qubit`` alone, final measurement included."""
    part = QuantumCircuit(circuit.num_qubits, 1)
    for instruction in circuit.data:
        indices = [circuit.find_bit(q).index for q in instruction.qubits]
        if instruction.operation.name == "barrier" or indices != [qubit]:
            continue
        if instruction.operation.name == "measure":
            part.measure(qubit, 0)
        else:
            part.append(instruction.operation, [qubit])
    return part


def evaluate_criteria(
    job: Job,
    arm_a_rows: Sequence[Mapping[str, Any]],
    arm_b: Mapping[str, Any],
    sim: Mapping[str, Any],
    *,
    matched: str,
    other: str,
    intervals: Mapping[int, Mapping[int, int]],
) -> dict[str, Any]:
    """The five acceptance criteria of the plan, each pass or fail with its figures."""
    out: dict[str, Any] = {"matched": matched, "other": other}
    # 1. Sampling: within 4 binomial standard errors of the truth's shot-free probability.
    z_a = [
        abs(r["p_hat"] - r["p_truth"]) / binomial_se(r["p_truth"], int(r["shots"]))
        for r in arm_a_rows
    ]
    z_b: list[float] = []
    minimum = min(min(r["p_truth"] for r in arm_a_rows), min(min(p) for p in sim["arm_b_truth_p"]))
    for counts, truth in zip(sim["arm_b_counts"], sim["arm_b_truth_p"], strict=True):
        freq = _counts_vector(counts, 3) / ARM_B_SHOTS
        for f, p in zip(freq, truth, strict=True):
            z_b.append(abs(f - p) / binomial_se(p, ARM_B_SHOTS))
    out["1_sampling"] = {
        "pass": bool(minimum > 0.0 and max(z_a) <= 4.0 and max(z_b) <= 4.0),
        "arm_a_rows": len(z_a),
        "arm_a_max_z": max(z_a),
        "arm_b_outcomes": len(z_b),
        "arm_b_max_z": max(z_b),
        "min_shot_free_probability": minimum,
    }
    # 2. Offset: the matched predictor's mean signed error equals the mean derived offset.
    signed = [r["p_hat"] - r[f"p_{matched}"] for r in arm_a_rows]
    derived = [r["p_truth"] - r[f"p_{matched}"] for r in arm_a_rows]
    se = math.sqrt(sum(binomial_se(r["p_truth"], int(r["shots"])) ** 2 for r in arm_a_rows)) / len(
        arm_a_rows
    )
    gap = float(np.mean(signed) - np.mean(derived))
    out["2_offset"] = {
        "pass": bool(abs(gap) <= 3.0 * se),
        "mean_signed_error": float(np.mean(signed)),
        "mean_derived_offset": float(np.mean(derived)),
        "difference": gap,
        "se_of_mean": se,
    }
    # 3. Direction, on the discriminating rows.
    disc = [r for r in arm_a_rows if r["stratum"] == "discriminating"]
    mae = {name: float(np.mean([r[f"abs_err_{name}"] for r in disc])) for name in POINT_PREDICTORS}
    diffs = [r[f"abs_err_{other}"] - r[f"abs_err_{matched}"] for r in disc]
    lo, hi = paired_bootstrap(diffs)
    out["3_direction"] = {
        "pass": bool(all(mae[matched] <= v for v in mae.values()) and lo > 0.0),
        "rows": len(disc),
        "mae": mae,
        f"{other}_minus_{matched}_90": [lo, hi],
        "bootstrap_unit": "row (smoke test of the code, not the decision rule's unit)",
    }
    # 4. Arm B end to end.
    out["4_arm_b"] = {
        "pass": bool(
            len(job.layouts) == N_LAYOUTS
            and all(isinstance(arm_b[name], dict) for name in SOURCES)
            and out["1_sampling"]["arm_b_max_z"] <= 4.0
        ),
        "layouts": [list(t) for t in job.layouts],
        "measured": arm_b["measured"],
        "per_predictor": {
            name: {k: v for k, v in arm_b[name].items() if k != "predicted"} for name in SOURCES
        },
        "unpredictable": {
            name: [
                list(t)
                for t, p in zip(job.layouts, arm_b[name]["predicted"], strict=True)
                if p is None
            ]
            for name in SOURCES
        },
    }
    # 5. Circuit timing: x end to measure start equals tau in every Arm A circuit.
    mismatches = [
        (k, q, got, int(job.slots[q][k] or 0))
        for k, per_qubit in intervals.items()
        for q, got in per_qubit.items()
        if got != int(job.slots[q][k] or 0)
    ]
    out["5_timing"] = {
        "pass": not mismatches,
        "checked": sum(len(v) for v in intervals.values()),
        "mismatches": mismatches,
    }
    out["all_pass"] = all(
        out[k]["pass"] for k in ("1_sampling", "2_offset", "3_direction", "4_arm_b", "5_timing")
    )
    return out


def write_json_lf(path: Path, payload: Any) -> None:
    """Write JSON with LF line endings on every platform, as the repository stores it, so a hash
    taken at write time is the hash every checkout reproduces (the same rule as PR #132's
    ``_write_json``)."""
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")


def _write_tsv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {k: (f"{v:.10g}" if isinstance(v, float) else v) for k, v in row.items()}
            )


def _parse_at(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise argparse.ArgumentTypeError("times must carry a zone")
    return stamp.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--ref", required=True)
    parser.add_argument("--at", type=_parse_at, required=True, help="t_s, ISO 8601 with zone")
    parser.add_argument("--execution-ref", required=True)
    parser.add_argument("--execution-at", type=_parse_at, default=None)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--backend", default="ibm_fez")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    t_s: datetime = args.at
    t_exec: datetime = args.execution_at or t_s + timedelta(hours=2)

    controls_doc, controls_sha = load_controls(args.controls, backend=args.backend)
    controls = [int(c["qubit"]) for c in controls_doc["controls"]]
    sha = resolve_archive_ref(args.repo, args.ref)
    exec_sha = resolve_archive_ref(args.repo, args.execution_ref)
    collected: Collected = collect(iter_archive(args.repo, sha), backend=args.backend, until=t_s)
    rows = predictor_rows(collected, at=t_s, live=None)
    selection = select_balanced(rows, k=8, controls=set(controls))
    later = collect(iter_archive(args.repo, exec_sha), backend=args.backend, until=t_exec)
    execution = execution_rows(later, at=t_exec, live=None)
    reading_file = [f for f in collected.files if f.time <= t_s][-1]
    execution_file = [f for f in later.files if f.time <= t_exec][-1]
    snapshot = _git_json(args.repo, sha, reading_file.path)

    job = build_job(
        rows=rows,
        execution=execution,
        selection=selection,
        controls=controls,
        snapshot=snapshot,
        t_s=t_s,
        seed=args.seed,
    )
    target = archived_backend(snapshot).target
    intervals = {k: x_to_measure_intervals(c, target) for k, c in enumerate(job.arm_a)}

    truth_docs: dict[str, tuple[dict[str, Any], list[int]]] = {"truth1": (dict(snapshot), [])}
    truth_docs["truth2"] = substitute_level(snapshot, job.sources["level"])
    matched = {"truth1": ("reading", "level"), "truth2": ("level", "reading")}
    args.out.mkdir(parents=True, exist_ok=True)
    criteria: dict[str, Any] = {}
    capped: dict[str, list[int]] = {}
    for name, (doc, kept) in truth_docs.items():
        backend = archived_backend(doc, name)
        truth = NoiseModel.from_backend(backend)
        capped[name] = sorted(
            q
            for q, qp in enumerate(backend.target.qubit_properties)
            if qp is not None and qp.t1 and qp.t2 and qp.t2 > 2.0 * qp.t1
        )
        sim = simulate_truth(job, truth, seed=args.seed)
        a_rows = score_arm_a(job, sim["arm_a_counts"], truth_p=sim["arm_a_truth_p"])
        b_score = score_arm_b(job, sim["arm_b_counts"])
        criteria[name] = evaluate_criteria(
            job,
            a_rows,
            b_score,
            sim,
            matched=matched[name][0],
            other=matched[name][1],
            intervals=intervals,
        )
        criteria[name]["qubits_kept_at_reading"] = kept
        criteria[name]["t2_above_2t1_capped_by_aer"] = capped[name]
        _write_tsv(args.out / f"arm-a-{name}.tsv", a_rows)
        b_rows = [
            {
                "layout": "-".join(map(str, t)),
                "measured_fidelity": m,
                **{f"predicted_{s}": b_score[s]["predicted"][i] for s in SOURCES},
            }
            for i, (t, m) in enumerate(zip(job.layouts, b_score["measured"], strict=True))
        ]
        _write_tsv(args.out / f"arm-b-{name}.tsv", b_rows)

    longest = max((d or 0) for slots in job.slots.values() for d in slots) * job.dt
    manifest = {
        "label": "pipeline acceptance on Aer, not a measurement of the device; no NC row",
        "ref_sha": sha,
        "t_s": t_s.isoformat(),
        "reading_file": reading_file.path,
        "execution_ref_sha": exec_sha,
        "t_execute": t_exec.isoformat(),
        "execution_file": execution_file.path,
        "controls": controls,
        "controls_file_sha256": controls_sha,
        "discriminating": job.discriminating,
        "selection_log": {k: v for k, v in selection.items() if k != "discriminating"},
        "slots_dt": {str(q): s for q, s in job.slots.items()},
        "longest_delay_s": longest,
        "layouts": [list(t) for t in job.layouts],
        "layout_log": job.layout_log,
        "shots": {"arm_a": ARM_A_SHOTS, "arm_b": ARM_B_SHOTS},
        "seed": args.seed,
        "dt_s": job.dt,
        "versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "qiskit": qiskit.__version__,
            "qiskit_aer": qiskit_aer.__version__,
        },
        "snapshot_sha256": hashlib.sha256(
            json.dumps(snapshot, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
    for name, payload in (("manifest", manifest), ("criteria", criteria), ("selection", selection)):
        write_json_lf(args.out / f"{name}.json", payload)
    print(json.dumps({k: v["all_pass"] for k, v in criteria.items()}, indent=2))
    return 0 if all(v["all_pass"] for v in criteria.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
