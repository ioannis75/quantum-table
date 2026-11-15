# Logic designer I/O contract (for the Oumi Iris recipe)

This is what `agents/logic_designer.py` sends and what its parser (`parse_expr`, `normalise`) accepts. Anything outside it
falls back to the Claude answer, then to scripted statements; the kit (`qlogic/kit.py`) always overrides `prediction`.

## Input (one user message; system prompt = `logic_designer.SYSTEM`)
`Mode <ModeName>. Pairs: [(a, b), ...]`  — the mode's allowed (die0, die1) face pairs, uniform weight. Modes: Classical,
Bosonic, Fermionic, BosonicEntangled, FermionicEntangled.

## State encoding (fixed)
- Die `d` occupies qubits `3d .. 3d+2` (little-endian); the stored value is `face − 1` in binary (0..5); values 6, 7 have zero amplitude.
- Two dice = 6 qubits; a seated player adds 6 more (dice 2, 3 ...). House = dice 0 and 1.
- Prepared state = equal-amplitude superposition over the mode's allowed pairs.

## Output: ONE JSON object, no code fences, no text before or after
```json
{"task": "craps pass line",
 "reasoning": ["≤ 3 short steps"],
 "propositions": [
   {"name": "win",      "expr": "sum(0,1)==7 OR sum(0,1)==11"},
   {"name": "lose",     "expr": "sum(0,1)==2 OR sum(0,1)==3 OR sum(0,1)==12"},
   {"name": "point_4",  "expr": "sum(0,1)==4"}, {"name": "point_5", "expr": "sum(0,1)==5"},
   {"name": "point_6",  "expr": "sum(0,1)==6"}, {"name": "point_8", "expr": "sum(0,1)==8"},
   {"name": "point_9",  "expr": "sum(0,1)==9"}, {"name": "point_10","expr": "sum(0,1)==10"}],
 "queries": [{"type": "prob", "propositions": ["win"]},
             {"type": "compatible", "propositions": ["win", "lose"]},
             {"type": "implies", "propositions": ["point_4", "win"]}],
 "prediction": {"win": "8/36", "lose": "4/36", "point_4": "3/36", "compatible(win,lose)": true, "implies(point_4,win)": false}}
```
or `{"status": "needs_clarification", "reason": "..."}`.

### Expression grammar (`expr`, case-insensitive keywords)
```
expr   := term (OR term)*
term   := factor (AND factor)*
factor := NOT factor | '(' expr ')' | atom
atom   := face(die, k)            die ∈ {0,1,2,...}, k ∈ 1..6
        | sum(a, b) == n           n ∈ 2..12   (a, b are accepted but the kit sums dice 0 and 1 of the pair in question)
        | equal(a, b)              default equal(0,1)
        | qubit(i, axis, sign)     axis ∈ {X,Y,Z}, sign ∈ {1,-1}
```
Precedence: NOT > AND > OR; use parentheses otherwise. `expr` may also be the kit's JSON form
(`{"atom":"sum","n":7}`, `{"op":"or","args":[...]}`), which is accepted unchanged.

### Names the table looks for
`win`, `lose`, `point_4 … point_10` (also accepted: `point4`, `"4"`). Other propositions are evaluated if queried but do not
drive the game.

### Prediction values
`"a/b"` exact fraction string (preferred), a decimal, `true`/`false` for `compatible`/`implies`, or `"refused: reason"`.
Query labels: the proposition name for `prob`; `compatible(p,q)` / `implies(p,q)` otherwise.

## What the kit does with it
- Builds each proposition as a projector; AND = subspace intersection, OR = span, NOT = complement (never matrix products).
- `prob` = ⟨ψ|P|ψ⟩ on the mode's prepared state; `compatible` = commutator norm < 1e-9; `implies` = P ⊆ Q.
- Compares `win`/`lose`/`point_n` probabilities with direct enumeration of the pair table; any mismatch > 1e-9 is shown as
  **"Logic designer corrected"** and enumeration wins. Side bets on incompatible propositions are refused with
  "these two cannot be checked in the same roll".

## Two sample rows for the recipe
1. **Input:** `Mode BosonicEntangled. Pairs: [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6)]`
   **Output:** propositions as above; prediction `{"win": "0/6", "lose": "2/6", "point_4": "1/6", "point_6": "1/6", "point_8": "1/6", "point_10": "1/6", "point_5": "0/6", "point_9": "0/6"}`
   (only even sums exist; the kit confirms these exactly).
2. **Input:** `Mode FermionicEntangled. Pairs: [(1, 6), (2, 5), (3, 4)]`
   **Output:** prediction `{"win": "3/3", "lose": "0/3"}` and every `point_n` `"0/3"`.

Endpoint when deployed: `https://api.oumi.ai/inference/v1` (OpenAI-compatible), `model = projects/7HBTQDVH6J-14/deployments/<id>`,
set via `OUMI_MODEL` in `.env`. The code reads `OUMI_API_KEY`, `OUMI_PROJECT_ID`, `OUMI_DEPLOYMENT_ID`, `OUMI_MODEL` only.
