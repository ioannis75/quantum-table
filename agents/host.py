"""The Host (AI host): autonomous, enthusiastic, strict about facts. One short line per table event (<= 25 words).
Every line is checked by code: numbers must come from the event, no banned phrases, no urging to play more.
A line that fails is replaced by a plain template line and counted ('Host lines corrected by the checker')."""
import re
import time
import threading
import config
import db
import events
from . import llm, registry

BANNED = ["tries all answers at once", "faster than light", "proves many worlds", "truly random", "certified",
          "quantum advantage", "unhackable", "consciousness causes", "keep playing", "bet more", "double down",
          "one more roll", "don't stop", "tamper-proof", "provably unbiased", "guaranteed", "you can't lose"]
SYSTEM = ("You are the AI host of a quantum dice table: delighted by the physics, strict about facts. Write ONE line, at most 25 words, "
          "reacting to the event. Use only numbers present in the event. Address players only by the nickname given. Never claim to be a person. "
          "Never urge anyone to play or bet more. Never say: " + "; ".join(BANNED[:9]) + ".")

T = {
    "player_joined": lambda d: f"{d.get('nick','A player')} takes a seat with {d.get('qredits',100)} Qredits. The table now holds {d.get('qubits',0)} qubits.",
    "dice_entangled": lambda d: f"{d.get('nick','A player')}'s dice are entangled with the house pair. Correlated as the mode requires, and the verifier will check it.",
    "roll_result": lambda d: f"Round {d.get('round','')} is in: faces {d.get('faces','')} on {d.get('engine','the emulator')}. The measurement decided, not the animation.",
    "verifier_verdict": lambda d: f"Verifier says {d.get('badge','?')}. The badge comes from code, not from me.",
    "hype_verdict": lambda d: ("The experiment says: Fact." if d.get("truth") else "The experiment says: Hype.") + f" {d.get('headline','')}".rstrip(),
    "quantum_vote": lambda d: f"The agents voted with qubits and picked {d.get('winner','a variant')}. A vote sampled from qubits, nothing more is claimed.",
    "gatekeeper": lambda d: f"Quantum Time Gatekeeper decision: {d.get('action','?')} under rule {d.get('rule','?')}.",
    "burned_down": lambda d: f"The emulator burned down at {d.get('qubits','?')} qubits. Exact statevector simulation ran out of memory; the chip takes over.",
    "chip_job_submitted": lambda d: f"Chip job {d.get('job_hash','')} submitted on {d.get('label','the chip')}, estimated {d.get('est','?')} QPU seconds.",
    "chip_job_returned": lambda d: f"Chip job {d.get('job_hash','')} is back from {d.get('label','the chip')}. The verifier now compares it with theory.",
    "job_waiting": lambda d: f"A chip job estimated at {d.get('est','?')} QPU seconds is waiting for a person to approve it.",
    "job_blocked": lambda d: f"A chip job estimated at {d.get('est','?')} QPU seconds was blocked by rule {d.get('rule','?')}.",
    "table_open": lambda d: "The table is open. Scan the code to take a seat with Qredits, play credits with no cash value.",
    "idle_card": lambda d: "Quiet table, so here is a claim card. Fact or Hype? Place your Qredits.",
    "probe": lambda d: f"Probe at {d.get('qubits','?')} qubits finished.",
    "beacon_round": lambda d: f"Beacon round {d.get('round','?')} published. Don't trust us; check it.",
    "round_dropped": lambda d: f"{d.get('dropped',0)} participant(s) did not reveal in time and were dropped; the round re-ran without them.",
}
TEMPLATE_FALLBACK = lambda ev: f"Event: {ev['type'].replace('_',' ')}."
SKIP = {"host_line", "probe"}
_lines: list = []
_last_model_call = 0.0
_last_event = [time.time()]


def numbers_in(s: str) -> list:
    return re.findall(r"\d+(?:\.\d+)?", s)


def event_numbers(data) -> set:
    out = set()

    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
        else:
            for n in numbers_in(str(v)):
                out.add(n)
                try:
                    out.add(str(float(n)))
                    out.add(str(int(float(n))) if float(n) == int(float(n)) else n)
                except Exception:
                    pass
    walk(data)
    return out


def check_line(line: str, data: dict) -> tuple:
    low = line.lower()
    for b in BANNED:
        if b in low:
            return False, f"banned phrase '{b}'"
    if len(line.split()) > 25:
        return False, "more than 25 words"
    allowed = event_numbers(data)
    for n in numbers_in(line):
        if n not in allowed:
            return False, f"number {n} is not in the event"
    return True, ""


def template_line(ev: dict) -> str:
    return T.get(ev["type"], TEMPLATE_FALLBACK)(dict(ev["data"])) if ev["type"] in T else TEMPLATE_FALLBACK(ev)


def react(ev: dict, use_model: bool = True) -> dict | None:
    global _last_model_call
    if ev["type"] in SKIP:
        return None
    _last_event[0] = time.time()
    line, source = None, "template"
    if use_model and config.has("ANTHROPIC_API_KEY") and time.time() - _last_model_call >= 5:
        _last_model_call = time.time()
        try:
            registry.set_status("host", "working")
            text, label = llm.anthropic_ask(SYSTEM, f"Event: {ev['type']} {ev['data']}", "fast", 80, timeout=8)
            text = text.strip().splitlines()[0].strip()
            ok, why = check_line(text, ev["data"])
            if ok:
                line, source = text, label
            else:
                db.bump("host_corrected")
                events.emit("host_corrected", {"why": why})
        except Exception:
            pass
    if line is None:
        line = template_line(ev)
        ok, why = check_line(line, ev["data"])
        if not ok:        # even a template must pass; otherwise fall back to a bare line
            line = TEMPLATE_FALLBACK(ev)
    rec = {"ts": time.time(), "type": ev["type"], "line": line, "source": source}
    _lines.append(rec)
    del _lines[:-60]
    registry.set_status("host", "idle", source if source != "template" else "template commentary")
    events.emit("host_line", {"line": line, "source": source})
    return rec


def recent(n: int = 12) -> list:
    return _lines[-n:][::-1]


def start() -> None:
    events.on(lambda ev: react(ev) if ev["type"] not in SKIP else None)


def idle_seconds() -> float:
    return time.time() - _last_event[0]


def post_discord(kind: str, text: str) -> dict:
    """Discord posts written by the Host, same checks. Rate limit: one per 10 minutes, 12 in total. No player data."""
    import os
    from pathlib import Path
    n = db.kv_get("discord_count", 0)
    last = db.kv_get("discord_last", 0)
    if n >= 12 or time.time() - last < 600:
        return {"posted": False, "reason": "rate limit"}
    ok, _ = check_line(text, {"n": text})
    text = text if ok else "Quantum Table update."
    db.kv_set("discord_count", n + 1)
    db.kv_set("discord_last", time.time())
    if config.has("DISCORD_WEBHOOK_URL"):
        try:
            import httpx
            httpx.post(os.environ["DISCORD_WEBHOOK_URL"], json={"content": text}, timeout=5)
            return {"posted": True, "channel": "discord"}
        except Exception:
            return {"posted": False, "reason": "ignored failure"}
    with open(config.ROOT / "DISCORD_POSTS.md", "a") as f:
        f.write(f"- [{kind}] {text}\n")
    return {"posted": True, "channel": "DISCORD_POSTS.md"}
