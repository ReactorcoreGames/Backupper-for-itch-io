# Promo Doc: Backupper for itch.io

Internal document, not shipped in the release zip.

## Strategy

The core audience is itch.io creators who have put years of work into their pages and have no export button. The hook is fear of loss: a page edit, an account problem or a site change can erase descriptions, devlogs and screenshots that exist nowhere else. A second, smaller audience is archivists who want to preserve pages by creators they care about.

Lead with the concrete finding that a simple scraper misses things: this tool checks the author's full profile, so it catches projects the front page doesn't link to. On the Reactorcore page itself, that was 32 projects.

Be upfront that it saves pages and not the downloadable files. This prevents disappointed users, and it also tells creators and itch.io that the tool can't be used to take paid content.

**Business model, decided.** Free with optional pay what you want, MIT licensed. The natural audience is other creators, who are also the people most likely to follow you and share tools, so this should bring more traffic and goodwill than a fixed price.

**The itch.io logo** is used only on the program's button that opens the official site, and the program, readme and listing all state that this is unofficial. The owner has reviewed and accepted this.

## Marketing Targets

These are from general knowledge. The owner has reviewed the list.

1. **itch.io community forums**, the release announcement boards. Persistent, and exactly the right audience.
2. **itch.io tag pages for tools**, reached through good tags on the listing, which people browse organically.
3. **AlternativeTo**, listed as an alternative to general website copiers such as HTTrack.
4. **GitHub topics** such as `itch-io` and `website-backup`, if the code goes public.
5. **r/DataHoarder**, a community focused on preserving web content. I can't access Reddit, so read its self-promotion rules first.

---

## itch.io

### Page setup

butler can only upload the build, so this page has to be created by hand first at https://itch.io/game/new.

| Field | Value |
|---|---|
| Title | Backupper for itch.io |
| Project URL | backupper-for-itch-io |
| Short description | The subtitle below |
| Classification | Tools |
| Kind of project | Downloadable |
| Release status | Released |
| Pricing | $0 or donate |
| Description | The description below |
| Tags | The tags below |
| Cover image | `promo/thumbnail_630x500.jpg` |
| Banner image, in Edit theme | `promo/cover_1280x720.jpg` |
| Screenshots | `promo/screenshot_1.png` to `promo/screenshot_4.png` |

Save it as a draft, then upload the build from the project root in Git Bash. Try it with `--dry-run` first.

```
/c/butler/butler.exe push --dry-run dist/Backupper-for-itch-io.zip reactorcore/backupper-for-itch-io:windows --userversion 1.0.0
/c/butler/butler.exe push dist/Backupper-for-itch-io.zip reactorcore/backupper-for-itch-io:windows --userversion 1.0.0
```

Use a freshly built zip and not the folder, since running the exe from the folder writes your `config.json` into it. Once the build shows on the page, set Visibility to Public.

### Name

Backupper for itch.io

### Subtitle (100 characters max)
Main:
Backup your own author pages from itch.io

Alt:
Save a browsable offline copy of any itch.io author's page, with every project page and devlog.

### Description
```
# Backupper for itch.io

This is a windows program to download a local copy of all of your author pages on itch.io for safekeeping. 

Its intended to safeguard you if itch.io ever goes down so you prevent losing any descriptions/themes/details/images that you've worked hard to set up and fill.

Note: **It does not and cannot download actual files/games/assets** - neither free nor paid - it can only download the pages that show them off.

## About

**Your itch.io page has no export button. This is the next best thing.**

Years of project descriptions, screenshots and devlogs live on your page, and most creators have no other copy. Backupper for itch.io saves all of it to your computer in one click, as real web pages you can browse offline.

### **How it works**

1. Enter an author's page
2. Choose a folder
3. Press Start Backup

### **What you get**

- The front page and every published project page, including projects your front page doesn't link to
- Devlog lists and devlog posts
- All page images, plus full-size screenshots
- Working links between the saved pages
- A report of exactly what was saved and anything that failed

Pages are saved like a browser's "Save Page As": an `.html` file and a folder of images. There's no special viewer and no lock-in, so they open in any browser.

Run it again any time to update your backup. Images you already have aren't downloaded again.

### **What it doesn't save**

The downloadable files themselves, browser-playable games, embedded videos and anything behind a login. Keep your own copies of your game and asset files. This tool can't be used to get paid content.

### **Plays nice**

It waits between pages, slows down when the server asks and obeys the site's robots.txt.

Windows 10 and 11. Nothing else to install.

Free to use, and you can pay what you want if it saves your work. MIT licensed.

*This is an unofficial tool. It is not made by, endorsed by or affiliated with itch.io.*

### Check out everything else I do: ✨🚀
https://linktr.ee/reactorcore

Enjoy and stay safe!
-Reactorcore
```
### Tags

backup, archive, offline, website-backup, itchio, utility, tool, windows, indie-dev, preservation

---

## GitHub

### Description

Windows app that saves a browsable offline copy of any itch.io author's page, with all project pages, devlogs and images.

### Topics

itch-io
backup
website-backup
web-archive
offline
web-scraper
python
ttkbootstrap
windows
digital-preservation

---

## YouTube

Upload `trailer/backupper_trailer_1080p.mp4` and set `trailer/youtube_thumbnail.png` as the thumbnail. Both come from `tools/make_trailer.py`. The attribution in the description is required by the music's CC BY 4.0 license, so keep it in any reupload or cut of this video.

### Title

Backupper for itch.io - Save an Offline Copy of Your Author Page

### Description
```
Your itch.io page has no export button. This is the next best thing.

Backupper for itch.io is a free Windows program that saves a browsable offline copy of an author's page, so years of descriptions, devlogs and screenshots aren't only stored in one place.

Get it here: https://reactorcore.itch.io/backupper-for-itchio

HOW IT WORKS
1. Enter an author's page
2. Choose a folder
3. Press Start Backup

WHAT YOU GET
- The front page and every published project page, including projects your front page doesn't link to
- Devlog lists and devlog posts
- All page images, plus full-size screenshots
- Working links between the saved pages
- A report of exactly what was saved and anything that failed

Pages are saved like a browser's "Save Page As", so they open in any browser with no special viewer. Run it again any time to update your backup.

WHAT IT DOESN'T SAVE
It saves the pages, not the downloadable files. Keep your own copies of your game and asset files. This tool can't be used to get paid content.

Windows 10 and 11. Free to use, pay what you want if it saves your work. MIT licensed.

This is an unofficial tool. It is not made by, endorsed by or affiliated with itch.io.

MUSIC
Guiton Sketch by Kevin MacLeod is licensed under a Creative Commons Attribution 4.0 license. https://creativecommons.org/licenses/by/4.0/
Source: http://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100473
Artist: http://incompetech.com/

MY LINKS
Home/Links: https://linktr.ee/reactorcore
Releases: https://reactorcore.itch.io
Blog: https://www.patreon.com/ReactorcoreGames
Discord: https://discord.gg/UdRavGhj47
Catalog: https://reactorcoregames.github.io/
```
### Tags

itch.io, itchio, backup, website backup, offline backup, web archive, indie dev, game dev tools, indie game developer, digital preservation, windows software, free software, open source, save page as, devlog
