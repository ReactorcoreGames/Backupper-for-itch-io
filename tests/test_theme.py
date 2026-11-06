"""The owner's standing rule: all text meets at least 4.5:1 contrast (WCAG AA)."""

import unittest

from gui.theme import PALETTE
from tools.make_itch_button import BUTTON_COLOR, HOVER_COLOR

MINIMUM = 4.5

# (text, background) pairs that really occur in the GUI.
PAIRS = [
    ("text_primary", "bg_base"),
    ("text_primary", "bg_surface"),
    ("text_primary", "bg_input"),
    ("text_secondary", "bg_base"),
    ("text_secondary", "bg_surface"),
    ("text_on_accent", "accent_strong"),
    ("text_on_accent", "accent_mid"),
    ("accent_mid", "bg_base"),
    ("success", "bg_base"),
    ("danger", "bg_base"),
    ("warning", "bg_base"),
    ("info", "bg_base"),
    ("disabled_fg", "disabled_bg"),
]


def luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class ContrastTests(unittest.TestCase):
    def test_visit_button_artwork_contrast(self):
        # Large logo artwork rather than body text, so WCAG's 3:1 applies.
        self.assertGreaterEqual(contrast("#FFFFFF", BUTTON_COLOR), 3.0)
        self.assertGreaterEqual(contrast("#FFFFFF", HOVER_COLOR), 3.0)

    def test_text_contrast(self):
        for text, background in PAIRS:
            ratio = contrast(PALETTE[text], PALETTE[background])
            self.assertGreaterEqual(ratio, MINIMUM, f"{text} on {background} is only {ratio:.2f}:1")


if __name__ == "__main__":
    unittest.main()
