"""Build the header button images from docs/visit itch io.svg.

    python tools/make_itch_button.py

The artwork stays white on a coral button, because the itch.io press kit asks
that the logo stays black or white. Edge renders the SVG, since no SVG library
is a dependency. Only needed again if the artwork or button colours change.
"""

import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "docs" / "visit itch io.svg"
ASSETS = ROOT / "assets"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

BUTTON_SIZE = (272, 76)
ART_HEIGHT = 50
RENDER_SCALE = 4
BUTTON_COLOR = "#EC4A4A"
HOVER_COLOR = "#D6293E"


def render_art_mask(height):
    """White artwork as a greyscale mask, height pixels tall, supersampled for clean edges."""
    with tempfile.TemporaryDirectory() as folder:
        page = Path(folder) / "art.html"
        shot = Path(folder) / "art.png"
        svg = SVG.read_text(encoding="utf-8")
        tall = height * RENDER_SCALE
        page.write_text(
            f'<!doctype html><body style="margin:0;background:#000"><div style="height:{tall}px;width:max-content">'
            f'<style>svg{{height:{tall}px;width:auto;display:block}}</style>{svg}</div></body>',
            encoding="utf-8",
        )
        subprocess.run(
            [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={folder}\\profile",
             f"--window-size=2000,{tall + 100}", f"--screenshot={shot}", page.as_uri()],
            check=True, capture_output=True,
        )
        mask = Image.open(shot).convert("L")
        mask = mask.crop(mask.getbbox()).copy()
    scale = height / mask.height
    return mask.resize((round(mask.width * scale), height), Image.LANCZOS)


def make_button(mask, color, path):
    button = Image.new("RGB", BUTTON_SIZE, color)
    x, y = (BUTTON_SIZE[0] - mask.width) // 2, (BUTTON_SIZE[1] - mask.height) // 2
    button.paste("#FFFFFF", (x, y), mask)
    button.save(path, optimize=True)


def main():
    mask = render_art_mask(ART_HEIGHT)
    if mask.width > BUTTON_SIZE[0] - 24:
        raise SystemExit(f"Artwork is {mask.width}px wide and will not fit the button")
    make_button(mask, BUTTON_COLOR, ASSETS / "visit_itch_button.png")
    make_button(mask, HOVER_COLOR, ASSETS / "visit_itch_button_hover.png")
    print("Wrote button images, artwork", mask.size)


if __name__ == "__main__":
    main()
