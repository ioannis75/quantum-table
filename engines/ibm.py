"""IBM chip engine. The ONE DOOR: submit_qpu_job() is the only function that reads IBM_QUANTUM_TOKEN and talks to IBM.
It calls the Quantum Time Gatekeeper first and proceeds only on ALLOW (or on a recorded human approval of the exact job hash).
Without a token every result is labelled "Simulated chip (fake backend)"."""
import hashlib
import json
import math
import os
import time

import db
import events
from gatekeeper import gate

FAKE_LABEL = "Simulated chip (fake backend)"
REP_DELAY_S = 250e-6        # default repetition delay used in the estimate
PER_SHOT_EXEC_S = 20e-6     # gate + measurement time per shot (rough, stated in the UI)
OVERHEAD_S = 2.0            # fixed per-job overhead
_cache: dict = {}


def fake_backend():
    if "fb" not in _cache:
        from qiskit_ibm_runtime.fake_provider import FakeBrisbane
        _cache["fb"] = FakeBrisbane()
    return _cache["fb"]


def _positions() -> dict:
    rows = [(0, 13, 0), (18, 32, 0), (37, 51, 0), (56, 70, 0), (75, 89, 0), (94, 108, 0), (113, 126, 1)]
    pos = {}
    for r, (a, z, x0) in enumerate(rows):
        for i, q in enumerate(range(a, z + 1)):
            pos[q] = (i + x0, 2 * r)
    for r, (a, z) in enumerate([(14, 17), (33, 36), (52, 55), (71, 74), (90, 93), (109, 112)]):
        xs = [0, 4, 8, 12] if r % 2 == 0 else [2, 6, 10, 14]
        for q, x in zip(range(a, z + 1), xs):
            pos[q] = (x, 2 * r + 1)
    return pos


PRICE_FORMULA = "price = 5 + round(15 * (1 - (e - e_min) / (e_max - e_min))) Qredits, where e = 2-qubit error + both readout errors"


def chip_map() -> dict:
    """Backend qubit map with live calibration (fake backend: stored snapshot) and a Qredits price per coupled pair."""
    if "map" in _cache:
        return _cache["map"]
    b = fake_backend()
    t = b.target
    pos = _positions()
    ro = {q: float(t["measure"][(q,)].error or 0.0) for q in range(b.num_qubits)}
    edges = {}
    for k, v in t["ecr"].items():
        u, w = sorted(k)
        e = float(v.error or 0.0)
        if (u, w) not in edges or e < edges[(u, w)]:
            edges[(u, w)] = e
    raw = {k: e + ro[k[0]] + ro[k[1]] for k, e in edges.items()}
    lo, hi = min(raw.values()), max(raw.values())
    pairs = []
    for (u, w), e in sorted(edges.items()):
        r = raw[(u, w)]
        price = 5 + round(15 * (1 - (r - lo) / (hi - lo)))
        pairs.append({"u": u, "v": w, "err2q": e, "ro_u": ro[u], "ro_v": ro[w], "price": price})
    m = {"backend": b.name, "label": FAKE_LABEL, "n": b.num_qubits,
         "pos": {q: p for q, p in pos.items()}, "pairs": pairs, "formula": PRICE_FORMULA,
         "calibration": "snapshot stored in qiskit_ibm_runtime.fake_provider (not live)"}
    _cache["map"] = m
    return m


def pair_circuit(pairs: list, ghz_pairs=None):
    """One circuit holding a Bell pair per player on distinct physical pairs (logical qubits 2i, 2i+1)."""
    from qiskit import QuantumCircuit
    k = len(pairs)
    qc = QuantumCircuit(2 * k, 2 * k)
    for i in range(k):
        qc.h(2 * i)
        qc.cx(2 * i, 2 * i + 1)
    qc.measure(range(2 * k), range(2 * k))
    return qc


def job_hash(job: dict) -> str:
    keep = {"pairs": [[p["u"], p["v"]] for p in job.get("pairs", [])], "shots": job.get("shots"),
            "circuits": job.get("circuits", 1), "backend": job.get("backend", fake_backend().name)}
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:16]


def estimate_qpu_seconds(circuits: int, shots: int) -> float:
    """Computed by code, never by a model: circuits x shots x repetition time, plus overhead."""
    return round(circuits * shots * (REP_DELAY_S + PER_SHOT_EXEC_S) + OVERHEAD_S, 3)


def ledger_total() -> float:
    r = db.one("SELECT COALESCE(SUM(seconds),0) AS s FROM qpu_ledger WHERE source='ibm'")
    return float(r["s"])


# ---- the only code that touches the token -----------------------------------------------------
def _ibm_service():
    from qiskit_ibm_runtime import QiskitRuntimeService
    return QiskitRuntimeService(channel="ibm_quantum_platform", token=os.environ["IBM_QUANTUM_TOKEN"])


def _paid_plan(service=None) -> bool:
    """True if the account is on a paid plan. If it cannot be determined, answer True (fails closed)."""
    if not os.environ.get("IBM_QUANTUM_TOKEN", "").strip():
        return False  # no token: nothing real can run; fake backend only
    try:
        info = (service or _ibm_service()).active_account() or {}
        plan = str(info.get("plan_name") or info.get("instance_plan") or "").lower()
        if plan in ("open", "free"):
            return False
    except Exception:
        pass
    return True


def submit_qpu_job(job: dict, agent: str = "agt_lab_agent", purpose: str = "chip buy-in") -> dict:
    """THE ONE DOOR. job = {pairs:[{player,nick,u,v}], shots, circuits(=1)}. Returns a stored job record."""
    shots = int(job.get("shots", 1000))
    ncirc = int(job.get("circuits", 1))
    est = estimate_qpu_seconds(ncirc, shots)
    h = job_hash(job)
    used = ledger_total()
    real = bool(os.environ.get("IBM_QUANTUM_TOKEN", "").strip())
    paid = _paid_plan() if real else False
    decision = gate.decide(agent, "submit_qpu_job",
                           {"est_qpu_seconds": est, "budget_after_seconds": used + est, "paid_plan": paid},
                           purpose=purpose)
    rec = {"job_hash": h, "est": est, "decision": decision["action"], "rule": decision["rule"], "shots": shots,
           "circuits": ncirc, "engine_gate": decision["engine"]}
    approved = db.one("SELECT 1 AS x FROM approvals WHERE job_hash=?", (h,))
    if decision["action"] == "REQUIRE_HUMAN" and approved:
        decision = dict(decision, action="ALLOW", rule=decision["rule"] + "+human_approved")
        rec["decision"], rec["rule"] = "ALLOW", decision["rule"]
    if decision["action"] == "REQUIRE_HUMAN":
        db.q("INSERT INTO qpu_jobs(ts,job_hash,label,backend,job_id,qubits,est,actual,status,counts,payload) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
             (time.time(), h, "waiting for approval", fake_backend().name, None, json.dumps(job.get("pairs", [])), est, None,
              "waiting for approval", None, json.dumps(job)))
        events.emit("job_waiting", {"job_hash": h, "est": est})
        return dict(rec, status="waiting for approval")
    if decision["action"] != "ALLOW":
        events.emit("job_blocked", {"job_hash": h, "est": est, "rule": decision["rule"]})
        return dict(rec, status="blocked")
    # ALLOW from here
    events.emit("chip_job_submitted", {"job_hash": h, "est": est, "label": "IBM backend" if real else FAKE_LABEL})
    if real:
        out = _run_ibm(job, h)
    else:
        out = _run_fake(job, h)
    db.q("INSERT INTO qpu_jobs(ts,job_hash,label,backend,job_id,qubits,est,actual,status,counts,payload) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         (time.time(), h, out["label"], out["backend"], out["job_id"], json.dumps(job.get("pairs", [])), est,
          out["qpu_seconds"], "done", json.dumps(out["counts"]), json.dumps(job)))
    if real and out["qpu_seconds"]:
        db.q("INSERT INTO qpu_ledger(ts,job_hash,seconds,source) VALUES(?,?,?,?)", (time.time(), h, out["qpu_seconds"], "ibm"))
    events.emit("chip_job_returned", {"job_hash": h, "label": out["label"], "job_id": out["job_id"]})
    return dict(rec, status="done", **out)


def _split_counts(counts: dict, k: int) -> list:
    """Per-pair 2-bit marginals from the joint counts (Qiskit order: pair i = bits 2i, 2i+1 from the right)."""
    out = [dict() for _ in range(k)]
    for bs, c in counts.items():
        bs = bs.replace(" ", "")
        for i in range(k):
            key = bs[len(bs) - 2 * i - 2: len(bs) - 2 * i]
            out[i][key] = out[i].get(key, 0) + c
    return out


def _run_fake(job: dict, h: str) -> dict:
    from qiskit import transpile
    from qiskit_aer import AerSimulator
    b = fake_backend()
    pairs = job["pairs"]
    layout = [q for p in pairs for q in (p["u"], p["v"])]
    qc = pair_circuit(pairs)
    sim = AerSimulator.from_backend(b)
    tqc = transpile(qc, sim, initial_layout=layout, optimization_level=1, seed_transpiler=1)
    shots = int(job.get("shots", 1000))
    counts = sim.run(tqc, shots=shots, seed_simulator=2026).result().get_counts()
    noisy = sim.run(tqc, shots=shots, seed_simulator=777).result().get_counts()   # independent noise-model run
    return {"label": FAKE_LABEL, "backend": b.name, "job_id": "fake-" + h, "qpu_seconds": 0.0,
            "counts": counts, "noise_model_counts": noisy, "per_pair": _split_counts(counts, len(pairs)),
            "per_pair_noise_model": _split_counts(noisy, len(pairs)), "shots": shots}


def _run_ibm(job: dict, h: str) -> dict:
    """Real submission via qiskit-ibm-runtime SamplerV2. UNTESTED in this build (no token, IBM docs host unreachable)."""
    from qiskit import transpile
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import SamplerV2
    from qiskit_aer import AerSimulator
    service = _ibm_service()
    backend = service.least_busy(operational=True, simulator=False, min_num_qubits=job["pairs"][0]["v"] + 1)
    pairs = job["pairs"]
    layout = [q for p in pairs for q in (p["u"], p["v"])]
    qc = pair_circuit(pairs)
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1, initial_layout=layout)
    isa = pm.run(qc)
    shots = int(job.get("shots", 1000))
    sampler = SamplerV2(mode=backend)
    j = sampler.run([isa], shots=shots)
    res = j.result()
    counts = res[0].data.c.get_counts()
    usage = 0.0
    try:
        usage = float(j.usage())
    except Exception:
        try:
            usage = float(j.metrics()["usage"]["seconds"])
        except Exception:
            usage = estimate_qpu_seconds(1, shots)
    noisy = AerSimulator.from_backend(backend).run(transpile(qc, AerSimulator.from_backend(backend), initial_layout=layout), shots=shots).result().get_counts()
    return {"label": f"IBM {backend.name}", "backend": backend.name, "job_id": j.job_id(), "qpu_seconds": usage,
            "counts": counts, "noise_model_counts": noisy, "per_pair": _split_counts(counts, len(pairs)),
            "per_pair_noise_model": _split_counts(noisy, len(pairs)), "shots": shots}
