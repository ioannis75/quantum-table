"""Burn-down: statevector memory = 16 bytes x 2^n. Real probes: run Aer on n qubits in a memory-capped subprocess
until the box refuses (never above 80% of RAM)."""
import json
import os
import subprocess
import sys
import time
import threading
import db

BYTES_PER_AMP = 16
_state = {"running": False, "current": None, "done": False}


def ram_total() -> int:
    for line in open("/proc/meminfo"):
        if line.startswith("MemTotal"):
            return int(line.split()[1]) * 1024
    return 0


def ram_limit() -> int:
    return int(0.8 * ram_total())


def need_bytes(n: int) -> int:
    return BYTES_PER_AMP * 2 ** n


def analytic_limit_n() -> int:
    n = 1
    while need_bytes(n + 1) <= ram_limit():
        n += 1
    return n


PROBE = r'''
import resource, sys, time, json
cap = int(sys.argv[2]); n = int(sys.argv[1])
resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
try:
    from qiskit import QuantumCircuit, transpile
    from qiskit_aer import AerSimulator
    qc = QuantumCircuit(n); qc.h(0)
    for i in range(1, n): qc.cx(0, i)
    qc.measure_all()
    sim = AerSimulator(method="statevector", max_parallel_threads=4)
    t0 = time.time()
    res = sim.run(transpile(qc, sim, optimization_level=0), shots=16, seed_simulator=1).result()
    ok = res.success
    counts = res.get_counts()
    ok = ok and set(counts) <= {"0"*n, "1"*n}
    print(json.dumps({"ok": bool(ok), "seconds": time.time()-t0, "rss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}))
except BaseException as e:
    print(json.dumps({"ok": False, "error": str(e)[:120]}))
'''


def probe_one(n: int) -> dict:
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, "-I", "-c", PROBE, str(n), str(ram_limit())], capture_output=True, text=True, timeout=300)
        out = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"ok": False, "error": "no output / killed"}
    except Exception as e:
        out = {"ok": False, "error": str(e)[:100]}
    out.setdefault("seconds", time.time() - t0)
    db.q("INSERT OR REPLACE INTO probe(n,bytes,seconds,rss,ok,engine) VALUES(?,?,?,?,?,?)",
         (n, need_bytes(n), out.get("seconds"), out.get("rss"), 1 if out["ok"] else 0, "Aer emulator"))
    return out


def probe_all(start: int = 6, stop_after_fail: bool = True) -> None:
    """Run n = start.. until the first refusal (or the 80% line plus one: the attempt past the line is the one that burns)."""
    if _state["running"]:
        return
    _state.update(running=True, done=False)
    try:
        n = start
        while True:
            _state["current"] = n
            r = probe_one(n)
            import events
            events.emit("probe", {"qubits": n, "ok": r["ok"]})
            if not r["ok"]:
                events.emit("burned_down", {"qubits": n, "bytes": need_bytes(n)})
                break
            n += 1
            if need_bytes(n) > ram_limit() * 1.0 and n > analytic_limit_n() + 1:
                break
    finally:
        _state.update(running=False, done=True, current=None)


def start_background(start: int = 6):
    if _state["running"]:
        return False
    threading.Thread(target=probe_all, args=(start,), daemon=True).start()
    return True


def status() -> dict:
    rows = db.rows("SELECT * FROM probe ORDER BY n")
    ok = [r["n"] for r in rows if r["ok"]]
    bad = [r["n"] for r in rows if not r["ok"]]
    return {"ram_total": ram_total(), "ram_limit_80": ram_limit(), "analytic_limit_n": analytic_limit_n(),
            "probes": rows, "max_ok_n": max(ok) if ok else None, "burned_down_at": min(bad) if bad else None,
            "running": _state["running"], "current": _state["current"], "bytes_per_amplitude": BYTES_PER_AMP}
