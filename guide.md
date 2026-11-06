# How to Use Backupper for itch.io

## Quickstart

1. Unzip the download anywhere and run `Backupper-for-itch-io.exe`.
2. Enter the author's page, like `https://example.itch.io/`, or just `example`.
3. Press **Choose Output Folder** and pick where the backup should go.
4. Press **Start Backup**.
5. When it finishes, press **View Backup in Browser**.

Keep the exe next to its `_internal` folder, since it needs that folder to run. If Windows SmartScreen warns about an unrecognised program, choose "More info" and then "Run anyway".

## Where your backup ends up

Each author gets their own subfolder inside the folder you chose:

```
Your Folder/
└── example/
    ├── index.html                 the front page, open this to start browsing
    ├── index_files/
    ├── some-game.html
    ├── some-game_files/
    ├── some-game__devlog.html
    ├── some-game__devlog__123__first-post.html
    └── backup-report.json
```

Links between saved pages work offline. Links to anything that wasn't saved, like purchase buttons or other authors, still go to the live site.

Pages repeat a lot of the same files. On a normal Windows drive those repeats are stored only once, using hard links, so the folder takes up less disk space than Windows Explorer's size count suggests. If you copy the backup to another drive, the copy may become larger.

## Options

| Option | What it does |
|---|---|
| Include devlogs and other subpages | Turn off to save only the front page and the project pages. |
| Save full-size screenshots | Turn off for a smaller backup with only the image sizes shown on the page. |
| Seconds to wait between pages | Higher is gentler on itch.io's servers but slower. The minimum is 0.5. |

## Updating a backup

Run it again with the same author and folder. Pages are refreshed, while images already saved aren't downloaded again, so it's much faster. This also finishes a backup that you stopped or that was interrupted. Pages removed from the live site stay in your backup.

## If something goes wrong

- **The status line turns amber.** The backup finished, but something couldn't be saved. See `backup-report.json` in the author's folder, then try running it again. Saved pages keep a link to the live site for any image that failed.
- **"Server said 429" in the log.** itch.io asked the program to slow down. It waits and retries by itself, so you don't need to do anything. If it happens a lot, raise the seconds between pages.
- **"Dead link on the live site" in the log.** The author's page links to something that no longer exists. This isn't a problem with your backup.
- **A saved page looks wrong.** Keep the `.html` file next to its `_files` folder, because each page needs its folder to display.

## What's not included

Downloadable files, browser-playable games, embedded videos and anything needing a login are not saved. See `readme.md` for details.

## Contact

mailto:reactorcoregames@gmail.com

---

Check out everything else I do: ✨🚀

https://linktr.ee/reactorcore

https://reactorcore.itch.io/

-Reactorcore

---

My other links:
Home/Links: https://linktr.ee/reactorcore
Releases: https://reactorcore.itch.io
Blog: https://www.patreon.com/ReactorcoreGames
Discord: https://discord.gg/UdRavGhj47
Catalog: https://reactorcoregames.github.io/
