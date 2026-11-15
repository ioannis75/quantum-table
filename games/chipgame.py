"""The front-page game: one craps table on the chip.
Each die is a 6-level qudit stored in 3 physical qubits. A player owns two dice (6 qubits); the house owns the six qubits
entangled with them ("hearts"). Every roll runs a real circuit: each house die is prepared as a uniform superposition over
faces 1-6 (values 0..5 on 3 qubits); the player's die is either a CNOT copy of the house die (entangled circuit) or an
independent uniform die (independent circuit). The entanglement level L in [0,1] is the probability, drawn from the
emulator's seeded RNG, that a roll uses the entangled circuit; L=1 means every roll is entangled. Circuits are kept shallow
on purpose: an exact partially-entangled pure state needs ~100 two-qubit gates after transpiling to the heavy-hex and the
noise model erases the correlation (measured in the build log).
The shot that decides the game comes from the noise model of the assigned physical qubits (fake backend calibration).
"""
import hashlib
import json
import math
import random
import time

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector, partial_trace, entropy
from qiskit_aer import AerSimulator

import db
import events
from engines import ibm
from verifier import core

LOG2_6 = math.log2(6)
ROW_STARTS = [0, 18, 37, 56, 75, 94, 113]          # one 12-qubit row segment per player on fake_brisbane
COLOURS = ["#4aa3ff", "#f0b429", "#2fbf71", "#c084fc", "#ff8a65", "#26c6da", "#f06292"]
_state = {"level": 1.0, "shots": 1, "players": {}, "last": None, "agg": {}, "cache": {}}
_rng = random.Random(2026)
_ideal = AerSimulator(method="statevector")


# ---------------- layout on the chip ----------------
def assign_layout(seat: int) -> dict:
    """Seat k (1-based) gets a 12-qubit row segment: house A, player A, house B, player B, 3 qubits each."""
    r = ROW_STARTS[(seat - 1) % len(ROW_STARTS)]
    q = list(range(r, r + 12))
    return {"house": [q[0:3], q[6:9]], "player": [q[3:6], q[9:12]], "colour": COLOURS[(seat - 1) % len(COLOURS)],
            "links": [[q[i], q[3 + i]] for i in range(3)] + [[q[6 + i], q[9 + i]] for i in range(3)]}


def join(nick: str) -> dict:
    seat = len(_state["players"]) + 1
    if seat > len(ROW_STARTS):
        raise ValueError("table full (7 seats)")
    pid = "g" + hashlib.sha256(f"{time.time()}{seat}{nick}".encode()).hexdigest()[:8]
    p = {"id": pid, "nick": nick[:16] or "Player", "seat": seat, "qredits": 100, "point": None, **assign_layout(seat)}
    _state["players"][pid] = p
    events.emit("player_joined", {"nick": p["nick"], "qredits": 100, "seat": seat, "qubits": 12 * seat})
    events.emit("dice_entangled", {"nick": p["nick"], "rule": "equal"})
    return p


def reset():
    _state["players"].clear(); _state["last"] = None; _state["agg"].clear()


# ---------------- circuits ----------------
def _uniform6() -> np.ndarray:
    u = np.zeros(8); u[:6] = 1 / math.sqrt(6); return u


def die_pair_circuit(entangled: bool) -> QuantumCircuit:
    """6 qubits: house die on 0-2, player die on 3-5. No measurements."""
    qc = QuantumCircuit(6)
    qc.prepare_state(_uniform6(), [0, 1, 2])
    if entangled:
        qc.cx(0, 3); qc.cx(1, 4); qc.cx(2, 5)
    else:
        qc.prepare_state(_uniform6(), [3, 4, 5])
    return qc


def expected_pair(entangled: bool) -> dict:
    """Stated exact distribution of (house value h, player value p) as 6-bit strings (Qiskit order, player bits on the left)."""
    out = {}
    for h in range(6):
        for p in range(6):
            if entangled and p != h:
                continue
            out[format(h | (p << 3), "06b")] = (1 / 6) if entangled else (1 / 36)
    return out


def table_circuit(entangled: bool) -> QuantumCircuit:
    """12 qubits = two die pairs: [houseA(0-2), playerA(3-5), houseB(6-8), playerB(9-11)]."""
    qc = QuantumCircuit(12, 12)
    qc.compose(die_pair_circuit(entangled), qubits=range(0, 6), inplace=True)
    qc.compose(die_pair_circuit(entangled), qubits=range(6, 12), inplace=True)
    return qc


def expected_table(entangled: bool) -> dict:
    a = expected_pair(entangled)
    return {kb + ka: pa * pb for ka, pa in a.items() for kb, pb in a.items()}   # pair B is the high 6 bits


def decode(bits: str) -> dict:
    """12-bit string -> values; faces 1..6 or None for an invalid level (6, 7)."""
    v = int(bits.replace(" ", ""), 2)
    val = lambda s: ((v >> s) & 7)
    face = lambda x: x + 1 if x < 6 else None
    return {"house": [face(val(0)), face(val(6))], "player": [face(val(3)), face(val(9))]}


def entanglement_entropy(entangled: bool) -> float:
    sv = Statevector(die_pair_circuit(entangled))
    return float(entropy(partial_trace(sv, [0, 1, 2]), base=2))


# ---------------- running ----------------
def _transpiled(entangled: bool, layout: list):
    key = (entangled, tuple(layout))
    if key not in _state["cache"]:
        sim = AerSimulator.from_backend(ibm.fake_backend())
        qc = table_circuit(entangled); qc.measure(range(12), range(12))
        t = transpile(qc, sim, initial_layout=layout, optimization_level=3, seed_transpiler=7)
        _state["cache"][key] = (sim, t, fidelity_estimate(t))
    return _state["cache"][key]


def fidelity_estimate(tqc) -> dict:
    """Product of (1 - error) over every gate and readout in the transpiled circuit, from the backend's calibration."""
    tgt = ibm.fake_backend().target
    f, n1, n2 = 1.0, 0, 0
    for inst in tqc.data:
        name = inst.operation.name
        if name in ("barrier", "delay"):
            continue
        phys = tuple(tqc.find_bit(q).index for q in inst.qubits)
        try:
            e = tgt[name][phys].error or 0.0
        except Exception:
            e = 0.0
        f *= (1 - e)
        if len(phys) == 2:
            n2 += 1
        elif name != "measure":
            n1 += 1
    return {"fidelity": round(f, 4), "two_qubit_gates": n2, "one_qubit_gates": n1, "depth": tqc.depth()}


def _settings_key(entangled: bool) -> str:
    return f"{'entangled' if entangled else 'independent'}"


def roll(pid: str, level: float | None = None, shots: int | None = None) -> dict:
    p = _state["players"].get(pid)
    if not p:
        raise ValueError("join first")
    level = _state["level"] if level is None else max(0.0, min(1.0, float(level)))
    shots = _state["shots"] if shots is None else (100 if int(shots) >= 100 else 1)
    _state["level"], _state["shots"] = level, shots
    coin = _rng.random()
    entangled = coin < level
    layout = p["house"][0] + p["player"][0] + p["house"][1] + p["player"][1]
    # (1) exact check of the circuit against the stated distribution
    qc = table_circuit(entangled)
    exact = {format(i, "012b"): float(x) for i, x in enumerate(np.abs(Statevector(qc).data) ** 2) if x > 1e-15}
    stated = expected_table(entangled)
    ex = core.check_expectation(exact, stated)
    code = f"die_pair_circuit(entangled={entangled}) x2  # games/chipgame.py"
    h = core.commit_hash(code, stated)
    # (2) the shot(s) that decide the game: noise model of the assigned physical qubits
    sim, tqc, fid = _transpiled(entangled, layout)
    seed = int(hashlib.sha256(f"{pid}{time.time()}{coin}".encode()).hexdigest()[:8], 16)
    counts = sim.run(tqc, shots=shots, seed_simulator=seed).result().get_counts()
    if shots == 1:
        bits = next(iter(counts))
    else:   # majority face per die, from the aggregate of this roll's shots
        tally = {}
        for b, c in counts.items():
            d = decode(b)
            tally[(tuple(d["house"]), tuple(d["player"]))] = tally.get((tuple(d["house"]), tuple(d["player"])), 0) + c
        bits = next(b for b in counts if (tuple(decode(b)["house"]), tuple(decode(b)["player"])) == max(tally, key=tally.get))
    faces = decode(bits)
    misfire = any(f is None for f in faces["house"] + faces["player"])
    # (3) aggregate verifier over all rolls with the same settings (one shot cannot be chi-square tested)
    key = _settings_key(entangled)
    agg = _state["agg"].setdefault(key, {"noisy": {}, "ideal": {}, "rolls": 0})
    for b, c in counts.items():
        agg["noisy"][b] = agg["noisy"].get(b, 0) + c
    ideal_counts = _ideal.run(transpile(table_circuit_measured(entangled), _ideal), shots=shots, seed_simulator=seed).result().get_counts()
    for b, c in ideal_counts.items():
        agg["ideal"][b] = agg["ideal"].get(b, 0) + c
    agg["rolls"] += 1
    ideal_check = core.check_counts(agg["ideal"], exact) if sum(agg["ideal"].values()) >= 30 else None
    noisy_hw = core.check_hardware(agg["noisy"], exact)
    nshots = sum(agg["noisy"].values())
    badge = ("EXPECTATION WRONG" if not ex["ok"] else
             f"VERIFIED: exact circuit check this roll; aggregate {agg['rolls']} rolls ({nshots} shots, {key}): "
             + (f"ideal emulator chi-square p={ideal_check['p_value']:.2f}, " if ideal_check else "chi-square needs 30+ shots, ")
             + f"noise-model TVD vs exact {noisy_hw['tvd_ideal']:.2f}")
    ok = ex["ok"] and (ideal_check is None or ideal_check["ok"])
    if ex["ok"] and ideal_check and not ideal_check["ok"]:
        badge = "CHECK FAILED: aggregate ideal shots disagree with the exact distribution"
    res = {"player": pid, "nick": p["nick"], "entangled": entangled, "level": level, "coin": round(coin, 3), "shots": shots,
           "faces": faces, "misfire": misfire, "bits": bits, "engine": "Simulated chip (fake backend noise model, fake_brisbane)",
           "layout": layout, "fidelity": fid, "entropy_bits": round(entanglement_entropy(entangled), 3), "entropy_max": round(LOG2_6, 3),
           "expectation": ex, "commit": h, "aggregate": {"rolls": agg["rolls"], "shots": nshots, "ideal_check": ideal_check,
                                                          "noisy_tvd_vs_exact": noisy_hw["tvd_ideal"], "settings": key},
           "badge": badge, "ok": ok}
    if not misfire:
        res.update(_craps(p, faces["player"]))
    else:
        res["outcome"] = "misfire: an invalid level (7 or 8) was read on the chip model; no result, roll again"
    _state["last"] = res
    events.emit("roll_result", {"round": agg["rolls"], "faces": "-".join(str(f or "x") for f in faces["house"]), "engine": "Simulated chip", "n": 12})
    events.emit("verifier_verdict", {"round": agg["rolls"], "badge": badge.split(":")[0]})
    return res


def table_circuit_measured(entangled: bool) -> QuantumCircuit:
    qc = table_circuit(entangled); qc.measure(range(12), range(12)); return qc


def _craps(p: dict, faces: list) -> dict:
    a, b = faces
    total = a + b
    out = {"player_total": total}
    q = p["qredits"]
    if p["point"] is None:
        q -= 5
        if total in (7, 11):
            q += 10; out["outcome"] = "win"
        elif total in (2, 3, 12):
            out["outcome"] = "lose"
        else:
            p["point"] = total; out["outcome"] = f"point {total}"
    else:
        if total == p["point"]:
            q += 10; out["outcome"] = "win"; p["point"] = None
        elif total == 7:
            out["outcome"] = "lose"; p["point"] = None
        else:
            out["outcome"] = f"point {p['point']}, rolled {total}"
    p["qredits"] = max(q, 0)
    out["qredits"] = p["qredits"]; out["point"] = p["point"]
    return out


def state() -> dict:
    return {"level": _state["level"], "shots": _state["shots"], "players": list(_state["players"].values()),
            "last": _state["last"], "aggregate": {k: {"rolls": v["rolls"], "shots": sum(v["noisy"].values())} for k, v in _state["agg"].items()},
            "backend": ibm.fake_backend().name, "label": ibm.FAKE_LABEL, "seats": len(ROW_STARTS)}


def used_region() -> dict:
    """Chip-map viewport around the rows in use (or the first row before anyone joins)."""
    pos = ibm._positions()
    qs = [q for p in _state["players"].values() for d in (p["house"] + p["player"]) for q in d] or list(range(0, 12))
    xs = [pos[q][0] for q in qs]; ys = [pos[q][1] for q in qs]
    return {"x0": min(xs) - 1, "y0": min(ys) - 1, "w": max(xs) - min(xs) + 2, "h": max(ys) - min(ys) + 2}
