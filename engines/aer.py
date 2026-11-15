"""Engine: Qiskit Aer statevector emulator (the reference engine)."""
import time
from qiskit import transpile
from qiskit_aer import AerSimulator

LABEL = "Aer emulator"


def run_statevector(circ, shots: int = 1024, seed: int = 12345, with_probs: bool = True) -> dict:
    """Run on Aer. Returns exact probabilities (from the statevector) and seeded shot counts."""
    qc = circ.copy()
    if with_probs:
        qc.save_probabilities_dict()
    qc.measure_all()
    sim = AerSimulator(method="statevector")
    t0 = time.time()
    tqc = transpile(qc, sim, optimization_level=0)
    res = sim.run(tqc, shots=shots, seed_simulator=seed).result()
    data = res.data(0)
    probs = {}
    if with_probs:
        probs = {format(int(k, 16) if isinstance(k, str) and k.startswith("0x") else int(k), f"0{circ.num_qubits}b"): float(v)
                 for k, v in data["probabilities"].items()} if "probabilities" in data else {}
    counts = {k.replace(" ", ""): v for k, v in res.get_counts().items()}
    return {"engine": LABEL, "counts": counts, "exact": probs, "shots": shots, "seed": seed,
            "seconds": time.time() - t0}
