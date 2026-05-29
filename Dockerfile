FROM python:3.11-slim

# Install ffmpeg (required by yt-dlp for audio conversion and merging)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN pip install --no-cache-dir yt-dlp

WORKDIR /app
COPY core/ ./core/
COPY cli/ ./cli/

# Downloads will be written here — mount a host folder to this path
VOLUME /downloads

ENTRYPOINT ["python", "cli/cli.py"]
