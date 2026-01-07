import os
import requests
import mimetypes
import tempfile
import tweepy
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN_F")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET_F")
CONSUMER_KEY = os.getenv("X_API_KEY")
CONSUMER_SECRET = os.getenv("X_API_KEY_SECRET")

client = tweepy.Client(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

auth = tweepy.OAuth1UserHandler(
    CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET
)
api = tweepy.API(auth)

def get_mime_type(url):

    try:
        response = requests.head(url, timeout=5)
        content_type = response.headers.get('content-type')
        if content_type:
            return content_type.split(';')[0].strip()
    except Exception:
        pass
    
    # Fallback to guessing from extension
    mime_type, _ = mimetypes.guess_type(url)
    return mime_type

def upload_media_from_url(media_url):
    """
    Downloads media to a temp file, determines type, and uploads to X.
    Returns the media_id_string.
    """
    if not media_url:
        return None

    try:
        # Determine file extension and type
        mime_type = get_mime_type(media_url)
        ext = mimetypes.guess_extension(mime_type) if mime_type else ".jpg"
        if not ext: ext = ".jpg"

        # Stream download to a temporary file (Handles large videos without eating RAM)
        with requests.get(media_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            
            # Create a temp file to store the download
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
                for chunk in r.iter_content(chunk_size=8192):
                    tf.write(chunk)
                temp_filename = tf.name

        try:
            print(f"Uploading media: {temp_filename} ({mime_type})")
            
            # Upload Logic
            if mime_type and mime_type.startswith('video'):
                # Chunked upload is REQUIRED for videos
                media = api.media_upload(
                    filename=temp_filename, 
                    chunked=True, 
                    media_category='tweet_video'
                )
            else:
                # Standard upload for images
                media = api.media_upload(filename=temp_filename)
            
            return media.media_id_string

        finally:
            # Cleanup: Remove the temporary file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

    except Exception as e:
        print(f"Error uploading {media_url}: {str(e)}")
        return None

def post_to_x(text, media_url=None):
    media_ids = []

    # 1. Handle Media Processing
    if media_url:
        # Normalize input to a list (whether user passes string or list)
        urls = [media_url] if isinstance(media_url, str) else media_url
        
        # X allows max 4 images OR 1 video per tweet.
        # We process the list, but the API will throw error if limits exceeded.
        for url in urls:
            mid = upload_media_from_url(url)
            if mid:
                media_ids.append(mid)

    # 2. Create Tweet
    try:
        # If we have media, pass media_ids, otherwise just text
        if media_ids:
            response = client.create_tweet(text=text, media_ids=media_ids)
        else:
            response = client.create_tweet(text=text)
            
        print(f"Tweet posted successfully! ID: {response.data['id']}")
        return response.data
    except Exception as e:
        print(f"Failed to post tweet: {e}")
        return None


# post_to_x(text="Hello Z 👋")

# 2. Single Image
# post_to_x(
#     text="Testing...",
#     media_url="https://i.ibb.co/7Jv4VVXh/2000623158680838611-1.jpg"
# )

# 3. List of Images
# post_to_x(
#     text="Testing multiple images!",
#     media_url=[
#         "https://i.ibb.co/fYvMLdGj/149b2dd2-0df4-46e3-9236-e15edd8fcd5e-20260102-135512.png",
#         "https://i.ibb.co/7Jv4VVXh/2000623158680838611-1.jpg"
#     ]
# )

# 4. Video (High Scale / Chunked Upload)
# post_to_x(
#     text="Testing Video Upload 🎥",
#     media_url="https://www.w3schools.com/html/mov_bbb.mp4"
# )