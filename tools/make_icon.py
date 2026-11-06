"""Build assets/icon.ico from the master art at promo/icon_og.jpg.

    python tools/make_icon.py

The art has a plain white background. It is removed by flood fill from the
corners, so white areas inside the icon, like the arrow, stay opaque.
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "promo" / "icon_og.jpg"
ICON = ROOT / "assets" / "icon.ico"
TRANSPARENT = ROOT / "promo" / "icon_transparent.png"
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
FILL_TOLERANCE = 40
MARGIN_FRACTION = 0.03


def remove_background(image):
    rgb = image.convert("RGB")
    width, height = rgb.size
    marker = (255, 0, 255)
    for corner in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        ImageDraw.floodfill(rgb, corner, marker, thresh=FILL_TOLERANCE)
    mask = rgb.point(lambda _: 255).convert("L")
    pixels_in, pixels_mask = rgb.load(), mask.load()
    for y in range(height):
        for x in range(width):
            if pixels_in[x, y] == marker:
                pixels_mask[x, y] = 0
    result = image.convert("RGBA")
    result.putalpha(mask)
    return result


def square_crop(image):
    box = image.getchannel("A").getbbox()
    cropped = image.crop(box)
    side = int(max(cropped.size) * (1 + 2 * MARGIN_FRACTION))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2), cropped)
    return canvas


def main():
    art = square_crop(remove_background(Image.open(MASTER)))
    art.save(TRANSPARENT)
    ICON.parent.mkdir(parents=True, exist_ok=True)
    art.resize((256, 256), Image.LANCZOS).save(ICON, format="ICO", sizes=ICON_SIZES)
    print(f"Wrote {ICON} and {TRANSPARENT}")


if __name__ == "__main__":
    main()
