"""Logic designer (Oumi, fallback Claude, fallback scripted). Writes game statements as quantum-logic JSON; the qlogic kit
evaluates them exactly; direct enumeration has the last word ('Logic designer corrected')."""
import json
import re
import numpy as np
import config
import db
from games.qraps import modes
from games.qraps.modes import MODES, total_dist
from qlogic.kit import QLogic, pair_state, implies_on_state, diag_face, side_bet_check
from . import llm, registry

SYSTEM = """You are the Logic designer for a dice table. Write statements in QUANTUM LOGIC as JSON only.
Grammar: {"atom":"sum","n":7} | {"atom":"face","die":0,"k":3} | {"atom":"equal"} | {"atom":"qubit","i":0,"axis":"X","sign":1}
| {"op":"and"|"or","args":[...]} | {"op":"not","args":[x]}. Dice are die 0 and die 1. Reply with ONE JSON object:
{"win":<stmt>,"lose":<stmt>,"points":{"4":<stmt>,"5":<stmt>,...}} for the craps pass line (come-out 7/11 win, 2/3/12 lose, other totals are points)."""

_cache: dict = {}


def _scripted() -> dict:
    s = lambda n: {"atom": "sum", "n": n}
    return {"win": {"op": "or", "args": [s(7), s(11)]},
            "lose": {"op": "or", "args": [s(2), s(3), s(12)]},
            "points": {str(n): s(n) for n in (4, 5, 6, 8, 9, 10)}}


def statements(mode: str) -> dict:
    if mode in _cache:
        return _cache[mode]
    registry.set_status("logic_designer", "working")
    stm, source = None, "scripted statements"
    for fn, name in ((llm.oumi_ask, None), (lambda s, u, **k: llm.anthropic_ask(s, u, "smart", 900), None)):
        try:
            text, label = fn(SYSTEM, f"Mode {mode}. Pairs: {MODES[mode]}")
            m = re.search(r"\{.*\}", text, re.S)
            stm, source = json.loads(m.group(0)), label
            break
        except Exception:
            continue
    if stm is None:
        stm = _scripted()
    ql = QLogic(6)
    psi = pair_state(MODES[mode])
    td = total_dist(mode)
    corrected = []

    def evaluate(node, truth_totals):
        try:
            p_kit = ql.prob(ql.build(node), psi)
        except Exception as e:
            p_kit = None
        p_enum = float(sum(td.get(t, 0) for t in truth_totals))
        if p_kit is None or abs(p_kit - p_enum) > 1e-9:
            corrected.append({"kit": p_kit, "enumeration": p_enum})
            from db import bump
            bump("logic_corrected")
            return p_enum, True
        return p_kit, False

    win, wc = evaluate(stm.get("win", _scripted()["win"]), (7, 11))
    lose, lc = evaluate(stm.get("lose", _scripted()["lose"]), (2, 3, 12))
    points = {}
    for n in (4, 5, 6, 8, 9, 10):
        node = stm.get("points", {}).get(str(n), {"atom": "sum", "n": n})
        points[n] = evaluate(node, (n,))[0]
    out = {"mode": mode, "source": source, "statements": stm, "p_win_comeout": win, "p_lose_comeout": lose,
           "p_point": points, "corrected": corrected, "corrected_flag": bool(corrected),
           "pass_line_win_exact": float(modes.craps_win_probability(mode))}
    _cache[mode] = out
    registry.set_status("logic_designer", "idle", source)
    return out


def entanglement_implication(mode: str, rule: str, table_psi: np.ndarray, n_qubits: int) -> dict:
    """In an 'equal' mode face(player die A, k) implies face(house die A, k) on the prepared state's support."""
    results = []
    for k in range(1, 7):
        if rule == "equal":
            Q = diag_face(n_qubits, 0, k)
        else:
            Q = diag_face(n_qubits, 0, 7 - k)
        results.append(implies_on_state(diag_face(n_qubits, 2, k), Q, table_psi))
    return {"rule": rule, "implications_hold": all(results), "per_face": results}


def side_bet(mode: str, a: dict, b: dict) -> dict:
    return side_bet_check(QLogic(6), a, b)
