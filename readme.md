# Backupper for itch.io

**Video:** https://www.youtube.com/watch?v=kZe8LkoGR3o

**Get it here:** https://reactorcore.itch.io/backupper-for-itchio

<img width="1600" height="900" alt="screenshot_1" src="https://github.com/user-attachments/assets/273dbfeb-5b2a-4f75-bae4-a1851425cd3f" />

## About

Saves an offline copy of any itch.io author's public page to your computer, so it can still be read and browsed if the live page changes or disappears.

Open the program, enter an author's page, choose a folder and press Start Backup. You get the author's front page, every project page and their devlogs, each saved the way a browser's "Save Page As" does it: an `.html` file plus a folder holding its images and styling. The links between saved pages work offline.

## What it saves

- The author's front page
- Every published project page, including projects their front page doesn't link to
- Devlog lists and devlog posts
- All images on those pages, plus the full-size screenshots if you want them
- A `backup-report.json` listing what was saved and anything that went wrong

## What it does not save

- **The downloadable files themselves.** Games, tools and asset packs behind the download or purchase buttons are not fetched, so keep your own copies of those. Paid content is never touched.
- **Browser games and embedded videos.** Games that play on the page and embedded videos such as YouTube stay linked to the live site.
- **Anything needing a login.** The program only sees what a logged-out visitor sees.

## Requirements

Windows 10 or 11. Nothing else to install.

## Being a good guest

The program waits between pages, slows down if the server asks it to and obeys the site's robots.txt. Only back up pages you have a reason to keep, such as your own. Saved copies remain the work of their original author, so don't republish other people's pages.

This is an unofficial tool. It is not made by, endorsed by or affiliated with itch.io.

## License

MIT, see `LICENSE`. Copyright (c) 2026 Reactorcore. Free to use, and you can pay what you want on the itch.io page if it helps you.

## Credits

Built with Python, [ttkbootstrap](https://github.com/israel-dryer/ttkbootstrap), [Requests](https://requests.readthedocs.io/) and [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/). Uses the [Lato](https://www.latofonts.com/) typeface by Łukasz Dziedzic under the SIL Open Font License, included as `_internal/assets/fonts/OFL.txt`.

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
