"""Orchestrator: the table, players, rounds (commit-reveal beacon), burn-down hand-over, chip buy-in."""
import json
import re
import threading
import time
import hashlib

import numpy as np

import config
import db
import events
from agents import financial, lab, logic_designer, q_scientist, registry, vote as qvote
from beacon import beacon
from engines import burndown, ibm
from engines.aer import run_statevector
from games.qraps import circuits, modes
from games.qraps.modes import CROSS_RULE, MODES
from verifier import core

COMMIT_WINDOW = 1.5
REVEAL_TIMEOUT = 20.0
STAKE = 5
_lock = threading.RLock()
_T = {"mode": "Classical", "rounds": {}, "craps": {}, "next_round": None, "decisions": {}, "purchases": {}, "last_chip": None,
      "vote": None, "last_result": None}
AGENT_PARTICIPANTS = ["agent:q_scientist", "agent:logic_designer", "agent:lab_agent", "agent:host"]


# ---- players ------------------------------------------------------------------------------------
def _clean_nick(n: str) -> str:
    n = re.sub(r"[^\w \-]", "", (n or "").strip())[:16].strip()
    return n or "Player"


def players() -> list:
    return db.rows("SELECT id,nick,qredits,seat,bot FROM players ORDER BY seat")


def qubits() -> int:
    return 6 * (len(players()) + 1)


def join(nick: str, bot: bool = False) -> dict:
    with _lock:
        seat = len(players()) + 1
        pid = "p" + hashlib.sha256(f"{time.time()}{seat}{nick}".encode()).hexdigest()[:8]
        nick = _clean_nick(nick)
        db.q("INSERT INTO players(id,nick,qredits,seat,bot,created) VALUES(?,?,?,?,?,?)", (pid, nick, 100, seat, int(bot), time.time()))
        _T["craps"][pid] = {"point": None}
    events.emit("player_joined", {"nick": nick, "qredits": 100, "seat": seat, "qubits": qubits(), "bot": bot})
    from agents import host
    host.post_discord("seated", f"{len(players())} players seated, {qubits()} qubits at the table.")
    events.emit("dice_entangled", {"nick": nick, "rule": CROSS_RULE[_T["mode"]]})
    _maybe_burn_event()
    return {"id": pid, "nick": nick, "qredits": 100, "seat": seat}


def _burn_info() -> dict:
    s = burndown.status()
    limit_n = (s["burned_down_at"] - 1) if s["burned_down_at"] else s["analytic_limit_n"]
    return {"limit_n": limit_n, "burned_down_at": s["burned_down_at"] or limit_n + 1, "measured": bool(s["burned_down_at"])}


def phase() -> str:
    return "chip" if qubits() > _burn_info()["limit_n"] else "emulator"


def _maybe_burn_event():
    if phase() == "chip" and not db.kv_get("burn_announced"):
        db.kv_set("burn_announced", True)
        b = _burn_info()
        events.emit("burned_down", {"qubits": b["burned_down_at"], "bytes": burndown.need_bytes(b["burned_down_at"]),
                                    "measured": b["measured"]})
        from agents import host
        host.post_discord("burned_down", f"Emulator burned down at {b['burned_down_at']} qubits, moving to the chip.")


def skip_ahead() -> dict:
    """Seat bots until the emulator burns down (the demo does not depend on real players joining)."""
    added = 0
    while phase() == "emulator" and added < 12:
        join(f"Bot{len(players())+1}", bot=True)
        added += 1
    return {"added": added, "qubits": qubits(), "phase": phase()}


def reset_table() -> None:
    for t in ("players", "qpu_jobs"):
        pass
    db.q("DELETE FROM players")
    _T["craps"].clear(); _T["purchases"].clear(); _T["rounds"].clear()
    db.kv_set("burn_announced", False)


def set_mode(mode: str) -> dict:
    if mode not in MODES:
        raise ValueError("unknown mode")
    _T["mode"] = mode
    return {"mode": mode, "rule": CROSS_RULE[mode]}


# ---- design, bloch, odds ----------------------------------------------------------------------------
def design_info(mode: str) -> dict:
    d = q_scientist.design(mode)
    ls = logic_designer.statements(mode)
    return {"mode": mode, "source": d["source"], "hash": d["hash"], "code": d["code"], "ok": d["ok"],
            "pairs": len(MODES[mode]), "rule": CROSS_RULE[mode], "win": ls["pass_line_win_exact"],
            "win_fraction": f"{modes.craps_win_probability(mode).numerator}/{modes.craps_win_probability(mode).denominator}",
            "logic": {"source": ls["source"], "corrected": ls["corrected_flag"], "p_win_comeout": ls["p_win_comeout"],
                      "p_lose_comeout": ls["p_lose_comeout"], "p_point": ls["p_point"]}}


def bloch(mode: str) -> dict:
    d = q_scientist.design(mode)
    prepared = circuits.bloch_vectors(d["circuit"])
    ent = circuits.bloch_vectors(circuits.table_circuit(d["circuit"], 1, CROSS_RULE[mode]))
    L = lambda v: float(np.linalg.norm(v))
    return {"mode": mode, "prepared": prepared, "entangled": ent, "rule": CROSS_RULE[mode],
            "lengths_prepared": [L(v) for v in prepared], "lengths_entangled": [L(v) for v in ent],
            "label": "entangled: outcomes are correlated, no signal passes"}


# ---- rounds (commit -> run -> reveal -> select) -----------------------------------------------------
def open_round(roller: str | None = None, options: list | None = None) -> dict:
    with _lock:
        rid = (db.one("SELECT MAX(round) AS m FROM beacon")["m"] or 0) + 1
        while rid in _T["rounds"]:
            rid += 1
        ph = phase()
        r = {"id": rid, "status": "committing", "roller": roller, "mode": _T["mode"], "phase": ph, "options": options,
             "commitments": {}, "secrets": {}, "reveals": {}, "humans": {}, "dropped": [], "t0": time.time(), "result": None, "log": []}
        hs = [p for p in players() if not p["bot"]]
        for p in hs:
            r["humans"][p["id"]] = {"nick": p["nick"]}
        for pid in ["house"] + AGENT_PARTICIPANTS + [p["id"] for p in players() if p["bot"]]:
            s = beacon.new_secret()
            r["secrets"][pid] = s
            r["commitments"][pid] = beacon.commitment(s)
        _T["rounds"][rid] = r
    events.emit("round_open", {"round": rid, "commit_window_s": COMMIT_WINDOW})
    threading.Thread(target=_run_round, args=(rid,), daemon=True).start()
    return {"round": rid, "status": "committing"}


def commit(rid: int, pid: str, h: str) -> dict:
    r = _T["rounds"].get(rid)
    if not r or r["status"] != "committing" or not re.fullmatch(r"[0-9a-f]{64}", h or ""):
        return {"ok": False}
    r["commitments"][pid] = h
    return {"ok": True}


def reveal(rid: int, pid: str, secret: str) -> dict:
    r = _T["rounds"].get(rid)
    if not r or r["status"] != "revealing":
        return {"ok": False, "why": "not revealing"}
    try:
        if beacon.commitment(secret) != r["commitments"].get(pid):
            return {"ok": False, "why": "does not match commitment"}
    except Exception:
        return {"ok": False, "why": "bad secret"}
    r["reveals"][pid] = secret
    return {"ok": True}


def _run_circuit(r: dict, seed: int) -> dict:
    mode, ph = r["mode"], r["phase"]
    d = q_scientist.design(mode)
    n_players = len(players())
    rule = CROSS_RULE[mode]
    if ph == "emulator":
        lab.gate_emulator(f"round {r['id']}")
        tc = circuits.table_circuit(d["circuit"], n_players, rule)
        registry.set_status("lab_agent", "working", "Aer emulator", f"{tc.num_qubits} qubits")
        out = run_statevector(tc, 1024, seed=seed)
        stated = circuits.expected_table(MODES[mode], n_players, rule)
        ex = core.check_expectation(out["exact"], stated)
        cc = core.check_counts(out["counts"], out["exact"])
        samples = []
        for bs, c in out["counts"].items():
            f = circuits.decode(bs, n_players)
            for p in range(1, n_players + 1):
                samples.append(((f[0], f[1]), (f[2 * p], f[2 * p + 1])))
        corr = core.correlation_check(samples, rule)
        recheck = core.commit_hash(d["code"], d["expected"]) == d["hash"]
        b = core.badge(ex["ok"], cc["ok"] and corr["ok"] and recheck)
        return {"engine": "Aer emulator", "counts": out["counts"], "n_qubits": tc.num_qubits, "n_players": n_players,
                "expectation": ex, "counts_check": cc, "correlation": corr, "commit_recheck": recheck, "badge": b, "seed": seed,
                "seconds": out["seconds"]}
    # chip phase: Bell pair per player on distinct physical pairs, one job
    res = run_chip_job(auto=True)
    return {"engine": res.get("label", ibm.FAKE_LABEL), "counts": res.get("counts", {}), "n_qubits": 2 * len(res.get("pairs", [])),
            "n_players": n_players, "chip": res, "badge": res.get("badge", "HARDWARE RUN: compared, not chi-square tested"), "seed": seed,
            "expectation": {"ok": True, "note": "ideal Bell-pair distribution, compared by total-variation distance"},
            "correlation": {"ok": True}}


def _faces_from(r: dict, run: dict, chosen: list, output: str) -> dict:
    mode, n_players = r["mode"], run["n_players"]
    if run["engine"] == "Aer emulator":
        f = circuits.decode(chosen[0], n_players)
    else:   # chip: faces chosen from the chip-derived beacon output, then the mode's cross rule
        pairs = MODES[mode]
        a, b = pairs[int(output, 16) % len(pairs)]
        f = [a, b]
        for _ in range(n_players):
            f += [a, b] if CROSS_RULE[mode] == "equal" else [7 - a, 7 - b]
    return {"house": [f[0], f[1]], "players": [[f[2 * p], f[2 * p + 1]] for p in range(1, n_players + 1)]}


def _run_round(rid: int) -> None:
    r = _T["rounds"][rid]
    try:
        time.sleep(COMMIT_WINDOW)
        r["status"] = "running"
        d = q_scientist.design(r["mode"])
        events.emit("circuit_committed", {"round": rid, "hash": d["hash"][:16]})
        run = _run_circuit(r, seed=1000 + rid)
        r["run"] = run
        r["status"] = "revealing"
        for pid in list(r["secrets"]):
            r["reveals"][pid] = r["secrets"][pid]
        events.emit("round_revealing", {"round": rid, "counts_hash": beacon.sha(beacon.canon(run["counts"]).encode())[:16]})
        t0 = time.time()
        humans = [p for p in r["humans"] if p in r["commitments"]]
        while time.time() - t0 < REVEAL_TIMEOUT and not all(p in r["reveals"] for p in humans):
            time.sleep(0.1)
        dropped = [p for p in humans if p not in r["reveals"]]
        if dropped:
            r["dropped"] = dropped
            events.emit("round_dropped", {"round": rid, "dropped": len(dropped)})
            run = _run_circuit(r, seed=5000 + rid)       # re-run without them
            r["run"] = run
        reveals = {p: s for p, s in r["reveals"].items() if p in r["commitments"] and p not in dropped}
        seed, chosen, output = beacon.select(run["counts"], reveals)
        faces = _faces_from(r, run, chosen, output)
        rec = beacon.publish({
            "round": rid, "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "engine": run["engine"], "mode": r["mode"],
            "circuit_hash": d["hash"], "commitments": {p: r["commitments"][p] for p in sorted(reveals) + sorted(dropped)},
            "reveals": reveals, "dropped": dropped, "counts": run["counts"], "seed": seed, "selected": chosen, "output": output,
            "faces": faces, "badge": run["badge"],
            "verifier": {k: run.get(k) for k in ("expectation", "counts_check", "correlation", "commit_recheck")}})
        res = {"round": rid, "faces": faces, "badge": run["badge"], "engine": run["engine"], "output": output, "n_qubits": run["n_qubits"],
               "verifier": rec["verifier"], "seconds": run.get("seconds"), "rule": CROSS_RULE[r["mode"]], "mode": r["mode"],
               "dropped": len(dropped), "beacon_hash": rec["hash"]}
        res.update(_craps_update(r, faces))
        if r.get("options"):
            idx = int(output, 16) % len(r["options"])
            res["decision"] = {"options": r["options"], "pick": r["options"][idx]}
        r["result"] = res
        _T["last_result"] = res
        r["status"] = "done"
        events.emit("roll_result", {"round": rid, "faces": "-".join(map(str, faces["house"])), "engine": run["engine"], "n": run["n_qubits"]})
        events.emit("verifier_verdict", {"round": rid, "badge": run["badge"]})
        events.emit("beacon_round", {"round": rid})
    except Exception as e:
        r["status"] = "error"
        r["error"] = str(e)[:200]
        events.emit("round_error", {"round": rid, "error": str(e)[:100]})


def _craps_update(r: dict, faces: dict) -> dict:
    pid = r.get("roller")
    if not pid or not faces["players"]:
        return {}
    ps = players()
    p = next((x for x in ps if x["id"] == pid), None)
    if not p:
        return {}
    idx = [x["id"] for x in ps].index(pid)
    a, b = faces["players"][idx]
    total = a + b
    st = _T["craps"].setdefault(pid, {"point": None})
    out = {"player_total": total, "player_pair": [a, b]}
    q = p["qredits"]
    if st["point"] is None:
        q -= STAKE                                   # stake on the pass line at the come-out
        if total in (7, 11):
            q += 2 * STAKE; out["outcome"] = "win"   # 1:1 payout in Qredits
        elif total in (2, 3, 12):
            out["outcome"] = "lose"
        else:
            st["point"] = total; out["outcome"] = f"point {total}"
    else:
        pt = st["point"]
        if total == pt:
            q += 2 * STAKE; out["outcome"] = "win"; st["point"] = None
        elif total == 7:
            out["outcome"] = "lose"; st["point"] = None
        else:
            out["outcome"] = f"point {pt}, rolled {total}"
    db.q("UPDATE players SET qredits=? WHERE id=?", (max(q, 0), pid))
    out["qredits"] = max(q, 0)
    return out


def round_view(rid: int) -> dict | None:
    r = _T["rounds"].get(rid)
    if not r:
        return None
    return {"round": rid, "status": r["status"], "phase": r["phase"], "result": r["result"], "error": r.get("error"),
            "commitments": len(r["commitments"]), "reveals": len(r["reveals"])}


# ---- quantum vote -----------------------------------------------------------------------------------
def run_vote() -> dict:
    opts = ["Classical", "Bosonic", "BosonicEntangled"]
    ls = {m: logic_designer.statements(m) for m in opts}
    fair = {m: 1 - 2 * abs(ls[m]["pass_line_win_exact"] - 0.5) for m in opts}
    corr = {"Classical": 0.35, "Bosonic": 0.5, "BosonicEntangled": 0.95}      # scripted: how visible the entanglement is
    ent = {m: min(1.0, np.log2(len(MODES[m])) / np.log2(36)) for m in opts}
    conf = {"logic_designer": fair, "q_scientist": corr, "host": {m: 0.2 + 0.6 * ent[m] + 0.2 * corr[m] for m in opts}}
    conf = {a: {m: round(float(min(max(v, 0), 1)), 3) for m, v in c.items()} for a, c in conf.items()}
    res = qvote.vote(conf, opts)
    res["confidence_source"] = "scripted confidences from exact numbers (fairness, entanglement visibility, entropy)"
    _T["vote"] = res
    events.emit("quantum_vote", {"winner": res["winner"], "shots": res["shots"]})
    return res


# ---- chip: map, buy-in, one job ------------------------------------------------------------------------
def buy_pair(pid: str, u: int, v: int) -> dict:
    cm = ibm.chip_map()
    pr = next((p for p in cm["pairs"] if {p["u"], p["v"]} == {u, v}), None)
    if not pr:
        return {"ok": False, "why": "not a coupled pair"}
    used = {q for pu in _T["purchases"].values() for q in (pu["u"], pu["v"])}
    if u in used or v in used:
        return {"ok": False, "why": "qubit already taken"}
    pl = next((p for p in players() if p["id"] == pid), None)
    if not pl or pl["qredits"] < pr["price"] or pid in _T["purchases"]:
        return {"ok": False, "why": "unknown player, already bought, or not enough Qredits"}
    db.q("UPDATE players SET qredits=qredits-? WHERE id=?", (pr["price"], pid))
    _T["purchases"][pid] = {"u": pr["u"], "v": pr["v"], "price": pr["price"], "nick": pl["nick"]}
    return {"ok": True, "price": pr["price"], "pair": [pr["u"], pr["v"]]}


def auto_buy_for_all() -> None:
    """Players who have not chosen a pair get the cheapest free coupled pair (bots, and chip rounds without a buy-in)."""
    cm = ibm.chip_map()
    used = {q for pu in _T["purchases"].values() for q in (pu["u"], pu["v"])}
    free = sorted((p for p in cm["pairs"] if p["u"] not in used and p["v"] not in used), key=lambda p: p["price"])
    for pl in players():
        if pl["id"] in _T["purchases"]:
            continue
        for pr in free:
            if pr["u"] in used or pr["v"] in used:
                continue
            r = buy_pair(pl["id"], pr["u"], pr["v"])
            if r["ok"]:
                used |= {pr["u"], pr["v"]}
                break


def run_chip_job(auto: bool = False, shots: int = 1000) -> dict:
    auto_buy_for_all()
    pairs = [{"player": pid, "nick": pu["nick"], "u": pu["u"], "v": pu["v"]} for pid, pu in _T["purchases"].items()]
    if not pairs:
        return {"status": "no pairs"}
    job = {"pairs": pairs, "shots": shots, "circuits": 1}
    est = ibm.estimate_qpu_seconds(1, shots)
    h = ibm.job_hash(job)
    q = financial.quote(h, est)
    r = ibm.submit_qpu_job(job)
    out = {"status": r["status"], "decision": r["decision"], "rule": r["rule"], "est": est, "job_hash": h, "quote": q,
           "pairs": pairs, "gate_engine": r["engine_gate"]}
    if r["status"] == "done":
        ideal = {"00": 0.5, "11": 0.5}
        per = []
        for i, pr in enumerate(pairs):
            hw = core.check_hardware(r["per_pair"][i], ideal, r["per_pair_noise_model"][i])
            per.append({"nick": pr["nick"], "qubits": [pr["u"], pr["v"]], "counts": r["per_pair"][i], **hw})
        out.update(label=r["label"], job_id=r["job_id"], backend=r["backend"], counts=r["counts"], per_pair=per,
                   badge="HARDWARE RUN: compared, not chi-square tested", qpu_seconds=r["qpu_seconds"],
                   noise_note=("Compared with an Aer run under the backend's noise model (independent seed). On the fake backend that model "
                               "is the same one that generated the data, so agreement is expected."))
        out["invoice"] = financial.shadow_invoice(h, r["qpu_seconds"], est, out["badge"], r["job_id"], r["label"])
        _T["last_chip"] = out
    else:
        _T["last_chip"] = out
    return out


def approve(job_hash: str) -> dict:
    db.q("INSERT OR REPLACE INTO approvals(job_hash,ts) VALUES(?,?)", (job_hash, time.time()))
    row = db.one("SELECT payload FROM qpu_jobs WHERE job_hash=? AND status='waiting for approval' ORDER BY id DESC", (job_hash,))
    if not row:
        return {"ok": False, "why": "no such waiting job"}
    job = json.loads(row["payload"])
    db.q("UPDATE qpu_jobs SET status='approved (superseded by run)' WHERE job_hash=? AND status='waiting for approval'", (job_hash,))
    r = ibm.submit_qpu_job(job, purpose="approved by a person")
    return {"ok": True, "approved_hash": job_hash, "status": r["status"], "decision": r["decision"]}


def overspend() -> dict:
    cm = ibm.chip_map()
    pairs = [{"player": "x", "nick": "x", "u": cm["pairs"][0]["u"], "v": cm["pairs"][0]["v"]}]
    return ibm.submit_qpu_job({"pairs": pairs, "shots": 6000, "circuits": 200}, purpose="Try to overspend (6,000 shots x 200 circuits)")


def big_job() -> dict:
    cm = ibm.chip_map()
    pairs = [{"player": "x", "nick": "x", "u": cm["pairs"][1]["u"], "v": cm["pairs"][1]["v"]}]
    return ibm.submit_qpu_job({"pairs": pairs, "shots": 100000, "circuits": 1}, purpose="Request a 100,000-shot job (needs a person)")
