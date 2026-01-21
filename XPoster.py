import os
import requests
import mimetypes
import tempfile
import tweepy
import time
from dotenv import load_dotenv
from PlatformTokenGen import get_platform_credentials_sync

load_dotenv()


def _get_twitter_clients():

    XTkn = get_platform_credentials_sync("twitter")
    if not XTkn:
        raise RuntimeError("Twitter credentials not found in database")

    ACCESS_TOKEN = XTkn.access_token
    ACCESS_TOKEN_SECRET = XTkn.meta.get("ACCESS_TOKEN_SECRET")
    CONSUMER_KEY = os.getenv("X_API_KEY")
    CONSUMER_SECRET = os.getenv("X_API_KEY_SECRET")

    if not all([ACCESS_TOKEN, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET]):
        raise RuntimeError("Missing Twitter/X environment variables")

    client = tweepy.Client(
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
    )

    auth = tweepy.OAuth1UserHandler(
        CONSUMER_KEY,
        CONSUMER_SECRET,
        ACCESS_TOKEN,
        ACCESS_TOKEN_SECRET,
    )

    api = tweepy.API(auth, timeout=300, wait_on_rate_limit=True)

    return client, api


def get_mime_type(url):
    try:
        response = requests.head(url, timeout=10)
        return response.headers.get("content-type", "").split(";")[0].strip()
    except Exception:
        return mimetypes.guess_type(url)[0]


def upload_media_with_retries(media_url, retries=3):
    temp_filename = None
    client, api = _get_twitter_clients()

    for attempt in range(retries):
        try:
            mime_type = get_mime_type(media_url)
            ext = mimetypes.guess_extension(mime_type) or ".mp4"
            is_video = mime_type and mime_type.startswith("video")

            with requests.get(media_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                tf = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    tf.write(chunk)
                temp_filename = tf.name
                tf.close()

            media = api.media_upload(
                filename=temp_filename,
                chunked=True,
                media_category="tweet_video" if is_video else "tweet_image",
            )

            if is_video:
                while True:
                    status = api.get_media_upload_status(media.media_id_string)
                    if status.processing_info["state"] == "succeeded":
                        break
                    elif status.processing_info["state"] == "failed":
                        raise RuntimeError("Video processing failed")
                    time.sleep(status.processing_info.get("check_after_secs", 5))

            return media.media_id_string

        except Exception:
            if attempt < retries - 1:
                time.sleep(5)
        finally:
            if temp_filename and os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except Exception:
                    pass

    return None


def post_to_x(text, media_url=None):
    client, api = _get_twitter_clients()

    media_ids = []
    if media_url:
        urls = [media_url] if isinstance(media_url, str) else media_url
        for url in urls:
            mid = upload_media_with_retries(url)
            if mid:
                media_ids.append(mid)

    response = client.create_tweet(
        text=text,
        media_ids=media_ids if media_ids else None,
    )
    return response.data
