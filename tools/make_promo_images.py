"""Generate the store images from promo/cover_art.jpg.

    python tools/make_promo_images.py

Writes promo/thumbnail_630x500.jpg and promo/cover_1280x720.jpg, and frames any
promo/raw_*.png window captures as 16:9 screenshots. Edit the copy below to
change the wording. Pricing must not be mentioned here: the owner decides that.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PROMO = ROOT / "promo"
ART = PROMO / "cover_art.jpg"
FONT_BOLD = str(ROOT / "assets" / "fonts" / "Lato-Bold.ttf")

INK = "#222222"
PAPER = "#FFFFFF"
CRIMSON = "#D6293E"

THUMB_LINES = [("BACKUPPER", PAPER, 0.92), ("for itch.io", "#FFD9D9", 0.62)]
THUMB_TAGLINE = "Backup your own author pages"

COVER_LINES = [("BACKUPPER", PAPER, 0.50), ("for itch.io", "#FFD9D9", 0.34)]
COVER_POINTS = ["Every project page", "Every devlog", "Every image", "Browsable offline"]

THUMB_BAND_HEIGHT = 92
JPEG_QUALITY = 88


def fit_font(draw, text, max_width, max_height):
    """Largest font where text fits. Glyph widths are measured, never assumed."""
    size = 8
    while True:
        font = ImageFont.truetype(FONT_BOLD, size + 2)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] > max_width or box[3] - box[1] > max_height:
            return ImageFont.truetype(FONT_BOLD, size)
        size += 2


def cover_crop(image, size):
    width, height = size
    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left = resized.width - width  # Keep the right side, where the vault is.
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def darken(image, strength_left, strength_right, hold=0.0, fade_end=1.0):
    """A dark wash so light text stays readable over busy art.

    Stays at strength_left up to the hold fraction of the width, then fades to
    strength_right by fade_end, so all the text can sit on the strong part.
    """
    width, height = image.size
    mask = Image.new("L", (width, 1))
    for x in range(width):
        position = x / max(width - 1, 1)
        t = min(max((position - hold) / (fade_end - hold), 0.0), 1.0)
        mask.putpixel((x, 0), round(255 * (strength_left + (strength_right - strength_left) * t)))
    mask = mask.resize((width, height))
    overlay = Image.new("RGB", image.size, (20, 14, 18))
    return Image.composite(overlay, image.convert("RGB"), mask)


def draw_text(image, position, text, font, fill, shadow=7):
    x, y = position
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.text((x, y), text, font=font, fill=(0, 0, 0, 255), stroke_width=shadow // 2, stroke_fill=(0, 0, 0, 255))
    blurred = layer.filter(ImageFilter.GaussianBlur(shadow))
    image.paste(blurred, (0, 0), blurred)
    ImageDraw.Draw(image).text((x, y), text, font=font, fill=fill, stroke_width=2, stroke_fill=(20, 14, 18))


def text_height(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[3] - box[1], box[1]


def make_thumbnail():
    size = (630, 500)
    image = darken(cover_crop(Image.open(ART).convert("RGB"), size), 0.86, 0.66)
    draw = ImageDraw.Draw(image)
    margin = 26
    y = 26
    for text, color, share in THUMB_LINES:
        font = fit_font(draw, text, int((size[0] - 2 * margin) * share), 130)
        height, offset = text_height(draw, text, font)
        draw_text(image, (margin, y - offset), text, font, color)
        y += height + 18

    band_top = size[1] - THUMB_BAND_HEIGHT
    draw.rectangle((0, band_top, size[0], size[1]), fill=CRIMSON)
    font = fit_font(draw, THUMB_TAGLINE, size[0] - 2 * margin, THUMB_BAND_HEIGHT - 36)
    # Centred on the measured ink, since a font's line box is not symmetrical around its glyphs.
    left, top, right, bottom = draw.textbbox((0, 0), THUMB_TAGLINE, font=font)
    x = (size[0] - (right - left)) // 2 - left
    y = band_top + (THUMB_BAND_HEIGHT - (bottom - top)) // 2 - top
    draw.text((x, y), THUMB_TAGLINE, font=font, fill=PAPER)
    image.save(PROMO / "thumbnail_630x500.jpg", quality=JPEG_QUALITY, optimize=True)


def make_cover():
    size = (1280, 720)
    image = darken(cover_crop(Image.open(ART).convert("RGB"), size), 0.88, 0.12, hold=0.50, fade_end=0.82)
    draw = ImageDraw.Draw(image)
    margin = 52
    y = 56
    for text, color, share in COVER_LINES:
        font = fit_font(draw, text, int(size[0] * share), 150)
        height, offset = text_height(draw, text, font)
        draw_text(image, (margin, y - offset), text, font, color)
        y += height + 24

    y += 26
    font = fit_font(draw, max(COVER_POINTS, key=len), int(size[0] * 0.36), 60)
    # Measured on fixed glyphs: lines without descenders would otherwise shift their marker.
    height, offset = text_height(draw, "Ey", font)
    square = height // 2
    for point in COVER_POINTS:
        top = y + (height - square) // 2
        draw.rectangle((margin, top, margin + square, top + square), fill="#FA5C5C")
        draw_text(image, (margin + square + 20, y - offset), point, font, PAPER, shadow=5)
        y += height + 26
    image.save(PROMO / "cover_1280x720.jpg", quality=JPEG_QUALITY, optimize=True)


def frame_screenshots():
    """Fit each raw capture on a 16:9 canvas, shadowed, without cropping any of it."""
    canvas_size = (1600, 900)
    margin = 40
    for number, path in enumerate(sorted(PROMO.glob("raw_*.png")), start=1):
        canvas = Image.new("RGB", canvas_size, "#F4F4F4")
        ImageDraw.Draw(canvas).rectangle((0, 0, canvas_size[0], 10), fill="#FA5C5C")
        shot = Image.open(path).convert("RGB")
        scale = min((canvas_size[0] - 2 * margin) / shot.width, (canvas_size[1] - 2 * margin - 10) / shot.height)
        shot = shot.resize((round(shot.width * scale), round(shot.height * scale)), Image.LANCZOS)
        x, y = (canvas_size[0] - shot.width) // 2, 10 + (canvas_size[1] - 10 - shot.height) // 2
        shadow = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rectangle((x + 4, y + 6, x + shot.width + 4, y + shot.height + 6), fill=(0, 0, 0, 90))
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))
        canvas.paste(shadow, (0, 0), shadow)
        canvas.paste(shot, (x, y))
        canvas.save(PROMO / f"screenshot_{number}.png", optimize=True)


def main():
    make_thumbnail()
    make_cover()
    frame_screenshots()
    print("Wrote store images to", PROMO)


if __name__ == "__main__":
    main()
