"""HTTP access: retries, pacing, size limits and refusal of private addresses."""

import ipaddress
import socket
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urljoin, urlsplit

import requests

USER_AGENT = "BackupperForItchIo/1.0 (personal offline backup tool; https://reactorcore.itch.io/)"
TIMEOUT = (15, 60)
MAX_ATTEMPTS = 4
MAX_REDIRECTS = 5
MAX_RETRY_WAIT = 120.0
MAX_PAGE_BYTES = 32 * 1024 * 1024
MAX_ASSET_BYTES = 512 * 1024 * 1024
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
CHUNK_SIZE = 64 * 1024


class BackupStopped(Exception):
    """The user pressed Stop."""


class FetchError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class NotHtml(Exception):
    """A page URL turned out to be something other than a web page."""


@lru_cache(maxsize=512)
def _is_public_host(host):
    if not host or host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        return True  # Unresolvable: the request itself will report the failure.
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        if not ip.is_global:
            return False
    return True


def _retry_wait(response, attempt):
    header = response.headers.get("Retry-After") if response is not None else None
    wait = 2.0 ** (attempt + 1)
    # itch.io sends 429 with no Retry-After, and short waits just get another 429.
    if response is not None and response.status_code == 429:
        wait = 30.0 * 2 ** attempt
    if header:
        try:
            wait = float(header)
        except ValueError:
            try:
                wait = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError):
                pass
    return min(max(wait, 1.0), MAX_RETRY_WAIT)


class Fetcher:
    def __init__(self, stop_event, log=lambda message: None):
        self.stop_event = stop_event
        self.log = log
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.bytes_downloaded = 0

    def pause(self, seconds):
        if seconds > 0 and self.stop_event.wait(seconds):
            raise BackupStopped()
        if self.stop_event.is_set():
            raise BackupStopped()

    def _open(self, url):
        """GET with redirects followed by hand, so each hop can be vetted."""
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            parts = urlsplit(current)
            if parts.scheme not in ("http", "https"):
                raise FetchError(f"unsupported address {current}")
            if not _is_public_host(parts.hostname):
                raise FetchError(f"refused private address {parts.hostname}")
            response = self.session.get(current, stream=True, timeout=TIMEOUT, allow_redirects=False)
            if not response.is_redirect:
                return response
            location = response.headers.get("Location", "")
            response.close()
            current = urljoin(current, location)
        raise FetchError("too many redirects")

    def open_with_retries(self, url):
        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            self.pause(0)
            response = None
            try:
                response = self._open(url)
            except requests.RequestException as error:
                last_error = FetchError(f"{type(error).__name__}")
            else:
                if response.status_code == 200:
                    return response
                last_error = FetchError(f"HTTP {response.status_code}", response.status_code)
                wait = _retry_wait(response, attempt)
                response.close()
                if last_error.status not in RETRYABLE_STATUS:
                    raise last_error
                if attempt + 1 < MAX_ATTEMPTS:
                    self.log(f"  Server said {response.status_code}, waiting {wait:.0f}s before retrying")
                    self.pause(wait)
                continue
            if attempt + 1 < MAX_ATTEMPTS:
                self.pause(_retry_wait(None, attempt))
        raise last_error

    def _read(self, response, limit):
        data = bytearray()
        try:
            for chunk in response.iter_content(CHUNK_SIZE):
                data.extend(chunk)
                if len(data) > limit:
                    raise FetchError(f"larger than the {limit // (1024 * 1024)} MB limit")
                if self.stop_event.is_set():
                    raise BackupStopped()
        except requests.RequestException as error:
            raise FetchError(type(error).__name__) from error
        finally:
            response.close()
        self.bytes_downloaded += len(data)
        return bytes(data)

    def get_page(self, url):
        """Return (final_url, html_text). Raises NotHtml without reading other content."""
        response = self.open_with_retries(url)
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            response.close()
            raise NotHtml(content_type or "unknown type")
        final_url = response.url
        encoding = "utf-8"
        if "charset=" in content_type:
            encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip() or encoding
        data = self._read(response, MAX_PAGE_BYTES)
        try:
            return final_url, data.decode(encoding, errors="replace")
        except LookupError:
            return final_url, data.decode("utf-8", errors="replace")

    def get_text_optional(self, url):
        """Return (status, text) for robots.txt, or (None, '') if unreachable."""
        try:
            response = self.open_with_retries(url)
        except FetchError as error:
            return error.status, ""
        return 200, self._read(response, MAX_PAGE_BYTES).decode("utf-8", errors="replace")

    def get_asset(self, url):
        """Return (content, content_type)."""
        response = self.open_with_retries(url)
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        length = response.headers.get("Content-Length", "")
        if length.isdigit() and int(length) > MAX_ASSET_BYTES:
            response.close()
            raise FetchError(f"larger than the {MAX_ASSET_BYTES // (1024 * 1024)} MB limit")
        return self._read(response, MAX_ASSET_BYTES), content_type
