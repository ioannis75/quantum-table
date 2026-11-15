# How this was made

One page, from records only: `MAKING_OF_NOTES.md` (the planning conversation, Sat evening to Sun 03:43 Athens), the git log of this repository, the "Cut" and "Faked or mocked" lists in `HACKATHON.md`, and the counters the build produced.

## What the human brought

The leaps. The notes record a person moving the idea in steps: a quantum question with a checker (Sat evening); players buying chip positions and entangling dice with the house (02:20); "simulate my old game Qraps" (02:30); a multi-agent studio with no human in the code loop (02:50); "tokens should be called Qredits" (03:00); the mentor's ADAP project as a gate before spending QPU time (03:05); players in the room via QR and Discord (03:10); a science communicator with paradoxes and less hype (03:22); an autonomous, enthusiastic host (03:26); 3D Bloch-sphere dice on an old-school table (03:30); quantum logic for the Oumi agent (03:39); monetising through the Gatekeeper (03:40); and the closing idea, "collective verified randomness, for people and agents" (03:43). During the build the same person supplied the fal.ai, Oumi and Claude keys at 04:20–04:28 and said: no real QPU for the demo.

One concrete example: the "Hype or Fact" round exists because the human asked at 03:22 for the scientific method inside the game. The AI team turned that into a card format where the experiment, not any agent, gives the verdict.

## What the agents brought

Structure, checks and limits. In planning: commit-reveal for sealed choices (02:20), a general platform with Qraps as its test (02:30), fallbacks for every missing key (02:50), the Gatekeeper's seven rules tested against ADAP's engine (03:05), banned hype phrases for the video and the host (03:22–03:26), arrows computed from the real state (03:30), the quantum-logic kit evaluated by code (03:39), a Financial agent that can quote but is blocked from charging (03:40), and the narrowed wording "collectively generated, publicly checkable" (03:43).

In the build (git log, 03:58 → 04:29 Athens): verifier and sandbox first; the five Qraps modes transcribed from `EntangledDice.cs` and prepared exactly; the burn-down measured rather than estimated (29 qubits ran, 30 refused); the ADAP engine built and all 17 policy cases passed; the beacon with a standard-library verifier; the 3D table verified headlessly before being made the default.

One concrete example: the Q-Scientist on Claude Sonnet wrote the Fermionic-mode circuit at 04:27; it ran only inside the sandbox, and the verifier's exact check passed it before it reached the table.

## Where each corrected the other

- **Human overruling the agents**: at 02:37 the human removed the SpinQ machine and the teaching steps the AI had planned; at 03:39 the human removed the second emulator (Pagonis) that an earlier plan had centred on. The build followed the shorter plan.
- **Agents narrowing the human**: the "buy positions on a chip" idea (02:20) became a Qredits-only buy-in with no payments; "monetise" (03:40) became shadow invoices; "verified randomness" (03:43) became "collectively generated, publicly checkable", never "certified".
- **Checks correcting the agents**: the Host's own template for the quantum vote contained a banned phrase ("no quantum advantage claimed") and was caught by the line checker during testing and reworded. The built-in Gatekeeper port initially allowed a job with a missing estimate; the test against ADAP's engine showed BLOCK, and the port was fixed.
- **Checks correcting the human's expectation**: the brief assumed the Oumi agent would answer; the API reported no deployed model in the project, so the documented fallback ran and the screen says which model answered.

## Counters at the end of the build

| Counter | Value |
|---|---|
| Hype or Fact experiments run | 6 (seed deck: 4 Fact, 2 Hype) |
| AI-written claim cards overturned | 0 of 0 dealt (model cards appear from the third deal with a key present) |
| Host lines corrected by the checker | 0 (model lines so far) + 1 template reworded during tests |
| Logic designer corrections by enumeration | 0 |
| Gatekeeper decisions | 23 ALLOW, 2 BLOCK, 0 REQUIRE_HUMAN pending |
| Beacon rounds published | 11 |
| Real QPU seconds used | 0 |

No agent in this record "understood" or "realised" anything; these are the events as logged.
