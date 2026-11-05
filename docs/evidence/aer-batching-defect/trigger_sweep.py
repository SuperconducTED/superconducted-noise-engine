"""Aer batching defect: every prediction in section 3 of README.md, one line per row.

Run with:  python -W ignore -I trigger_sweep.py

Uses only qiskit and qiskit-aer. Prints each row's measured value and method beside `met` or `MISSED`.
Exits 1 if any row misses, so a rerun on another machine that differs is visible.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable

import numpy as np
import qiskit
import qiskit_aer
from qiskit import QuantumCircuit
from qiskit.primitives import BackendSamplerV2
from qiskit.quantum_info import PauliList, hellinger_fidelity
from qiskit_aer import AerSimulator
from qiskit_aer.noise import (
    NoiseModel,
    PauliLindbladError,
    ReadoutError,
    amplitude_damping_error,
    coherent_unitary_error,
    depolarizing_error,
    mixed_unitary_error,
    pauli_error,
    phase_damping_error,
    reset_error,
    thermal_relaxation_error,
)
from qiskit_aer.primitives import SamplerV2 as AerSamplerV2

SHOTS = 2048
SEED = 97
GAMMA = 0.1
SUM_TOLERANCE = 1e-9
SIGMAS = 4.0
SHORT = {
    "statevector": "SV",
    "density_matrix": "DM",
    "stabilizer": "ST",
    "matrix_product_state": "MPS",
}

outcomes: list[tuple[str, bool]] = []


def record(row: str, ok: bool, text: str) -> None:
    outcomes.append((row, ok))
    print(f"{row:6s} {'met   ' if ok else 'MISSED'} {text}", flush=True)


def model(error=None, gates=("x",)) -> NoiseModel:
    noise = NoiseModel()
    noise.add_all_qubit_quantum_error(
        amplitude_damping_error(GAMMA) if error is None else error, list(gates)
    )
    return noise


def f_n(n: int) -> QuantumCircuit:
    """n qubits, rz on each, measured: non-Clifford, so never stabilizer."""
    circuit = QuantumCircuit(n)
    circuit.rz(0.3, range(n))
    circuit.measure_all()
    return circuit


def s_k(k: int, width: int = 1) -> QuantumCircuit:
    """k noisy x gates on qubit 0, probabilities saved, no measurement."""
    circuit = QuantumCircuit(width)
    for _ in range(k):
        circuit.x(0)
    for q in range(1, width):
        circuit.rz(0.3, q)
    circuit.save_probabilities()
    return circuit


def s_m() -> QuantumCircuit:
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.measure_all()
    return circuit


def methods(result) -> list[str]:
    return [SHORT.get(r.metadata["method"], r.metadata["method"]) for r in result.results]


def noises(result) -> list[str]:
    return [str(r.metadata.get("noise")) for r in result.results]


def run(sim: AerSimulator, circuits, shots: int = SHOTS):
    return sim.run(circuits, shots=shots, seed_simulator=SEED).result()


def total(result, index: int) -> float:
    return float(np.sum(result.data(index)["probabilities"]))


def close(got: float, want: float) -> bool:
    return abs(got - want) <= SUM_TOLERANCE * want


def sums(
    row: str,
    label: str,
    sim: AerSimulator,
    circuits,
    want: dict[int, float],
    want_methods: list[str] | None,
    shots: int = SHOTS,
) -> None:
    """A row that predicts the sum of saved probabilities at given positions, and the methods."""
    result = run(sim, circuits, shots)
    got = {i: total(result, i) for i in want}
    got_methods = methods(result)
    ok = all(close(got[i], want[i]) for i in want) and (
        want_methods is None or got_methods == want_methods
    )
    values = ", ".join(f"{got[i]:.9f} (want {want[i]:g})" for i in sorted(want))
    method_note = "" if want_methods is not None else " (method not predicted)"
    record(
        row,
        ok,
        f"{label}: sum {values}; shots {shots}; methods {','.join(got_methods)}{method_note}; "
        f"noise {','.join(noises(result))}",
    )


def within(observed: float, want: float, shots: int) -> bool:
    spread = math.sqrt(want * (1 - want) / shots)
    return abs(observed - want) <= SIGMAS * spread


def has_kraus(errors) -> bool:
    return any(
        instruction["name"] in ("kraus", "superop")
        for error in errors
        for circuit in error.to_dict().get("instructions", [])
        for instruction in circuit
    )


def part_a() -> None:
    sim = AerSimulator(noise_model=model())
    print("A. The trace law")
    sums("A1", "[F_11, S_1]", sim, [f_n(11), s_k(1)], {1: 2.0}, ["SV", "DM"])
    sums("A2", "[F_11, S_2]", sim, [f_n(11), s_k(2)], {1: 4.0}, ["SV", "DM"])
    sums("A3", "[F_11, S_3]", sim, [f_n(11), s_k(3)], {1: 8.0}, ["SV", "DM"])
    sums("A4", "[F_11, S_0]", sim, [f_n(11), s_k(0)], {1: 1.0}, ["SV", "DM"])
    sums("A5", "[S_1, F_11]", sim, [s_k(1), f_n(11)], {0: 1.0}, ["DM", "SV"])
    sums("A6", "S_1 alone", sim, s_k(1), {0: 1.0}, ["DM"])

    for row, count in (("A7", 1), ("A8", 2)):
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        for _ in range(count):
            circuit.x(0)
        circuit.save_density_matrix(label="rho")
        alone = np.asarray(run(sim, circuit).data(0)["rho"])
        batch = run(sim, [f_n(11), circuit])
        wrong = np.asarray(batch.data(1)["rho"])
        factor = 2.0**count
        gap = float(np.max(np.abs(wrong - factor * alone)))
        ok = gap <= SUM_TOLERANCE and methods(batch) == ["SV", "DM"]
        record(
            row,
            ok,
            f"density matrix after F_11 against {factor:g} times alone: largest element gap "
            f"{gap:.2e}; trace alone {np.trace(alone).real:.9f}, after {np.trace(wrong).real:.9f}; "
            f"methods {','.join(methods(batch))}",
        )

    for gamma in (0.05, 0.1, 0.2):
        noisy = AerSimulator(noise_model=model(amplitude_damping_error(gamma)))
        alone = run(noisy, s_m()).get_counts(0).get("0", 0) / SHOTS
        after = run(noisy, [f_n(11), s_m()]).get_counts(1).get("0", 0) / SHOTS
        ok = within(alone, gamma, SHOTS) and within(after, 2 * gamma, SHOTS)
        record(
            "A9",
            ok,
            f"gamma {gamma}: P(0) alone {alone:.4f} (want {gamma}), after F_11 {after:.4f} "
            f"(want {2 * gamma})",
        )


def part_b() -> None:
    print("B. Which noise")
    amp = amplitude_damping_error(GAMMA)
    x_matrix = np.array([[0, 1], [1, 0]])
    theta = 0.1
    rotation = np.array(
        [[np.cos(theta), -1j * np.sin(theta)], [-1j * np.sin(theta), np.cos(theta)]]
    )
    lindblad = PauliLindbladError(PauliList(["X", "Z"]), [0.05, 0.05])
    plain: list[tuple[str, str, object, float]] = [
        ("B1", "depolarizing", depolarizing_error(GAMMA, 1), 1.0),
        ("B2", "pauli X", pauli_error([("X", GAMMA), ("I", 1 - GAMMA)]), 1.0),
        ("B3", "reset", reset_error(GAMMA), 1.0),
        ("B4", "thermal T2<T1", thermal_relaxation_error(100e3, 80e3, 50), 1.0),
        (
            "B5",
            "mixed unitary",
            mixed_unitary_error([(np.eye(2), 1 - GAMMA), (x_matrix, GAMMA)]),
            1.0,
        ),
        ("B6", "coherent unitary", coherent_unitary_error(rotation), 1.0),
        ("B7", "amplitude damping", amp, 2.0),
        ("B8", "phase damping", phase_damping_error(GAMMA), 2.0),
        ("B9", "thermal T2>T1", thermal_relaxation_error(100e3, 150e3, 50), 2.0),
    ]
    for row, label, error, want in plain:
        kraus = has_kraus([error])
        ok_rule = kraus == (want == 2.0)
        sim = AerSimulator(noise_model=model(error))
        result = run(sim, [f_n(11), s_k(1)])
        got = total(result, 1)
        ok = close(got, want) and methods(result) == ["SV", "DM"] and ok_rule
        record(
            row,
            ok,
            f"{label}: sum {got:.9f} (want {want:g}); kraus in error {kraus}; "
            f"methods {','.join(methods(result))}; noise {','.join(noises(result))}",
        )

    def mixed(first, first_gate: str, second, second_gate: str) -> NoiseModel:
        noise = NoiseModel()
        noise.add_all_qubit_quantum_error(first, [first_gate])
        noise.add_all_qubit_quantum_error(second, [second_gate])
        return noise

    depol = depolarizing_error(GAMMA, 1)
    amp_cz = amp.tensor(amp)
    sim = AerSimulator(noise_model=mixed(depol, "x", amp_cz, "cz"))
    sums("B10", "depolarizing on x, damping on unused cz", sim, [f_n(11), s_k(1)], {1: 2.0}, None)

    readout = NoiseModel()
    readout.add_all_qubit_readout_error(ReadoutError([[0.98, 0.02], [0.02, 0.98]]))
    sim = AerSimulator(noise_model=readout)
    sums("B11", "readout error only", sim, [f_n(11), s_k(1)], {1: 1.0}, None)

    sim = AerSimulator(noise_model=model(lindblad))
    sums("B12", "Pauli-Lindblad on x", sim, [f_n(11), s_k(1)], {1: 1.0}, ["SV", "DM"])

    sim = AerSimulator(noise_model=mixed(lindblad, "x", amp_cz, "cz"))
    sums(
        "B13",
        "Pauli-Lindblad on x, damping on unused cz",
        sim,
        [f_n(11), s_k(1)],
        {1: 1.0},
        ["SV", "DM"],
    )

    sim = AerSimulator(noise_model=mixed(amp, "x", lindblad, "y"))
    both = QuantumCircuit(1)
    both.x(0)
    both.y(0)
    both.save_probabilities()
    sums(
        "B14",
        "damping on x, Pauli-Lindblad on y, circuit x y",
        sim,
        [f_n(11), both],
        {1: 2.0},
        ["SV", "DM"],
    )


def part_c() -> None:
    print("C. The first circuit")
    sim = AerSimulator(noise_model=model())
    for n in range(1, 11):
        sums("C1", f"[F_{n}, S_1]", sim, [f_n(n), s_k(1)], {1: 1.0}, ["DM", "DM"])
    for n in range(11, 14):
        sums("C2", f"[F_{n}, S_1]", sim, [f_n(n), s_k(1)], {1: 2.0}, ["SV", "DM"])

    only_measure = QuantumCircuit(11)
    only_measure.measure_all()
    sums("C3", "11 qubits, measures only", sim, [only_measure, s_k(1)], {1: 2.0}, ["SV", "DM"])

    noisy_gates = QuantumCircuit(11)
    noisy_gates.x(range(11))
    noisy_gates.measure_all()
    sums("C4", "11 qubits, noisy x on each", sim, [noisy_gates, s_k(1)], {1: 2.0}, ["SV", "DM"])

    wide_one = QuantumCircuit(20, 1)
    wide_one.rz(0.3, 0)
    wide_one.measure(0, 0)
    sums("C5", "width 20, one used, one measured", sim, [wide_one, s_k(1)], {1: 1.0}, ["DM", "DM"])

    wide_twelve = QuantumCircuit(20, 12)
    wide_twelve.rz(0.3, range(12))
    wide_twelve.measure(range(12), range(12))
    sums("C6", "width 20, 12 used, 12 measured", sim, [wide_twelve, s_k(1)], {1: 2.0}, ["SV", "DM"])

    wide_unmeasured = QuantumCircuit(20, 1)
    wide_unmeasured.rz(0.3, range(12))
    wide_unmeasured.measure(0, 0)
    sums(
        "C7",
        "width 20, 12 used, one measured",
        sim,
        [wide_unmeasured, s_k(1)],
        {1: 1.0},
        ["DM", "DM"],
    )

    mid = QuantumCircuit(1, 2)
    mid.x(0)
    mid.measure(0, 0)
    mid.x(0)
    mid.measure(0, 1)
    sums("C8", "one qubit with a mid-circuit measure", sim, [mid, s_k(1)], {1: 2.0}, ["SV", "DM"])


def part_d() -> None:
    print("D. Shots and the second circuit")
    sim = AerSimulator(noise_model=model())
    pairs = [
        ("D1", 11, 2048, 2.0, ["SV", "DM"]),
        ("D2", 11, 2049, 1.0, ["DM", "DM"]),
        ("D3", 3, 8, 2.0, ["SV", "DM"]),
        ("D4", 3, 9, 1.0, ["DM", "DM"]),
        ("D5", 2, 2, 1.0, ["SV", "SV"]),
        ("D6", 2, 3, 2.0, ["SV", "DM"]),
        ("D7", 2, 4, 2.0, ["SV", "DM"]),
        ("D8", 2, 5, 1.0, ["DM", "DM"]),
    ]
    for row, n, shots, want, want_methods in pairs:
        sums(row, f"[F_{n}, S_1]", sim, [f_n(n), s_k(1)], {1: want}, want_methods, shots)
    sums("D9", "[F_12, ten-qubit S_1]", sim, [f_n(12), s_k(1, 10)], {1: 2.0}, ["SV", "DM"])
    sums("D10", "[F_12, eleven-qubit S_1]", sim, [f_n(12), s_k(1, 11)], {1: 1.0}, ["SV", "SV"])


def part_e() -> None:
    print("E. Order, scope and escapes")
    noise = model()
    sim = AerSimulator(noise_model=noise)
    sums(
        "E1",
        "[S_1, F_11, S_2]",
        sim,
        [s_k(1), f_n(11), s_k(2)],
        {0: 1.0, 2: 1.0},
        ["DM", "SV", "DM"],
    )
    sums(
        "E2",
        "[F_11, S_1, S_2]",
        sim,
        [f_n(11), s_k(1), s_k(2)],
        {1: 2.0, 2: 4.0},
        ["SV", "DM", "DM"],
    )

    run(sim, [f_n(11), s_k(1)])
    sums("E3", "S_1 alone, same simulator, after a batched run", sim, s_k(1), {0: 1.0}, ["DM"])

    noisy_gates = QuantumCircuit(11)
    noisy_gates.x(range(11))
    noisy_gates.measure_all()
    alone = run(sim, noisy_gates).get_counts(0)
    batched = run(sim, [noisy_gates, s_k(1)]).get_counts(0)
    record(
        "E4",
        alone == batched,
        f"11 noisy qubits, alone against first in a batch: counts identical {alone == batched}, "
        f"{len(alone)} distinct outcomes",
    )

    forced_sv = AerSimulator(noise_model=noise, method="statevector")
    sums("E5", "method=statevector", forced_sv, [f_n(11), s_k(1)], {1: 1.0}, ["SV", "SV"])
    forced_dm = AerSimulator(noise_model=noise, method="density_matrix")
    sums("E6", "method=density_matrix", forced_dm, [f_n(11), s_k(1)], {1: 1.0}, ["DM", "DM"])
    explicit = AerSimulator(noise_model=noise, method="automatic")
    sums("E7", "method=automatic, explicit", explicit, [f_n(11), s_k(1)], {1: 2.0}, ["SV", "DM"])
    sums("E8", "no noise model", AerSimulator(), [f_n(11), s_k(1)], {1: 1.0}, None)
    serial = AerSimulator(noise_model=noise, max_parallel_threads=1)
    sums("E9", "max_parallel_threads=1", serial, [f_n(11), s_k(1)], {1: 2.0}, ["SV", "DM"])

    local = NoiseModel()
    local.add_quantum_error(amplitude_damping_error(GAMMA), ["x"], [0])
    sim_local = AerSimulator(noise_model=local)
    sums("E10", "error local to qubit 0", sim_local, [f_n(11), s_k(1)], {1: 2.0}, ["SV", "DM"])

    many = NoiseModel()
    for q in range(12):
        many.add_quantum_error(amplitude_damping_error(GAMMA), ["x"], [q])
    sim_many = AerSimulator(noise_model=many)
    sums("E11", "12 local errors", sim_many, [f_n(11), s_k(1)], {1: 2.0}, ["SV", "DM"])


def part_f() -> None:
    print("F. Primitives")
    noise = model()
    sim = AerSimulator(noise_model=noise)
    backend_sampler: Callable = lambda: BackendSamplerV2(
        backend=sim, options={"default_shots": SHOTS, "seed_simulator": SEED}
    )
    aer_sampler: Callable = lambda: AerSamplerV2(
        default_shots=SHOTS, seed=SEED, options={"backend_options": {"noise_model": noise}}
    )
    same = [f_n(11), s_m()]
    apart = [(f_n(11), None, SHOTS), (s_m(), None, 2 * SHOTS)]
    rows = [
        ("F1", "BackendSamplerV2, same shots", backend_sampler, same, 2 * GAMMA, SHOTS),
        ("F2", "BackendSamplerV2, 2048 and 4096", backend_sampler, apart, GAMMA, 2 * SHOTS),
        ("F3", "qiskit_aer SamplerV2, same shots", aer_sampler, same, 2 * GAMMA, SHOTS),
        ("F4", "qiskit_aer SamplerV2, 2048 and 4096", aer_sampler, apart, GAMMA, 2 * SHOTS),
    ]
    for row, label, factory, pubs, want, shots in rows:
        counts = factory().run(pubs).result()[1].data.meas.get_counts()
        observed = counts.get("0", 0) / shots
        record(
            row,
            within(observed, want, shots),
            f"{label}: P(0) {observed:.4f} (want {want:g}), {shots} shots",
        )


def part_g() -> None:
    print("G. The original symptom")
    damp = amplitude_damping_error(0.05)
    readout = ReadoutError([[0.98, 0.02], [0.02, 0.98]])

    def ghz_model(with_readout: bool) -> NoiseModel:
        noise = NoiseModel()
        noise.add_all_qubit_quantum_error(damp, ["h"])
        noise.add_all_qubit_quantum_error(damp.tensor(damp), ["cx"])
        if with_readout:
            noise.add_all_qubit_readout_error(readout)
        return noise

    ghz = QuantumCircuit(3)
    ghz.h(0)
    ghz.cx(0, 1)
    ghz.cx(1, 2)
    ghz.measure_all()
    ideal = {"000": 0.5, "111": 0.5}

    def rates(counts: dict[str, int]) -> str:
        shots = sum(counts.values())
        return (
            f"000 {counts.get('000', 0) / shots:.4f}, 111 {counts.get('111', 0) / shots:.4f}, "
            f"Hellinger fidelity {hellinger_fidelity(counts, ideal):.4f}"
        )

    noisy = ghz_model(True)
    auto = AerSimulator(noise_model=noisy)
    forced = AerSimulator(noise_model=noisy, method="density_matrix")
    alone = run(auto, ghz)
    reference = run(forced, ghz).get_counts(0)
    record(
        "G1",
        alone.get_counts(0) == reference,
        f"alone, automatic against forced density matrix: identical "
        f"{alone.get_counts(0) == reference}; method {methods(alone)[0]}; "
        f"{rates(alone.get_counts(0))}",
    )

    after = run(auto, [f_n(12), ghz]).get_counts(1)
    target = 0.98**3
    observed = after.get("000", 0) / SHOTS
    record(
        "G2",
        within(observed, target, SHOTS) and after.get("111", 0) == 0,
        f"after F_12: {rates(after)}; 000 wanted {target:.4f}; 111 counts {after.get('111', 0)}",
    )

    clean = AerSimulator(noise_model=ghz_model(False))
    after_clean = run(clean, [f_n(12), ghz]).get_counts(1)
    fidelity = hellinger_fidelity(after_clean, ideal)
    record(
        "G3",
        after_clean.get("000", 0) == SHOTS and abs(fidelity - 0.5) <= SUM_TOLERANCE,
        f"after F_12, no readout error: {rates(after_clean)}; counts {after_clean}",
    )


def main() -> int:
    print(
        f"qiskit {qiskit.__version__}, qiskit-aer {qiskit_aer.__version__}, numpy {np.__version__}"
    )
    print(
        f"{SHOTS} shots unless a row says otherwise, seed {SEED}, sum tolerance {SUM_TOLERANCE:g}"
    )
    for part in (part_a, part_b, part_c, part_d, part_e, part_f, part_g):
        part()
    missed = [row for row, ok in outcomes if not ok]
    print(
        f"\nrows {len(outcomes)}, met {len(outcomes) - len(missed)}, missed {len(missed)}: {missed}"
    )
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
