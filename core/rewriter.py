"""Rewrites a saved page so it displays from local files."""

from urllib.parse import quote, urlsplit

from bs4 import BeautifulSoup

from core.assets import rewrite_css
from core.urls import canonical_page_url, resolve

ASSET_HOSTS = {"img.itch.zone", "static.itch.io"}
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".avif")
STATIC_EXTENSIONS = IMAGE_EXTENSIONS + (".css", ".js", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp4", ".webm", ".ogg", ".mp3")

# Attributes that always name something the page needs in order to display.
REQUISITE_ATTRIBUTES = {
    "img": ("src", "data-lazy_src"),
    "script": ("src", "data-src"),
    "source": ("src",),
    "video": ("src", "poster"),
    "audio": ("src",),
    "track": ("src",),
}
SRCSET_ATTRIBUTES = ("srcset", "data-srcset")
REQUISITE_LINK_RELS = {"stylesheet", "icon", "shortcut", "apple-touch-icon", "preload", "image_src"}
LINK_ATTRIBUTES = {"a": "href", "area": "href", "form": "action", "iframe": "src", "link": "href"}


def _path_of(url):
    return urlsplit(url).path.lower()


def is_image_url(url):
    return _path_of(url).endswith(IMAGE_EXTENSIONS)


def _is_hosted_asset(url):
    return urlsplit(url).hostname in ASSET_HOSTS and _path_of(url).endswith(STATIC_EXTENSIONS)


def _rewrite_srcset(value, localize):
    candidates = []
    for candidate in value.split(","):
        pieces = candidate.split()
        if not pieces:
            continue
        pieces[0] = localize(pieces[0]) or pieces[0]
        candidates.append(" ".join(pieces))
    return ", ".join(candidates)


class PageRewriter:
    """Rewrites one page. page_files maps canonical page URLs to local filenames."""

    def __init__(self, page_url, stem, folder, store, page_files, host, full_size_images=True):
        self.page_url = page_url
        self.stem = stem
        self.folder = folder
        self.store = store
        self.page_files = page_files
        self.host = host
        self.full_size_images = full_size_images

    def _local_reference(self, absolute):
        name = self.store.localize(absolute, self.folder)
        return None if name is None else f"{quote(self.stem)}_files/{quote(name)}"

    def _localize(self, reference):
        """Local reference for a page requisite, else its absolute URL."""
        absolute = resolve(self.page_url, reference)
        if absolute is None:
            return reference
        return self._local_reference(absolute) or absolute

    def _css(self, text):
        return rewrite_css(text, self.page_url, self._local_reference)

    def rewrite(self, html):
        soup = BeautifulSoup(html, "html.parser")

        # A per-visit anti-forgery token: meaningless in a backup.
        for tag in soup.find_all("meta", attrs={"name": "csrf_token"}):
            tag.decompose()

        for tag in soup.find_all(True):
            self._rewrite_tag(tag)
        for tag in soup.find_all("style"):
            if tag.string:
                tag.string.replace_with(self._css(str(tag.string)))
        return str(soup)

    def _rewrite_tag(self, tag):
        name = tag.name
        handled = set()

        for attribute in REQUISITE_ATTRIBUTES.get(name, ()):
            if tag.has_attr(attribute):
                tag[attribute] = self._localize(tag[attribute])
                handled.add(attribute)
        for attribute in SRCSET_ATTRIBUTES:
            if tag.has_attr(attribute):
                tag[attribute] = _rewrite_srcset(tag[attribute], self._localize)
                handled.add(attribute)
        # Lazy images have no src until the site's script runs. Fill it in so
        # the backup still displays with scripts blocked, as file:// pages may.
        if name == "img" and not tag.get("src") and tag.get("data-lazy_src"):
            tag["src"] = tag["data-lazy_src"]

        if name == "link":
            self._rewrite_link_tag(tag)
            handled.add("href")
        elif name == "meta":
            self._rewrite_meta_tag(tag)
            handled.add("content")
        elif name in ("a", "area"):
            self._rewrite_anchor(tag)
            handled.add("href")
        elif name in LINK_ATTRIBUTES:
            attribute = LINK_ATTRIBUTES[name]
            if tag.has_attr(attribute):
                tag[attribute] = resolve(self.page_url, tag[attribute]) or tag[attribute]
                handled.add(attribute)

        if tag.has_attr("style") and "url(" in tag["style"]:
            tag["style"] = self._css(tag["style"])
            handled.add("style")

        # Catch the site's own data-* attributes, such as data-gif, that name assets.
        for attribute, value in list(tag.attrs.items()):
            if attribute in handled or not isinstance(value, str):
                continue
            if value.startswith(("http://", "https://", "//")):
                absolute = resolve(self.page_url, value)
                if absolute and _is_hosted_asset(absolute):
                    tag[attribute] = self._local_reference(absolute) or absolute

    def _rewrite_link_tag(self, tag):
        if not tag.has_attr("href"):
            return
        rel = tag.get("rel") or []
        rel = {rel.lower()} if isinstance(rel, str) else {r.lower() for r in rel}
        if rel & REQUISITE_LINK_RELS:
            tag["href"] = self._localize(tag["href"])
        else:
            tag["href"] = resolve(self.page_url, tag["href"]) or tag["href"]

    def _rewrite_meta_tag(self, tag):
        # og:image is the project's full cover art, so it is worth keeping.
        # The cropped social-card variants are not.
        if tag.get("property") == "og:image" and tag.get("content"):
            tag["content"] = self._localize(tag["content"])

    def _rewrite_anchor(self, tag):
        if not tag.has_attr("href"):
            return
        href = tag["href"]
        absolute = resolve(self.page_url, href)
        if absolute is None:
            return

        if (urlsplit(absolute).hostname or "").lower() == self.host:
            local = self.page_files.get(canonical_page_url(absolute))
            if local is not None:
                fragment = urlsplit(absolute).fragment
                tag["href"] = local + (f"#{fragment}" if fragment else "")
                return
        elif self.full_size_images and _is_hosted_asset(absolute) and is_image_url(absolute):
            # Screenshot thumbnails link to their full-size originals.
            tag["href"] = self._local_reference(absolute) or absolute
            return
        tag["href"] = absolute


def extract_links(html, page_url):
    """All link targets on a page, as absolute URLs."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all(["a", "area"], href=True):
        absolute = resolve(page_url, tag["href"])
        if absolute:
            links.append(absolute)
    return links
