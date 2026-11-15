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

SYSTEM = """You are the Logic designer for a dice table. Write statements in QUANTUM LOGIC (Birkhoff-von Neumann): a statement is a
subspace; AND = intersection, OR = span, NOT = orthogonal complement. Atoms: face(die,k), sum(a,b)==n, equal(a,b), qubit(i,axis,sign).
Dice are die 0 and die 1. Reply with ONE JSON object, no fences, in this contract:
{"task":"craps pass line","reasoning":["at most 3 short steps"],
 "propositions":[{"name":"win","expr":"sum(0,1)==7 OR sum(0,1)==11"},{"name":"lose","expr":"sum(0,1)==2 OR sum(0,1)==3 OR sum(0,1)==12"},
                 {"name":"point_4","expr":"sum(0,1)==4"}, ... point_5, point_6, point_8, point_9, point_10],
 "queries":[{"type":"prob","propositions":["win"]}, ...],
 "prediction":{"win":"8/36","lose":"4/36", ...}}
Exact fractions as strings. A code kit evaluates every proposition exactly and overrides your prediction. If the task is unclear reply {"status":"needs_clarification","reason":"..."}."""

# ---- tolerant parser for the Iris output contract (string or JSON expressions) ---------------------------------
_TOK = re.compile(r"\s*(\(|\)|==|,|NOT|AND|OR|[A-Za-z_]+|-?\d+)", re.I)


def parse_expr(src):
    """'sum(0,1)==7 OR NOT face(0,3)' -> kit JSON. Also accepts the kit's JSON form unchanged."""
    if isinstance(src, dict):
        return src
    toks = [t for t in _TOK.findall(src)]
    pos = [0]

    def peek():
        return toks[pos[0]].upper() if pos[0] < len(toks) else None

    def eat(x=None):
        t = toks[pos[0]]; pos[0] += 1
        if x and t.upper() != x:
            raise ValueError(f"expected {x} got {t}")
        return t

    def atom():
        if peek() == "(":
            eat("("); e = expr_or(); eat(")"); return e
        if peek() == "NOT":
            eat("NOT"); return {"op": "not", "args": [atom()]}
        name = eat().lower(); eat("(")
        args = []
        while peek() != ")":
            t = eat()
            if t != ",":
                args.append(t)
        eat(")")
        if name == "face":
            return {"atom": "face", "die": int(args[0]), "k": int(args[1])}
        if name == "sum":
            eat("=="); n = int(eat()); return {"atom": "sum", "n": n}
        if name == "equal":
            return {"atom": "equal", "a": int(args[0]) if args else 0, "b": int(args[1]) if len(args) > 1 else 1}
        if name == "qubit":
            return {"atom": "qubit", "i": int(args[0]), "axis": args[1].upper(), "sign": int(args[2])}
        raise ValueError("unknown atom " + name)

    def expr_and():
        e = atom()
        while peek() == "AND":
            eat("AND"); e = {"op": "and", "args": [e, atom()]}
        return e

    def expr_or():
        e = expr_and()
        while peek() == "OR":
            eat("OR"); e = {"op": "or", "args": [e, expr_and()]}
        return e
    out = expr_or()
    if pos[0] != len(toks):
        raise ValueError("trailing tokens")
    return out


def normalise(stm: dict) -> dict:
    """Accept the legacy {win,lose,points} form or the Iris contract {propositions,queries,prediction}."""
    if not isinstance(stm, dict) or stm.get("status") == "needs_clarification":
        raise ValueError("model asked for clarification")
    if "propositions" in stm:
        props = {p["name"].lower(): parse_expr(p["expr"]) for p in stm["propositions"] if "name" in p and "expr" in p}
        out = {"win": props.get("win"), "lose": props.get("lose"), "points": {}, "prediction": stm.get("prediction", {}),
               "reasoning": stm.get("reasoning", [])}
        for n in (4, 5, 6, 8, 9, 10):
            k = next((x for x in (f"point_{n}", f"point{n}", str(n)) if x in props), None)
            if k:
                out["points"][str(n)] = props[k]
        return out
    out = {"win": parse_expr(stm["win"]) if "win" in stm else None, "lose": parse_expr(stm["lose"]) if "lose" in stm else None,
           "points": {k: parse_expr(v) for k, v in stm.get("points", {}).items()}, "prediction": stm.get("prediction", {})}
    return out

_cache: dict = {}


def user_message(mode: str) -> str:
    return (f"Task: craps pass line for the dice mode '{mode}'. The two dice are die 0 and die 1; each roll the pair "
            f"(die 0, die 1) is uniform over exactly these face pairs: {MODES[mode]}. Rules: at the come-out a total of 7 or 11 "
            f"wins, 2, 3 or 12 loses, any other total (4, 5, 6, 8, 9, 10) becomes the point. Write the propositions win, lose, "
            f"point_4, point_5, point_6, point_8, point_9, point_10 in the expr grammar, the prob queries for each, and your "
            f"prediction as exact fractions. Reply with the single JSON object only.")


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
    for fn, tag in ((llm.oumi_ask, ""), (lambda s, u, **k: llm.anthropic_ask(s, u, "smart", 2500, timeout=60), "fallback")):
        try:
            text, label = fn(SYSTEM, user_message(mode))
            m = re.search(r"\{.*\}", text, re.S)
            stm = normalise(json.loads(m.group(0)))
            source = label if not tag else label.replace("Claude (", "Claude (fallback, ")
            break
        except Exception:
            stm = None
            continue
    if stm is None:
        stm = normalise(_scripted())
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

    win, wc = evaluate(stm.get("win") or _scripted()["win"], (7, 11))
    lose, lc = evaluate(stm.get("lose") or _scripted()["lose"], (2, 3, 12))
    points = {}
    for n in (4, 5, 6, 8, 9, 10):
        node = stm.get("points", {}).get(str(n), {"atom": "sum", "n": n})
        points[n] = evaluate(node, (n,))[0]
    # the model's own prediction is checked against the kit; a mismatch is shown as "Logic designer corrected"
    from fractions import Fraction
    pred_checks = []
    kit_vals = {"win": win, "lose": lose, **{f"point_{n}": v for n, v in points.items()}}
    for name, val in (stm.get("prediction") or {}).items():
        if name not in kit_vals or not isinstance(val, str) or "/" not in val:
            continue
        try:
            pv = float(Fraction(val))
        except Exception:
            continue
        ok = abs(pv - kit_vals[name]) < 1e-9
        pred_checks.append({"name": name, "model": val, "kit": kit_vals[name], "ok": ok})
        if not ok:
            corrected.append({"name": name, "model_prediction": val, "kit": kit_vals[name]})
            db.bump("logic_corrected")
    out = {"mode": mode, "source": source, "statements": stm, "prediction": stm.get("prediction", {}), "prediction_checks": pred_checks, "p_win_comeout": win, "p_lose_comeout": lose,
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
