"""The backup pipeline: find every page, then save each with its assets."""

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from core.assets import AssetStore
from core.fetcher import BackupStopped, FetchError, Fetcher, NotHtml
from core.rewriter import PageRewriter, extract_links
from core.robots import RobotRules
from core.urls import (ITCH_DOMAIN, author_host, author_profile, author_root, canonical_page_url,
                       is_crawlable, is_project_url, page_stem)

REPORT_FILENAME = "backup-report.json"
DEFAULT_PAGE_DELAY = 1.0
DEFAULT_ASSET_DELAY = 0.1
DEFAULT_MAX_PAGES = 3000


class BackupFailed(Exception):
    """The backup could not start or could not continue. The message is user-facing."""


@dataclass
class BackupOptions:
    author: str
    output_dir: Path
    include_subpages: bool = True
    full_size_images: bool = True
    page_delay: float = DEFAULT_PAGE_DELAY
    asset_delay: float = DEFAULT_ASSET_DELAY
    max_pages: int = DEFAULT_MAX_PAGES
    discover_only: bool = False


@dataclass
class BackupResult:
    author: str
    folder: Path
    pages_saved: list = field(default_factory=list)
    pages_discovered: list = field(default_factory=list)
    page_failures: dict = field(default_factory=dict)
    dead_links: list = field(default_factory=list)
    asset_failures: dict = field(default_factory=dict)
    skipped_by_robots: list = field(default_factory=list)
    skipped_not_html: list = field(default_factory=list)
    assets_downloaded: int = 0
    assets_reused: int = 0
    bytes_downloaded: int = 0
    hit_page_limit: bool = False
    stopped: bool = False
    listing_unverified: str = ""

    @property
    def clean(self):
        return not (self.page_failures or self.asset_failures or self.hit_page_limit
                    or self.stopped or self.listing_unverified)


def _no_progress(phase, done, total):
    pass


def _no_log(message):
    pass


def run_backup(options, log=_no_log, progress=_no_progress, stop_event=None):
    """Run a backup. Raises BackupFailed if it cannot run at all.

    log(message) receives human-readable lines. progress(phase, done, total)
    receives "scan" and then "save" counts. Both are called on this thread.
    """
    stop_event = stop_event or threading.Event()
    host = author_host(options.author)
    folder = Path(options.output_dir) / options.author
    result = BackupResult(author=options.author, folder=folder)
    fetcher = Fetcher(stop_event, log)
    store = AssetStore(fetcher, options.asset_delay, log)

    try:
        rules, page_delay = _load_robots(fetcher, host, options.page_delay, log)
        pages = _discover_pages(fetcher, options, host, rules, page_delay, result, log, progress)
        result.pages_discovered = list(pages)
        if not options.discover_only:
            _save_pages(pages, options, host, folder, store, result, log, progress)
    except BackupStopped:
        result.stopped = True
        log("Stopped.")

    result.asset_failures = dict(store.failures)
    result.assets_downloaded = store.downloaded
    result.assets_reused = store.reused
    result.bytes_downloaded = fetcher.bytes_downloaded
    if not options.discover_only and result.pages_saved:
        _write_report(result, options, folder)
    return result


def _load_robots(fetcher, host, page_delay, log):
    status, text = fetcher.get_text_optional(f"https://{host}/robots.txt")
    if status == 200:
        rules = RobotRules(text)
    elif status is not None and 400 <= status < 500:
        rules = RobotRules("")  # No robots.txt means no restrictions.
    else:
        raise BackupFailed(f"Could not reach {host}. Please check your internet connection and try again.")
    if rules.crawl_delay > page_delay:
        log(f"The site asks for {rules.crawl_delay:g}s between pages, so that is what will be used.")
    return rules, max(page_delay, rules.crawl_delay)


def _discover_pages(fetcher, options, host, rules, page_delay, result, log, progress):
    """Breadth-first crawl of the author's pages. Returns {canonical_url: html}."""
    root = canonical_page_url(author_root(options.author))
    queue = [root]
    seen = {root}
    pages = {}
    index = 0
    log(f"Scanning {host} for pages...")

    while index < len(queue):
        url = queue[index]
        index += 1
        progress("scan", index, len(queue))

        if not rules.allows(url):
            result.skipped_by_robots.append(url)
            continue
        if len(pages) >= options.max_pages:
            result.hit_page_limit = True
            log(f"Reached the limit of {options.max_pages} pages, so the rest were left out.")
            break

        if url != root:
            fetcher.pause(page_delay)
        try:
            final_url, html = fetcher.get_page(url)
        except NotHtml:
            result.skipped_not_html.append(url)
            continue
        except FetchError as error:
            if url == root:
                if error.status == 404:
                    raise BackupFailed(f"No author page exists at https://{host}/. Please check the name.") from error
                raise BackupFailed(f"Could not load https://{host}/ ({error}). Please try again later.") from error
            if error.status in (404, 410):
                # The live site links to something that no longer exists.
                # Nothing was lost, so this does not make the backup incomplete.
                result.dead_links.append(url)
                log(f"  Dead link on the live site: {url}")
                continue
            result.page_failures[url] = str(error)
            log(f"  Could not load {url}: {error}")
            continue

        final = canonical_page_url(final_url)
        if (urlsplit(final).hostname or "") != host:
            log(f"  {url} leads away from this author's site, so it was skipped")
            continue
        seen.add(final)
        if final in pages:
            continue
        pages[final] = html
        log(f"  Found {final}")

        for link in extract_links(html, final):
            if not is_crawlable(link, host, options.include_subpages):
                continue
            target = canonical_page_url(link)
            if target not in seen:
                seen.add(target)
                queue.append(target)

        if url == root:
            _add_profile_projects(fetcher, options, host, queue, seen, page_delay, result, log)

    log(f"Found {len(pages)} page(s).")
    return pages


def _add_profile_projects(fetcher, options, host, queue, seen, page_delay, result, log):
    """Queue projects from the author's profile, which is only read, never saved.

    An author's own site need not link to all their projects, while the profile
    lists every one. Only project links are taken: its "recent posts" feed links
    to comment pages for a random few projects, which repeat the project page.
    """
    profile = author_profile(options.author)
    status, robots_text = fetcher.get_text_optional(f"https://{ITCH_DOMAIN}/robots.txt")
    if status == 200 and not RobotRules(robots_text).allows(profile):
        result.listing_unverified = "the itch.io profile page is off limits to automated tools"
        log(f"Could not check the project list: {result.listing_unverified}.")
        return

    fetcher.pause(page_delay)
    try:
        _, html = fetcher.get_page(profile)
    except (FetchError, NotHtml) as error:
        result.listing_unverified = f"the itch.io profile page could not be read ({error})"
        log(f"Could not check the project list: {result.listing_unverified}. Projects not linked from the author's own site may be missing.")
        return

    added = 0
    for link in extract_links(html, profile):
        if not is_project_url(link, host):
            continue
        target = canonical_page_url(link)
        if target not in seen:
            seen.add(target)
            queue.append(target)
            added += 1
    log(f"The author's profile added {added} project(s) not linked from their front page.")


def _save_pages(pages, options, host, folder, store, result, log, progress):
    folder.mkdir(parents=True, exist_ok=True)
    page_files = {url: f"{page_stem(url)}.html" for url in pages}
    total = len(pages)
    log(f"Saving to {folder}")

    for number, (url, html) in enumerate(pages.items(), start=1):
        progress("save", number - 1, total)
        store.fetcher.pause(0)  # Pages whose assets are all reused never touch the network.
        stem = page_stem(url)
        log(f"[{number}/{total}] {url}")
        rewriter = PageRewriter(
            url, stem, folder / f"{stem}_files", store, page_files, host, options.full_size_images
        )
        target = folder / page_files[url]
        temporary = target.with_name(target.name + ".part")
        try:
            temporary.write_text(rewriter.rewrite(html), encoding="utf-8")
            os.replace(temporary, target)
        except OSError as error:
            result.page_failures[url] = f"could not write file: {error}"
            log(f"  Could not write {target.name}: {error}")
            continue
        result.pages_saved.append(url)
    progress("save", total, total)


def _write_report(result, options, folder):
    report = {
        "author": result.author,
        "source": author_root(result.author),
        "finished": datetime.now().isoformat(timespec="seconds"),
        "complete": result.clean,
        "stopped_early": result.stopped,
        "hit_page_limit": result.hit_page_limit,
        "project_list_unverified": result.listing_unverified,
        "pages": {url: f"{page_stem(url)}.html" for url in result.pages_saved},
        "page_failures": result.page_failures,
        "dead_links_on_live_site": result.dead_links,
        "asset_failures": result.asset_failures,
        "skipped_by_robots_txt": result.skipped_by_robots,
        "skipped_not_html": result.skipped_not_html,
        "assets_downloaded": result.assets_downloaded,
        "assets_already_present": result.assets_reused,
        "bytes_downloaded": result.bytes_downloaded,
        "options": {
            "include_subpages": options.include_subpages,
            "full_size_images": options.full_size_images,
            "page_delay": options.page_delay,
        },
    }
    (folder / REPORT_FILENAME).write_text(json.dumps(report, indent=2), encoding="utf-8")


def summarize(result):
    """A short human-readable account of how the backup went."""
    size_mb = result.bytes_downloaded / (1024 * 1024)
    lines = []
    if result.stopped:
        lines.append(f"Stopped early: {len(result.pages_saved)} of {len(result.pages_discovered)} pages saved. Run it again to finish.")
    else:
        lines.append(f"Done: {len(result.pages_saved)} pages saved, {result.assets_downloaded} files downloaded ({size_mb:.1f} MB).")
    if result.page_failures:
        lines.append(f"{len(result.page_failures)} page(s) could not be saved.")
    if result.asset_failures:
        lines.append(f"{len(result.asset_failures)} image or file(s) could not be saved. Those stay linked to the live site.")
    if result.hit_page_limit:
        lines.append("The page limit was reached, so the backup is incomplete.")
    if result.listing_unverified:
        lines.append(f"Some projects may be missing: {result.listing_unverified}.")
    if result.page_failures or result.asset_failures:
        lines.append(f"Details are in {REPORT_FILENAME}.")
    return "\n".join(lines)
