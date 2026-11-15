"""Lab agent: chooses where a roll runs (emulator -> chip), asks the Quantum Time Gatekeeper, keeps the library of past runs.
No LLM. The only thing that may talk to IBM is engines.ibm.submit_qpu_job()."""
import json
import db
from engines import burndown, ibm
from gatekeeper import gate
from . import registry


def choose_engine(n_qubits: int) -> dict:
    lim = burndown.status()
    max_ok = lim["max_ok_n"] if lim["burned_down_at"] else burndown.analytic_limit_n()
    burned = lim["burned_down_at"] is not None and n_qubits >= lim["burned_down_at"]
    if n_qubits > burndown.analytic_limit_n():
        burned = True
    if burned:
        return {"engine": "chip", "label": ibm.FAKE_LABEL, "n": n_qubits, "reason": "statevector memory 16 bytes x 2^n exceeds the 80% line"}
    return {"engine": "emulator", "label": "Aer emulator", "n": n_qubits, "reason": "fits in memory"}


def gate_emulator(purpose: str = "roll on the emulator") -> dict:
    return gate.decide("agt_lab_agent", "run_emulator", {}, purpose=purpose)


def library() -> dict:
    jobs = db.rows("SELECT id,ts,job_hash,label,backend,job_id,est,actual,status FROM qpu_jobs ORDER BY id DESC LIMIT 30")
    log = db.rows("SELECT ts,agent,tool,purpose,est,action,rule,engine FROM gate_log WHERE tool != 'run_emulator' ORDER BY id DESC LIMIT 40")
    return {"jobs": jobs, "gate_log": log, "qpu_seconds_used": ibm.ledger_total(), "gate_credit": gate.credit_line()}
