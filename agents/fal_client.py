"""fal.ai access for the Art director (images, at most 6, cached under assets/) and the Science communicator's voice-over
(stock synthetic voice, no cloning). Called only at build time, never at request time. Key read here only; never logged."""
import json
import os
import time
from pathlib import Path

import httpx

import config

IMAGE_MODEL = "fal-ai/flux/schnell"          # checked on 15 Nov 2026: answers at https://fal.run/fal-ai/flux/schnell
TTS_MODEL = "fal-ai/kokoro/american-english"  # stock voices (af_heart etc.), not a cloning model
ASSETS = config.ROOT / "assets"
VOICE = "af_heart"


def available() -> bool:
    return config.has("FAL_KEY")


def _call(model: str, payload: dict, timeout: float = 120) -> dict:
    r = httpx.post(f"https://fal.run/{model}", json=payload, timeout=timeout,
                   headers={"Authorization": "Key " + os.environ["FAL_KEY"], "content-type": "application/json"})
    r.raise_for_status()
    return r.json()


def _download(url: str, dest: Path) -> Path:
    with httpx.stream("GET", url, timeout=60, follow_redirects=True) as r:
        r.raise_for_status()
        dest.write_bytes(b"".join(r.iter_bytes()))
    return dest


ART_PROMPTS = {
    "fal_felt": "top-down view of an original dark green casino felt texture with cream chalk lines, abstract, no text, no logos, no people, flat illustration",
    "fal_dice": "a set of white six-sided dice with black pips on dark green felt, soft studio light, original design, no text, no logos, no people",
    "fal_chip": "abstract illustration of a quantum processor: a hexagonal lattice of glowing blue nodes on deep navy, no text, no logos, no people",
}


def make_art(max_images: int = 6) -> dict:
    """Generates the table art once; files cached in assets/. Returns {name: path}. Never more than max_images."""
    ASSETS.mkdir(exist_ok=True)
    out = {}
    made = 0
    for name, prompt in ART_PROMPTS.items():
        dest = ASSETS / f"{name}.jpg"
        if dest.exists():
            out[name] = str(dest)
            continue
        if made >= max_images or not available():
            continue
        res = _call(IMAGE_MODEL, {"prompt": prompt, "image_size": "landscape_16_9", "num_images": 1, "seed": 2026})
        _download(res["images"][0]["url"], dest)
        made += 1
        out[name] = str(dest)
    (ASSETS / "fal_log.json").write_text(json.dumps({"model": IMAGE_MODEL, "generated": list(out), "date": time.strftime("%Y-%m-%d")}, indent=1))
    return out


def tts(text: str, dest: Path, voice: str = VOICE) -> Path:
    res = _call(TTS_MODEL, {"prompt": text, "voice": voice}, timeout=180)
    return _download(res["audio"]["url"], dest)


def make_video_stills(prompts: dict, dest_dir: Path, max_images: int = 8) -> dict:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for i, (name, prompt) in enumerate(prompts.items()):
        if i >= max_images:
            break
        dest = dest_dir / f"{name}.jpg"
        if not dest.exists():
            res = _call(IMAGE_MODEL, {"prompt": prompt + ", original abstract art, no people, no characters, no logos, no text", "image_size": "landscape_16_9", "num_images": 1, "seed": 100 + i})
            _download(res["images"][0]["url"], dest)
        out[name] = str(dest)
    return out
