"""Command line version of the backup, using the same engine as the GUI.

    python cli.py                                  uses config.json
    python cli.py someauthor -o "D:/My Backups"
    python cli.py someauthor --discover-only       lists pages, saves nothing
"""

import argparse
import sys

from core.backup import BackupFailed, BackupOptions, DEFAULT_MAX_PAGES, run_backup, summarize
from core.urls import InvalidAuthorError, parse_author
from utils.config import load_config, resolve_output_folder


def main():
    config = load_config()
    parser = argparse.ArgumentParser(description="Back up an itch.io author's public pages.")
    parser.add_argument("author", nargs="?", default=config["author_url"], help="author name or page URL")
    parser.add_argument("-o", "--output", default=config["output_folder"], help="output folder")
    parser.add_argument("--no-subpages", action="store_true", help="only the root and project pages")
    parser.add_argument("--no-full-size", action="store_true", help="skip full-size screenshot originals")
    parser.add_argument("--delay", type=float, default=config["page_delay"], help="seconds between pages")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--discover-only", action="store_true", help="list the pages and save nothing")
    args = parser.parse_args()

    if not args.output and not args.discover_only:
        parser.error("no output folder: pass -o or set output_folder in config.json")

    try:
        author = parse_author(args.author)
    except InvalidAuthorError as error:
        parser.error(str(error))

    options = BackupOptions(
        author=author,
        output_dir=resolve_output_folder(args.output or "."),
        include_subpages=not args.no_subpages,
        full_size_images=not args.no_full_size,
        page_delay=args.delay,
        max_pages=args.max_pages,
        discover_only=args.discover_only,
    )

    try:
        result = run_backup(options, log=lambda message: print(message, flush=True))
    except BackupFailed as error:
        print(f"Backup failed: {error}", file=sys.stderr)
        return 2

    if args.discover_only:
        print("\n".join(result.pages_discovered))
        print(f"\n{len(result.pages_discovered)} pages, {len(result.dead_links)} dead links, {len(result.page_failures)} failed to load, "
              f"{len(result.skipped_by_robots)} blocked by robots.txt, {len(result.skipped_not_html)} not web pages")
        return 0 if not result.page_failures else 1

    print()
    print(summarize(result))
    return 0 if result.clean else 1


if __name__ == "__main__":
    sys.exit(main())
