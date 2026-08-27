# Converterw

A YouTube to MP3 / MP4 converter with a graphical interface.
Built with Python because I wanted a local tool instead of relying on online converter websites.

**Features**
- Download YouTube videos as MP4, MKV or WebM, with a quality picker (up to 4K)
- Extract audio as MP3, M4A, Opus, FLAC or WAV, with a bitrate picker
- Embed cover art, title/artist tags and chapters automatically
- Embed subtitles, and skip sponsor segments via SponsorBlock
- Trim: download only part of a video by start/end time (collapsed until you turn it on)
- Playlists: whole list or a range like `1-5,8`, saved into their own folder
- Live progress with speed and ETA, a cancel button, and a log panel
- Remembers your settings between runs
- **Keeps its own downloader engine up to date, so it doesn't break every few weeks**
- Fully portable `.exe` — nothing else to install, ffmpeg and yt-dlp are bundled inside

---

## Download

Grab the latest `Converterw-win64.zip` from the [Releases](https://github.com/teterw/Converterw/releases) page, unzip it, and run `Converterw.exe`.

That's it — no Python, no ffmpeg, no yt-dlp install required. Everything the app needs ships inside the `.exe`.

**Windows Defender warning:** The `.exe` may trigger a warning because it is unsigned.
This is a common false positive for PyInstaller apps. Click **More info → Run anyway** to proceed.

---

## Why downloads used to stop working after a while

YouTube changes how it serves video every few weeks. When it does, older versions
of [yt-dlp](https://github.com/yt-dlp/yt-dlp) — the library that does the actual
downloading — start failing with **`HTTP Error 403: Forbidden`**.

Because yt-dlp was frozen inside the `.exe` at build time, it could never fix
itself, so every release slowly rotted until a new one was published. Converterw
now handles this on its own, in two layers:

1. **A self-updating engine.** yt-dlp is pure Python, so the app keeps its own
   copy in `%LOCALAPPDATA%\Converterw\engine` and prefers it over the bundled one
   whenever it is newer. It checks for updates on launch and (by default) fetches
   them in the background; updates are staged and applied on the next start, so an
   update can never corrupt a running download. You can also update, or roll back
   to the bundled version, from the **Advanced** tab.

2. **Player-client fallback.** If YouTube returns 403 anyway, the download is
   retried automatically against other YouTube player clients before giving up.
   This alone recovers most 403s even on an out-of-date engine.

If a download still fails with 403, open **Advanced → Update engine now**, restart,
and try again.

---

## Running from source

**1. Install dependencies**
```
pip install -r requirements.txt
```

**2. Run the app**
```
python main.py
```

When running from source, the app will use `ffmpeg` from your system `PATH` if it can't find a bundled copy in `vendor/ffmpeg/` (see below), so install ffmpeg separately if you're developing this way and don't already have it.

---

## Building the .exe

Just run:
```
build.bat
```

This will:
1. Install `pyinstaller` and the packages in `requirements.txt` (always upgrading to the newest `yt-dlp`)
2. Download a portable static `ffmpeg.exe` build into `vendor/ffmpeg/` (one-time, skipped if already present)
3. Bundle the app, `yt-dlp`, `mutagen` and `ffmpeg` together into a single `dist\Converterw.exe`
4. Zip it up as `release\Converterw-win64.zip`, ready to attach to a GitHub release

Because `yt-dlp` is imported directly as a Python library (instead of being called as a separate command-line tool) and `ffmpeg` is bundled into the `.exe` itself, the resulting build works on any Windows machine with nothing extra installed — this is what fixes the "works on my PC, not on others'" problem.

---

## Where the app stores things

| What | Where |
| --- | --- |
| Settings | `%LOCALAPPDATA%\Converterw\settings.json` |
| Updated yt-dlp engine | `%LOCALAPPDATA%\Converterw\engine\` |

**Advanced → Open data folder** takes you straight there. Deleting that folder resets the app to a clean state.

---

## Releasing to GitHub

Releases are built automatically by [`.github/workflows/build.yml`](.github/workflows/build.yml) — it runs on a real Windows GitHub Actions runner (there's no local Windows machine involved), so this works the same whether you're developing on Windows, macOS, or Linux.

**1. Tag the version and push it**
```
git tag v1.1.0
git push origin v1.1.0
```

That's it. The workflow builds `Converterw.exe`, zips it, and attaches `Converterw-win64.zip` to a new GitHub Release named after the tag.

You can also trigger a build without releasing (e.g. to sanity-check a branch) from the **Actions** tab → **Build Windows release** → **Run workflow**; the zip shows up as a downloadable build artifact on that run.

For future releases, bump `__version__` in [`core/version.py`](core/version.py), then tag and push.

### Building locally instead

If you're on Windows and want a local build without going through CI, `build.bat` still does the same thing `build.ps1` runs in CI — installs dependencies, downloads a portable `ffmpeg.exe` into `vendor/ffmpeg/`, builds `dist\Converterw.exe`, and zips it to `release\Converterw-win64.zip`.

---

## Built with

- [Python](https://python.org)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- [mutagen](https://github.com/quodlibet/mutagen) (cover art and tags)
- [PyInstaller](https://pyinstaller.org)
- [ffmpeg](https://ffmpeg.org) (static builds from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds))
