"""Financial agent: prices real QPU time, quotes, shadow invoices. SIMULATION ONLY: no payment code of any kind.
Every action passes the Gatekeeper's finance policy. All arithmetic is Decimal; a model may only word the summary."""
import json
import os
import re
import time
from decimal import Decimal, ROUND_HALF_UP

import config
import db
from gatekeeper import gate
from . import registry, llm

PRICING_URL = "https://www.ibm.com/quantum/pricing"
AGENT = "agt_finance"
C = Decimal("0.01")


def margin_pct() -> Decimal:
    try:
        return Decimal(os.environ.get("SERVICE_MARGIN_PCT", "20"))
    except Exception:
        return Decimal(20)


def fetch_price() -> dict:
    """Look up IBM's published pay-as-you-go price per QPU second. Never typed from memory."""
    cached = db.kv_get("ibm_price")
    if cached:
        return cached
    res = {"price_per_second_usd": None, "url": PRICING_URL, "fetched": time.strftime("%Y-%m-%d"), "status": "price unavailable"}
    try:
        import httpx
        r = httpx.get(PRICING_URL, timeout=10, follow_redirects=True, headers={"User-Agent": "quantum-table-build"})
        txt = re.sub(r"<[^>]+>", " ", r.text)
        m = re.search(r"\$\s?(\d+(?:\.\d+)?)\s*(?:/|per)\s*(?:second|sec)", txt, re.I)
        if r.status_code == 200 and m:
            res.update(price_per_second_usd=m.group(1), status="fetched")
    except Exception:
        pass
    db.kv_set("ibm_price", res)
    return res


def quote(job_hash: str, est_seconds: float) -> dict:
    g = gate.decide(AGENT, "quote_qpu_job", {"job_hash": job_hash}, purpose="quote a chip job")
    if g["action"] != "ALLOW":
        return {"status": "blocked", "gate": g}
    registry.set_status("financial_agent", "working")
    p = fetch_price()
    est = Decimal(str(est_seconds))
    q = {"job_hash": job_hash, "est_qpu_seconds": str(est), "price_source": p["url"], "price_date": p["fetched"],
         "margin_pct": str(margin_pct()), "gate": g["action"]}
    if p["price_per_second_usd"] is None:
        q.update(cost="price unavailable", total="quoted in QPU seconds only")
    else:
        cost = (est * Decimal(p["price_per_second_usd"])).quantize(C, ROUND_HALF_UP)
        total = (cost * (1 + margin_pct() / 100)).quantize(C, ROUND_HALF_UP)
        q.update(cost=str(cost), total=str(total), price_per_second=p["price_per_second_usd"])
    db.q("INSERT INTO quotes(ts,job_hash,kind,data) VALUES(?,?,?,?)", (time.time(), job_hash, "quote", json.dumps(q)))
    registry.set_status("financial_agent", "idle", "code (Decimal)")
    return q


def shadow_invoice(job_hash: str, actual_seconds: float, est_seconds: float, verdict: str, job_id: str, label: str) -> dict:
    g = gate.decide(AGENT, "write_shadow_invoice", {"job_hash": job_hash}, purpose="write a shadow invoice")
    if g["action"] != "ALLOW":
        return {"status": "blocked", "gate": g}
    p = fetch_price()
    act, est = Decimal(str(actual_seconds)), Decimal(str(est_seconds))
    inv = {"banner": "SHADOW INVOICE: simulation, not a bill", "job_hash": job_hash, "job_id": job_id, "engine": label,
           "actual_qpu_seconds": str(act), "estimated_qpu_seconds": str(est), "verifier": verdict, "margin_pct": str(margin_pct()),
           "true_cost_note": "On the free plan (or a fake backend) the true cost is zero."}
    if p["price_per_second_usd"] is None:
        inv.update(list_price_equivalent="price unavailable", margin="price unavailable", total="price unavailable")
    else:
        basis = act if act > 0 else est
        cost = (basis * Decimal(p["price_per_second_usd"])).quantize(C, ROUND_HALF_UP)
        margin = (cost * margin_pct() / 100).quantize(C, ROUND_HALF_UP)
        inv.update(list_price_equivalent=str(cost), margin=str(margin), total=str(cost + margin),
                   would_cost_on_paid_plan=str(cost), basis="estimate" if act == 0 else "actual")
    db.q("INSERT INTO quotes(ts,job_hash,kind,data) VALUES(?,?,?,?)", (time.time(), job_hash, "shadow_invoice", json.dumps(inv)))
    return inv


def try_charge_player() -> dict:
    """The jury button: the Financial agent tries to charge a player; the Gatekeeper blocks it."""
    return gate.decide(AGENT, "charge_customer", {}, purpose="try to charge a player")


def ledger_summary() -> dict:
    rows = db.rows("SELECT data FROM quotes WHERE kind='shadow_invoice'")
    invs = [json.loads(r["data"]) for r in rows]
    qpu = sum(Decimal(i["actual_qpu_seconds"]) for i in invs)
    est = sum(Decimal(i["estimated_qpu_seconds"]) for i in invs)
    lp = [Decimal(i["list_price_equivalent"]) for i in invs if i.get("list_price_equivalent") not in (None, "price unavailable")]
    mg = [Decimal(i["margin"]) for i in invs if i.get("margin") not in (None, "price unavailable")]
    return {"invoices": len(invs), "qpu_seconds_used": str(qpu), "qpu_seconds_estimated": str(est),
            "list_price_equivalent_usd": str(sum(lp)) if lp else "price unavailable",
            "margin_usd": str(sum(mg)) if mg else "price unavailable"}


def summary_text() -> dict:
    """One paragraph built only from ledger numbers. A model may only word it; any number must match or the template wins."""
    s = ledger_summary()
    tmpl = (f"This session priced {s['invoices']} chip job(s): {s['qpu_seconds_used']} QPU seconds used, "
            f"{s['qpu_seconds_estimated']} estimated, list-price equivalent {s['list_price_equivalent_usd']}, "
            f"service margin {s['margin_usd']}. Shadow invoices only: simulation, not a bill.")
    text, src = tmpl, "template summary"
    try:
        t, label = llm.anthropic_ask("You word one short paragraph for a business summary. Use only the numbers given. No hype.",
                                     "Numbers: " + json.dumps(s), "fast", 200)
        nums = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(s)))
        if all(n in nums for n in re.findall(r"\d+(?:\.\d+)?", t)):
            text, src = t, label
    except Exception:
        pass
    return {"text": text, "source": src, "ledger": s}
