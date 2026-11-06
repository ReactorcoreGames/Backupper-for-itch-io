"""Saves page assets into a page's _files folder, downloading each URL only once."""

import mimetypes
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from core.fetcher import FetchError
from core.urls import asset_filename, asset_hash, resolve

MAX_CSS_DEPTH = 4

_CSS_URL = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)""", re.IGNORECASE | re.DOTALL)
_CSS_IMPORT = re.compile(r"""@import\s+(['"])(.+?)\1""", re.IGNORECASE)


def rewrite_css(css, base_url, localize):
    """Point every url() and @import in css at whatever localize(url) returns.

    localize returns a replacement reference, or None to keep the remote URL.
    """
    def _target(reference):
        reference = reference.strip()
        if not reference or reference.startswith(("data:", "#")):
            return None
        absolute = resolve(base_url, reference)
        if absolute is None:
            return None
        return localize(absolute) or absolute

    def _replace_url(match):
        target = _target(match.group(2))
        return match.group(0) if target is None else f'url("{target}")'

    def _replace_import(match):
        target = _target(match.group(2))
        return match.group(0) if target is None else f'@import "{target}"'

    return _CSS_URL.sub(_replace_url, _CSS_IMPORT.sub(_replace_import, css))


def _atomic_write(target, content):
    temporary = target.with_name(target.name + ".part")
    temporary.write_bytes(content)
    os.replace(temporary, target)


@dataclass
class _Known:
    path: Path
    dependencies: list = field(default_factory=list)


class AssetStore:
    def __init__(self, fetcher, delay=0.1, log=lambda message: None):
        self.fetcher = fetcher
        self.delay = delay
        self.log = log
        self.known = {}
        self.failures = {}
        self.downloaded = 0
        self.reused = 0

    def localize(self, url, folder, depth=0):
        """Ensure url is saved in folder. Returns its filename, or None on failure."""
        url = url.split("#", 1)[0]
        if url in self.failures:
            return None

        entry = self.known.get(url)
        if entry is not None:
            return self._share(url, entry, folder, depth)

        existing = None if self._is_css_url(url) else self._find_existing(url, folder)
        if existing is not None:
            self.known[url] = _Known(existing)
            self.reused += 1
            return existing.name

        return self._download(url, folder, depth)

    @staticmethod
    def _is_css_url(url):
        return urlsplit(url).path.lower().endswith(".css")

    @staticmethod
    def _find_existing(url, folder):
        if not folder.is_dir():
            return None
        for path in folder.glob(f"*-{asset_hash(url)}.*"):
            if not path.name.endswith(".part") and path.stat().st_size > 0:
                return path
        return None

    def _share(self, url, entry, folder, depth):
        """Give this page its own copy of an asset fetched for an earlier page."""
        target = folder / entry.path.name
        if not target.exists():
            folder.mkdir(parents=True, exist_ok=True)
            try:
                os.link(entry.path, target)
            except OSError:
                shutil.copy2(entry.path, target)
        for dependency in entry.dependencies:
            self.localize(dependency, folder, depth + 1)
        return target.name

    def _download(self, url, folder, depth):
        self.fetcher.pause(self.delay)
        try:
            content, content_type = self.fetcher.get_asset(url)
        except FetchError as error:
            self.failures[url] = str(error)
            self.log(f"  Could not save {url}: {error}")
            return None

        dependencies = []
        is_css = self._is_css_url(url) or content_type == "text/css"
        if is_css and depth < MAX_CSS_DEPTH:
            content = self._localize_stylesheet(content, url, folder, depth, dependencies)

        extension = None
        if not os.path.splitext(urlsplit(url).path)[1]:
            extension = mimetypes.guess_extension(content_type) or ".bin"
        target = folder / asset_filename(url, extension)
        folder.mkdir(parents=True, exist_ok=True)
        try:
            _atomic_write(target, content)
        except OSError as error:
            self.failures[url] = f"could not write file: {error}"
            self.log(f"  Could not write {target.name}: {error}")
            return None
        self.known[url] = _Known(target, dependencies)
        self.downloaded += 1
        return target.name

    def _localize_stylesheet(self, content, url, folder, depth, dependencies):
        def _localize(reference):
            name = self.localize(reference, folder, depth + 1)
            if name is not None:
                dependencies.append(reference)
            return name

        css = content.decode("utf-8", errors="replace")
        return rewrite_css(css, url, _localize).encode("utf-8")
