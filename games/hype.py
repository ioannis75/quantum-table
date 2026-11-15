"""Hype or Fact. Every card is decidable by a run in this repo; the verifier (code), never an agent, gives the verdict.
Card JSON: {id, sentence, origin, check:{type,...}, claim}. 'claim' is what the sentence asserts; the run decides if it holds."""
import json
import math
import time
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
import db
from games.qraps import circuits, modes
from games.qraps.modes import MODES
from verifier import core, sandbox

SEED_DECK = [
    {"id": "fermionic-doubles", "sentence": "Fermionic dice never roll doubles.", "origin": "seed deck", "check": {"type": "no_doubles", "mode": "Fermionic"}},
    {"id": "no-signalling", "sentence": "Entangled dice let the player send a message to the house instantly.", "origin": "seed deck", "check": {"type": "signalling", "mode": "BosonicEntangled"}},
    {"id": "marginal-uniform", "sentence": "Each entangled die on its own is just as random as a normal die.", "origin": "seed deck", "check": {"type": "marginal_uniform", "mode": "BosonicEntangled"}},
    {"id": "measure-twice", "sentence": "Measuring the dice twice gives a fresh random result each time.", "origin": "seed deck", "check": {"type": "repeat_measure", "mode": "Classical"}},
    {"id": "cheat-sheet", "sentence": "These correlations could be faked with a hidden cheat sheet inside the dice.", "origin": "seed deck", "check": {"type": "chsh"}},
    {"id": "all-36", "sentence": "A quantum computer rolls all 36 outcomes at once and reads them all.", "origin": "seed deck", "check": {"type": "one_shot", "mode": "Classical"}},
    {"id": "distributive", "sentence": "For quantum dice, 'A and (B or C)' always means the same as '(A and B) or (A and C)'.", "origin": "seed deck", "check": {"type": "distributive"}},
    {"id": "sum7", "sentence": "In Fermionic Entangled mode the two dice always add up to 7.", "origin": "seed deck", "check": {"type": "stat", "mode": "FermionicEntangled", "stat": "sum:7", "op": "==", "value": 1}},
    {"id": "classical-less-half", "sentence": "In Classical mode the pass line wins less than half the time.", "origin": "seed deck", "check": {"type": "stat", "mode": "Classical", "stat": "win", "op": "<", "value": 0.5}},
]
# Stand-ins for model-written cards when no model key is present (labelled as such; the Host does not know the verdicts).
STAND_IN = [
    {"id": "bosonic-win", "sentence": "In Bosonic mode the pass line wins more than half the time.", "origin": "scripted stand-in (no AI key)", "check": {"type": "stat", "mode": "Bosonic", "stat": "win", "op": ">", "value": 0.5}},
    {"id": "bosonic-doubles", "sentence": "In Bosonic mode doubles come up more than one time in four.", "origin": "scripted stand-in (no AI key)", "check": {"type": "stat", "mode": "Bosonic", "stat": "doubles", "op": ">", "value": 0.25}},
]
CARD_SYSTEM = """You are the Host writing a Hype or Fact claim card about dice. Reply with ONE JSON object only:
{"sentence": "...", "check": {"type":"stat","mode": one of %s,"stat": "win"|"doubles"|"sum:N","op": ">"|"<"|"==","value": number}}.
The sentence must say exactly what the check tests. You do NOT know whether it is true." """ % list(MODES)


def _exact_pair_probs(mode: str) -> dict:
    from agents import q_scientist
    from engines.aer import run_statevector
    d = q_scientist.design(mode)
    out = run_statevector(d["circuit"], 512)
    pairs = {}
    for bs, p in out["exact"].items():
        v = int(bs, 2)
        pairs[((v & 7) + 1, ((v >> 3) & 7) + 1)] = p
    return pairs, out


def _stat_value(mode: str, stat: str) -> tuple:
    pairs, out = _exact_pair_probs(mode)
    if stat == "win":
        v = float(modes.craps_win_probability(mode))
        return v, "exact (Fraction) craps odds from the mode table"
    if stat == "doubles":
        return sum(p for (a, b), p in pairs.items() if a == b), "exact, from the circuit's statevector"
    if stat.startswith("sum:"):
        n = int(stat.split(":")[1])
        return sum(p for (a, b), p in pairs.items() if a + b == n), "exact, from the circuit's statevector"
    raise ValueError(stat)


def _cmp(v, op, ref, tol=1e-9):
    return {">": v > ref + tol, "<": v < ref - tol, "==": abs(v - ref) <= tol}[op]


def run_card(card: dict) -> dict:
    """Run the experiment and return {truth, headline, numbers, run_id}. Raises if the check cannot be computed."""
    ck = card["check"]
    t = ck["type"]
    run_id = f"hype-{card['id']}-{int(time.time())}"
    if t == "stat":
        v, how = _stat_value(ck["mode"], ck["stat"])
        truth = _cmp(v, ck["op"], ck["value"])
        return {"truth": bool(truth), "run_id": run_id, "engine": "Aer emulator + exact enumeration",
                "headline": f"Measured by calculation: {ck['stat']} in {ck['mode']} is {v:.6f}; the claim says {ck['op']} {ck['value']}.",
                "numbers": {"value": v, "threshold": ck["value"]}, "how": how}
    if t == "no_doubles":
        pairs, out = _exact_pair_probs(ck["mode"])
        p = sum(q for (a, b), q in pairs.items() if a == b)
        seen = sum(c for bs, c in out["counts"].items() if (int(bs, 2) & 7) == ((int(bs, 2) >> 3) & 7))
        return {"truth": p == 0 and seen == 0, "run_id": run_id, "engine": "Aer emulator",
                "headline": f"Exact P(doubles) = {p:.1f}; doubles seen in {out['shots']} shots: {seen}.",
                "numbers": {"p_doubles": p, "doubles_seen": seen, "shots": out["shots"]}}
    if t == "signalling":
        from agents import q_scientist
        d = q_scientist.design(ck["mode"])
        base = circuits.table_circuit(d["circuit"], 1, modes.CROSS_RULE[ck["mode"]])
        marg = lambda c: np.array(Statevector(c).probabilities(list(range(6))))
        ref = marg(base)
        worst = 0.0
        for variant in ("h", "ry", "rz_h"):
            c = base.copy()
            for q in range(6, 12):                      # the player does something to their own dice
                if variant == "h":
                    c.h(q)
                elif variant == "ry":
                    c.ry(0.7, q)
                else:
                    c.rz(1.1, q); c.h(q)
            worst = max(worst, float(np.abs(marg(c) - ref).max()))
        return {"truth": worst > 1e-9, "run_id": run_id, "engine": "Aer / exact statevector",
                "headline": f"Biggest change in the house's own distribution after the player acted: {worst:.1e}. No message passes.",
                "numbers": {"max_change": worst}}
    if t == "marginal_uniform":
        pairs, out = _exact_pair_probs(ck["mode"])
        marg = {k: sum(p for (a, b), p in pairs.items() if a == k) for k in range(1, 7)}
        exact_uniform = all(abs(v - 1 / 6) < 1e-9 for v in marg.values())
        faces = {}
        for bs, c in out["counts"].items():
            f = (int(bs, 2) & 7) + 1
            faces[str(f)] = faces.get(str(f), 0) + c
        ch = core.check_counts(faces, {str(k): 1 / 6 for k in range(1, 7)})
        return {"truth": bool(exact_uniform and ch["ok"]), "run_id": run_id, "engine": "Aer emulator",
                "headline": f"One die on its own: exactly 1/6 per face, chi-square p = {ch['p_value']:.2f}. Correlation only shows when the two dice are compared.",
                "numbers": {"p_value": ch["p_value"], "shots": ch["shots"]}}
    if t == "repeat_measure":
        from agents import q_scientist
        d = q_scientist.design(ck["mode"])
        qc = QuantumCircuit(6, 12)
        qc.compose(d["circuit"], inplace=True)
        qc.measure(range(6), range(0, 6)); qc.measure(range(6), range(6, 12))
        sim = AerSimulator()
        cnt = sim.run(transpile(qc, sim), shots=500, seed_simulator=11).result().get_counts()
        same = sum(c for bs, c in cnt.items() if bs.replace(" ", "")[:6] == bs.replace(" ", "")[6:])
        return {"truth": same < 500, "run_id": run_id, "engine": "Aer emulator",
                "headline": f"The second measurement repeated the first in {same} of 500 shots.",
                "numbers": {"repeated": same, "shots": 500}}
    if t == "chsh":
        S, sig = _chsh()
        faked = (S - 2 * sig) <= 2        # claim: 'could be faked by a hidden cheat sheet'
        return {"truth": bool(faked), "run_id": run_id, "engine": "Aer emulator",
                "headline": f"CHSH S = {S:.3f} with sigma {sig:.3f}; S - 2 sigma = {S-2*sig:.3f} > 2, so in this simulation of quantum theory no cheat sheet fits.",
                "numbers": {"S": S, "sigma": sig}}
    if t == "one_shot":
        from agents import q_scientist
        d = q_scientist.design(ck["mode"])
        sim = AerSimulator()
        qc = d["circuit"].copy(); qc.measure_all()
        cnt = sim.run(transpile(qc, sim), shots=1, seed_simulator=5).result().get_counts()
        return {"truth": len(cnt) > 1, "run_id": run_id, "engine": "Aer emulator",
                "headline": f"One roll returned exactly {len(cnt)} outcome out of {len(MODES[ck['mode']])} possible.",
                "numbers": {"outcomes_read": len(cnt), "possible": len(MODES[ck['mode']])}}
    if t == "distributive":
        from qlogic.kit import distributivity_counterexample
        r = distributivity_counterexample()
        return {"truth": r["equal"], "run_id": run_id, "engine": "qlogic kit (exact NumPy)",
                "headline": f"On one qubit: left side {r['lhs_prob']:.1f}, right side {r['rhs_prob']:.1f}. Not the same.",
                "numbers": {"lhs": r["lhs_prob"], "rhs": r["rhs_prob"]}}
    raise ValueError("uncomputable check: " + t)


def _chsh(shots: int = 20000, seed: int = 99) -> tuple:
    sim = AerSimulator()
    angles = {("a0", "b0"): (0, np.pi / 4), ("a0", "b1"): (0, -np.pi / 4), ("a1", "b0"): (np.pi / 2, np.pi / 4), ("a1", "b1"): (np.pi / 2, -np.pi / 4)}
    E, var = {}, 0.0
    for (ka, kb), (ta, tb) in angles.items():
        qc = QuantumCircuit(2, 2); qc.h(0); qc.cx(0, 1); qc.ry(-ta, 0); qc.ry(-tb, 1); qc.measure([0, 1], [0, 1])
        cnt = sim.run(transpile(qc, sim), shots=shots, seed_simulator=seed).result().get_counts()
        e = sum((1 if bs[0] == bs[1] else -1) * c for bs, c in cnt.items()) / shots
        E[(ka, kb)] = e
        var += (1 - e * e) / shots
    S = E[("a0", "b0")] + E[("a0", "b1")] + E[("a1", "b0")] - E[("a1", "b1")]
    return abs(S), math.sqrt(var)


def validate(card: dict) -> bool:
    """Cards whose check cannot be computed are discarded before they reach the table."""
    try:
        run_card(card)
        return True
    except Exception:
        return False


def model_card() -> dict | None:
    """Host (model) writes a card in the stat schema. Returns None without a model."""
    from agents import llm
    try:
        text, label = llm.anthropic_ask(CARD_SYSTEM, "Write one new claim card. Vary the mode and statistic.", "fast", 300)
        import re
        j = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        card = {"id": f"model-{int(time.time())}", "sentence": j["sentence"], "origin": f"AI-written ({label})", "check": j["check"]}
        if card["check"].get("type") == "stat" and validate(card):
            return card
    except Exception:
        pass
    return None
