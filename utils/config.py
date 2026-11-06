import json
import sys
from pathlib import Path

# Empty on purpose: a fresh copy of the program asks the user where to save
# and whose page to back up. Personal choices live only in config.json.
DEFAULT_CONFIG = {
    "author_url": "",
    "output_folder": "",
    "include_subpages": True,
    "full_size_images": True,
    "page_delay": 1.0,
}


def program_folder():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _config_path():
    return program_folder() / "config.json"


def load_config():
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
        return {**DEFAULT_CONFIG, **data}
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(data):
    _config_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def resolve_output_folder(value):
    """A relative output folder is relative to the program, not the working directory."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else program_folder() / path
