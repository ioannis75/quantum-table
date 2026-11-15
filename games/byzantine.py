"""Three-party agreement with the house as third party: the three-qutrit singlet (Aharonov state), step 1 of
docs/IDEAS_byzantine_qkd.md. Fitzi, Gisin, Maurer, PRL 87, 217901 (2001): detectable Byzantine agreement from this state.
Here: build it exactly, check it, and show the rule that makes liar detection possible. A qutrit is a 3-sided die, encoded
in 2 qubits with the fourth level at zero amplitude. Engine: Aer emulator. An illustration of detectable agreement, not a
contract-signing system; the house still sees everything classically."""
import itertools
import math
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector, random_unitary
from qiskit_aer import AerSimulator

from verifier import core

PERMS = list(itertools.permutations(range(3)))


def _sign(p) -> int:
    s = 1
    for i in range(3):
        for j in range(i + 1, 3):
            if p[i] > p[j]:
                s = -s
    return s


def singlet_amplitudes() -> np.ndarray:
    """|S> = (1/sqrt6) sum_pi sign(pi) |pi0 pi1 pi2>, each qutrit on 2 qubits: party k uses qubits 2k, 2k+1 (little-endian)."""
    amp = np.zeros(64, complex)
    for p in PERMS:
        amp[p[0] | (p[1] << 2) | (p[2] << 4)] = _sign(p) / math.sqrt(6)
    return amp


def expected() -> dict:
    return {format(p[0] | (p[1] << 2) | (p[2] << 4), "06b"): 1 / 6 for p in PERMS}


def circuit(common_basis: np.ndarray | None = None) -> QuantumCircuit:
    """Prepare the singlet; optionally all three parties measure in the same rotated qutrit basis U (3x3 unitary,
    embedded as a 4x4 block-diagonal unitary on the 2 qubits so the unused level stays apart)."""
    qc = QuantumCircuit(6)
    qc.prepare_state(singlet_amplitudes(), range(6))
    if common_basis is not None:
        U4 = np.eye(4, dtype=complex)
        U4[:3, :3] = common_basis.conj().T       # rotate into the measurement basis
        from qiskit.circuit.library import UnitaryGate
        g = UnitaryGate(U4, label="U†")
        for k in range(3):
            qc.append(g, [2 * k, 2 * k + 1])
    return qc


def decode(bits: str) -> list:
    v = int(bits.replace(" ", ""), 2)
    return [(v >> (2 * k)) & 3 for k in range(3)]


def run(shots: int = 2048, seed: int = 2026, rotate: bool = True) -> dict:
    code = "games/byzantine.circuit(): prepare_state(singlet) [+ common basis U on each qutrit]"
    stated = expected()
    h = core.commit_hash(code, stated)
    # exact distribution of the bare singlet
    exact = {format(i, "06b"): float(x) for i, x in enumerate(np.abs(Statevector(circuit()).data) ** 2) if x > 1e-15}
    ex = core.check_expectation(exact, stated)
    sim = AerSimulator(method="statevector")
    out = {"commit": h, "expectation": ex, "engine": "Aer emulator", "shots": shots, "literature": "Fitzi, Gisin, Maurer, PRL 87, 217901 (2001)"}
    # shots in the computational basis
    qc = circuit(); qc.measure_all()
    counts = {k.replace(" ", ""): v for k, v in sim.run(transpile(qc, sim), shots=shots, seed_simulator=seed).result().get_counts().items()}
    out["counts_check"] = core.check_counts(counts, exact)
    out["all_different_z"] = all(len(set(decode(b))) == 3 and max(decode(b)) < 3 for b in counts)
    out["counts"] = counts
    if rotate:
        U = random_unitary(3, seed=seed).data
        qr = circuit(U); qr.measure_all()
        cr = {k.replace(" ", ""): v for k, v in sim.run(transpile(qr, sim), shots=shots, seed_simulator=seed + 1).result().get_counts().items()}
        out["all_different_rotated"] = all(len(set(decode(b))) == 3 and max(decode(b)) < 3 for b in cr)
        out["rotated_counts"] = cr
        out["rotated_check"] = core.check_counts(cr, exact)      # the singlet is U⊗U⊗U invariant: same distribution
    # a liar: one party reports the value of another; detectable because two equal reports are impossible
    sample = next(iter(counts))
    honest = decode(sample)
    lie = list(honest); lie[2] = honest[0]
    out["liar_demo"] = {"honest_reports": honest, "party_3_lies": lie, "inconsistent": len(set(lie)) < 3,
                        "rule": "same basis for all three means three different outcomes; two equal reports expose a liar"}
    out["badge"] = core.badge(ex["ok"], out["counts_check"]["ok"] and out["all_different_z"] and out.get("all_different_rotated", True))
    out["limits"] = ("Illustration of detectable agreement on an emulator, not a contract-signing system or an unforgeable signature; "
                     "the house still sees everything classically.")
    return out
