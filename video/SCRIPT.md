# Quantum Table — 3-minute explainer, script

Audience: the public and a mixed jury. Tone: curious and concrete. English. No voice-over in this build (no `FAL_KEY`): every line is a burned-in caption. Target ≤ 3:00, 1080p.

| # | Time | On screen | Caption (spoken line) |
|---|---|---|---|
| 1 | 0:00–0:07 | The 3D table, dice tumbling, then landing | Quantum Table. A craps game where AI agents design the dice and nobody at the table controls the roll alone. |
| 2 | 0:07–0:14 | The verifier badge turns VERIFIED | Who checks the AI? The experiment. A verifier made of code, not a model, checks every roll. |
| 3 | 0:14–0:20 | Beacon link, verify_beacon.py PASS | Every roll is published. Anyone can recompute it. Don't trust us; check it. |
| 4 | 0:20–0:32 | One die, six Bloch spheres, prepared state | Superposition: before the roll each die is a mix of all six faces. Six faces, three qubits per die. |
| 5 | 0:32–0:47 | Join, thread glows, arrows shrink to the centre | Entanglement: your dice and the house's agree without either being fixed in advance. Each qubit's arrow shrinks: alone, it has no state of its own. |
| 6 | 0:47–0:57 | Roll; dice land; thread disappears; arrows snap to poles | Measurement: looking gives one answer, and the pair falls apart. One roll, one outcome. |
| 7 | 0:57–1:05 | Burn-down meter growing; "Emulator burned down at 30 qubits" | The fourth resource is classical memory. Exact simulation doubles per qubit. On this machine the emulator ran 29 qubits and was refused at 30. Then a chip takes over. |
| 8 | 1:05–1:15 | Hype or Fact card: "Entangled dice let the player send a message to the house instantly." | Hype or Fact. The AI host deals a claim. Players bet Qredits, play credits with no cash value. |
| 9 | 1:15–1:32 | The experiment runs; numbers appear | The experiment: the player does three different things to their dice. The house's own distribution changes by 4.2e-16. Nothing. |
| 10 | 1:32–1:50 | Verdict screen: HYPE | Verdict: Hype. Correlation is not communication. The verifier decided, not the host. |
| 11 | 1:50–2:03 | Still: a die half in shadow (cat) | Schrödinger's cat is really a question: where does "one outcome" come from, when the equations keep every branch? |
| 12 | 2:03–2:14 | Still: two dice joined by a thread | "Spooky action": the dice agree instantly, yet no message passes. You only see the agreement when you compare notes. |
| 13 | 2:14–2:30 | Still: branching paths | Many worlds reads the same equations as every outcome happening in a branch. Copenhagen-style readings stop at the measurement. Pilot-wave readings add hidden positions. They are interpretations: all predict the same dice statistics, so this table cannot tell you which is right. Physicists disagree. |
| 14 | 2:30–2:42 | HACKATHON.md "Faked or mocked" list on screen | What is real today: the circuits, the verifier, the Aer emulator runs, the beacon, the ADAP policy gate. What is simulated: the chip (a fake backend), the art, the host's model. Everything in this video ran on an emulator; nothing ran on a quantum chip. |
| 15 | 2:42–2:52 | Credits | Qraps modes from the Quantum Game Jam 2021 game. Gatekeeper on ADAP's policy engine. Built by a person's ideas, agents doing the building, and checks deciding what stayed. |
| 16 | 2:52–3:00 | End card + join QR | Narration and images AI-generated. Results from real runs; ids in the repo. |

## Hype-rule check
Each caption was checked against the banned list ("tries all answers at once", "faster than light communication", "proves many worlds", "truly random, certified", "quantum advantage", "unhackable", consciousness causing collapse). None appears. Each interpretation in #13 is named as an interpretation; none is presented as a result of this demo. #14 is the sentence that says which parts ran on an emulator and which on a chip (none).

## Numbers spoken or shown, with their origin
| Number | Origin |
|---|---|
| six faces, three qubits per die | `games/qraps/circuits.py` layout (3 qubits per die) |
| ran 29 qubits, refused at 30 | burn-down probe rows in `data/quantum_table.db` table `probe` (n=29 ok, 26.4 s, 8.8 GB RSS; n=30 refused). 16 B × 2³⁰ = 17.2 GB > 13.5 GB (80 % of 16.9 GB). |
| 4.2e-16 | Hype or Fact run `hype-no-signalling-*` (`games/hype.py`, check `signalling`: max change of the house marginal over three player operations, exact statevector) |
| 1 outcome of 36 (on the card screen) | run `hype-all-36-*` (one shot on Aer) |
| 100 Qredits (join screen) | `orchestrator.join()` |
| 2021 | Qraps repository (Quantum Game Jam 2021) |
