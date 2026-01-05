import subprocess

def youtube_to_mp4(url):
    subprocess.run([
        "yt-dlp",
        "-f", "bv*+ba/best",
        "--merge-output-format", "mp4",
        "-o", "downloads/%(title)s.%(ext)s",
        url
    ], check=True)

def youtube_to_mp3(url):
    subprocess.run([
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", "downloads/%(title)s.%(ext)s", #Path
        url
    ], check=True)

if __name__ == "__main__":
    url = "https://youtu.be/ddQ7YR0qQSo?si=QKMYohk3Mv9NSlax"

    # Uncomment ONE at a time to test
    # youtube_to_mp4(url)
    youtube_to_mp4(url) #function call
