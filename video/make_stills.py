"""Original abstract stills for the explainer (PIL only): a die half in shadow, two dice joined by a thread, branching paths,
a real-vs-simulated card read from HACKATHON.md, credits and the end card with the join QR."""
import math
import random
import re
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "video" / "stills"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1920, 1080
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BG = (14, 17, 22)
random.seed(7)


def canvas():
    im = Image.new("RGB", (W, H), BG)
    return im, ImageDraw.Draw(im)


def die(d, cx, cy, s, face, fill=(250, 250, 250), pip=(17, 17, 17)):
    d.rounded_rectangle([cx - s, cy - s, cx + s, cy + s], radius=s * 0.18, fill=fill)
    pips = {1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8]}[face]
    for i in pips:
        x = cx + ((i % 3) - 1) * s * 0.55
        y = cy + ((i // 3) - 1) * s * 0.55
        d.ellipse([x - s * 0.11, y - s * 0.11, x + s * 0.11, y + s * 0.11], fill=pip)


def cat():
    im, d = canvas()
    die(d, 960, 520, 220, 5)
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    sd.rectangle([960, 0, W, H], fill=(14, 17, 22, 215))
    im.paste(Image.alpha_composite(im.convert("RGBA"), shade).convert("RGB"))
    d = ImageDraw.Draw(im)
    for i in range(6):
        d.text((1120 + 40 * (i % 2), 340 + 60 * i), "?", font=ImageFont.truetype(FONTB, 64), fill=(74, 163, 255))
    im.save(OUT / "still_cat.png")


def thread():
    im, d = canvas()
    die(d, 520, 540, 170, 3); die(d, 1400, 540, 170, 3)
    for k in range(40):
        y = 540 + 18 * math.sin(k / 3.0)
        x0 = 690 + k * 13.5
        d.line([x0, y, x0 + 14, 540 + 18 * math.sin((k + 1) / 3.0)], fill=(74, 163, 255), width=6)
    im.save(OUT / "still_thread.png")


def branches():
    im, d = canvas()

    def grow(x, y, ang, depth, w):
        if depth == 0:
            return
        L = 150 * (0.8 ** (6 - depth))
        x2, y2 = x + L * math.cos(ang), y - L * math.sin(ang)
        d.line([x, y, x2, y2], fill=(74 + 20 * depth, 163, 255 - 20 * depth), width=w)
        for da in (-0.5, 0.5):
            grow(x2, y2, ang + da + random.uniform(-0.15, 0.15), depth - 1, max(1, w - 2))
    grow(960, 1000, math.pi / 2, 7, 14)
    die(d, 960, 1000, 60, 1)
    im.save(OUT / "still_branches.png")


def textcard(name, title, lines, size=40):
    im, d = canvas()
    d.text((120, 110), title, font=ImageFont.truetype(FONTB, 72), fill=(233, 238, 245))
    y = 250
    for ln in lines:
        d.text((140, y), ln, font=ImageFont.truetype(FONT, size), fill=(200, 210, 225))
        y += size + 22
    im.save(OUT / name)


def real_vs_sim():
    txt = (ROOT / "HACKATHON.md").read_text()
    sec = txt.split("## Faked or mocked")[1].split("## ")[0]
    items = [re.sub(r"\*\*|`", "", l.strip("- ").split(":")[0]) for l in sec.splitlines() if l.startswith("- ")]
    real = ["Circuits + exact odds", "Verifier (code)", "Aer emulator runs (29 qubits)", "Beacon + verify_beacon.py", "Quantum Time Gatekeeper on ADAP's engine"]
    lines = ["REAL in this build:"] + ["  • " + r for r in real] + ["", "SIMULATED or mocked (from HACKATHON.md):"] + ["  • " + i for i in items[:9]]
    textcard("still_realvsim.png", "What is real today, what is simulated", lines, 36)


def credits():
    textcard("still_credits.png", "Credits", [
        "Qraps dice modes: the original Qraps, Quantum Game Jam 2021 (SuperStingray/qraps)",
        "Quantum Time Gatekeeper: powered by ADAP's policy engine (Hardalion, Apache-2.0)",
        "Engines: Qiskit Aer; chip map from qiskit-ibm-runtime's fake backend",
        "Three.js for the 3D table",
        "",
        "This project was made the way the game works:",
        "a person's ideas, agents doing the building, and checks deciding what stayed.",
    ], 38)


def end(qr_path):
    im, d = canvas()
    d.text((120, 160), "Narration and images AI-generated.", font=ImageFont.truetype(FONTB, 60), fill=(233, 238, 245))
    d.text((120, 250), "Results from real runs; ids in the repo.", font=ImageFont.truetype(FONTB, 60), fill=(233, 238, 245))
    d.text((120, 420), "Join the table: scan, pick a nickname, 100 Qredits (play credits, no cash value).", font=ImageFont.truetype(FONT, 40), fill=(200, 210, 225))
    if qr_path and Path(qr_path).exists():
        q = Image.open(qr_path).convert("RGB").resize((420, 420))
        im.paste(q, (1380, 560))
    im.save(OUT / "still_end.png")


if __name__ == "__main__":
    cat(); thread(); branches(); real_vs_sim(); credits(); end(sys.argv[1] if len(sys.argv) > 1 else None)
    print("stills:", sorted(p.name for p in OUT.iterdir()))
