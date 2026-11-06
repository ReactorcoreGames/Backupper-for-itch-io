"""Render the YouTube trailer and its text-only thumbnail.

    python tools/make_trailer.py                  Render both
    python tools/make_trailer.py --thumbnail      Thumbnail only
    python tools/make_trailer.py --sheet out.png  Contact sheet of still frames, for checking

Writes trailer/backupper_trailer_1080p.mp4 and trailer/youtube_thumbnail.png.
Every scene starts on a beat of the music, so the timing below is in beats.
Each frame is a pure function of its time, which is what lets --sheet jump
straight to any moment without rendering the frames before it.
"""

import argparse
import math
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PROMO = ROOT / "promo"
TRAILER = ROOT / "trailer"
MUSIC = TRAILER / "Guiton Sketch - Kevin MacLeod.mp3"
OUTPUT = TRAILER / "backupper_trailer_1080p.mp4"
THUMBNAIL = TRAILER / "youtube_thumbnail.png"
FONT_BOLD = str(ROOT / "assets" / "fonts" / "Lato-Bold.ttf")
FONT_REGULAR = str(ROOT / "assets" / "fonts" / "Lato-Regular.ttf")

W, H = 1920, 1080
FPS = 60
BEAT = 60 / 113  # Measured from the track's onsets, its sections land on beats 16, 32 and 48.
SECONDS = 34.06

INK = (30, 26, 28)
TEXT_INK = (34, 34, 34)
PAPER = (244, 244, 244)
WHITE = (255, 255, 255)
CORAL = (250, 92, 92)
CRIMSON = (214, 41, 62)
BLUSH = (255, 217, 217)
GREY = (200, 200, 200)

URL = "reactorcore.itch.io/backupper-for-itchio"
CREDIT = "Music: \"Guiton Sketch\" by Kevin MacLeod (incompetech.com), licensed under CC BY 4.0"
MARQUEE = "project pages   devlogs   screenshots   descriptions   images   "


def b(n):
    return n * BEAT


def clamp(value, low=0.0, high=1.0):
    return min(max(value, low), high)


def ease_out(p):
    return 1 - (1 - p) ** 3


def ease_in_out(p):
    return p * p * (3 - 2 * p)


def ease_back(p):
    c = 1.9
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


def blend(a, c, amount):
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, c))


def pulse(t):
    """A small kick on every beat, so text that is holding still keeps moving."""
    since = (t % BEAT) / BEAT
    return 1 + 0.014 * math.exp(-5 * since)


@lru_cache(maxsize=None)
def font_of(size, regular=False):
    return ImageFont.truetype(FONT_REGULAR if regular else FONT_BOLD, size)


@lru_cache(maxsize=None)
def text_sprite(text, size, color, stroke=2, regular=False):
    """Text on transparency. The RGB is solid everywhere so scaling can't fringe the edges."""
    font = font_of(size, regular)
    pad = 8 + stroke
    left, _, right, _ = font.getbbox(text, stroke_width=stroke)
    ascent, descent = font.getmetrics()
    size_px = (right - left + 2 * pad, ascent + descent + 2 * pad)
    mask = Image.new("L", size_px, 0)
    ImageDraw.Draw(mask).text((pad - left, pad), text, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
    sprite = Image.new("RGBA", size_px, color + (0,))
    sprite.putalpha(mask)
    return sprite


def place(frame, sprite, x, y, scale=1.0, alpha=1.0, anchor=(0.5, 0.5)):
    """Draw a sprite with its anchor at (x, y), at subpixel positions so slow moves stay smooth."""
    if alpha <= 0 or scale <= 0:
        return
    ax, ay = sprite.width * anchor[0], sprite.height * anchor[1]
    left = max(math.floor(x - ax * scale) - 1, 0)
    top = max(math.floor(y - ay * scale) - 1, 0)
    right = min(math.ceil(x + (sprite.width - ax) * scale) + 1, frame.width)
    bottom = min(math.ceil(y + (sprite.height - ay) * scale) + 1, frame.height)
    if right <= left or bottom <= top:
        return
    inverse = 1 / scale
    coefficients = (inverse, 0, (left - x) * inverse + ax, 0, inverse, (top - y) * inverse + ay)
    out = sprite.transform((right - left, bottom - top), Image.AFFINE, coefficients, Image.BICUBIC)
    if out.mode != "RGBA":
        frame.paste(out, (left, top))
        return
    if alpha < 1:
        out.putalpha(out.getchannel("A").point(lambda value: round(value * alpha)))
    frame.paste(out, (left, top), out)


def enter(t, start, style):
    """Offset, scale and opacity for a word arriving at time start."""
    since = t - start
    if since < 0:
        return None
    if style == "slam":
        p = clamp(since / 0.2)
        return 0, 0, 1 + 0.9 * (1 - ease_out(p)), clamp(p * 4)
    if style == "pop":
        p = clamp(since / 0.3)
        return 0, 0, 0.5 + 0.5 * ease_back(p), clamp(p * 4)
    p = clamp(since / 0.28)
    distance = (1 - ease_out(p)) * 260
    dx, dy = {"left": (-distance, 0), "right": (distance, 0), "up": (0, distance * 0.4)}[style]
    return dx, dy, 1.0, clamp(p * 3)


def word(frame, text, size, color, x, y, t, start, style="pop", anchor=(0.5, 0.5), alpha=1.0, stroke=2, regular=False):
    state = enter(t, start, style)
    if state is None:
        return
    dx, dy, scale, opacity = state
    place(frame, text_sprite(text, size, color, stroke, regular), x + dx, y + dy, scale * pulse(t), opacity * alpha, anchor)


def word_row(frame, words, size, y, t, style="pop", alpha=1.0):
    """A centred line where each (text, start, color) word arrives on its own."""
    font = font_of(size)
    space = font.getlength(" ")
    widths = [font.getlength(text) for text, _, _ in words]
    x = (W - sum(widths) - space * (len(words) - 1)) / 2
    for (text, start, color), width in zip(words, widths):
        word(frame, text, size, color, x + width / 2, y, t, start, style, alpha=alpha)
        x += width + space


@lru_cache(maxsize=None)
def marquee_strip(color):
    font = font_of(150)
    period = font.getlength(MARQUEE)
    text = MARQUEE * (math.ceil(W / period) + 2)
    return text_sprite(text, 150, color, stroke=0), period


def marquee(frame, t, background, tint, amount=0.045):
    """Faint rows of words drifting behind the type."""
    strip, period = marquee_strip(blend(background, tint, amount))
    for row in range(6):
        travel = (t * (70 + row * 14) + row * 397) % period
        x = -travel if row % 2 else travel - period
        frame.paste(strip, (round(x), row * 182 - 28), strip)


def rounded(size, radius, fill, outline=None, width=0, scale=4):
    """An antialiased rounded rectangle sprite, drawn large and shrunk."""
    big = Image.new("RGBA", (size[0] * scale, size[1] * scale), (fill or outline) + (0,))
    box = (0, 0, big.width - 1, big.height - 1)
    color = fill + (255,) if fill else None
    edge = outline + (255,) if outline else None
    ImageDraw.Draw(big).rounded_rectangle(box, radius * scale, fill=color, outline=edge, width=width * scale)
    return big.resize(size, Image.LANCZOS)


def wipe(frame, t, at, colors):
    """Colour bars sweep across and fully cover the frame at time at, hiding the cut."""
    for index, color in enumerate(colors):
        lead = clamp((t - (at - 0.2 + index * 0.02)) / (0.18 - index * 0.02 - 1 / FPS))
        trail = clamp((t - (at + index * 0.03)) / 0.18)
        if lead > trail:
            box = (round(trail * W), 0, round(ease_in_out(lead) * W) if lead < 1 else W, H)
            if box[2] > box[0]:
                ImageDraw.Draw(frame).rectangle(box, fill=color)


# Scenes. Each paints a whole frame for its beats.


def scene_years(frame, t):
    frame.paste(INK, (0, 0, W, H))
    marquee(frame, t, INK, WHITE)
    if t < b(4):
        word_row(frame, [("Years", b(0), WHITE), ("of", b(1), WHITE), ("work.", b(2), CORAL)], 230, H / 2, t)
        return
    items = ["Descriptions.", "Devlogs.", "Screenshots.", "Themes."]
    for index, text in enumerate(items):
        style = "left" if index % 2 == 0 else "right"
        word(frame, text, 170, WHITE, W / 2, 240 + index * 200, t, b(4 + index), style)


@lru_cache(maxsize=None)
def export_button():
    button = rounded((520, 170), 16, GREY)
    label = text_sprite("Export", 96, (120, 120, 120))
    button.paste(label, ((button.width - label.width) // 2, (button.height - label.height) // 2 - 4), label)
    return button


@lru_cache(maxsize=None)
def strike_mark():
    scale = 4
    size = 300
    big = Image.new("RGBA", (size * scale, size * scale), CORAL + (0,))
    draw = ImageDraw.Draw(big)
    inset = 30 * scale
    far = big.width - inset
    for line in (((inset, inset), (far, far)), ((far, inset), (inset, far))):
        draw.line(line, fill=CORAL + (255,), width=30 * scale)
    return big.resize((size, size), Image.LANCZOS)


def scene_export(frame, t):
    frame.paste(INK, (0, 0, W, H))
    marquee(frame, t, INK, WHITE)
    # The music thins out just before the title lands, so the screen empties with it.
    alpha = 1 - clamp((t - b(15)) / 0.3)
    word_row(frame, [("Your", b(8), WHITE), ("itch.io", b(8.5), CORAL), ("page", b(9), WHITE)], 170, 230, t, alpha=alpha)
    line = [("has", b(10), WHITE), ("no", b(10.5), WHITE), ("export", b(11), WHITE), ("button.", b(11.5), WHITE)]
    word_row(frame, line, 130, 420, t, alpha=alpha)
    state = enter(t, b(12), "pop")
    if state:
        place(frame, export_button(), W / 2, 720, state[2] * pulse(t), state[3] * alpha)
    state = enter(t, b(13), "slam")
    if state:
        place(frame, strike_mark(), W / 2, 720, state[2], state[3] * alpha)


def scene_title(frame, t):
    frame.paste(CRIMSON, (0, 0, W, H))
    marquee(frame, t, CRIMSON, WHITE, 0.055)
    word(frame, "Backupper", 330, WHITE, W / 2, 400, t, b(16), "slam", stroke=4)
    word(frame, "for itch.io", 170, BLUSH, W / 2, 640, t, b(17), "up")
    word(frame, "Save an offline copy of any author's page", 66, WHITE, W / 2, 840, t, b(18), "up", stroke=1)


CAMERA = [(20, 500, 380, 1.0), (20.01, 500, 190, 1.25), (24, 500, 320, 1.25), (28, 500, 515, 1.25)]
RINGS = [
    (20, 24, (24, 156, 976, 210)),
    (24, 28, (24, 292, 976, 350)),
    (28, 30, (16, 487, 226, 543)),
    (30, 32, (14, 545, 986, 596)),
]
STEPS = [(20, "1", "Enter an", "author's page"), (24, "2", "Choose", "a folder"), (28, "3", "Press", "Start Backup")]


@lru_cache(maxsize=None)
def program_window():
    """The program capture with a soft shadow, plus how far the shadow pads it."""
    shot = Image.open(PROMO / "raw_1_program.png").convert("RGB")
    pad = 40
    sprite = Image.new("RGBA", (shot.width + 2 * pad, shot.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(sprite).rectangle((pad + 3, pad + 6, pad + shot.width, pad + shot.height), fill=(0, 0, 0, 110))
    sprite = sprite.filter(ImageFilter.GaussianBlur(14))
    sprite.paste(shot, (pad, pad))
    return sprite, pad


@lru_cache(maxsize=None)
def ring_sprite(width, height):
    return rounded((width * 2 + 32, height * 2 + 32), 18, None, outline=CRIMSON, width=8, scale=2)


def camera_at(t):
    x, y, scale = CAMERA[0][1:]
    for beat, target_x, target_y, target_scale in CAMERA[1:]:
        p = ease_in_out(clamp((t - b(beat)) / 0.4))
        x += (target_x - x) * p
        y += (target_y - y) * p
        scale += (target_scale - scale) * p
    return x, y, scale


def scene_steps(frame, t):
    frame.paste(PAPER, (0, 0, W, H))
    sprite, pad = program_window()
    focus_x, focus_y, scale = camera_at(t)
    screen_x, screen_y = 1290, H / 2
    anchor = ((focus_x + pad) / sprite.width, (focus_y + pad) / sprite.height)
    place(frame, sprite, screen_x, screen_y, scale, anchor=anchor)

    for start, end, (left, top, right, bottom) in RINGS:
        state = enter(t, b(start) + 0.3, "pop") if b(start) <= t < b(end) else None
        if state:
            ring = ring_sprite(right - left, bottom - top)
            x = screen_x + ((left + right) / 2 - focus_x) * scale
            y = screen_y + ((top + bottom) / 2 - focus_y) * scale
            place(frame, ring, x, y, scale / 2 * (2.1 - state[2] * 1.1), state[3])

    for start, number, first, second in STEPS:
        if b(start) <= t < b(start + 4):
            word(frame, number, 260, CRIMSON, 70, 340, t, b(start), "slam", (0, 0.5))
            word(frame, first, 80, TEXT_INK, 70, 560, t, b(start + 0.25), "left", (0, 0.5), stroke=1)
            word(frame, second, 80, TEXT_INK, 70, 660, t, b(start + 0.5), "left", (0, 0.5), stroke=1)


SHOTS = [
    (32, "raw_2_saved_front_page.png", "Your front page"),
    (36, "raw_3_saved_project_page.png", "Every project page"),
    (40, "raw_4_saved_devlog.png", "Every devlog"),
]


@lru_cache(maxsize=None)
def shot_image(name):
    return Image.open(PROMO / name).convert("RGB")


@lru_cache(maxsize=None)
def caption_band(text):
    label = text_sprite(text, 96, WHITE)
    band = Image.new("RGBA", (label.width + 130, 170), CRIMSON + (255,))
    band.paste(label, (90, (band.height - label.height) // 2 - 4), label)
    return band


def scene_shots(frame, t):
    for start, name, caption in reversed(SHOTS):
        if t >= b(start):
            break
    since = t - b(start)
    punch = 1 + 0.07 * (1 - ease_out(clamp(since / 0.3)))
    shot = shot_image(name)
    scale = W / shot.width * punch
    # Slow enough that the caption stays over the sample page's price, which is another product's.
    pan = -since * 25
    place(frame, shot, W / 2, pan, scale, anchor=(0.5, 0))
    band = caption_band(caption)
    slide = 1 - ease_out(clamp(since / 0.25))
    place(frame, band, -slide * band.width, 860, anchor=(0, 0.5))


def scene_hidden(frame, t):
    frame.paste(INK, (0, 0, W, H))
    marquee(frame, t, INK, WHITE)
    word(frame, "Even the projects", 170, WHITE, W / 2, 310, t, b(44), "left")
    word(frame, "your front page", 170, WHITE, W / 2, 530, t, b(45), "right")
    word(frame, "doesn't link to.", 170, CORAL, W / 2, 750, t, b(46), "slam")


def scene_offline(frame, t):
    frame.paste(CRIMSON, (0, 0, W, H))
    marquee(frame, t, CRIMSON, WHITE, 0.055)
    word(frame, "Browse it offline.", 190, WHITE, W / 2, 430, t, b(48), "slam")
    word(frame, "In any browser.", 130, BLUSH, W / 2, 660, t, b(50), "up")


def scene_honest(frame, t):
    frame.paste(CORAL, (0, 0, W, H))
    marquee(frame, t, CORAL, TEXT_INK, 0.04)
    word(frame, "It saves the pages.", 170, TEXT_INK, W / 2, 430, t, b(52), "left")
    word(frame, "Not the downloadable files.", 112, TEXT_INK, W / 2, 660, t, b(54), "right")


def scene_end(frame, t):
    frame.paste(INK, (0, 0, W, H))
    marquee(frame, t, INK, WHITE, 0.03)
    word(frame, "Backupper", 220, WHITE, W / 2, 210, t, b(56), "slam", stroke=3)
    word(frame, "for itch.io", 110, BLUSH, W / 2, 380, t, b(56.5), "up")
    word(frame, URL, 76, CORAL, W / 2, 545, t, b(58), "pop")

    points = ["Free, pay what you want", "Windows 10 and 11", "MIT licensed"]
    sprites = [text_sprite(point, 50, WHITE, 1) for point in points]
    gap = 90
    x = (W - sum(sprite.width for sprite in sprites) - gap * (len(sprites) - 1)) / 2
    for index, (point, sprite) in enumerate(zip(points, sprites)):
        word(frame, point, 50, WHITE, x + sprite.width / 2, 700, t, b(59 + index * 0.5), "up", stroke=1)
        x += sprite.width + gap

    word(frame, "Made by Reactorcore. Unofficial tool, not affiliated with itch.io.", 34, GREY, W / 2, 880, t, b(60), "up", stroke=0, regular=True)
    word(frame, CREDIT, 34, GREY, W / 2, 940, t, b(60), "up", stroke=0, regular=True)


SCENES = [
    (0, scene_years, CORAL),
    (8, scene_export, CORAL),
    (16, scene_title, WHITE),
    (20, scene_steps, CRIMSON),
    (32, scene_shots, CRIMSON),
    (44, scene_hidden, CORAL),
    (48, scene_offline, WHITE),
    (52, scene_honest, TEXT_INK),
    (56, scene_end, CORAL),
]
WIPES = [
    (20, (WHITE, CORAL, PAPER)),
    (32, (CRIMSON, INK, CORAL)),
    (44, (CORAL, WHITE, INK)),
    (48, (INK, CORAL, CRIMSON)),
    (52, (CRIMSON, WHITE, CORAL)),
    (56, (CORAL, CRIMSON, INK)),
]


def render_frame(t):
    frame = Image.new("RGB", (W, H), INK)
    for start, scene, bar in reversed(SCENES):
        if t >= b(start):
            break
    scene(frame, t)
    # The running bar borrows the program's own progress bar, and is full when the video ends.
    ImageDraw.Draw(frame).rectangle((0, H - 10, round(W * clamp(t / b(64))), H), fill=bar)
    for beat, colors in WIPES:
        if abs(t - b(beat)) < 0.4:
            wipe(frame, t, b(beat), colors)
    return frame


def render_video():
    command = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(MUSIC),
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-g", "30", "-bf", "2",
        # The track decodes above full scale, so it is limited on the way in.
        "-af", "volume=3dB,alimiter=limit=0.84:level=0:attack=1:release=60",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
        "-movflags", "+faststart", str(OUTPUT),
    ]
    encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
    total = round(SECONDS * FPS)
    for index in range(total):
        encoder.stdin.write(render_frame(index / FPS).tobytes())
        if index % 300 == 0:
            print(f"frame {index} of {total}", flush=True)
    encoder.stdin.close()
    if encoder.wait() != 0:
        raise SystemExit("ffmpeg failed")
    print("Wrote", OUTPUT)


def render_thumbnail():
    image = Image.new("RGB", (W, H), CRIMSON)
    marquee(image, 3.0, CRIMSON, WHITE, 0.04)
    place(image, text_sprite("Backupper", 370, WHITE, 6), W / 2, 310)
    place(image, text_sprite("for itch.io", 220, BLUSH, 3), 62, 620, anchor=(0, 0.5))
    ImageDraw.Draw(image).rectangle((0, 810, W, H), fill=INK)
    place(image, text_sprite("Save your whole page offline", 118, WHITE, 2), W / 2, 930)
    image.save(THUMBNAIL, optimize=True)
    print("Wrote", THUMBNAIL)


def contact_sheet(path):
    """Stills taken late in each beat, when the arrivals have settled."""
    columns = 6
    thumb = (480, 270)
    beats = [n + 0.8 for n in range(0, 64, 2)] + [8.02, 16.1, 19.98, 31.5, 47.98, 63.9]
    beats.sort()
    rows = math.ceil(len(beats) / columns)
    sheet = Image.new("RGB", (columns * thumb[0], rows * thumb[1]), "black")
    for index, beat in enumerate(beats):
        still = render_frame(b(beat)).resize(thumb, Image.LANCZOS)
        ImageDraw.Draw(still).text((6, 4), f"b{beat} {b(beat):.2f}s", fill="yellow", stroke_width=1, stroke_fill="black")
        sheet.paste(still, ((index % columns) * thumb[0], (index // columns) * thumb[1]))
    sheet.save(path)
    print("Wrote", path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--thumbnail", action="store_true", help="render only the thumbnail")
    parser.add_argument("--sheet", metavar="PATH", help="write a contact sheet of stills instead")
    args = parser.parse_args()
    if args.sheet:
        contact_sheet(args.sheet)
        return
    render_thumbnail()
    if not args.thumbnail:
        render_video()


if __name__ == "__main__":
    main()
