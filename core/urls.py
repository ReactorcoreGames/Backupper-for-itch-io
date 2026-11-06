"""URL rules: which author is meant, what is in scope, and where things are saved."""

import hashlib
import re
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

ITCH_DOMAIN = "itch.io"

# Subdomains that belong to itch.io itself rather than to an author.
RESERVED_SUBDOMAINS = {"www", "static", "img", "api", "ww", "cdn", "assets", "html", "v6p9d9t4"}

# Author-page routes that are actions, gated, or disallowed rather than content.
# Matched against any path segment after the first, or the whole path for "-".
EXCLUDED_SEGMENTS = {
    "purchase", "rate", "download", "download_url", "rh", "rp", "-",
    "add-to-collection", "report", "edit", "admin", "login", "register",
    "follow", "unfollow", "claim", "new", "reply", "delete", "vote",
}

# Query parameters that select different content. Everything else is tracking noise.
CONTENT_QUERY_PARAMS = {"page", "before", "after"}

WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

_SAFE_NAME = re.compile(r"[^a-z0-9._-]+")
_AUTHOR_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_MAX_NAME_LENGTH = 90


class InvalidAuthorError(ValueError):
    pass


def parse_author(text):
    """Turn whatever the user typed into an author name.

    Accepts a bare name, author.itch.io, any URL on that host, or an
    itch.io/profile/name URL. Raises InvalidAuthorError for anything else.
    """
    text = (text or "").strip()
    if not text:
        raise InvalidAuthorError("Please enter an itch.io author page, like https://example.itch.io/")

    candidate = text if "://" in text else f"https://{text}"
    parts = urlsplit(candidate)
    host = (parts.hostname or "").lower()

    if host in (ITCH_DOMAIN, f"www.{ITCH_DOMAIN}"):
        segments = [s for s in parts.path.split("/") if s]
        if len(segments) >= 2 and segments[0] == "profile":
            name = segments[1].lower()
        else:
            raise InvalidAuthorError(
                "That is an itch.io address, not an author page. Author pages look like https://example.itch.io/"
            )
    elif host.endswith(f".{ITCH_DOMAIN}"):
        name = host[: -len(ITCH_DOMAIN) - 1]
    elif "." not in host:
        name = host
    else:
        raise InvalidAuthorError("Only itch.io author pages can be backed up, like https://example.itch.io/")

    if not _AUTHOR_NAME.match(name) or name in RESERVED_SUBDOMAINS:
        raise InvalidAuthorError(f"\"{name}\" is not a valid itch.io author name.")
    return name


def author_host(author):
    return f"{author}.{ITCH_DOMAIN}"


def author_root(author):
    return f"https://{author_host(author)}/"


def author_profile(author):
    """The author's profile lists every project, including ones nothing on their own site links to."""
    return f"https://{ITCH_DOMAIN}/profile/{author}"


def is_project_url(url, host):
    """Whether url is a top-level project page on the author's site."""
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    return (parts.hostname or "").lower() == host and len(segments) == 1 and is_crawlable(url, host)


def canonical_page_url(url):
    """Normalise a page URL so the same page is only ever crawled once."""
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    query = sorted((k, v) for k, v in parse_qsl(parts.query) if k in CONTENT_QUERY_PARAMS)
    return urlunsplit(("https", (parts.hostname or "").lower(), path, urlencode(query), ""))


def is_crawlable(url, host, include_subpages=True):
    """Whether url is a page on the author's site that should be saved."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or (parts.hostname or "").lower() != host:
        return False
    segments = [unquote(s).lower() for s in parts.path.split("/") if s]
    if any(s in EXCLUDED_SEGMENTS for s in segments):
        return False
    return include_subpages or len(segments) <= 1


def resolve(base, href):
    """Absolute URL for href on a page at base, or None for non-web links."""
    href = (href or "").strip()
    if not href or href.startswith("#"):
        return None
    try:
        absolute = urljoin(base, href)
        scheme = urlsplit(absolute).scheme
    except ValueError:
        return None
    return absolute if scheme in ("http", "https") else None


def _short_hash(text, length=10):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def _make_safe(name):
    return _SAFE_NAME.sub("_", name.lower()).strip("._") or "file"


def page_stem(canonical_url):
    """Flat, deterministic file stem for a page: the root is 'index'."""
    parts = urlsplit(canonical_url)
    raw_segments = [unquote(s) for s in parts.path.split("/") if s]
    if not raw_segments and not parts.query:
        return "index"

    raw = "__".join(raw_segments) or "index"
    if parts.query:
        raw += "__" + parts.query.replace("=", "-").replace("&", "__")

    safe = _make_safe(raw)
    # Anything altered, overlong, or colliding with the root or a device name
    # gets a hash, so two different URLs can never share a file.
    lossy = (
        safe != raw
        or len(safe) > _MAX_NAME_LENGTH
        or safe == "index"
        or safe in WINDOWS_RESERVED_NAMES
        or any("__" in s for s in raw_segments)
    )
    if lossy:
        return f"{safe[:_MAX_NAME_LENGTH]}-{_short_hash(canonical_url)}"
    return safe


def asset_hash(url):
    return _short_hash(url)


def asset_filename(url, extension=None):
    """Filename for an asset. The hash of the full URL is its identity."""
    path = unquote(urlsplit(url).path)
    leaf = path.rsplit("/", 1)[-1]
    stem, dot, ext = leaf.rpartition(".")
    if not dot:
        stem, ext = leaf, ""
    if extension is None:
        extension = f".{_make_safe(ext)[:8]}" if ext else ".bin"
    return f"{_make_safe(stem)[:60]}-{asset_hash(url)}{extension}"
