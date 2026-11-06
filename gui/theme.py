import sys
from pathlib import Path

THEME_NAME = "itchbackup"

# The itch.io look: white and light grey, charcoal text, carnation accents.
# Colours from https://itch.io/press-kit, adjusted only where they fail 4.5:1
# contrast as text. tests/test_theme.py enforces that.
PALETTE = {
    # Backgrounds
    "bg_base":        "#FFFFFF",   # root window, header, footer
    "bg_surface":     "#F4F4F4",   # LabelFrames, like the itch.io filter sidebar
    "bg_input":       "#FFFFFF",   # Entry, Spinbox, log

    # Accents
    "accent_brand":   "#FA5C5C",   # itchy carnation: the header line only, never behind text
    "accent_strong":  "#D6293E",   # primary buttons, white text passes on this
    "accent_mid":     "#B81F32",   # hover, links, LabelFrame titles
    "accent_glow":    "#CFCFCF",   # borders, separators

    # Text
    "text_primary":   "#222222",
    "text_secondary": "#434343",
    "text_on_accent": "#FFFFFF",

    # Semantic
    "success":        "#1B7A43",
    "danger":         "#C42B2B",
    "warning":        "#8A5A00",
    "info":           "#1F6AA5",

    # Disabled controls
    "disabled_bg":    "#E4E4E4",
    "disabled_fg":    "#5E5E5E",
}

BUNDLED_FONTS = ("Lato-Regular.ttf", "Lato-Bold.ttf")
FONT_FAMILY    = "Segoe UI"        # Replaced by Lato in load_bundled_fonts() when it loads.
FONT_TITLE     = (FONT_FAMILY, 21, "bold")
FONT_HEADING   = (FONT_FAMILY, 14, "bold")
FONT_BODY      = (FONT_FAMILY, 12)
FONT_BODY_BOLD = (FONT_FAMILY, 12, "bold")
FONT_SMALL     = (FONT_FAMILY, 11)
FONT_TINY      = (FONT_FAMILY, 10)
FONT_MONO      = ("Consolas", 10)


def assets_folder():
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def load_bundled_fonts():
    """Make Lato available to this process only, nothing gets installed.

    Must run before the Tk root window exists. Falls back to Segoe UI silently.
    """
    global FONT_FAMILY, FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_TINY
    if sys.platform != "win32":
        return
    import ctypes
    FR_PRIVATE = 0x10
    for name in BUNDLED_FONTS:
        path = assets_folder() / "fonts" / name
        if not path.exists() or ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0) == 0:
            return
    FONT_FAMILY    = "Lato"
    FONT_TITLE     = (FONT_FAMILY, 21, "bold")
    FONT_HEADING   = (FONT_FAMILY, 14, "bold")
    FONT_BODY      = (FONT_FAMILY, 12)
    FONT_BODY_BOLD = (FONT_FAMILY, 12, "bold")
    FONT_SMALL     = (FONT_FAMILY, 11)
    FONT_TINY      = (FONT_FAMILY, 10)


def inject_theme():
    from ttkbootstrap.themes.standard import STANDARD_THEMES
    p = PALETTE
    STANDARD_THEMES[THEME_NAME] = {
        "type": "light",
        "colors": {
            "primary":   p["accent_strong"],
            "secondary": p["text_secondary"],
            "success":   p["success"],
            "info":      p["info"],
            "warning":   p["warning"],
            "danger":    p["danger"],
            "light":     p["bg_surface"],
            "dark":      p["text_primary"],
            "bg":        p["bg_base"],
            "fg":        p["text_primary"],
            "selectbg":  p["accent_strong"],
            "selectfg":  p["text_on_accent"],
            "border":    p["accent_glow"],
            "inputfg":   p["text_primary"],
            "inputbg":   p["bg_input"],
            "active":    p["accent_glow"],
        },
    }


def apply_theme(style, root=None):
    import tkinter.ttk as _stdlib_ttk
    p = PALETTE

    if root is not None:
        root.configure(bg=p["bg_base"])

    style.configure(".",
                    background=p["bg_base"],
                    foreground=p["text_primary"],
                    bordercolor=p["accent_glow"],
                    selectbackground=p["accent_strong"],
                    selectforeground=p["text_on_accent"],
                    fieldbackground=p["bg_input"],
                    font=FONT_BODY)

    # Apply LabelFrame styles to both engines so _tk_ttk.LabelFrame picks them up.
    for s in (style, _stdlib_ttk.Style()):
        s.configure("TLabelframe",       background=p["bg_surface"], bordercolor=p["accent_glow"])
        s.configure("TLabelframe.Label", background=p["bg_surface"], foreground=p["text_primary"],
                    font=FONT_BODY_BOLD)

    style.configure("TFrame",         background=p["bg_base"])
    style.configure("Surface.TFrame", background=p["bg_surface"])

    style.configure("TLabel", background=p["bg_base"], foreground=p["text_primary"], font=FONT_BODY)
    style.configure("Surface.TLabel", background=p["bg_surface"], foreground=p["text_primary"], font=FONT_BODY)
    style.configure("Hint.TLabel", background=p["bg_surface"], foreground=p["text_secondary"], font=FONT_SMALL)
    style.configure("Subtitle.TLabel", background=p["bg_base"], foreground=p["text_secondary"], font=FONT_BODY)
    style.configure("Title.TLabel", background=p["bg_base"], foreground=p["text_primary"], font=FONT_TITLE)
    style.configure("Footer.TLabel", background=p["bg_base"], foreground=p["text_secondary"], font=FONT_TINY)
    style.configure("Link.TLabel", background=p["bg_base"], foreground=p["accent_mid"], font=FONT_TINY)
    for state in ("success", "danger", "warning", "info"):
        style.configure(f"Status{state.title()}.TLabel", background=p["bg_base"], foreground=p[state], font=FONT_BODY_BOLD)
    style.configure("Status.TLabel", background=p["bg_base"], foreground=p["text_primary"], font=FONT_BODY)

    style.configure("Primary.TButton",
                    background=p["accent_strong"], foreground=p["text_on_accent"],
                    bordercolor=p["accent_strong"], darkcolor=p["accent_strong"], lightcolor=p["accent_strong"],
                    focuscolor=p["text_on_accent"], font=FONT_BODY_BOLD, padding=(16, 9))
    style.map("Primary.TButton",
              background=[("disabled", p["disabled_bg"]), ("pressed", p["accent_mid"]), ("active", p["accent_mid"])],
              foreground=[("disabled", p["disabled_fg"])],
              bordercolor=[("disabled", p["disabled_bg"]), ("active", p["accent_mid"])],
              darkcolor=[("disabled", p["disabled_bg"]), ("active", p["accent_mid"])],
              lightcolor=[("disabled", p["disabled_bg"]), ("active", p["accent_mid"])])

    style.configure("Plain.TButton",
                    background=p["bg_base"], foreground=p["text_primary"],
                    bordercolor=p["text_secondary"], darkcolor=p["bg_base"], lightcolor=p["bg_base"],
                    focuscolor=p["text_primary"], font=FONT_BODY, padding=(12, 7))
    style.map("Plain.TButton",
              background=[("disabled", p["disabled_bg"]), ("pressed", p["accent_glow"]), ("active", p["bg_surface"])],
              foreground=[("disabled", p["disabled_fg"])],
              bordercolor=[("disabled", p["disabled_bg"]), ("active", p["accent_mid"])],
              darkcolor=[("disabled", p["disabled_bg"]), ("active", p["bg_surface"])],
              lightcolor=[("disabled", p["disabled_bg"]), ("active", p["bg_surface"])])

    style.configure("TEntry", fieldbackground=p["bg_input"], foreground=p["text_primary"],
                    bordercolor=p["text_secondary"], padding=6)
    style.map("TEntry",
              fieldbackground=[("readonly", p["bg_base"])],
              foreground=[("readonly", p["text_primary"])],
              bordercolor=[("focus", p["accent_strong"])])
    style.configure("TSpinbox", fieldbackground=p["bg_input"], foreground=p["text_primary"],
                    bordercolor=p["text_secondary"], arrowcolor=p["text_primary"], padding=5)

    style.configure("TCheckbutton", background=p["bg_surface"], foreground=p["text_primary"], font=FONT_BODY)
    style.map("TCheckbutton", background=[("active", p["bg_surface"])], foreground=[("active", p["text_primary"])])

    style.configure("Backup.Horizontal.TProgressbar",
                    background=p["accent_strong"], troughcolor=p["bg_surface"],
                    bordercolor=p["accent_glow"], lightcolor=p["accent_strong"], darkcolor=p["accent_strong"],
                    thickness=14)
    style.configure("TSeparator", background=p["accent_glow"])
