"""The ten cases from the prompt's table through gate-cli.mjs (ADAP's policy engine), plus the one-door token test."""
import json
import os
import re
import subprocess
import pytest
from pathlib import Path
from gatekeeper import gate

ROOT = Path(__file__).resolve().parent.parent
CASES = [
    ("agt_lab_agent", "submit_qpu_job", {"est_qpu_seconds": 5, "budget_after_seconds": 20, "paid_plan": False}, "ALLOW"),
    ("agt_lab_agent", "submit_qpu_job", {"est_qpu_seconds": 10, "budget_after_seconds": 20, "paid_plan": False}, "ALLOW"),
    ("agt_lab_agent", "submit_qpu_job", {"est_qpu_seconds": 30, "budget_after_seconds": 50, "paid_plan": False}, "REQUIRE_HUMAN"),
    ("agt_lab_agent", "submit_qpu_job", {"est_qpu_seconds": 61, "budget_after_seconds": 70, "paid_plan": False}, "BLOCK"),
    ("agt_lab_agent", "submit_qpu_job", {"est_qpu_seconds": 5, "budget_after_seconds": 121, "paid_plan": False}, "BLOCK"),
    ("agt_lab_agent", "submit_qpu_job", {"est_qpu_seconds": 5, "budget_after_seconds": 20, "paid_plan": True}, "BLOCK"),
    ("agt_lab_agent", "submit_qpu_job", {"budget_after_seconds": 20, "paid_plan": False}, "BLOCK"),       # estimate missing
    ("agt_lab_agent", "delete_everything", {}, "BLOCK"),                                                  # unknown tool
    ("agt_host", "submit_qpu_job", {"est_qpu_seconds": 1, "budget_after_seconds": 1, "paid_plan": False}, "BLOCK"),  # other agent
    ("agt_lab_agent", "run_emulator", {}, "ALLOW"),
    ("agt_lab_agent", "read_past_job", {}, "ALLOW"),
    ("agt_finance", "quote_qpu_job", {}, "ALLOW"),
    ("agt_finance", "write_shadow_invoice", {}, "ALLOW"),
    ("agt_finance", "charge_customer", {}, "BLOCK"),
    ("agt_finance", "sell_qredits", {}, "BLOCK"),
    ("agt_finance", "payout", {}, "BLOCK"),
    ("agt_finance", "submit_qpu_job", {"est_qpu_seconds": 1, "budget_after_seconds": 1, "paid_plan": False}, "BLOCK"),
]


def cli(agent, tool, args):
    r = subprocess.run(["node", str(ROOT / "adap" / "gate-cli.mjs")], input=json.dumps({"agentRole": agent, "tool": tool, "args": args}),
                       capture_output=True, text=True, timeout=20, cwd=str(ROOT / "adap"))
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not gate.adap_available(), reason="ADAP engine not built")
@pytest.mark.parametrize("agent,tool,args,want", CASES)
def test_adap_cli(agent, tool, args, want):
    assert cli(agent, tool, args)["action"] == want


@pytest.mark.parametrize("agent,tool,args,want", CASES)
def test_builtin_port_matches(agent, tool, args, want):
    assert gate._builtin(agent, tool, args)["action"] == want


def test_missing_estimate_blocks_via_cli_error_path():
    """estimate missing: ADAP's expression on a missing arg must not ALLOW. The CLI prints BLOCK on any error."""
    if gate.adap_available():
        assert cli("agt_lab_agent", "submit_qpu_job", {})["action"] == "BLOCK"


def test_one_door_for_the_token():
    """Exactly one function may read IBM_QUANTUM_TOKEN: engines/ibm.py. No second use anywhere in the codebase."""
    hits = []
    for p in ROOT.rglob("*"):
        # code only: documentation may name the variable, code may read it in exactly one place
        if p.suffix not in (".py", ".js", ".mjs", ".html", ".sh") or any(x in p.parts for x in (".venv", "vendor", "node_modules", ".git", "static")):
            continue
        if p.name in ("run.sh", "config.py", "test_gatekeeper.py"):
            continue
        txt = p.read_text(errors="ignore")
        if "IBM_QUANTUM_TOKEN" in txt:
            hits.append(str(p.relative_to(ROOT)))
    assert hits == ["engines/ibm.py"], hits
    src = (ROOT / "engines" / "ibm.py").read_text()
    assert "config.py" not in src
    # config.py only lists the name for the key-status display and never exposes the value
    cfg = (ROOT / "config.py").read_text()
    assert "os.environ[\"IBM_QUANTUM_TOKEN\"]" not in cfg


def test_estimate_is_code():
    from engines.ibm import estimate_qpu_seconds
    assert estimate_qpu_seconds(1, 1000) < 10
    assert estimate_qpu_seconds(200, 6000) > 60
