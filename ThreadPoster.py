import os
import uuid
import tempfile
import requests
from dotenv import load_dotenv
import tweepy
from tweepy import OAuth1UserHandler, API
from PIL import Image
from typing import List, Optional, Union

load_dotenv()

# API Credentials
CONSUMER_KEY = os.getenv("X_API_KEY")
CONSUMER_SECRET = os.getenv("X_API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

# Clients
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


def _download_image_to_temp(image_url: str) -> str:
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()

    if not response.headers.get("Content-Type", "").startswith("image/"):
        raise ValueError(f"Not a valid image URL: {image_url}")

    suffix = os.path.splitext(image_url)[1] or ".jpg"
    if len(suffix) > 6:
        suffix = ".jpg"

    temp_path = os.path.join(tempfile.gettempdir(), f"temp_img_{uuid.uuid4().hex}{suffix}")
    with open(temp_path, "wb") as f:
        f.write(response.content)

    size_mb = os.path.getsize(temp_path) / (1024 * 1024)
    print(f"Downloaded {image_url} → {temp_path} ({size_mb:.2f} MB)")
    return temp_path


def compress_image(input_path: str, max_size_mb: float = 4.9, max_dimension: int = 4096) -> str:
    img = Image.open(input_path)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    if max(img.size) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    output_path = input_path.rsplit(".", 1)[0] + "_compressed.jpg"

    quality = 95
    img.save(output_path, "JPEG", quality=quality, optimize=True)

    while os.path.getsize(output_path) / (1024 * 1024) > max_size_mb and quality > 20:
        quality -= 10
        img.save(output_path, "JPEG", quality=quality, optimize=True)

    final_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Compressed → {output_path} ({final_size:.2f} MB, quality={quality})")
    return output_path


def upload_single_image(image_input: Optional[str]) -> Optional[str]:
    if not image_input:
        return None

    is_url = image_input.startswith(("http://", "https://"))

    if is_url:
        temp_path = _download_image_to_temp(image_input)
    elif os.path.exists(image_input):
        temp_path = image_input
    else:
        raise FileNotFoundError(f"Image not found: {image_input}")

    compressed_path = compress_image(temp_path)

    if os.path.getsize(compressed_path) / (1024 * 1024) > 5:
        raise ValueError("Image exceeds 5MB even after compression.")

    media = api_v1.media_upload(filename=compressed_path)
    print(f"Uploaded → media_id: {media.media_id_string}")

    # Cleanup temp files
    for path in [compressed_path]:
        if path != image_input:  # Don't delete original local file
            try:
                os.remove(path)
            except:
                pass
    if is_url:
        try:
            os.remove(temp_path)
        except:
            pass

    return media.media_id_string


def post_thread(
    captions: Union[str, List[str]],
    image_per_tweet: Optional[Union[str, List[Optional[str]]]] = None,
    hashtags: Optional[str] = None
) -> List[str]:

    # Normalize captions to list
    if isinstance(captions, str):
        captions_list = [captions]
    else:
        captions_list = list(captions)

    if not captions_list:
        raise ValueError("At least one caption is required.")

    # Normalize image_per_tweet
    if image_per_tweet is None:
        image_list = [None] * len(captions_list)
    elif isinstance(image_per_tweet, str):
        # Single image for single caption
        if len(captions_list) == 1:
            image_list = [image_per_tweet]
        else:
            raise ValueError("If captions is a list, image_per_tweet must be a list or None.")
    else:
        image_list = list(image_per_tweet)
        if len(image_list) != len(captions_list):
            raise ValueError("image_per_tweet list must match captions length.")

    # Append hashtags
    if hashtags:
        captions_list = [f"{c.strip()} {hashtags}".strip() for c in captions_list]

    # Add thread numbering if more than one tweet
    total = len(captions_list)
    if total > 1:
        for i in range(total):
            counter = f" ({i+1}/{total})"
            if len(captions_list[i]) + len(counter) <= 280:
                captions_list[i] += counter

    previous_tweet_id = None
    tweet_urls = []

    for i, caption in enumerate(captions_list):
        image_input = image_list[i]
        media_id = upload_single_image(image_input)
        media_ids = [media_id] if media_id else None

        response = client_v2.create_tweet(
            text=caption,
            media_ids=media_ids,
            in_reply_to_tweet_id=previous_tweet_id
        )

        tweet_id = response.data["id"]
        tweet_url = f"https://x.com/your_username/status/{tweet_id}"  # ← Change to your handle
        print(f"Posted tweet {i+1}/{total}: {tweet_url}")
        tweet_urls.append(tweet_url)

        previous_tweet_id = tweet_id

    print("Thread posted successfully!" + (f" ({total} tweet{'s' if total > 1 else ''})"))
    return tweet_urls


# post_thread(
#     captions="High-res AI art thread",
#     image_per_tweet="https://pub-582b7213209642b9b995c96c95a30381.r2.dev/flux-schnell-cf/prompt-1765086317630-41419.png",
#     hashtags="#AIArt #Generated"
# )