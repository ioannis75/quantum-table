# Quantum Table: technical notes

Full build notes, moved here from the README on 15 Nov 2026. The README is the short version. Where this file and the README differ, the README describes the current front page.


A team of AI agents designs and runs quantum dice games. The first game is **Qraps** (quantum craps). Players join a table, each brings a pair of dice and entangles them with the house's dice; every player adds qubits; the table runs on an emulator until exact simulation runs out of memory ("the emulator burned down"), then moves to a quantum chip where players buy physical qubit pairs with **Qredits** (play credits, no cash value). A **verifier made of code, not a model,** checks every roll, and every roll is published as a record anyone can recompute.

> One sentence: Quantum Table turns a craps game into collectively generated, publicly checkable randomness: people and AI agents each put something in, nobody at the table controls the outcome alone, and a verifier (not a model) checks every roll.

## Run it

```bash
./run.sh
```

That creates `.venv`, installs `requirements.txt`, builds ADAP's policy engine if Node 22+ and pnpm 10+ are present, and starts on `0.0.0.0:$PORT` (default 8080). Open `http://<host>:8080/`.

- `/` the table (3D by default; `?view=2d`, and the automatic fallback without WebGL). **One game: Bosonic dice entangled to the house** (the original Qraps `BosonicEntangled` table: doubles only, player dice equal the house dice). Every roll runs **1024 shots** on the Aer emulator; one shot picked by the beacon rule decides the faces, and the whole sample is shown in the **Dice tomography** card (measured frequency per pair vs the exact probability; Bloch arrows from the reduced density matrices). Measurement statistics in one basis, not full state tomography, and it says so. The rest of the page: agent strip, burn-down, chip map and buy-in, Gatekeeper, Hype or Fact, quantum vote, join QR, AI host.
- `/chip` the alternative front page built earlier today: gameplay only, each die as 3 physical qubits with the house "hearts" on the chip map, one circuit per roll through the fake backend's noise model, one shot (`games/chipgame.py`)
- `/lab` same as `/`
- `/join` seats a player (nickname only, 100 Qredits, nothing personal stored); the Join QR is behind the small button on the front page
- `/table` the projector view
- `/beacon/latest`, `/beacon/{round}` the public records; `verify_beacon.py` re-checks them
- `/making-of` how this was built

`PUBLIC_URL` in `.env` (or the environment) overrides the detected LAN address in the join URL and QR, for tunnels or a venue hostname.

Keys go in `.env` (see `PROMPT.md`, "Keys"). Every key is optional: a keyless run works end to end in scripted mode and the page names the fallback in use. `.env` is git-ignored; never commit it.

Tests: `. .venv/bin/activate && python -m pytest -q tests` (≈100 tests, 1–3 minutes).

## What is real and what is simulated (this build, 15 Nov 2026)

| Part | Status |
|---|---|
| `/chip` roll: circuit per roll, noise model of the assigned qubits, one shot, aggregate verifier | real circuits, **simulated chip** (fake backend calibration); no QPU |
| Qraps circuits, exact odds (`fractions.Fraction`), verifier, sandbox | real, tested |
| Emulator runs | **Qiskit Aer** statevector; burn-down measured on this machine: 29 qubits ran (26.4 s, 8.8 GB), **refused at 30** (16 B × 2³⁰ = 17.2 GB > 80 % of 16.9 GB) |
| Q-Scientist | Claude (`claude-sonnet-5-5`) writes the circuit code; it runs only in the AST-allowlisted subprocess sandbox; the verifier decides. Fallback: scripted circuits |
| Logic designer | **Oumi** (project 7HBTQDVH6J-14, deployment 2, `OUMI_BASE_URL=https://inference.oumi.ai/v1`) writes the quantum-logic propositions in the Iris contract (`docs/IRIS_CONTRACT.md`); the `qlogic/` kit evaluates them exactly, enumeration has the last word, and the model's own predictions are checked ("Logic designer corrected" when they differ). Claude is the fallback, labelled when used |
| Host | Claude (`claude-haiku-5-5`), one short call per event, every line checked by code (numbers must come from the event, banned phrases, ≤ 25 words); failures counted on screen. Templates otherwise |
| Art | fal.ai (`flux/schnell`), 3 images generated once and cached in `assets/`; never called at request time |
| Chip | **Simulated chip (fake backend)**: `FakeBrisbane` from `qiskit_ibm_runtime.fake_provider` (127 qubits, stored calibration snapshot). No real QPU job was run; `IBM_QUANTUM_TOKEN` left empty on purpose |
| Quantum Time Gatekeeper | **ADAP's policy engine**, in-process via `adap/gate-cli.mjs` (commit a652f74). Not ADAP's signed-delegation path; no signed receipts |
| Beacon | real commit-reveal over every round; `verify_beacon.py` (standard library) recomputes it |
| Video | `video/quantum_table.mp4`, 154.8 s, 1080p, fal.ai Kokoro stock voice, burned-in captions; footage recorded from the real page |

Honest wording we use: "consistent with theory at the stated threshold", "correlated as the mode requires, checked by the verifier", "collectively generated, publicly checkable". We never say "certified random", "proves", "quantum advantage", "tamper-proof".

## How a /chip roll works (`games/chipgame.py`)

- Each die is a 6-level qudit in 3 physical qubits. A seat is a 12-qubit row segment of `fake_brisbane`: house die A, player die A, house die B, player die B (3 qubits each). Links on the map join each player qubit to its house partner.
- The house die is prepared as the uniform superposition over faces 1–6; the player's die is a CNOT copy of it (entangled circuit, entanglement entropy log₂6 = 2.585 bits) or an independent uniform die (independent circuit, 0 bits). The **entanglement level** is the fraction of rolls that use the entangled circuit, drawn per roll by the emulator's seeded RNG (the coin and the choice are shown). We measured why the circuits are shallow: an exact partially-entangled pure state needs ~100 two-qubit gates after transpiling to the heavy-hex and the noise model erases the correlation (28 % equal faces at full entanglement vs 80 % for the shallow copy).
- The circuit is transpiled to the player's physical qubits and run through the backend's noise model; the **fidelity** shown is Π(1 − error) over every gate and readout actually used, from the calibration snapshot. **One shot** decides the roll (switch: 100 shots, majority face). A reading of level 7 or 8 is a **misfire** (no result), which is what noise does to a qudit.
- Verifier: one shot cannot be chi-square tested, so it checks the exact circuit distribution against the stated one on every roll (1e-9) and runs chi-square (ideal emulator shots) and TVD (noise-model shots) on the **aggregate** of all rolls with the same settings; the badge says so.

## How the lab works

- **Dice**: two 3-qubit registers; the value `face−1` is written in binary; faces 7 and 8 have zero amplitude. Each Qraps mode is prepared exactly as a uniform superposition over the original game's allowed pairs (`games/qraps/modes.py`, transcribed from `EntangledDice.cs`).
- **Entangling with the house**: a joining player's registers are CNOT-copied from the house pair (modes Classical/Bosonic/BosonicEntangled: always equal) or copied and complemented k→7−k (Fermionic modes: always summing to 7). Our reconstruction; labelled so.
- **Verifier** (`verifier/core.py`): exact distribution vs the agent's stated distribution to 1e-9 → else **EXPECTATION WRONG**; seeded shots vs exact, χ² p > 0.01 plus total-variation distance → else **CHECK FAILED**; commit-reveal SHA-256 of code + expected distribution shown before the run and re-checked after; correlation rule checked over the shots. Hardware results are compared by TVD (to the ideal and to an Aer run under the backend's noise model) and are never χ²-tested against the ideal.
- **Bloch arrows** (`games/qraps/circuits.bloch_vectors`): reduced density matrix per qubit from the statevector → (x, y, z). Entangled qubits shrink toward the centre; after measurement they snap to the poles that spell the face.
- **Burn-down**: memory = 16 bytes × 2ⁿ; probes run Aer in a subprocess with `RLIMIT_AS` at 80 % of RAM. The meter marks this machine, Daidalos (no public memory figure found; sources in `data/daidalos.json`) and ~50 qubits. This is the cost of exact statevector simulation, not of every classical method.
- **Chip**: pairs priced from calibration: `price = 5 + round(15·(1 − (e − e_min)/(e_max − e_min)))` Qredits with `e` = two-qubit error + both readout errors. All players' pairs go into **one** job; results per pair with TVD error bars.
- **Quantum Time Gatekeeper** (`gatekeeper/`, `adap/`): estimate = circuits × shots × (250 µs + 20 µs) + 2 s, computed by code; ledger in SQLite; `paid_plan` from the account or `true` if unknown. ≤ 10 s ALLOW, 10–60 s REQUIRE_HUMAN (stored as "waiting for approval", Approve button valid for that job hash only), > 60 s or > 120 s total or paid plan BLOCK. Exactly one function (`engines/ibm.submit_qpu_job`) may read the token; a test greps for any second use.
- **Financial agent** (`agents/financial.py`): quotes and **shadow invoices** only ("SHADOW INVOICE: simulation, not a bill"); `charge_customer`, `sell_qredits`, `payout` are BLOCKed by the finance policy. The IBM price page could not be fetched from the build box → "price unavailable", quotes in QPU seconds only. No payment code of any kind exists.
- **Beacon** (`beacon/`): each participant (house, players, agents) commits SHA-256(secret) before the round and reveals after; XOR of secrets + hash of counts seeds a partial Fisher–Yates over the shots; output = SHA-256 of the selection; each record links the previous one's hash. A participant who does not reveal within 20 s is dropped and the round re-runs without them (a late revealer can force a re-run, not choose a result). On an emulator the quantum part is simulated and the unpredictability comes from the participants' secrets. The real thing is NIST/CU Boulder's CURBy beacon; this is a small, playful cousin with weaker guarantees. Randomness here can break a tie or pick an order; it does not count or decide votes.

### Beacon for other agents

```bash
curl -s http://HOST:8080/beacon/latest | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['round'], r['output'])"
python3 verify_beacon.py http://HOST:8080            # PASS or FAIL for the latest round (and its chain link)
```

Fields: `round, time, engine, mode, circuit_hash, commitments, reveals, dropped, counts, seed, selected, output, faces, badge, verifier, prev_hash, selection_rule, hash`. Use `output` (hex) modulo your number of options for a fair pick, and keep the round id as the receipt.

## Layout

`agents/` (one file per agent + `orchestrator.py`), `engines/` (aer, ibm, burndown), `verifier/`, `games/qraps/`, `games/hype.py`, `qlogic/`, `beacon/`, `gatekeeper/` + `adap/`, `static/` (plain HTML/JS, Three.js vendored), `tests/`, `assets/`, `data/` (SQLite), `video/`, `docs/` (screenshots).

## Credits and sources

- **Qraps** dice modes: the original Qraps by its Quantum Game Jam 2021 team, https://github.com/SuperStingray/qraps (`Assets/Dice/Plugins/EntangledDice.cs`). Circuits and cross-table rules here are our reconstruction.
- **Quantum Time Gatekeeper, powered by ADAP's policy engine**: Agent Delegated Authority Protocol, https://github.com/Hardalion/agent-delegated-authority (Apache-2.0).
- Qiskit, Qiskit Aer, qiskit-ibm-runtime (fake provider); Three.js (MIT, `static/vendor/THREE_LICENSE`); FastAPI; fal.ai (`flux/schnell`, `kokoro/american-english`).
- Daidalos: GRNET tender specification (https://grnet.gr/wp-content/uploads/2022/11/01_Techical_Specifications_DAEDALUS.2022.12.01.pdf), EuroHPC JU (https://eurohpc-ju.europa.eu/daedalus-call-acquire-new-european-world-class-supercomputer-greece-2024-06-25_en). No official total-memory figure was found, so none is shown.
- CURBy (NIST / CU Boulder) as the real randomness beacon we compare ourselves against.
- Birkhoff & von Neumann, "The Logic of Quantum Mechanics" (1936), for the `qlogic/` kit.

---

## For the human admin (how to run the demo)

1. **Start**: `./run.sh` on the demo machine. Open `http://<lan-ip>:8080/` on the laptop and `http://<lan-ip>:8080/table` on the projector. The join QR on both pages points at `/join` on the LAN address the server detects; if the room's Wi-Fi isolates clients, use a hotspot or type the URL shown.
2. **Keys**: put them in `.env` before starting (`ANTHROPIC_API_KEY`; `OUMI_API_KEY` + `OUMI_PROJECT_ID` + `OUMI_DEPLOYMENT_ID` + `OUMI_MODEL` + `OUMI_BASE_URL`; `FAL_KEY`; optional `DISCORD_WEBHOOK_URL`). Leave `IBM_QUANTUM_TOKEN` empty for the demo: the chip stays "Simulated chip (fake backend)" and no QPU time can be spent. With a token, the Gatekeeper limits apply and REQUIRE_HUMAN jobs wait for your **Approve** tap.
3. **Reset between runs**: `curl -X POST localhost:8080/api/reset` clears seats and purchases (rounds and the beacon chain are kept on purpose).
4. **Script of the show** (≈3 min): Roll once (badge VERIFIED) → Join (thread glows, arrows shrink) → Roll (dice land on measured faces) → Skip ahead (emulator burns down at 30 qubits) → Run chip job (per-pair TVD, shadow invoice) → Try to overspend (BLOCK) → Try to charge a player (BLOCK) → Hype or Fact: deal, bet, run → Decide something (beacon pick) → open `/beacon/latest` and run `verify_beacon.py`.
5. **Discord**: with `DISCORD_WEBHOOK_URL` set, the Host posts at most one message per 10 minutes, 12 in total; otherwise copy them from `DISCORD_POSTS.md`.
6. **Before the stage**: record a plain screen capture of the page as backup, rehearse `PITCH.md`, and watch `video/quantum_table.mp4` once. Rotate any API key that was ever pasted into a chat.
7. **If something breaks**: `?view=2d` for the 2D table; the server log is `data/server.log`; `python -m pytest -q tests` tells you what still passes.

## For players (what to do at the table)

1. Scan the QR (or open the join URL), pick a nickname. You get **100 Qredits**: play credits, no cash value, nothing to buy or cash out.
2. Your pair of dice is entangled with the house pair. Watch the thread and the six small arrows above your dice.
3. Tap **Roll**. Order: the circuit runs and the verifier checks it → the faces are known → the dice land on them. Pass line: 7 or 11 wins, 2/3/12 loses, otherwise your total becomes the point. Stake 5 Qredits, 1:1.
4. When the host deals a **Hype or Fact** card, bet 5 Qredits on Fact or Hype. The experiment decides, not the host.
5. On the chip phase, tap a link on the chip map and **Buy chosen pair**; your pair's results come back with error bars.
6. Everything you rolled is at `/beacon/<round>`. Don't trust us; check it with `verify_beacon.py`.
