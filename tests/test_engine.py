"""Offline engine tests. Nothing here touches the network."""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from core import backup as backup_module
from core.assets import AssetStore, rewrite_css
from core.backup import BackupFailed, BackupOptions, run_backup
from core.fetcher import FetchError, NotHtml, _is_public_host
from core.rewriter import PageRewriter
from core.robots import RobotRules
from core.urls import (InvalidAuthorError, asset_filename, canonical_page_url, is_crawlable, page_stem, parse_author)

ITCH_ROBOTS = """
User-agent: Mediapartners-Google
Disallow:

User-agent: *
Disallow: /*/download/
Disallow: /*/rh/
Disallow: /*/rp/
Disallow: /-/
"""


class ParseAuthorTests(unittest.TestCase):
    def test_accepted_forms(self):
        for text in ("reactorcore", "reactorcore.itch.io", "https://reactorcore.itch.io/",
                     "http://Reactorcore.itch.io/some-project?x=1", "  reactorcore  ",
                     "https://itch.io/profile/reactorcore"):
            self.assertEqual(parse_author(text), "reactorcore", text)

    def test_rejected_forms(self):
        for text in ("", "https://itch.io/", "https://example.com/", "https://www.itch.io/games",
                     "https://static.itch.io/", "https://evil.itch.io.example.com/", "bad_name!"):
            with self.assertRaises(InvalidAuthorError, msg=text):
                parse_author(text)


class ScopeTests(unittest.TestCase):
    host = "a.itch.io"

    def test_project_and_subpages_in_scope(self):
        self.assertTrue(is_crawlable("https://a.itch.io/game", self.host))
        self.assertTrue(is_crawlable("https://a.itch.io/game/devlog/1/post", self.host))

    def test_subpages_can_be_excluded(self):
        self.assertTrue(is_crawlable("https://a.itch.io/game", self.host, False))
        self.assertFalse(is_crawlable("https://a.itch.io/game/devlog/1/post", self.host, False))

    def test_other_hosts_and_actions_out_of_scope(self):
        for url in ("https://b.itch.io/game", "https://itch.io/c/1/x", "mailto:a@b.c",
                    "https://a.itch.io/game/purchase", "https://a.itch.io/game/rate",
                    "https://a.itch.io/game/download/abc", "https://a.itch.io/-/x"):
            self.assertFalse(is_crawlable(url, self.host), url)

    def test_canonical_merges_variants(self):
        expected = "https://a.itch.io/game"
        for url in ("http://A.itch.io/game/", "https://a.itch.io/game#comments", "https://a.itch.io/game?utm_source=x"):
            self.assertEqual(canonical_page_url(url), expected)
        self.assertEqual(canonical_page_url("https://a.itch.io/game?page=2"), "https://a.itch.io/game?page=2")
        self.assertEqual(canonical_page_url("https://a.itch.io"), "https://a.itch.io/")


class FilenameTests(unittest.TestCase):
    def test_page_stems(self):
        self.assertEqual(page_stem("https://a.itch.io/"), "index")
        self.assertEqual(page_stem("https://a.itch.io/game"), "game")
        self.assertEqual(page_stem("https://a.itch.io/game/devlog/1/post"), "game__devlog__1__post")
        self.assertEqual(page_stem("https://a.itch.io/game?page=2"), "game__page-2")

    def test_dangerous_page_names_are_made_unique(self):
        self.assertNotEqual(page_stem("https://a.itch.io/index"), "index")
        self.assertNotEqual(page_stem("https://a.itch.io/con"), "con")
        self.assertNotEqual(page_stem("https://a.itch.io/GAME"), page_stem("https://a.itch.io/game"))
        self.assertLess(len(page_stem("https://a.itch.io/" + "x" * 500)), 110)

    def test_asset_names_are_safe_on_windows(self):
        for url in ("https://static.itch.io/user.css?1793954460",
                    "https://img.itch.zone/aW1n/315x250%23cb/Ao%2FyKc.jpg",
                    "https://x.example/..%2F..%2Fevil.exe",
                    "https://x.example/CON",
                    'https://x.example/a<b>:"|?.png'):
            name = asset_filename(url)
            self.assertRegex(name, r"^[a-z0-9._-]+$", url)
            self.assertNotIn("/", name)
            self.assertFalse(name.startswith("."))

    def test_query_string_distinguishes_assets(self):
        self.assertNotEqual(asset_filename("https://s/a.css?1"), asset_filename("https://s/a.css?2"))


class RobotsTests(unittest.TestCase):
    def test_itch_wildcard_rules(self):
        rules = RobotRules(ITCH_ROBOTS)
        self.assertTrue(rules.allows("https://a.itch.io/game"))
        self.assertTrue(rules.allows("https://a.itch.io/"))
        self.assertFalse(rules.allows("https://a.itch.io/game/download/abc"))
        self.assertFalse(rules.allows("https://a.itch.io/game/rh/x"))
        self.assertFalse(rules.allows("https://a.itch.io/-/thing"))

    def test_longest_match_and_anchor(self):
        rules = RobotRules("User-agent: *\nDisallow: /a\nAllow: /a/b\nDisallow: /*.xml$\nCrawl-delay: 3")
        self.assertFalse(rules.allows("https://x/a/c"))
        self.assertTrue(rules.allows("https://x/a/b"))
        self.assertFalse(rules.allows("https://x/feed.xml"))
        self.assertTrue(rules.allows("https://x/feed.xml?y"))
        self.assertEqual(rules.crawl_delay, 3)

    def test_other_agent_groups_are_ignored(self):
        self.assertTrue(RobotRules("User-agent: Googlebot\nDisallow: /").allows("https://x/y"))


class SafetyTests(unittest.TestCase):
    def test_private_hosts_refused(self):
        for host in ("localhost", "127.0.0.1", "192.168.1.1", "10.0.0.5", "169.254.169.254", "printer.local"):
            _is_public_host.cache_clear()
            self.assertFalse(_is_public_host(host), host)


class FakeFetcher:
    """Serves assets from a dict and records how often each was requested."""

    def __init__(self, assets):
        self.assets = assets
        self.requests = []
        self.bytes_downloaded = 0

    def pause(self, seconds):
        pass

    def get_asset(self, url):
        self.requests.append(url)
        if url not in self.assets:
            raise FetchError("HTTP 404", 404)
        return self.assets[url]


class AssetStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_shared_asset_is_downloaded_once(self):
        fetcher = FakeFetcher({"https://s/a.png": (b"PNG", "image/png")})
        store = AssetStore(fetcher, 0)
        one = store.localize("https://s/a.png", self.root / "one_files")
        two = store.localize("https://s/a.png", self.root / "two_files")
        self.assertEqual(fetcher.requests, ["https://s/a.png"])
        self.assertEqual((self.root / "one_files" / one).read_bytes(), b"PNG")
        self.assertEqual((self.root / "two_files" / two).read_bytes(), b"PNG")

    def test_css_dependencies_follow_shared_stylesheet(self):
        fetcher = FakeFetcher({
            "https://s/a.css?1": (b'body{background:url(img/bg.png)} @import "b.css";', "text/css"),
            "https://s/img/bg.png": (b"BG", "image/png"),
            "https://s/b.css": (b"p{color:red}", "text/css"),
        })
        store = AssetStore(fetcher, 0)
        name = store.localize("https://s/a.css?1", self.root / "one_files")
        css = (self.root / "one_files" / name).read_text()
        self.assertNotIn("https://", css)
        store.localize("https://s/a.css?1", self.root / "two_files")
        self.assertEqual(len(list((self.root / "two_files").iterdir())), 3)
        self.assertEqual(len(fetcher.requests), 3)

    def test_existing_file_is_not_downloaded_again(self):
        assets = {"https://s/a.png": (b"PNG", "image/png")}
        AssetStore(FakeFetcher(assets), 0).localize("https://s/a.png", self.root / "p_files")
        second = FakeFetcher(assets)
        store = AssetStore(second, 0)
        self.assertIsNotNone(store.localize("https://s/a.png", self.root / "p_files"))
        self.assertEqual(second.requests, [])
        self.assertEqual(store.reused, 1)

    def test_failure_is_recorded_and_not_retried(self):
        fetcher = FakeFetcher({})
        store = AssetStore(fetcher, 0)
        self.assertIsNone(store.localize("https://s/gone.png", self.root / "p_files"))
        self.assertIsNone(store.localize("https://s/gone.png", self.root / "q_files"))
        self.assertEqual(len(fetcher.requests), 1)
        self.assertIn("https://s/gone.png", store.failures)

    def test_css_data_uri_untouched(self):
        css = "a{background:url(data:image/png;base64,AAAA)}"
        self.assertEqual(rewrite_css(css, "https://s/x.css", lambda u: "LOCAL"), css)


PAGE = """<!DOCTYPE html><html><head><meta name="csrf_token" value="SECRET"/>
<link rel="stylesheet" href="https://static.itch.io/game.css?123"/>
<link rel="canonical" href="/game"/>
<meta property="og:image" content="https://img.itch.zone/cover/original/c.png"/>
<meta name="twitter:image" content="https://img.itch.zone/cover/508x254/t.png"/>
<style>body{background:url(https://img.itch.zone/bg/original/b.png)}</style>
<script src="https://static.itch.io/game.min.js?123"></script>
<script data-src="https://static.itch.io/react.min.js?123"></script>
</head><body>
<img data-lazy_src="https://img.itch.zone/thumb/315x250/l.jpg" class="lazy_loaded"/>
<img src="https://img.itch.zone/s/347x500/s.png" srcset="https://img.itch.zone/s/347x500/s.png 1x, https://img.itch.zone/s/794x1000/s2.png 2x"/>
<div data-gif="https://img.itch.zone/g/original/g.gif"></div>
<div style="background-image:url('https://img.itch.zone/i/original/i.png')"></div>
<a href="https://img.itch.zone/s/original/full.png"><img src="https://img.itch.zone/s/347x500/s.png"/></a>
<a href="https://a.itch.io/other#comments">other</a>
<a href="/missing">missing</a>
<a href="https://a.itch.io/game/purchase">buy</a>
<a href="https://b.itch.io/elsewhere">elsewhere</a>
<a href="https://example.com/file.zip">zip</a>
<a href="mailto:x@y.z">mail</a>
<form action="/game/rate"></form>
<iframe src="https://www.youtube.com/embed/x"></iframe>
</body></html>"""


class RewriterTests(unittest.TestCase):
    def rewrite(self, full_size=True):
        store = mock.Mock()
        store.localize.side_effect = lambda url, folder: "F" + str(abs(hash(url)))
        rewriter = PageRewriter(
            "https://a.itch.io/game", "game", Path("game_files"), store,
            {"https://a.itch.io/other": "other.html"}, "a.itch.io", full_size,
        )
        return rewriter.rewrite(PAGE), store

    def test_requisites_become_local(self):
        html, store = self.rewrite()
        fetched = {call.args[0] for call in store.localize.call_args_list}
        for url in ("https://static.itch.io/game.css?123", "https://static.itch.io/game.min.js?123",
                    "https://static.itch.io/react.min.js?123", "https://img.itch.zone/cover/original/c.png",
                    "https://img.itch.zone/bg/original/b.png", "https://img.itch.zone/thumb/315x250/l.jpg",
                    "https://img.itch.zone/s/794x1000/s2.png", "https://img.itch.zone/g/original/g.gif",
                    "https://img.itch.zone/i/original/i.png", "https://img.itch.zone/s/original/full.png"):
            self.assertIn(url, fetched)
            self.assertNotIn(url, html)

    def test_lazy_image_gets_a_real_src(self):
        html, _ = self.rewrite()
        self.assertRegex(html, r'<img[^>]*\bsrc="game_files/[^"]+"[^>]*lazy_loaded|<img[^>]*lazy_loaded[^>]*\bsrc="game_files/')

    def test_links(self):
        html, _ = self.rewrite()
        self.assertIn('href="other.html#comments"', html)
        self.assertIn('href="https://a.itch.io/missing"', html)
        self.assertIn('href="https://a.itch.io/game/purchase"', html)
        self.assertIn('href="https://b.itch.io/elsewhere"', html)
        self.assertIn('href="https://example.com/file.zip"', html)
        self.assertIn('href="mailto:x@y.z"', html)
        self.assertIn('action="https://a.itch.io/game/rate"', html)
        self.assertIn('href="https://a.itch.io/game"', html)

    def test_only_page_content_is_downloaded(self):
        _, store = self.rewrite()
        fetched = {call.args[0] for call in store.localize.call_args_list}
        self.assertNotIn("https://example.com/file.zip", fetched)
        self.assertNotIn("https://www.youtube.com/embed/x", fetched)
        self.assertNotIn("https://img.itch.zone/cover/508x254/t.png", fetched)

    def test_full_size_can_be_turned_off(self):
        html, store = self.rewrite(full_size=False)
        self.assertIn('href="https://img.itch.zone/s/original/full.png"', html)

    def test_csrf_token_removed(self):
        html, _ = self.rewrite()
        self.assertNotIn("SECRET", html)


class PipelineTests(unittest.TestCase):
    PAGES = {
        "https://a.itch.io/": '<a href="/game">g</a> <a href="/dead">d</a> <a href="/file.zip">z</a> '
                              '<a href="/game/download/x">dl</a> <a href="/moved">m</a> <img src="https://img.itch.zone/t/a.png"/>',
        "https://a.itch.io/game": '<a href="/">home</a> <a href="/game/devlog/1/post">post</a> <img src="https://img.itch.zone/t/a.png"/>',
        "https://a.itch.io/game/devlog/1/post": '<a href="/game">back</a> <img src="https://img.itch.zone/gone.png"/>',
        "https://a.itch.io/hidden": '<p>only the profile links here</p>',
        "https://itch.io/profile/a": '<a href="https://a.itch.io/hidden">h</a> <a href="https://a.itch.io/game/comments">c</a> '
                                     '<a href="https://b.itch.io/theirs">other author</a>',
    }

    def fake_fetcher_class(self):
        pages = self.PAGES
        requested = self.requested = []

        class Fake:
            def __init__(self, stop_event, log):
                self.stop_event = stop_event
                self.bytes_downloaded = 0

            def pause(self, seconds):
                if self.stop_event.is_set():
                    raise backup_module.BackupStopped()

            def get_text_optional(self, url):
                return 200, ITCH_ROBOTS

            def get_page(self, url):
                requested.append(url)
                if url == "https://a.itch.io/file.zip":
                    raise NotHtml("application/zip")
                if url == "https://a.itch.io/moved":
                    return "https://elsewhere.example/", "<p>away</p>"
                if url not in pages:
                    raise FetchError("HTTP 404", 404)
                return url, pages[url]

            def get_asset(self, url):
                if "gone" in url:
                    raise FetchError("HTTP 404", 404)
                return b"IMG", "image/png"

        return Fake

    def run_it(self, **kwargs):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        options = BackupOptions("a", Path(temp.name), page_delay=0, asset_delay=0, **kwargs)
        with mock.patch.object(backup_module, "Fetcher", self.fake_fetcher_class()):
            return run_backup(options), Path(temp.name) / "a"

    def test_full_backup(self):
        result, folder = self.run_it()
        self.assertEqual(len(result.pages_saved), 4)
        self.assertTrue((folder / "index.html").exists())
        self.assertTrue((folder / "hidden.html").exists())
        self.assertTrue((folder / "game.html").exists())
        self.assertTrue((folder / "game__devlog__1__post.html").exists())
        index = (folder / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="game.html"', index)
        self.assertIn('href="https://a.itch.io/dead"', index)
        self.assertIn("index_files/", index)
        self.assertFalse(list(folder.rglob("*.part")))

    def test_results_and_report(self):
        result, folder = self.run_it()
        self.assertFalse(result.clean)
        self.assertIn("https://a.itch.io/dead", result.dead_links)
        self.assertEqual(result.page_failures, {})
        self.assertIn("https://a.itch.io/file.zip", result.skipped_not_html)
        self.assertIn("https://img.itch.zone/gone.png", result.asset_failures)
        self.assertNotIn("https://a.itch.io/game/download/x", self.requested)
        report = json.loads((folder / "backup-report.json").read_text(encoding="utf-8"))
        self.assertFalse(report["complete"])
        self.assertEqual(report["pages"]["https://a.itch.io/"], "index.html")

    def test_profile_is_read_but_not_saved_and_only_gives_projects(self):
        result, folder = self.run_it()
        self.assertIn("https://itch.io/profile/a", self.requested)
        self.assertNotIn("https://itch.io/profile/a", result.pages_saved)
        self.assertNotIn("https://a.itch.io/game/comments", self.requested)
        self.assertNotIn("https://b.itch.io/theirs", self.requested)

    def test_unreadable_profile_is_flagged(self):
        original = self.PAGES
        self.PAGES = {k: v for k, v in original.items() if "profile" not in k}
        result, _ = self.run_it()
        self.assertIn("profile", result.listing_unverified)
        self.assertEqual(len(result.pages_saved), 3)

    def test_no_subpages(self):
        result, folder = self.run_it(include_subpages=False)
        self.assertEqual(len(result.pages_saved), 3)
        self.assertFalse((folder / "game__devlog__1__post.html").exists())

    def test_discover_only_writes_nothing(self):
        result, folder = self.run_it(discover_only=True)
        self.assertEqual(len(result.pages_discovered), 4)
        self.assertFalse(folder.exists())

    def test_page_limit_is_reported(self):
        result, _ = self.run_it(max_pages=1)
        self.assertTrue(result.hit_page_limit)
        self.assertFalse(result.clean)
        self.assertEqual(len(result.pages_saved), 1)

    def test_missing_author_fails_clearly(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        options = BackupOptions("nobody", Path(temp.name), page_delay=0, asset_delay=0)
        with mock.patch.object(backup_module, "Fetcher", self.fake_fetcher_class()):
            with self.assertRaisesRegex(BackupFailed, "No author page"):
                run_backup(options)

    def test_stop_keeps_partial_result(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        stop = threading.Event()
        options = BackupOptions("a", Path(temp.name), page_delay=0, asset_delay=0)

        def progress(phase, done, total):
            if phase == "save" and done == 1:
                stop.set()

        with mock.patch.object(backup_module, "Fetcher", self.fake_fetcher_class()):
            result = run_backup(options, progress=progress, stop_event=stop)
        self.assertTrue(result.stopped)
        self.assertEqual(len(result.pages_saved), 1)
        self.assertFalse(result.clean)


if __name__ == "__main__":
    unittest.main()
