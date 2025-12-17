import os
import uuid
import tempfile
import time
import requests
from dotenv import load_dotenv
import tweepy
from tweepy import OAuth1UserHandler, API
from PIL import Image
from typing import List, Optional, Union
from requests.exceptions import RequestException
from tweepy.errors import TweepyException

from meta_poster.utils import build_caption

load_dotenv()

CONSUMER_KEY = os.getenv("X_API_KEY")
CONSUMER_SECRET = os.getenv("X_API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

client_v2 = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET,
    wait_on_rate_limit=True
)

auth = OAuth1UserHandler(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

api_v1 = API(auth, wait_on_rate_limit=True, timeout=300)


try:
    USERNAME = client_v2.get_me().data.username
except Exception as e:
    print("Warning: Could not fetch username automatically. Using placeholder.")
    USERNAME = "dev"  


def retry_on_network_error(max_retries: int = 6, initial_delay: int = 8):
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (RequestException, TweepyException, ConnectionError, TimeoutError) as e:
                    if "RemoteDisconnected" in str(e) or "Connection aborted" in str(e) or isinstance(e, (ConnectionError, TimeoutError)):
                        if attempt == max_retries:
                            print(f"Failed after {max_retries} attempts: {e}")
                            raise
                        print(f"Transient network error (attempt {attempt}/{max_retries}): {e}")
                        print(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay *= 2  
                    else:
                        raise  
            return None
        return wrapper
    return decorator


def _download_image_to_temp(image_url: str) -> str:
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        raise ValueError(f"Not a valid image URL: {image_url} (Content-Type: {content_type})")

    suffix = os.path.splitext(image_url)[1] or ".jpg"
    if len(suffix) > 6:
        suffix = ".jpg"

    temp_path = os.path.join(tempfile.gettempdir(), f"temp_img_{uuid.uuid4().hex}{suffix}")
    with open(temp_path, "wb") as f:
        f.write(response.content)

    size_mb = os.path.getsize(temp_path) / (1024 * 1024)
    print(f"Downloaded {image_url} → {temp_path} ({size_mb:.2f} MB)")
    return temp_path


def compress_image(input_path: str, max_size_mb: float = 4.9, max_dimension: int = 2048) -> str:
    img = Image.open(input_path)

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    if max(img.size) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    output_path = input_path.rsplit(".", 1)[0] + "_compressed.jpg"

    quality = 95
    img.save(output_path, "JPEG", quality=quality, optimize=True)

    while os.path.getsize(output_path) / (1024 * 1024) > max_size_mb and quality > 10:
        quality -= 15
        if max(img.size) > 1024:
            new_size = tuple(int(dim * 0.8) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        img.save(output_path, "JPEG", quality=quality, optimize=True)

    final_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    if final_size_mb > 5:
        raise ValueError(f"Image could not be compressed under 5MB (final: {final_size_mb:.2f} MB)")

    print(f"Compressed → {output_path} ({final_size_mb:.2f} MB, quality={quality})")
    return output_path


def upload_single_image(image_input: Optional[str]) -> Optional[str]:
    if not image_input:
        return None

    is_url = image_input.startswith(("http://", "https://"))
    temp_files_to_cleanup = []

    try:
        if is_url:
            temp_path = _download_image_to_temp(image_input)
            temp_files_to_cleanup.append(temp_path)
        elif os.path.exists(image_input):
            temp_path = image_input
        else:
            raise FileNotFoundError(f"Image not found: {image_input}")

        compressed_path = compress_image(temp_path)
        temp_files_to_cleanup.append(compressed_path)

        @retry_on_network_error()
        def safe_media_upload():
            return api_v1.media_upload(filename=compressed_path)

        media = safe_media_upload()
        print(f"Uploaded → media_id: {media.media_id_string}")
        return media.media_id_string

    finally:
        for path in temp_files_to_cleanup:
            if path != image_input:
                try:
                    os.remove(path)
                except OSError:
                    pass


def post_to_x(
    captions: str,
    image_per_tweet: str,
    hashtags: Optional[List[str]] = None
) -> List[str]:

    caption_parts = [part.strip() for part in captions.split("\n\n") if part.strip()]
    
    if not caption_parts:
        raise ValueError("At least one caption is required.")

    final_captions = []
    for caption in caption_parts:
        final_caption = build_caption(caption, hashtags)
        final_captions.append(final_caption)

    total = len(final_captions)
    if total > 1:
        for i in range(total):
            counter = f" ({i+1}/{total})"
            if len(final_captions[i] + counter) <= 280:
                final_captions[i] += counter

    # Validate length
    for caption in final_captions:
        if len(caption) > 280:
            raise ValueError(f"Caption exceeds 280 characters: {len(caption)} chars")

    media_id = upload_single_image(image_per_tweet)
    media_ids = [media_id] if media_id else None

    previous_tweet_id = None
    tweet_urls = []

    @retry_on_network_error()
    def safe_create_tweet(**kwargs):
        return client_v2.create_tweet(**kwargs)

    for i, caption in enumerate(final_captions):
        response = safe_create_tweet(
            text=caption,
            media_ids=media_ids,
            in_reply_to_tweet_id=previous_tweet_id
        )

        tweet_id = response.data["id"]
        tweet_url = f"https://x.com/{USERNAME}/status/{tweet_id}"
        print(f"Posted tweet {i+1}/{total}: {tweet_url}")
        tweet_urls.append(tweet_url)

        previous_tweet_id = tweet_id

    print(f"Thread posted successfully! ({total} tweet{'s' if total > 1 else ''})")
    return tweet_urls

# post_to_x(
#     captions="High-res AI art thread",
#     image_per_tweet="https://pub-582b7213209642b9b995c96c95a30381.r2.dev/flux-schnell-cf/prompt-1765086317630-41419.png",
#     hashtags=["AIArt", "Generated", "Flux"]
# )