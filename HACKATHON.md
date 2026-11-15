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

## Keys present in this build
None. `.env` was empty: every agent row ran on its fallback. The code paths for the real services exist and are wired (see "Untested" below).

## Faked or mocked (what did NOT run for real)
- **Q-Scientist**: scripted circuits (no `ANTHROPIC_API_KEY`). The scripted code still goes through the same AST sandbox and verifier as model code would.
- **Logic designer**: scripted quantum-logic statements (no Oumi key; the Claude fallback also needs a key). `api.oumi.ai` is also not reachable from the build box.
- **Art director**: built-in SVG/canvas art (no `FAL_KEY`; `fal.run`/`fal.ai` not reachable from the build box). No fal.ai image was generated.
- **Host**: template commentary only; the number/banned-phrase checker runs on every line, including templates (it caught one template: "no quantum advantage claimed" contains a banned phrase; reworded).
- **Hype or Fact cards**: seed deck + two scripted stand-in cards. No AI-written cards (no key). The score line therefore shows "AI claims 0 of 0".
- **Chip**: every chip result is **"Simulated chip (fake backend)"** = `FakeBrisbane` from `qiskit_ibm_runtime.fake_provider` (127 qubits, 144 couplers, stored calibration snapshot, not live). No `IBM_QUANTUM_TOKEN`, so **0 real QPU seconds** were used. The "noise-model Aer" comparison on the fake backend uses the same noise model that generated the data, so agreement is expected (said on screen).
- **IBM price**: `www.ibm.com/quantum/pricing` could not be fetched (host not allowed from the build box) → "price unavailable", quotes in QPU seconds only. No price was typed from memory.
- **Daidalos memory**: no official total-memory figure found (sources in `data/daidalos.json`); shown as "Daidalos (Greek EuroHPC system)" without a number.
- **Discord**: no webhook → messages written to `DISCORD_POSTS.md`.
- **Video voice-over**: none (no `FAL_KEY`); burned-in captions only.
- **Quantum vote confidences**: scripted from exact numbers (fairness, entanglement visibility, entropy); with keys the agents would supply them.

## Untested code paths (written, not exercised)
- `engines/ibm._run_ibm()` (SamplerV2 submission, usage read-back) — no token, and `docs.quantum.ibm.com` was not reachable to confirm the current interface.
- `agents/llm.oumi_ask()` — OpenAI-compatible call, host unreachable.
- fal.ai image / TTS generation — not written beyond the hook (no key, host unreachable).

## Decisions ("our reconstruction")
- Qraps' five modes sample uniformly from fixed pair lists (`EntangledDice.cs`). We prepare that exact superposition on two 3-qubit registers (`prepare_state`); faces 7 and 8 have amplitude 0.
- Cross-table rule for a joining player: `equal` for Classical/Bosonic/BosonicEntangled, `sum7` for Fermionic/FermionicEntangled (CNOT copy + a 3-qubit permutation k→7−k).
- In the chip phase a round runs one Bell pair per player on distinct physical couplers; the dice faces are then drawn from the beacon output over the mode's pair table (labelled Simulated chip).
- The QPU-second estimate: `circuits × shots × (250 µs rep delay + 20 µs exec) + 2 s`.
- Pass-line stake 5 Qredits, payout 1:1; Hype or Fact 5 Qredits, 1:1.

## Cut
(none yet)

## Counters at the end of the build
(filled in by the final report)
