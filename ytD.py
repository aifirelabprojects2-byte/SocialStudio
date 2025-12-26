from pytubefix import YouTube
from pytubefix.cli import on_progress 

video_url = "https://youtube.com/shorts/s4b4-4TF85M?si=Li1nJBywY1KSLgKZ"

def progress_func(stream, chunk, bytes_remaining):
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage = (bytes_downloaded / total_size) * 100
    print(f"\rDownloading... {percentage:.2f}%", end="")

yt = YouTube(video_url, on_progress_callback=progress_func)

print(f"Title: {yt.title}")

stream = yt.streams.get_highest_resolution()

stream.download(output_path=".", filename="downloaded_video.mp4")

print("\nDownload completed!")