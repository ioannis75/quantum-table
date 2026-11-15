"""Qraps dice modes, transcribed from the original game's EntangledDice.cs (Quantum Game Jam 2021,
https://github.com/SuperStingray/qraps). Each roll samples uniformly from a fixed list of allowed (die1, die2) pairs.
Everything else here (quantum circuits, cross-table correlation rules) is OUR RECONSTRUCTION."""
from fractions import Fraction
from itertools import product

CLASSICAL = [(a, b) for a in range(1, 7) for b in range(1, 7)]
BOSONIC = [(a, b) for a in range(1, 7) for b in range(a, 7)]
FERMIONIC = [(a, b) for a in range(1, 7) for b in range(a + 1, 7)]
BOSONIC_ENT = [(k, k) for k in range(1, 7)]
FERMIONIC_ENT = [(1, 6), (2, 5), (3, 4)]

MODES = {
    "Classical": CLASSICAL,
    "Bosonic": BOSONIC,
    "Fermionic": FERMIONIC,
    "BosonicEntangled": BOSONIC_ENT,
    "FermionicEntangled": FERMIONIC_ENT,
}
# Our reconstruction: how a joining player's pair is correlated with the house pair.
CROSS_RULE = {"Classical": "equal", "Bosonic": "equal", "BosonicEntangled": "equal",
              "Fermionic": "sum7", "FermionicEntangled": "sum7"}
RULE_TEXT = {"equal": "each player die equals the matching house die",
             "sum7": "each player die and its house die sum to 7"}


def pair_dist(mode: str) -> dict:
    pairs = MODES[mode]
    return {p: Fraction(1, len(pairs)) for p in pairs}


def total_dist(mode: str) -> dict:
    d: dict = {}
    for (a, b), p in pair_dist(mode).items():
        d[a + b] = d.get(a + b, 0) + p
    return d


def craps_win_probability(mode: str) -> Fraction:
    """Pass-line win probability, exact. Come-out 7/11 win, 2/3/12 lose, else point: repeat until point or 7."""
    t = total_dist(mode)
    P = lambda s: t.get(s, Fraction(0))
    win = P(7) + P(11)
    for s, ps in t.items():
        if s in (2, 3, 7, 11, 12) or ps == 0:
            continue
        win += ps * ps / (ps + P(7))
    return win


def craps_win_probability_series(mode: str, terms: int = 4000) -> float:
    """Independent check: sum the geometric series term by term instead of the closed form."""
    t = {s: float(p) for s, p in total_dist(mode).items()}
    P = lambda s: t.get(s, 0.0)
    win = P(7) + P(11)
    for s, ps in t.items():
        if s in (2, 3, 7, 11, 12) or ps == 0:
            continue
        cont = 1 - ps - P(7)
        win += ps * sum(ps * cont ** k for k in range(terms))
    return win


def odds_table() -> dict:
    out = {}
    for m in MODES:
        w = craps_win_probability(m)
        out[m] = {"pairs": len(MODES[m]), "win": f"{w.numerator}/{w.denominator}",
                  "win_float": float(w), "rule": CROSS_RULE[m]}
    return out
