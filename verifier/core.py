"""The verifier: not an LLM. Exact and statistical checks. Its badge is final."""
import hashlib
import json
import math

import numpy as np
from scipy.stats import chi2

ALPHA = 0.01
TOL = 1e-9


def canon_dist(dist: dict) -> str:
    return json.dumps({k: round(float(v), 12) for k, v in sorted(dist.items())}, separators=(",", ":"))


def commit_hash(code: str, expected: dict) -> str:
    """SHA-256 of circuit code + expected distribution (shown before the run, re-checked after)."""
    return hashlib.sha256((code + "\n" + canon_dist(expected)).encode()).hexdigest()


def check_expectation(exact: dict, stated: dict, tol: float = TOL) -> dict:
    keys = set(exact) | set(stated)
    maxdiff = max((abs(exact.get(k, 0.0) - stated.get(k, 0.0)) for k in keys), default=0.0)
    return {"ok": maxdiff <= tol, "max_abs_diff": maxdiff, "tol": tol}


def tvd(p: dict, q: dict) -> float:
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def check_counts(counts: dict, exact: dict, alpha: float = ALPHA) -> dict:
    """Seeded-shot check of an emulator run against the exact distribution."""
    shots = sum(counts.values())
    emp = {k: v / shots for k, v in counts.items()}
    impossible = [k for k, v in counts.items() if exact.get(k, 0.0) <= 1e-15 and v > 0]
    # pool categories with expected count < 5
    big = [k for k, p in exact.items() if p * shots >= 5]
    rare_p = sum(p for k, p in exact.items() if p * shots < 5)
    obs = [counts.get(k, 0) for k in big]
    exp = [exact[k] * shots for k in big]
    if rare_p > 0:
        obs.append(sum(counts.get(k, 0) for k, p in exact.items() if p * shots < 5))
        exp.append(rare_p * shots)
    stat = sum((o - e) ** 2 / e for o, e in zip(obs, exp) if e > 0)
    dof = max(len(obs) - 1, 1)
    pval = float(chi2.sf(stat, dof)) if len(obs) > 1 else 1.0
    t = tvd(emp, exact)
    ok = (not impossible) and pval > alpha
    return {"ok": ok, "shots": shots, "chi2": stat, "dof": dof, "p_value": pval,
            "tvd": t, "alpha": alpha, "impossible_outcomes": impossible[:5]}


def check_hardware(counts: dict, ideal: dict, noisy_counts: dict | None = None) -> dict:
    """Hardware: TVD vs ideal and vs noise-model Aer; NO ideal chi-square."""
    shots = sum(counts.values())
    emp = {k: v / shots for k, v in counts.items()}
    t_ideal = tvd(emp, ideal)
    out = {"shots": shots, "tvd_ideal": t_ideal, "chi_square_applied": False}
    # 1-sigma-style error bar on TVD: sqrt(sum p(1-p)/N)/ 2 summed -> simple bound
    out["tvd_error_bar"] = 0.5 * sum(math.sqrt(max(p * (1 - p), 0) / shots) for p in emp.values())
    if noisy_counts:
        ns = sum(noisy_counts.values())
        out["tvd_noise_model"] = tvd(emp, {k: v / ns for k, v in noisy_counts.items()})
    return out


def badge(expectation_ok: bool, counts_ok: bool | None, hardware: bool = False) -> str:
    if not expectation_ok:
        return "EXPECTATION WRONG"
    if hardware:
        return "HARDWARE RUN: compared, not chi-square tested"
    if counts_ok is None:
        return "EXPECTATION OK"
    return "VERIFIED" if counts_ok else "CHECK FAILED"


def correlation_check(samples: list, rule: str) -> dict:
    """samples: list of (house_pair, player_pair) with faces 1..6. rule: 'equal' | 'sum7'."""
    bad = 0
    for h, p in samples:
        for x, y in zip(h, p):
            if (rule == "equal" and x != y) or (rule == "sum7" and x + y != 7):
                bad += 1
    return {"ok": bad == 0, "violations": bad, "samples": len(samples), "rule": rule}
