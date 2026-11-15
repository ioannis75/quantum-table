"""Assemble video/quantum_table.mp4 (≤180 s, 1080p) from Playwright footage + stills, with fal.ai (Kokoro) voice-over when
FAL_KEY is set, burned-in captions either way, silence otherwise. Then check duration, audio/captions, three non-black frames."""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

V = config.ROOT / "video"
RAW, STILLS, WORK = V / "raw", V / "stills", V / "work"
WORK.mkdir(exist_ok=True)
FONT = "DejaVu Sans"

# (caption, source, kind, start-offset into source for clips)
SCRIPT = [
    ("Quantum Table. A craps game where AI agents design the dice and nobody at the table controls the roll alone.", "seg_hook", "clip", 0),
    ("Who checks the AI? The experiment. A verifier made of code, not a model, checks every roll.", "seg_hook", "clip", 7),
    ("Every roll is published. Anyone can recompute it. Don't trust us; check it.", "seg_hook", "clip", 14),
    ("Superposition: before the roll each die is a mix of all six faces. Six faces, three qubits per die.", "seg_resources", "clip", 0),
    ("Entanglement: your dice and the house's agree without either being fixed in advance. Each qubit's arrow shrinks: alone, it has no state of its own.", "seg_resources", "clip", 6),
    ("Measurement: looking gives one answer, and the pair falls apart. One roll, one outcome.", "seg_resources", "clip", 14),
    ("The fourth resource is classical memory. Exact simulation doubles per qubit. On this machine the emulator ran 29 qubits and was refused at 30. Then a chip takes over.", "seg_resources", "clip", 23),
    ("Hype or Fact. The AI host deals a claim. Players bet Qredits, play credits with no cash value.", "seg_hype", "clip", 0),
    ("The experiment: the player does three different things to their dice. The house's own distribution changes by four times ten to the minus sixteen. Nothing.", "seg_hype", "clip", 12),
    ("Verdict: Hype. Correlation is not communication. The verifier decided, not the host.", "seg_hype", "clip", 22),
    ("Schrödinger's cat is really a question: where does one outcome come from, when the equations keep every branch?", "still_cat", "still", 0),
    ("Spooky action: the dice agree instantly, yet no message passes. You only see the agreement when you compare notes.", "still_thread", "still", 0),
    ("Many worlds reads the same equations as every outcome happening in a branch. Copenhagen-style readings stop at the measurement. Pilot-wave readings add hidden positions. They are interpretations: all predict the same dice statistics, so this table cannot tell you which is right. Physicists disagree.", "still_branches", "still", 0),
    ("What is real today: the circuits, the verifier, the Aer emulator runs, the beacon, the ADAP policy gate. What is simulated: the chip, a fake backend. Everything in this video ran on an emulator; nothing ran on a quantum chip.", "still_realvsim", "still", 0),
    ("Qraps modes from the Quantum Game Jam 2021 game. Gatekeeper on ADAP's policy engine. Built by a person's ideas, agents doing the building, and checks deciding what stayed.", "still_credits", "still", 0),
    ("Narration and images AI-generated. Results from real runs; ids in the repo.", "still_end", "still", 0),
]
MIN_SEC = 5.0


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])
    return r.stdout


def dur(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).strip())


def srt_time(t):
    h, m = divmod(t, 3600); m, s = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"


def wrap(text, n=60):
    out, line = [], ""
    for w in text.split():
        if len(line) + len(w) + 1 > n:
            out.append(line); line = w
        else:
            line = (line + " " + w).strip()
    return "\n".join(out + [line])


def main():
    voice = config.has("FAL_KEY") and "--novoice" not in sys.argv
    audios, lens = [], []
    if voice:
        from agents import fal_client
        for i, (text, *_rest) in enumerate(SCRIPT):
            wav = WORK / f"vo_{i:02d}.wav"
            if not wav.exists():
                fal_client.tts(text, wav)
            audios.append(wav)
    for i, (text, *_rest) in enumerate(SCRIPT):
        L = dur(audios[i]) + 0.6 if voice else max(MIN_SEC, 0.35 * len(text.split()) + 1.5)
        lens.append(max(MIN_SEC if not voice else 3.0, L))
    total = sum(lens)
    if total > 178:
        k = 178 / total
        lens = [l * k for l in lens]
    # build segments
    segs = []
    for i, ((text, src, kind, off), L) in enumerate(zip(SCRIPT, lens)):
        out = WORK / f"seg_{i:02d}.mp4"
        if kind == "clip":
            srcp = RAW / f"{src}.webm"
            srcd = dur(srcp) if srcp.exists() else 0
            if srcp.exists() and srcd > off + 1:
                ss = min(off, max(0, srcd - L))
                vf = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"
                cmd = ["ffmpeg", "-y", "-ss", f"{ss:.2f}", "-i", str(srcp), "-t", f"{L:.2f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)]
                # loop short footage if the source has less than L left
                if srcd - ss < L:
                    cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-ss", f"{ss:.2f}", "-i", str(srcp), "-t", f"{L:.2f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)]
                run(cmd)
            else:
                kind, src = "still", "still_realvsim"   # fallback: render as a still
        if kind == "still":
            img = STILLS / f"{src}.png"
            if not img.exists():
                img = STILLS / f"{src}.jpg"
            run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-t", f"{L:.2f}", "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)])
        segs.append(out)
    (WORK / "list.txt").write_text("".join(f"file '{s}'\n" for s in segs))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(WORK / "list.txt"), "-c", "copy", str(WORK / "video_noaudio.mp4")])
    # captions
    t = 0.0
    srt = []
    for i, ((text, *_r), L) in enumerate(zip(SCRIPT, lens)):
        srt.append(f"{i+1}\n{srt_time(t + 0.1)} --> {srt_time(t + L - 0.1)}\n{wrap(text)}\n")
        t += L
    (V / "captions.srt").write_text("\n".join(srt))
    # audio track: concatenated voice padded to each segment length, or silence
    if voice:
        parts = []
        for i, (a, L) in enumerate(zip(audios, lens)):
            p = WORK / f"a_{i:02d}.wav"
            run(["ffmpeg", "-y", "-i", str(a), "-af", f"apad=whole_dur={L:.3f}", "-t", f"{L:.3f}", "-ar", "44100", "-ac", "1", str(p)])
            parts.append(p)
        (WORK / "alist.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(WORK / "alist.txt"), "-c", "copy", str(WORK / "voice.wav")])
        audio_in = ["-i", str(WORK / "voice.wav")]
    else:
        audio_in = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
    sub = str(V / "captions.srt").replace(":", r"\:")
    run(["ffmpeg", "-y", "-i", str(WORK / "video_noaudio.mp4"), *audio_in, "-vf",
         f"subtitles='{sub}':force_style='FontName={FONT},FontSize=20,PrimaryColour=&H00FFFFFF,BackColour=&H90000000,BorderStyle=4,Outline=0,Shadow=0,MarginV=40'",
         "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", str(V / "quantum_table.mp4")])
    # checks
    final = V / "quantum_table.mp4"
    D = dur(final)
    streams = run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(final)])
    frames = {}
    for tag, frac in (("10", 0.1), ("50", 0.5), ("90", 0.9)):
        fp = V / f"frame_{tag}.png"
        run(["ffmpeg", "-y", "-ss", f"{D*frac:.2f}", "-i", str(final), "-frames:v", "1", str(fp)])
        from PIL import Image
        import numpy as np
        frames[tag] = float(np.asarray(Image.open(fp).convert("L")).mean())
    report = {"duration_s": round(D, 2), "ok_duration": D <= 180, "streams": streams.split(), "voice": voice,
              "captions": "burned-in (video/captions.srt)", "frame_mean_brightness": frames, "ok_not_black": all(v > 8 for v in frames.values()),
              "segment_lengths": [round(l, 2) for l in lens]}
    (V / "CHECK.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
