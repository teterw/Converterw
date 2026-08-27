$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "Installing dependencies..."
# --upgrade matters: YouTube breaks older yt-dlp releases with 403 errors, so a
# build must always bundle the newest yt-dlp available at build time.
pip install --upgrade -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

$ytdlpVersion = (pip show yt-dlp | Select-String '^Version:').ToString().Split(' ')[1]
Write-Host "Bundling yt-dlp $ytdlpVersion"

$ffmpegDir = Join-Path $PSScriptRoot "vendor\ffmpeg"
$ffmpegExe = Join-Path $ffmpegDir "ffmpeg.exe"

if (-not (Test-Path $ffmpegExe)) {
    Write-Host "Downloading a portable ffmpeg build (one-time, ~150 MB)..."
    $zipPath = Join-Path $env:TEMP "converterw-ffmpeg.zip"
    $extractPath = Join-Path $env:TEMP "converterw-ffmpeg-extract"

    Invoke-WebRequest -Uri "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" -OutFile $zipPath

    if (Test-Path $extractPath) { Remove-Item $extractPath -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

    $exe = Get-ChildItem -Path $extractPath -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
    if (-not $exe) { throw "Could not find ffmpeg.exe inside the downloaded archive" }

    New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null
    Copy-Item $exe.FullName $ffmpegExe -Force

    Remove-Item $zipPath -Force
    Remove-Item $extractPath -Recurse -Force
    Write-Host "ffmpeg ready at $ffmpegExe"
} else {
    Write-Host "Found existing ffmpeg at $ffmpegExe, skipping download."
}

Write-Host "Building Converterw.exe..."
pyinstaller --onefile --windowed --name Converterw `
    --collect-data customtkinter `
    --collect-all yt_dlp `
    --collect-all mutagen `
    --add-binary "$ffmpegExe;." `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host "Packaging release zip..."
$releaseDir = Join-Path $PSScriptRoot "release"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
$zipOut = Join-Path $releaseDir "Converterw-win64.zip"
Compress-Archive -Path (Join-Path $PSScriptRoot "dist\Converterw.exe") -DestinationPath $zipOut -Force

Write-Host ""
Write-Host "Done!"
Write-Host "  Exe: dist\Converterw.exe"
Write-Host "  Zip: release\Converterw-win64.zip  (upload this to GitHub Releases)"
Write-Host ""
Write-Host "The exe is fully self-contained - ffmpeg and yt-dlp are bundled inside it."
Write-Host "Nothing else needs to be installed on the machine that runs it."
Write-Host "yt-dlp $ytdlpVersion is bundled; the app keeps it updated by itself."
