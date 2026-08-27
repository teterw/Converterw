# Converterw

A YouTube to MP3 / MP4 converter with both a graphical interface and a command-line tool.
Built with Python because I wanted a local tool instead of relying on online converter websites.

**Features**
- Download YouTube videos as MP4, MKV or WebM, with a quality picker (up to 4K)
- Extract audio as MP3, M4A, Opus, FLAC or WAV, with a bitrate picker
- Embed cover art, title/artist tags and chapters automatically
- Embed subtitles, and skip sponsor segments via SponsorBlock
- Trim: download only part of a video by start/end time
- Playlists: a playlist link downloads the whole list (or a range like `1-5,8`) into its own
  folder, while a video link that merely carries `&list=` downloads just that video
- Live progress with speed and ETA, and a cancel button
- **Keeps its own downloader engine up to date, so it doesn't break every few weeks**
- Windows: a portable `.exe` with ffmpeg and yt-dlp bundled inside
- Linux / macOS / Windows: a `converterw` command you can install with `pip`

---

## Install

### Command line (Linux, macOS, Windows)

Converterw installs as a normal terminal command. [pipx](https://pipx.pypa.io) is
the tidiest way, since it keeps the tool in its own environment:

```sh
pipx install git+https://github.com/teterw/Converterw.git
```

Or with plain pip:

```sh
pip install git+https://github.com/teterw/Converterw.git
```

You also need **ffmpeg** for audio extraction, trimming and merging high-quality video:

```sh
sudo apt install ffmpeg        # Debian / Ubuntu
sudo dnf install ffmpeg        # Fedora
sudo pacman -S ffmpeg          # Arch
brew install ffmpeg            # macOS
```

Check it worked:

```sh
converterw --version
```

To install the desktop GUI as well (needs a graphical session):

```sh
pipx install "converterw[gui] @ git+https://github.com/teterw/Converterw.git"
converterw-gui
```

### Windows app (no Python needed)

Grab the latest `Converterw-win64.zip` from the [Releases](https://github.com/teterw/Converterw/releases) page, unzip it, and run `Converterw.exe`.

No Python, no ffmpeg, no yt-dlp install required — everything ships inside the `.exe`.

**Windows Defender warning:** The `.exe` may trigger a warning because it is unsigned.
This is a common false positive for PyInstaller apps. Click **More info → Run anyway** to proceed.

---

## Using the command line

```sh
converterw https://youtu.be/VIDEO
```

Downloads the best-quality MP4 into your Downloads folder. Some more examples:

```sh
# 1080p, saved as MKV, into a folder you choose
converterw https://youtu.be/VIDEO -q 1080p -c mkv -o ~/Videos

# audio only, 320 kbps MP3
converterw https://youtu.be/VIDEO --audio -a mp3 -b 320

# just the chorus: from 1:30 to 2:15
converterw https://youtu.be/VIDEO --start 1:30 --end 2:15

# first five entries of a playlist, into ~/Music
converterw "https://youtube.com/playlist?list=..." --items 1-5 -o ~/Music

# what is this link, without downloading it
converterw https://youtu.be/VIDEO --info
```

| Option | What it does |
| --- | --- |
| `-o, --output DIR` | Where to save (default: your Downloads folder) |
| `--audio` | Extract audio instead of video |
| `-q, --quality` | `best`, `2160p`/`4k`, `1440p`, `1080p`, `720p`, `480p`, `360p`, `240p` |
| `-c, --container` | `mp4`, `mkv`, `webm` |
| `-a, --audio-format` | `mp3`, `m4a`, `opus`, `flac`, `wav` |
| `-b, --bitrate` | `best`, `320`, `256`, `192`, `128`, `96` |
| `--start`, `--end` | Download only part of a video (`mm:ss`, `hh:mm:ss` or seconds) |
| `--subs LANGS` | Embed subtitles, e.g. `--subs en,es` |
| `--sponsorblock` | Cut sponsor segments out |
| `--no-thumbnail`, `--no-metadata` | Skip embedding cover art / tags |
| `--playlist` | Also take the list a video link carries (a mix, usually) |
| `--no-playlist` | Download one video only, even from a playlist link |
| `--items RANGE` | Which playlist entries to take, e.g. `1-5,8` |
| `--flat` | Don't put the playlist in its own folder |
| `--skip-existing` | Skip anything already downloaded to that folder |
| `--cookies-from-browser B` | Use browser cookies for age-restricted videos |
| `--info` | Print title, channel and duration, then exit |
| `--quiet`, `--verbose` | Less / more output |
| `--update-engine` | Fetch the newest yt-dlp now |

`converterw --help` lists everything. Exit status is `0` on success, `1` on failure,
and `130` if you press Ctrl-C — so it slots into scripts like any other tool.

---

## Why downloads used to stop working after a while

YouTube changes how it serves video every few weeks. When it does, older versions
of [yt-dlp](https://github.com/yt-dlp/yt-dlp) — the library that does the actual
downloading — start failing with **`HTTP Error 403: Forbidden`**.

Because yt-dlp was frozen inside the `.exe` at build time, it could never fix
itself, so every release slowly rotted until a new one was published. Converterw
now handles this on its own, in two layers:

1. **A self-updating engine.** yt-dlp is pure Python, so the app keeps its own
   copy in its data folder and prefers it over the bundled one whenever it is
   newer. It checks on launch and (by default) fetches updates in the background;
   updates are staged and applied at the next start, so an update can never
   disturb a running download. Update or roll back from the GUI's **Advanced**
   tab, or with `converterw --update-engine` / `--reset-engine`.

2. **Player-client fallback.** If YouTube returns 403 anyway, the download is
   retried against other YouTube player clients before giving up. This alone
   recovers most 403s even on an out-of-date engine.

If a download still fails with 403, run `converterw --update-engine` (or use
**Advanced → Update engine now** in the GUI), then try again.

---

## Where the app stores things

| What | Where |
| --- | --- |
| Settings | `%LOCALAPPDATA%\Converterw\settings.json` — Linux: `~/.local/share/Converterw/settings.json` |
| Updated yt-dlp engine | the `engine/` folder next to it |
| Failed downloads | `errors.log` next to it — paste this when reporting a problem |

**Advanced → Open data folder** takes you straight there in the GUI. Deleting that
folder resets the app to a clean state.

---

## Running from source

```sh
git clone https://github.com/teterw/Converterw.git
cd Converterw
pip install -e ".[gui]"
```

Then `converterw --help` for the CLI, or `python main.py` for the GUI.

When running from source the app uses `ffmpeg` from your `PATH` if it can't find a
bundled copy in `vendor/ffmpeg/`, so install ffmpeg separately if you don't have it.

---

## Building the Windows .exe

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

## Releasing to GitHub

Releases are built automatically by [`.github/workflows/build.yml`](.github/workflows/build.yml) — it runs on a real Windows GitHub Actions runner, so this works the same whether you're developing on Windows, macOS, or Linux.

**Tag the version and push it**

```
git tag v1.1.0
git push origin v1.1.0
```

That's it. The workflow builds `Converterw.exe`, zips it, and attaches `Converterw-win64.zip` to a new GitHub Release named after the tag.

You can also trigger a build without releasing from the **Actions** tab → **Build Windows release** → **Run workflow**; the zip shows up as a downloadable build artifact on that run.

For future releases, bump `__version__` in [`converterw/version.py`](converterw/version.py), then tag and push.

---

## Built with

- [Python](https://python.org)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- [mutagen](https://github.com/quodlibet/mutagen) (cover art and tags)
- [PyInstaller](https://pyinstaller.org)
- [ffmpeg](https://ffmpeg.org) (static builds from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds))
