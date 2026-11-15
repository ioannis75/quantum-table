"""Quantum Time Gatekeeper, powered by ADAP's policy engine (in-process policy check, not a sandbox).
Runs adap/gate-cli.mjs (ADAP's evaluateToolCall). If Node or the ADAP build is unavailable, falls back to a
built-in port of the same rules and says so ("built-in rules (ADAP-style)")."""
import json
import subprocess
import time
from config import ROOT
import db

GATE_CLI = ROOT / "adap" / "gate-cli.mjs"
ADAP_DIST = ROOT / "vendor" / "agent-delegated-authority" / "packages" / "policy-engine" / "dist" / "index.js"
CREDIT_ADAP = "Quantum Time Gatekeeper, powered by ADAP's policy engine"
CREDIT_BUILTIN = "Quantum Time Gatekeeper, built-in rules (ADAP-style)"


def adap_available() -> bool:
    return ADAP_DIST.exists() and GATE_CLI.exists()


def credit_line() -> str:
    return CREDIT_ADAP if adap_available() else CREDIT_BUILTIN


def _builtin(agent: str, tool: str, args: dict) -> dict:
    def d(action, rule, sev="LOW"):
        return {"matched": True, "action": action, "ruleId": rule, "reason": "built-in rule " + rule, "alertSeverity": sev}
    blocked = {"matched": False, "action": "BLOCK", "ruleId": "default_block", "reason": "default BLOCK", "alertSeverity": "LOW"}
    if agent == "agt_lab_agent":
        est, bud, paid = args.get("est_qpu_seconds"), args.get("budget_after_seconds"), args.get("paid_plan")
        if tool == "submit_qpu_job":
            if isinstance(est, (int, float)) and est > 60:
                return d("BLOCK", "qpu_block_over_job_cap", "CRITICAL")
            if isinstance(bud, (int, float)) and bud > 120:
                return d("BLOCK", "qpu_block_over_budget", "CRITICAL")
            if paid is True:
                return d("BLOCK", "qpu_block_paid_plan", "CRITICAL")
            if isinstance(est, (int, float)) and est > 10:
                return d("REQUIRE_HUMAN", "qpu_medium_needs_human", "MEDIUM")
            return d("ALLOW", "qpu_small_allow")
        if tool == "run_emulator":
            return d("ALLOW", "emulator_allow")
        if tool == "read_past_job":
            return d("ALLOW", "read_results_allow")
    if agent == "agt_finance":
        rules = {"charge_customer": "BLOCK", "sell_qredits": "BLOCK", "payout": "BLOCK",
                 "quote_qpu_job": "ALLOW", "write_shadow_invoice": "ALLOW"}
        if tool in rules:
            return d(rules[tool], tool + ("_allow" if rules[tool] == "ALLOW" else "_blocked"), "CRITICAL" if rules[tool] == "BLOCK" else "LOW")
    return blocked


def decide(agent: str, tool: str, args: dict | None = None, purpose: str = "", log: bool = True) -> dict:
    args = args or {}
    engine = "ADAP policy engine" if adap_available() else "built-in rules (ADAP-style)"
    out = None
    if adap_available():
        try:
            r = subprocess.run(["node", str(GATE_CLI)], input=json.dumps({"agentRole": agent, "tool": tool, "args": args}),
                               capture_output=True, text=True, timeout=15, cwd=str(GATE_CLI.parent))
            out = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            out = None
    if out is None:
        engine = "built-in rules (ADAP-style)"
        out = _builtin(agent, tool, args)
    res = {"agent": agent, "tool": tool, "action": out["action"], "rule": out.get("ruleId"), "engine": engine,
           "reason": out.get("reason", ""), "est": args.get("est_qpu_seconds"), "purpose": purpose, "credit": credit_line()}
    if log:
        db.q("INSERT INTO gate_log(ts,agent,tool,purpose,est,action,rule,engine,args) VALUES(?,?,?,?,?,?,?,?,?)",
             (time.time(), agent, tool, purpose, res["est"], res["action"], res["rule"], engine, json.dumps(args)))
        import events
        events.emit("gatekeeper", {k: res[k] for k in ("agent", "tool", "action", "rule", "est", "purpose", "engine")})
    return res
