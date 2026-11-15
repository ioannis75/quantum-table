# Quantum Table: new ideas (NOTES ONLY, not implemented)

Source: handoff brief (Sun 15 Nov 2026). Feature freeze 14:00, submission 18:00. Extension to the existing build, not a replacement.

## Idea
Two players sign something; each entangles with the house, so the house is a third party in the shared state. Three-party
Byzantine agreement: any one of three could lie. Entanglement plus the verifier's correlation check lets honest parties detect
an inconsistent report. Separately, each player and the house derive a shared secret key (BB84 or E91 style) which replaces the
random secret in the beacon commit-reveal. Qredits stay play tickets with no cash value.

## Part 1: Byzantine agreement with the house as third party
- Anchor literature (verify before quoting): Fitzi, Gisin, Maurer, PRL 87, 217901 (2001), arXiv quant-ph/0107127 (three-qutrit
  singlet, detectable Byzantine agreement); arXiv 0710.0290 (four-qubit version, liar detection); arXiv quant-ph/0507249
  (continuous-variable; W states as a discrete option); arXiv 2206.09159 (beating the fault-tolerance bound).
- Correction: build the three-qutrit singlet, not a plain GHZ.
- Fit with the dice: a qutrit is a 3-sided die; qudits avoid the rejected states of a 3-qubit die register. Prepare the singlet
  exactly on a qubit encoding (2 qubits per qutrit, unused level at zero amplitude) and check the exact distribution against theory.
- Verifier: exact vs statevector to 1e-9; chi-square p > 0.01 plus TVD on shots; singlet rule (same basis for all three means
  three different outcomes); commit-reveal hashes over all three parties.

## Part 2: key exchange on the table
- BB84 style: random bases, compare publicly, keep matching bits, sample to estimate error, abort above a threshold.
- E91 style: shared entangled pairs, matching-basis bits form the key, mismatched-basis runs give a CHSH test (reuse the CHSH
  verifier); say "above 2" only if S minus 2 sigma is above 2.
- Key replaces the random 32-byte secret in the beacon commit-reveal.
- Lab link: the Thorlabs BB84 laser QKD kit could be shown beside the emulated version.

## Honest limits (must be in the pitch)
- Emulator has no eavesdropper physics: a playful demonstration, not real key distribution.
- Illustration of detectable agreement, not a contract-signing system or an unforgeable signature; the house still sees
  everything classically.
- Allowed words: consistent with theory at the stated threshold, correlated as required, collectively generated, publicly
  checkable. Not allowed: certified random, proves, unhackable, quantum advantage, tamper-proof.
- Label every result with its engine (Aer emulator, Simulated chip, or IBM backend plus job ID).

## Build order if time allows (cut from the bottom, record cuts in HACKATHON.md)
1. Three-qutrit singlet circuit, exact distribution, verifier tests on Aer.
2. Table event "three-party agreement round": two players plus the house, correlation rule checked, badge, Host comments.
3. BB84 or E91 exchange between a player and the house, with error-rate or CHSH check.
4. Feed the derived key into the beacon commit-reveal.
5. One Hype or Fact card: "a quantum state alone lets two parties sign a contract no one can dispute" (expected verdict: Hype).

## Also noted today (not implemented)
- Front-page redesign already built and pushed (commit 79739b1): gameplay only, chip game with hearts, per-roll circuit, one
  shot; old page moved to /lab.
