# Storyboard

Footage is recorded from the real page with headless Playwright (software WebGL, 1280×720, scaled to 1080p). Stills are original abstract art drawn with PIL (`video/make_stills.py`): no people, no characters, no logos. No music; silence.

| Segment | Source | Seconds | Content |
|---|---|---|---|
| A hook | Playwright `seg_hook.webm` | 20 | `/?view=3d` fresh table → click Roll → tumble → land → badge; cut to `/beacon/latest` JSON and a terminal-style card "verify_beacon.py → PASS". |
| B resources | Playwright `seg_resources.webm` | 45 | Prepared Bloch arrows → Join (nickname "Guest") → thread glows, arrows shrink → Roll → land → arrows snap. Then scroll to the burn-down card → Skip ahead → "Emulator burned down at 30 qubits". |
| C hype | Playwright `seg_hype.webm` | 45 | Deal the no-signalling card → bet Hype → Run the experiment → verdict HYPE with the 4.2e-16 line. |
| D paradoxes | stills `still_cat.png`, `still_thread.png`, `still_branches.png` | 40 | Three stills, 13 s each, Ken-Burns-free (static), captions carry the words. |
| E real vs simulated + credits + end card | still `still_realvsim.png` (rendered from HACKATHON.md's list), `still_credits.png`, `still_end.png` with the QR | 30 | Text cards. |

Captions: `video/captions.srt`, burned in with libass (DejaVu Sans, bottom third, dark box). End card text: "Narration and images AI-generated. Results from real runs; ids in the repo."

Checks after render (`video/check.sh`): duration ≤ 180 s, captions present (SRT burned; audio stream absent is acceptable in this keyless build), three frames extracted at 10 %, 50 %, 90 % and checked non-black.
