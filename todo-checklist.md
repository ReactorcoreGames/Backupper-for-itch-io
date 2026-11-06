# Todo Checklist

Update this as work progresses, so a new session can pick up from here.

## Assessment

- [x] Read the original prompt, the legacy script and the docs
- [x] Test the legacy script against the live site (verdict: runs but does not back up correctly)

## Engine

- [x] `core/` URL scope, robots, fetcher, assets, rewriter, backup pipeline
- [x] `cli.py`
- [x] Offline unit tests
- [x] Discovery run against the live site, tune the excluded routes
- [x] Read the author's profile too, since the front page missed 32 projects

## GUI

- [x] `utils/config.py`, local `config.json` pointing at `downloaded-backups/`
- [x] `gui/theme.py` in the itch.io look, bundled Lato
- [x] `gui/app.py` and `main.py`
- [x] Icon from BAIG, `assets/icon.ico`

## The Actual Backup

- [x] Run the full backup of reactorcore.itch.io into `downloaded-backups/` (301 pages, all 169 profile projects)
- [x] Verify it: completeness, remaining remote references, renders offline in Firefox and Edge
- [ ] Optional: re-run to retry 3 failed third-party badge images. Owner prefers not to stress itch.io, so only if wanted.

## Release Materials

- [x] Thumbnail 630x500 and cover 1280x720 in `promo/`
- [x] Real screenshots: `promo/raw_*.png`, then `tools/make_promo_images.py`
- [x] `readme.md`, `guide.md`, `promo.md`
- [x] `build_release.bat`, first build works
- [x] Rebuild with the zip fix and screenshots, confirm the exe launches
- [x] Header button to itch.io from the owner's SVG
- [x] Owner tested the packaged exe on skelegant.itch.io: 68 pages, 303 files, no failures, recovered from a 429 by itself
- [ ] Not yet exercised in the packaged build: Stop, and running again to resume. Both pass in the unit tests.
- [x] MIT `LICENSE`, shipped in the release
- [x] `.gitignore`
- [x] Move legacy files to `old wip/`
- [x] YouTube trailer and text-only thumbnail in `trailer/`, copy in `promo.md`

## Owner Only

- [x] Decide pricing and license: free with optional pay what you want, MIT
- [x] Create the itch.io page by hand, using the setup table in `promo.md`
- [x] Push the build with butler (commands in `promo.md`) (Author: no need, I did it manually.)
- [x] Graduate the project to `c:/14 Repos`
