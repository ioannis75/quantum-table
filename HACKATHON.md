# HACKATHON.md — build log, Quantum Table (Sunday 15 Nov 2026)

Unattended build from `PROMPT.md`. Times are Athens (EET). Feature freeze 14:00, submission 18:00.

## Timeline
- 03:54 start. Machine: 16.9 GB RAM, 4 cores, Python 3.13.18, Node 22.23, pnpm 10.28, qiskit 2.6.2 / qiskit-aer 0.18.2 / qiskit-ibm-runtime 0.52.1.
- 03:58 step 1–2 done: verifier, sandbox, Qraps modes + circuits + exact odds. 39 tests pass. Commit.
- 04:00 ADAP cloned and `adap-policy` built (commit a652f74). `gate-cli.mjs` answers.
- 04:04 burn-down probe (real Aer runs in a memory-capped subprocess, 80% of RAM = 13.5 GB): 29 qubits ran in 26.4 s at 8.8 GB RSS; **refused at 30 qubits** (needs 16 B × 2³⁰ = 17.2 GB).
- 04:12 **Milestone A**: keyless page with Roll, badge, odds, burn-down meter, chip map, Gatekeeper log. Commit.
- 04:14 3D table (Three.js 0.170.0 vendored) renders headlessly with SwiftShader: 85 draw calls, no console errors; `docs/3d_before_roll.png`, `docs/3d_entangled.png`, `docs/3d_landed.png` are non-blank and differ. 3D is the default; `?view=2d` and the no-WebGL fallback keep the 2D table.
- 04:20 **Milestone B**: join → entangle → commit-reveal round → beacon record → `verify_beacon.py` PASS; skip-ahead seats bots until the emulator phase ends at 30 qubits; chip job on the fake backend with per-pair TVD and a shadow invoice.

- 04:20–04:28 the human supplied `FAL_KEY`, `ANTHROPIC_API_KEY`, `OUMI_API_KEY` + project id during the build. The egress allowlist was extended for `fal.run`, `queue.fal.run`, `v3b.fal.media`, `api.oumi.ai`, `api.anthropic.com`.
- 04:26 video rendered: 154.8 s, 1080p, fal.ai Kokoro stock voice, burned-in captions, 3 frames non-black (`video/CHECK.json`).
- 04:27 Q-Scientist on Claude Sonnet: model-written circuits pass the sandbox and the verifier for every mode tried.
- 04:59 Oumi status (from the platform side): no deployment exists yet; ids left empty. Logic designer parser made tolerant of the planned Iris contract; Claude fallback labelled "Claude (fallback, …)".
- 05:10 final test run, docs, commit.

- 11:46–12:40 **front-page redesign** (human's notes after first view): gameplay only on `/`; the old page became `/lab`. New `games/chipgame.py`: each die = 3 physical qubits on `fake_brisbane`, player qubits + house "hearts" highlighted on a zoomed chip map, one circuit per roll through the noise model, one shot by default, entanglement level as the fraction of entangled rolls, fidelity from calibration, aggregate verifier. Measured first: the exact partially-entangled pure state is too deep for the noise model (102 two-qubit gates, 28 % equal faces), the shallow copy keeps 80 %; recorded in the module docstring. `PUBLIC_URL` support in `lan_url()`.

- 12:50–13:10 human asked to go back to the previous page design as `/`, with only the Bosonic-entangled option and many shots: mode fixed to `BosonicEntangled`, 4096 shots per roll, new "Dice tomography" card (frequencies vs exact). The chip game stays at `/chip`.

- 13:00–13:15 demo trim: agent strip moved to a "Credits: the AI team that built this game" section; 1024 shots per roll; chip map, Gatekeeper, Hype or Fact, quantum vote and AI host folded into "Extended: future plan" (still working, one click away). `boxd_update.sh` added.

## Keys present in this build
`ANTHROPIC_API_KEY` (Q-Scientist, Host, Logic designer fallback, Financial summary), `FAL_KEY` (art, voice-over), `OUMI_API_KEY` + `OUMI_PROJECT_ID` (no deployment to call). `IBM_QUANTUM_TOKEN` empty on purpose ("no real QPU for the demo"). `DISCORD_WEBHOOK_URL` empty.

## Faked or mocked (what did NOT run for real)
- **Front-page chip**: every roll runs on `AerSimulator.from_backend(FakeBrisbane)` with the stored calibration snapshot, never on a QPU; the label says "Simulated chip (fake backend noise model, fake_brisbane)". The fidelity number is a product of calibration errors, not a measured fidelity. Misfires (levels 7/8) are real consequences of that noise model. The "entanglement level" is a per-roll mixture of two circuits, not a continuously tuned entangling angle (reason in the log above).
- **Logic designer: Oumi deployment not available, Claude fallback.** Project 7HBTQDVH6J-14 has no deployed model (API lists 0 models, 0 deployments); the UI shows "Claude (fallback, claude-sonnet-5-5)". When Iris is deployed, only `OUMI_DEPLOYMENT_ID` / `OUMI_MODEL` in `.env` change.
- **Host**: Claude Haiku lines when the 5-second budget allows, templates otherwise (most lines in a busy round are templates). The checker runs on every line including templates; it caught one template during tests ("no quantum advantage claimed"), reworded.
- **Hype or Fact cards**: seed deck + two scripted stand-in cards first; AI-written cards (Claude Haiku) from every third deal, validated by running them before they reach the table.
- **Quantum vote confidences**: scripted from exact numbers; with more time the agents would supply them from their own answers.
- **Chip**: every chip result is **"Simulated chip (fake backend)"** = `FakeBrisbane` from `qiskit_ibm_runtime.fake_provider` (127 qubits, 144 couplers, stored calibration snapshot, not live). No `IBM_QUANTUM_TOKEN`, so **0 real QPU seconds** were used. The "noise-model Aer" comparison on the fake backend uses the same noise model that generated the data, so agreement is expected (said on screen).
- **IBM price**: `www.ibm.com/quantum/pricing` could not be fetched (host not allowed from the build box) → "price unavailable", quotes in QPU seconds only. No price was typed from memory.
- **Daidalos memory**: no official total-memory figure found (sources in `data/daidalos.json`); shown as "Daidalos (Greek EuroHPC system)" without a number.
- **Discord**: no webhook → messages written to `DISCORD_POSTS.md`.
- **Video**: voice is a stock synthetic voice (fal.ai Kokoro `af_heart`), stills are PIL-drawn abstract art; footage is the real page. "Narration and images AI-generated" on the end card.
- **Art**: 3 fal.ai images (`flux/schnell`) cached in `assets/`, used as felt texture; dice and chip map remain code-drawn.

## Untested code paths (written, not exercised)
- `engines/ibm._run_ibm()` (SamplerV2 submission, usage read-back) — no token, and `docs.quantum.ibm.com` was not reachable to confirm the current interface.
- `agents/llm.oumi_ask()` against a real deployment — the call path was exercised (400/404 answers from the API), never a successful completion.
- The Iris output-contract parser (`agents/logic_designer.parse_expr/normalise`) is unit-tested on synthetic input only.

## Decisions ("our reconstruction")
- Qraps' five modes sample uniformly from fixed pair lists (`EntangledDice.cs`). We prepare that exact superposition on two 3-qubit registers (`prepare_state`); faces 7 and 8 have amplitude 0.
- Cross-table rule for a joining player: `equal` for Classical/Bosonic/BosonicEntangled, `sum7` for Fermionic/FermionicEntangled (CNOT copy + a 3-qubit permutation k→7−k).
- In the chip phase a round runs one Bell pair per player on distinct physical couplers; the dice faces are then drawn from the beacon output over the mode's pair table (labelled Simulated chip).
- The QPU-second estimate: `circuits × shots × (250 µs rep delay + 20 µs exec) + 2 s`.
- Pass-line stake 5 Qredits, payout 1:1; Hype or Fact 5 Qredits, 1:1.

## Ideas noted, not implemented
- Three-party Byzantine agreement with the house (three-qutrit singlet) and BB84/E91 key exchange feeding the beacon: `docs/IDEAS_byzantine_qkd.md`. Not started before the freeze.

## Cut
- Pagonis emulator: removed by the human in the final brief (not built).
- Model-supplied vote confidences: scripted instead (one line of work, not on the Roll → badge → burn-down → chip path).
- Real QPU job: off by the human's instruction for the demo.

## Counters at the end of the build
See `MAKING_OF.md` ("Counters"): 23 ALLOW / 2 BLOCK Gatekeeper decisions, 11 beacon rounds, 6 Hype or Fact experiments, 0 real QPU seconds, 0 Logic designer corrections, 0 model Host lines corrected (1 template reworded in tests).
