"""Art director: fal.ai images (generated once at build time, cached under assets/) with built-in SVG art as the fallback.
Never calls fal.ai at request time."""
import config
from pathlib import Path

ASSETS = config.ROOT / "assets"

FELT_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 400'><rect width='800' height='400' fill='#0f5a36'/>
<rect x='20' y='20' width='760' height='360' rx='18' fill='none' stroke='#e8d9a0' stroke-width='4'/>
<text x='400' y='120' fill='#e8d9a0' font-size='40' text-anchor='middle' font-family='serif'>PASS LINE</text>
<text x='400' y='290' fill='#e8d9a0' font-size='28' text-anchor='middle' font-family='serif'>FIELD  2 3 4 9 10 11 12</text></svg>"""
CHIP_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 200'><rect width='400' height='200' fill='#0b1d3a'/>
<g stroke='#4aa3ff' stroke-width='2' fill='none'><path d='M20 100h60l30-40h60l30 40h60l30-40h60l30 40h40'/><circle cx='110' cy='60' r='6'/><circle cx='200' cy='60' r='6'/></g></svg>"""


def ensure_assets() -> dict:
    ASSETS.mkdir(exist_ok=True)
    out = {}
    for name, svg in (("felt.svg", FELT_SVG), ("chip.svg", CHIP_SVG)):
        p = ASSETS / name
        if not p.exists():
            p.write_text(svg)
        out[name] = "built-in SVG art"
    for f in ASSETS.glob("fal_*.png"):
        out[f.name] = "fal.ai (cached)"
    return out


def source() -> str:
    return "fal.ai (cached images)" if list(ASSETS.glob("fal_*.png")) else "built-in SVG art"
