"""Quantum voting: each agent gives a confidence c per option; encode as Ry(2*asin(sqrt(c))); run on Aer with a fixed seed;
the option with the most approvals wins each ballot (shot); the majority of ballots decides. A vote sampled from qubits; no quantum advantage claimed."""
import math
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

LABEL = "a vote sampled from qubits; no quantum advantage claimed"


def vote(confidences: dict, options: list, shots: int = 101, seed: int = 2026) -> dict:
    agents = list(confidences)
    n = len(agents) * len(options)
    qc = QuantumCircuit(n, n)
    for a, ag in enumerate(agents):
        for o, opt in enumerate(options):
            c = min(max(float(confidences[ag][opt]), 0.0), 1.0)
            qc.ry(2 * math.asin(math.sqrt(c)), a * len(options) + o)
    qc.measure(range(n), range(n))
    sim = AerSimulator(method="statevector")
    counts = sim.run(transpile(qc, sim), shots=shots, seed_simulator=seed).result().get_counts()
    wins = {o: 0 for o in options}
    for bs, cnt in counts.items():
        bits = bs[::-1]               # bit i = qubit i
        tally = [sum(int(bits[a * len(options) + o]) for a in range(len(agents))) for o in range(len(options))]
        best = max(range(len(options)), key=lambda o: (tally[o], -o))
        wins[options[best]] += cnt
    winner = max(options, key=lambda o: (wins[o], sum(confidences[a][o] for a in agents)))
    return {"winner": winner, "ballots": wins, "shots": shots, "seed": seed, "circuit_qubits": n,
            "confidences": confidences, "label": LABEL, "qasm_depth": qc.depth()}
