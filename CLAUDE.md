# Backupper for itch.io — Claude Session Context

## What This Program Does

A Windows desktop program that makes a browsable offline copy of any author's public itch.io page (`https://<author>.itch.io/`): the root page, every project page and their subpages such as devlogs, each saved in Firefox "Save Page As" style as `<name>.html` plus a `<name>_files/` folder. The user picks the author and the output folder. It is not limited to one author.

## Key Docs

- `todo-checklist.md` — what is done and what is left. Read this first and keep it current.
- `promo.md` — store page fields, promo copy and push commands.

## Tech Stack

Python 3.13, requests, beautifulsoup4, ttkbootstrap 2.x, PyInstaller `--onedir`. Lato is bundled in `assets/fonts/` and loaded privately at runtime, so the user does not need it installed.

## Layout

- `main.py` — GUI entry point. `cli.py` — source-only command line entry point, same engine, not part of the exe.
- `core/urls.py` — author parsing, crawl scope, deterministic local filenames.
- `core/robots.py` — robots.txt matcher.
- `core/fetcher.py` — HTTP with retries, pacing and limits.
- `core/assets.py` — downloads page assets, reuses them across pages.
- `core/rewriter.py` — rewrites HTML and CSS to point at local files.
- `core/backup.py` — the crawl and save pipeline. Everything above is driven from here.
- `gui/` — `app.py` and `theme.py`. `utils/config.py` — `config.json` persistence.
- `tools/make_icon.py` — builds `assets/icon.ico` from `promo/icon_og.jpg`. `tools/make_promo_images.py` — builds store images from `promo/cover_art.jpg` and frames `promo/raw_*.png` captures. `tools/make_zip.py` — zips the release. `tools/make_trailer.py` — renders the YouTube trailer and thumbnail into `trailer/`, not part of the release.
- `build_release.bat` — builds `dist/<project>/` and the release zip.

## Non-Obvious Decisions

**The output location is never hardcoded.** `downloaded-backups/` is purely the owner's preference, stored in the gitignored `config.json`. Defaults in `utils/config.py` must stay empty so a release build asks the user. `build_release.bat` must never ship `config.json`. A relative `output_folder` resolves against the program folder.

**The author's front page is not a complete project list.** On reactorcore.itch.io, 32 of 169 projects were reachable only through `https://itch.io/profile/<author>`, including the project named in the original request. `_add_profile_projects` reads that page for top-level project links and never saves it. Its "recent posts" feed also links to `/comments` pages for a few projects, which repeat what the project page shows, so those are not taken. A front-page-only crawl looks like it worked and silently loses data, so if the profile can't be read the backup is reported as not verified.

**itch.io rate limits its main site harder than author subdomains.** `itch.io` returned 429 at about one request per second with no `Retry-After` header, while 300 author-subdomain pages at one per second were fine. 429s back off from 30 seconds.

**Dead links are not failures.** A 404 for a page the live site links to means nothing was lost, so it is listed separately and does not mark the backup incomplete.

**Python's `urllib.robotparser` cannot be used.** itch.io's robots.txt uses wildcard rules such as `Disallow: /*/download/`, which the stdlib treats as literal prefixes, so it would allow those paths. `core/robots.py` implements wildcard matching with longest-match precedence.

**Only public pages and what they display are saved.** Uploaded game and tool files, the things behind purchase and download buttons, are deliberately not fetched. `core/urls.py` excludes those routes, and non-HTML responses on the author host are abandoned without reading the body. Say this plainly in user-facing docs.

**Page HTML is fetched in a first phase and saved in a second.** Links between pages are rewritten to local files only when the target really was fetched, which needs the full page list up front. A dead link stays as its absolute URL instead of pointing at a missing file.

**Asset filenames carry a hash of the full URL.** itch.io image URLs contain `%2F` and `+`, and the CDN's `?1793954460` version suffix is illegal in Windows filenames. That suffix silently broke every CSS and JS download in the legacy script. Identity is the hash, so the same URL always maps to the same file across runs, which is what makes re-runs incremental.

**Assets repeated across pages are hardlinked, not re-downloaded.** Every page gets its own `_files/` folder so it stays self-contained like a real Save Page As, while the shared CSS and JS cost one download and, on NTFS, one copy on disk. Falls back to a plain copy across volumes. Stylesheets are never reused from a previous run: their rewritten contents no longer reveal which fonts they need, so a re-run fetches them again.

**Hostile pages are assumed.** The tool points at arbitrary third-party authors, so asset URLs are untrusted: filenames are fully sanitised, private and loopback addresses are refused even through redirects, and download sizes are capped.

**Light theme on purpose.** It follows https://itch.io/press-kit. The press kit's `#fa5c5c` fails the 4.5:1 contrast rule with white text, so buttons use a deeper crimson and `#fa5c5c` is kept for non-text accents. `#858585` also fails on white and is not used for text. `tests/test_theme.py` enforces this.

**Butler can't create or edit project pages.** It only uploads builds to a page that already exists, and itch.io's documented server API has no endpoints for editing them either. The page is created by hand. `promo.md` has the field values and push commands.

**Not affiliated with itch.io.** The itch.io logo is not used in the icon or promo art, the product name uses "for itch.io" and the docs state it is unofficial. The header's visit button uses the owner's artwork, kept white on a coral button because the press kit asks that the logo stays black or white. The button colours live in `tools/make_itch_button.py`. The source SVG is not in the repo, so that tool only runs if the artwork is put back at `docs/visit itch io.svg`. The finished images are in `assets/`. The press kit writes the name in lowercase, `itch.io`.

**Free with optional pay what you want, MIT licensed.** The owner's decision. Promo copy must not state specific amounts.

## Environment Notes

- ttkbootstrap 2.x moved `ToolTip` to `ttkbootstrap.widgets`. The older `ttkbootstrap.tooltip` path in the house docs no longer exists.
- A hook blocks permanent deletes. Move things to `C:\trash` instead.
- Run the build from Git Bash as `./build_release.bat`. It refuses to run while the exe is open from `dist/`. Git Bash's Unix `find` shadows the Windows one on PATH, so batch files must call `find.exe` by full path.
- `python -I` hides the user site-packages where the dependencies live on this machine.
- Backslashes in Bash heredocs get mangled in this environment. Write Python files with the Write tool.
- BAIG, the image generator, is at `C:\ClaudeWorkspace\AI image gen batch program\cli.py`. Use `--model klein4b`. It takes a `--prompt` for one-offs. Never print its credentials.

## Running

```
python main.py
python cli.py --help
python -m unittest discover -s tests
```
