"""Qraps circuits. Qubit layout: die d (0 = house A, 1 = house B, 2 = player1 A, 3 = player1 B, ...)
occupies qubits 3d..3d+2 (little-endian); die value v = face-1 in 0..5. Our reconstruction."""
import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import UnitaryGate
from qiskit.quantum_info import Statevector, partial_trace, DensityMatrix

from .modes import MODES, CROSS_RULE


def design_code(mode: str) -> str:
    """Scripted Q-Scientist output: source text that goes through the sandbox like any model-written code."""
    pairs = MODES[mode]
    return f'''import numpy as np
from qiskit import QuantumCircuit

PAIRS = {pairs!r}

def build_circuit():
    amp = np.zeros(64)
    for a, b in PAIRS:
        amp[(a - 1) | ((b - 1) << 3)] = 1.0
    amp = amp / np.linalg.norm(amp)
    qc = QuantumCircuit(6)
    qc.prepare_state(amp, range(6))
    return qc

def expected():
    n = len(PAIRS)
    return {{format((a - 1) | ((b - 1) << 3), "06b"): 1.0 / n for a, b in PAIRS}}
'''


def _complement_gate() -> UnitaryGate:
    """3-qubit permutation v -> 5 - v on 0..5 (6,7 fixed): face k -> 7 - k."""
    M = np.zeros((8, 8))
    for v in range(8):
        M[(5 - v) if v < 6 else v, v] = 1
    return UnitaryGate(M, label="7-k")


def table_circuit(design: QuantumCircuit, n_players: int, rule: str) -> QuantumCircuit:
    """House pair from the verified design on qubits 0..5; each player copies it by CNOT (+ permutation for sum7)."""
    n = 6 * (n_players + 1)
    qc = QuantumCircuit(n)
    qc.compose(design, qubits=range(6), inplace=True)
    for p in range(1, n_players + 1):
        base = 6 * p
        for i in range(6):
            qc.cx(i, base + i)
        if rule == "sum7":
            qc.append(_complement_gate(), [base, base + 1, base + 2])
            qc.append(_complement_gate(), [base + 3, base + 4, base + 5])
    return qc


def expected_table(pairs: list, n_players: int, rule: str) -> dict:
    """Stated (analytic, sparse) distribution of the full table register as bitstrings (Qiskit order)."""
    n = 6 * (n_players + 1)
    out = {}
    w = 1.0 / len(pairs)
    for a, b in pairs:
        faces = [a, b]
        for _ in range(n_players):
            faces += [a, b] if rule == "equal" else [7 - a, 7 - b]
        idx = 0
        for d, f in enumerate(faces):
            idx |= (f - 1) << (3 * d)
        out[format(idx, f"0{n}b")] = w
    return out


def decode(bitstring: str, n_players: int) -> list:
    """Bitstring (Qiskit order: leftmost = highest qubit) -> list of dice faces, house first."""
    idx = int(bitstring.replace(" ", ""), 2)
    return [((idx >> (3 * d)) & 7) + 1 for d in range(2 * (n_players + 1))]


def bloch_vectors(circ: QuantumCircuit) -> list:
    """Real physics: single-qubit reduced density matrices of the circuit's statevector -> (x, y, z)."""
    sv = Statevector(circ)
    n = circ.num_qubits
    out = []
    for q in range(n):
        rho = partial_trace(sv, [i for i in range(n) if i != q]).data
        out.append((float(2 * rho[0, 1].real), float(-2 * rho[0, 1].imag), float((rho[0, 0] - rho[1, 1]).real)))
    return out


def face_poles(face: int) -> list:
    """After measurement: the three qubits of a die snap to poles spelling (face-1) in binary. z=+1 means |0>."""
    v = face - 1
    return [(0.0, 0.0, 1.0 if not (v >> i) & 1 else -1.0) for i in range(3)]
