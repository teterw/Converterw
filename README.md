# Converterw

A simple YouTube to MP3 / MP4 converter with a graphical interface.
Built with Python because I wanted a local tool instead of relying on online converter websites.

**Features**
- Download YouTube videos as MP4
- Download YouTube audio as MP3
- Supports single videos and playlists
- Simple GUI with progress bar
- Portable `.exe` — no Python install needed

---

## Download

Grab the latest `Converterw.exe` from the [Releases](https://github.com/teterw/Converterw/releases) page.

**Requirement:** You also need `ffmpeg` installed on your machine.
Install it in one command:
```
winget install ffmpeg
```

**Windows Defender warning:** The `.exe` may trigger a warning because it is unsigned.
This is a common false positive for PyInstaller apps. Click **More info → Run anyway** to proceed.

---

## Running from source

**1. Install dependencies**
```
pip install -r requirements.txt
```
You also need `ffmpeg` (see above).

**2. Run the app**
```
python main.py
```

**CLI usage**
```
python cli/cli.py yt "https://youtu.be/VIDEO_ID" --mp3
python cli/cli.py yt "https://youtu.be/VIDEO_ID" --mp4 --out C:\Users\you\Music
```

---

## Building the .exe

**1. Install PyInstaller**
```
pip install pyinstaller
```

**2. Build**
```
pyinstaller --onefile --windowed --name Converterw --collect-data customtkinter main.py
```

Or just run the included script:
```
build.bat
```

The output will be at `dist\Converterw.exe`.

**Flags explained:**
- `--onefile` — bundles everything into a single `.exe`
- `--windowed` — hides the console window behind the GUI
- `--collect-data customtkinter` — includes CustomTkinter's theme files (required, it crashes without this)

---

## Releasing to GitHub

**1. Tag the version**
```
git tag v1.0.0
git push origin main --tags
```

**2. Create the release**
- Go to your repo on GitHub → **Releases** → **Create a new release**
- Select your tag
- Attach `dist\Converterw.exe`
- Publish

For future releases, bump the version number and repeat.

---

## Docker (CLI only)

Docker works for the CLI downloader. The GUI cannot run inside Docker on Windows.

**Build the image**
```
docker build -t converterw .
```

**Run it**
```
docker run --rm -v "C:\Users\you\Downloads:/downloads" converterw yt "https://youtu.be/VIDEO_ID" --mp3 --out /downloads
docker run --rm -v "C:\Users\you\Downloads:/downloads" converterw yt "https://youtu.be/VIDEO_ID" --mp4 --out /downloads
```

`-v` maps a folder on your machine to `/downloads` inside the container — that's where the file saves.
No Python, yt-dlp, or ffmpeg install needed on the host.

---

## Built with

- [Python](https://python.org)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- [PyInstaller](https://pyinstaller.org)
- [ffmpeg](https://ffmpeg.org)
