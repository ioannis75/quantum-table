"""Quantum Table: one FastAPI service (SQLite + server-sent events). `./run.sh` starts it."""
import asyncio
import io
import json
import os
import socket
import threading
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

import config
import db
import events
import orchestrator as orch
from agents import art, financial, host, lab, logic_designer, q_scientist, registry
from beacon import beacon
from engines import burndown, ibm
from gatekeeper import gate
from games import hype
from games import chipgame
from games.qraps import modes
from games.qraps.modes import MODES, CROSS_RULE, RULE_TEXT

ROOT = config.ROOT
app = FastAPI(title="Quantum Table")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")
app.mount("/docs-img", StaticFiles(directory=ROOT / "docs"), name="docs-img")
_hype = {"card": None, "bets": {}, "deck_i": 0, "last": None, "busy": False}
DAIDALOS = json.loads((ROOT / "data" / "daidalos.json").read_text()) if (ROOT / "data" / "daidalos.json").exists() else \
    {"label": "Daidalos (Greek EuroHPC system)", "bytes": None, "source": None}


def lan_url() -> str:
    """Join URL shown on the page and in the QR. PUBLIC_URL (e.g. a tunnel or the venue address) wins when set."""
    pub = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    if pub:
        return pub
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "localhost"
    return f"http://{ip}:{os.environ.get('PORT', '8080')}"


@app.on_event("startup")
def startup():
    db.conn()
    art.ensure_assets()
    host.start()
    if not db.rows("SELECT 1 FROM probe LIMIT 1"):
        burndown.start_background(6)
    threading.Thread(target=_idle_loop, daemon=True).start()
    events.emit("table_open", {"url": lan_url() + "/join"})
    host.post_discord("table_open", f"Table open. Join: {lan_url()}/join")


def _idle_loop():
    while True:
        time.sleep(5)
        try:
            if host.idle_seconds() > 30 and not _hype["card"]:
                events.emit("idle_card", {})
                _deal()
        except Exception:
            pass


# ---- state ------------------------------------------------------------------------------------------
@app.get("/api/state")
def state():
    bs = burndown.status()
    n = orch.qubits()
    binfo = orch._burn_info()
    return {
        "time_athens": config.athens_now().strftime("%H:%M"), "mode": orch._T["mode"], "rule": CROSS_RULE[orch._T["mode"]],
        "rule_text": RULE_TEXT[CROSS_RULE[orch._T["mode"]]], "players": orch.players(), "qubits": n,
        "bytes_needed": burndown.need_bytes(n), "phase": orch.phase(), "burn": binfo,
        "burndown": {"ram_total": bs["ram_total"], "ram_limit_80": bs["ram_limit_80"], "daidalos": DAIDALOS,
                     "classical_wall_qubits": 50, "probes": [{"n": p["n"], "ok": p["ok"], "seconds": p["seconds"], "rss": p["rss"]} for p in bs["probes"]],
                     "burned_down_at": bs["burned_down_at"], "running": bs["running"], "analytic_limit_n": bs["analytic_limit_n"],
                     "note": "This is the cost of exact statevector simulation (16 bytes x 2^n), not of every classical method."},
        "team": registry.snapshot(), "keys": config.key_status(), "versions": config.versions(),
        "host_lines": host.recent(8), "host_corrected": db.counter("host_corrected"), "logic_corrected": db.counter("logic_corrected"),
        "gate_credit": gate.credit_line(), "gate_blocks": db.one("SELECT COUNT(*) c FROM gate_log WHERE action='BLOCK'")["c"],
        "art": art.source(), "purchases": orch._T["purchases"], "last_result": orch._T["last_result"], "vote": orch._T["vote"],
        "hype": _hype_view(), "versions_note": "Aer emulator", "join_url": lan_url() + "/join",
        "qpu_seconds_used": ibm.ledger_total(), "stake": orch.STAKE,
    }


@app.get("/api/design/{mode}")
def design(mode: str):
    if mode not in MODES:
        raise HTTPException(404)
    return orch.design_info(mode)


@app.get("/api/odds")
def odds():
    return modes.odds_table()


@app.get("/api/bloch/{mode}")
def bloch(mode: str):
    if mode not in MODES:
        raise HTTPException(404)
    return orch.bloch(mode)


@app.post("/api/mode/{mode}")
def set_mode(mode: str):
    try:
        return orch.set_mode(mode)
    except ValueError:
        raise HTTPException(404)


@app.post("/api/join")
async def join(req: Request):
    b = await req.json()
    return orch.join(b.get("nick", "Player"))


@app.post("/api/skip_ahead")
def skip():
    return orch.skip_ahead()


@app.post("/api/reset")
def reset():
    orch.reset_table()
    return {"ok": True}


@app.post("/api/burndown/probe")
def probe():
    return {"started": burndown.start_background(6)}


# ---- rounds -----------------------------------------------------------------------------------------
@app.post("/api/round/open")
async def round_open(req: Request):
    b = await req.json() if (await req.body()) else {}
    opts = b.get("options")
    if opts is not None:
        opts = [str(o)[:40] for o in opts][:6]
        if not 2 <= len(opts) <= 6:
            raise HTTPException(400, "2 to 6 options")
    return orch.open_round(b.get("player"), opts)


@app.post("/api/round/{rid}/commit")
async def round_commit(rid: int, req: Request):
    b = await req.json()
    return orch.commit(rid, b.get("player"), b.get("hash"))


@app.post("/api/round/{rid}/reveal")
async def round_reveal(rid: int, req: Request):
    b = await req.json()
    return orch.reveal(rid, b.get("player"), b.get("secret"))


@app.get("/api/round/{rid}")
def round_get(rid: int):
    v = orch.round_view(rid)
    if not v:
        raise HTTPException(404)
    return v


@app.post("/api/vote")
def vote():
    return orch.run_vote()


# ---- beacon -----------------------------------------------------------------------------------------
@app.get("/beacon/latest")
def beacon_latest():
    r = beacon.latest()
    if not r:
        raise HTTPException(404, "no rounds yet")
    return r


@app.get("/beacon/{rid}")
def beacon_get(rid: int):
    r = beacon.get(rid)
    if not r:
        raise HTTPException(404)
    return r


@app.get("/verify_beacon.py")
def verify_file():
    return FileResponse(ROOT / "verify_beacon.py", media_type="text/plain")


# ---- chip, gatekeeper, finance ------------------------------------------------------------------------
@app.get("/api/chipmap")
def chipmap():
    return ibm.chip_map()


@app.post("/api/chip/buy")
async def chip_buy(req: Request):
    b = await req.json()
    return orch.buy_pair(b["player"], int(b["u"]), int(b["v"]))


@app.post("/api/chip/run")
def chip_run():
    return orch.run_chip_job()


@app.post("/api/chip/overspend")
def chip_overspend():
    return orch.overspend()


@app.post("/api/chip/big")
def chip_big():
    return orch.big_job()


@app.post("/api/chip/approve")
async def chip_approve(req: Request):
    b = await req.json()
    return orch.approve(str(b["job_hash"]))


@app.post("/api/finance/charge")
def finance_charge():
    return financial.try_charge_player()


@app.get("/api/library")
def library():
    return {**lab.library(), "finance": financial.ledger_summary(), "price": financial.fetch_price(),
            "chip": orch._T["last_chip"], "invoices": [json.loads(r["data"]) for r in db.rows("SELECT data FROM quotes WHERE kind='shadow_invoice' ORDER BY id DESC LIMIT 5")]}


@app.get("/api/finance/summary")
def finance_summary():
    return financial.summary_text()


@app.get("/api/logic/sidebet")
def side_bet(mode: str = "Classical"):
    a = {"atom": "face", "die": 0, "k": 3}
    return {"incompatible": logic_designer.side_bet(mode, a, {"atom": "qubit", "i": 0, "axis": "X", "sign": 1}),
            "compatible": logic_designer.side_bet(mode, a, {"atom": "sum", "n": 7})}


# ---- hype or fact ------------------------------------------------------------------------------------
def _deal():
    if _hype["card"]:
        return _hype["card"]
    card = None
    if db.counter("hype_dealt") % 3 == 2:
        card = hype.model_card()
    if not card:
        deck = hype.SEED_DECK + hype.STAND_IN
        for _ in range(len(deck)):
            c = deck[_hype["deck_i"] % len(deck)]
            _hype["deck_i"] += 1
            if hype.validate(c):
                card = c
                break
            db.bump("hype_discarded")
    if card:
        db.bump("hype_dealt")
        _hype["card"], _hype["bets"], _hype["last"] = card, {}, None
        registry.set_status("host", "idle", None, "dealt a card")
    return card


def _hype_view():
    c = _hype["card"]
    return {"card": {"id": c["id"], "sentence": c["sentence"], "origin": c["origin"]} if c else None,
            "bets": {k: v for k, v in _hype["bets"].items()}, "last": _hype["last"],
            "experiments": db.counter("hype_resolved"), "ai_claims_survived": db.counter("hype_ai_survived"),
            "ai_claims_total": db.counter("hype_ai_total"), "discarded": db.counter("hype_discarded")}


@app.post("/api/hype/deal")
def hype_deal():
    _deal()
    return _hype_view()


@app.post("/api/hype/bet")
async def hype_bet(req: Request):
    b = await req.json()
    if not _hype["card"] or b.get("side") not in ("fact", "hype"):
        raise HTTPException(400)
    amt = max(1, min(int(b.get("amount", 5)), 50))
    pl = next((p for p in orch.players() if p["id"] == b.get("player")), None)
    if not pl or pl["qredits"] < amt or b["player"] in _hype["bets"]:
        raise HTTPException(400, "cannot bet")
    db.q("UPDATE players SET qredits=qredits-? WHERE id=?", (amt, pl["id"]))
    _hype["bets"][pl["id"]] = {"side": b["side"], "amount": amt, "nick": pl["nick"]}
    return _hype_view()


@app.post("/api/hype/resolve")
def hype_resolve():
    card = _hype["card"]
    if not card:
        card = _deal()
    res = hype.run_card(card)
    truth = res["truth"]
    for pid, bet in _hype["bets"].items():
        if (bet["side"] == "fact") == truth:
            db.q("UPDATE players SET qredits=qredits+? WHERE id=?", (2 * bet["amount"], pid))    # 1:1
    ai = card["origin"].startswith("AI-written")
    db.bump("hype_resolved")
    if ai:
        db.bump("hype_ai_total")
        if truth:
            db.bump("hype_ai_survived")
    line = "The AI said this. The experiment says no." if (ai and not truth) else None
    db.q("INSERT INTO hype(ts,card,origin,truth,data) VALUES(?,?,?,?,?)", (time.time(), card["id"], card["origin"], int(truth), json.dumps(res)))
    _hype["last"] = {"sentence": card["sentence"], "origin": card["origin"], "truth": truth, "verdict": "FACT" if truth else "HYPE",
                     "headline": res["headline"], "run_id": res["run_id"], "engine": res["engine"], "ai_line": line}
    _hype["card"] = None
    events.emit("hype_verdict", {"truth": truth, "headline": res["headline"]})
    return _hype_view()


# ---- stream & pages ---------------------------------------------------------------------------------
@app.get("/api/stream")
async def stream(request: Request):
    buf = events.subscribe()

    async def gen():
        try:
            yield "retry: 2000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                while buf:
                    ev = buf.pop(0)
                    yield f"data: {json.dumps(ev)}\n\n"
                yield ": hb\n\n"
                await asyncio.sleep(0.5)
        finally:
            events.unsubscribe(buf)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/qr.png")
def qr(u: str | None = None):
    import qrcode
    img = qrcode.make(u or (lan_url() + "/join"), box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/join")
def join_page():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/lab")
def lab_page():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/chip")
def chip_page():
    return FileResponse(ROOT / "static" / "chip.html")


# ---- the front-page game (games/chipgame.py) ---------------------------------------------------------
@app.get("/api/game/state")
def game_state():
    s = chipgame.state()
    s["region"] = chipgame.used_region()
    s["join_url"] = lan_url() + "/join"
    s["host_lines"] = host.recent(4)
    return s


@app.post("/api/game/join")
async def game_join(req: Request):
    b = await req.json()
    try:
        return chipgame.join(orch._clean_nick(b.get("nick", "Player")))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/game/roll")
async def game_roll(req: Request):
    b = await req.json()
    try:
        return chipgame.roll(b["player"], b.get("level"), b.get("shots"))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/game/reset")
def game_reset():
    chipgame.reset()
    return {"ok": True}


@app.get("/table")
def table_page():
    return FileResponse(ROOT / "static" / "table.html")


@app.get("/making-of")
def making_of():
    p = ROOT / "MAKING_OF.md"
    return Response(p.read_text() if p.exists() else "MAKING_OF.md is written in the last step of the build.", media_type="text/plain; charset=utf-8")


@app.get("/api/health")
def health():
    return {"ok": True}
