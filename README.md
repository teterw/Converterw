# Converterw

A simple YouTube to MP3 / MP4 converter with a graphical interface.
Built with Python because I wanted a local tool instead of relying on online converter websites.

**Features**
- Download YouTube videos as MP4
- Download YouTube audio as MP3
- Supports single videos and playlists
- Simple GUI with progress bar
- Fully portable `.exe` — nothing else to install, ffmpeg and yt-dlp are bundled inside

---

## Download

Grab the latest `Converterw-win64.zip` from the [Releases](https://github.com/teterw/Converterw/releases) page, unzip it, and run `Converterw.exe`.

That's it — no Python, no ffmpeg, no yt-dlp install required. Everything the app needs ships inside the `.exe`.

**Windows Defender warning:** The `.exe` may trigger a warning because it is unsigned.
This is a common false positive for PyInstaller apps. Click **More info → Run anyway** to proceed.

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
1. Install `pyinstaller` and the packages in `requirements.txt`
2. Download a portable static `ffmpeg.exe` build into `vendor/ffmpeg/` (one-time, skipped if already present)
3. Bundle the app, `yt-dlp`, and `ffmpeg` together into a single `dist\Converterw.exe`
4. Zip it up as `release\Converterw-win64.zip`, ready to attach to a GitHub release

Because `yt-dlp` is imported directly as a Python library (instead of being called as a separate command-line tool) and `ffmpeg` is bundled into the `.exe` itself, the resulting build works on any Windows machine with nothing extra installed — this is what fixes the "works on my PC, not on others'" problem.

---

## Releasing to GitHub

Releases are built automatically by [`.github/workflows/build.yml`](.github/workflows/build.yml) — it runs on a real Windows GitHub Actions runner (there's no local Windows machine involved), so this works the same whether you're developing on Windows, macOS, or Linux.

**1. Tag the version and push it**
```
git tag v1.0.0
git push origin v1.0.0
```

That's it. The workflow builds `Converterw.exe`, zips it, and attaches `Converterw-win64.zip` to a new GitHub Release named after the tag.

You can also trigger a build without releasing (e.g. to sanity-check a branch) from the **Actions** tab → **Build Windows release** → **Run workflow**; the zip shows up as a downloadable build artifact on that run.

For future releases, bump the version number and repeat.

### Building locally instead

If you're on Windows and want a local build without going through CI, `build.bat` still does the same thing `build.ps1` runs in CI — installs dependencies, downloads a portable `ffmpeg.exe` into `vendor/ffmpeg/`, builds `dist\Converterw.exe`, and zips it to `release\Converterw-win64.zip`.

---

## Built with

- [Python](https://python.org)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- [PyInstaller](https://pyinstaller.org)
- [ffmpeg](https://ffmpeg.org) (static builds from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds))
