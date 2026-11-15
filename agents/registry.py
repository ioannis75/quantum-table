"""Agent team registry: who exists, what they run on, what they are doing (the team strip on the page)."""
import time

ROLES = {
    "q_scientist": {"name": "Q-Scientist", "job": "writes the circuits and states the exact expected distribution", "wants": "Claude API", "fallback": "scripted circuits"},
    "logic_designer": {"name": "Logic designer", "job": "rules, payouts, exact odds, quantum-logic statements", "wants": "Oumi", "fallback": "Claude API, then scripted statements"},
    "art_director": {"name": "Art director", "job": "table, dice and chip-map graphics", "wants": "fal.ai", "fallback": "built-in SVG art"},
    "lab_agent": {"name": "Lab agent", "job": "chooses where a roll runs; asks the Gatekeeper before any chip job", "wants": "code + IBM runtime", "fallback": "fake backend"},
    "financial_agent": {"name": "Financial agent", "job": "quotes and shadow invoices; never charges anyone", "wants": "code + Claude API summary", "fallback": "template summary"},
    "table_builder": {"name": "Table builder", "job": "3D table and dice; animates verified outcomes", "wants": "code (Three.js)", "fallback": "2D table"},
    "host": {"name": "Host (AI host)", "job": "live commentary, claim cards, Discord posts", "wants": "Claude API", "fallback": "template commentary"},
    "verifier": {"name": "Verifier", "job": "exact and statistical checks; its badge is final", "wants": "code (not an LLM)", "fallback": "-"},
}
_status = {k: {"state": "idle", "model": "-", "last": None, "note": ""} for k in ROLES}


def set_status(role: str, state: str, model: str | None = None, note: str = "") -> None:
    s = _status[role]
    s["state"] = state
    if model:
        s["model"] = model
    s["note"] = note
    s["last"] = time.time()


def snapshot() -> list:
    return [dict(id=k, **ROLES[k], **_status[k]) for k in ROLES]
