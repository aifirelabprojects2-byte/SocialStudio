import os
from apify_client import ApifyClient
from dotenv import load_dotenv
import json  
load_dotenv()


API_KEY= os.getenv("APIFY_KEY")
def get_insta_data(post_url):
    client = ApifyClient(API_KEY)
    run_input = {
        "directUrls": [post_url],
        "resultsType": "posts",
        "resultsLimit": 1,
        "searchLimit": 1,
    }

    run = client.actor("shu8hvrXbJbY3Eb9W").call(run_input=run_input)
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        media_url = item.get("videoUrl") if item.get("videoUrl") else item.get("displayUrl")
        caption = item.get("caption", "No caption available")

        return {
            "caption": caption,
            "media_url": media_url,
            "type": "video" if item.get("videoUrl") else "image"
        }




def get_x_media_v2(tweet_url: str):
    client = ApifyClient(API_KEY)
    tweet_id = tweet_url.split("/")[-1].split("?")[0]

    run = client.actor(
        "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"
    ).call(run_input={
        "tweetIDs": [tweet_id],
        "maxItems": 1
    })

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    if not items:
        return {"status": "No items in dataset"}

    item = items[0]  # Take first (and only) item

    caption = item.get("text") or "No text found"

    # -------- media --------
    media_url = None
    media_entities = item.get("extendedEntities", {}).get("media", []) or []

    if media_entities:
        media = media_entities[0]  # First media item

        media_type = media.get("type", "")
        if media_type == "photo":
            media_url = media.get("media_url_https") or media.get("url") or media.get("media_url")
        elif media_type in ("video", "animated_gif"):
            # For videos/GIFs, variants are nested under "video_info"
            video_info = media.get("video_info", {})
            variants = video_info.get("variants", [])
            mp4s = [
                v for v in variants
                if isinstance(v, dict) and v.get("content_type") == "video/mp4" and "bitrate" in v
            ]
            if mp4s:
                # Highest quality (bitrate)
                media_url = max(mp4s, key=lambda x: x.get("bitrate", 0)).get("url")
            else:
                # Fallback to any video URL (e.g., m3u8 or first MP4)
                for v in variants:
                    if isinstance(v, dict) and "url" in v:
                        media_url = v["url"]
                        break
                # Or direct fallback
                media_url = media_url or media.get("videoUrl") or media.get("url")

    return {
        "caption": caption,
        "media_url": media_url,
        "status": "Success" if media_url else ("Text Only" if caption != "No text found" else "No Data Found")
    }


# # --- Example Usage X ---
# tweet_url = "https://x.com/ShouldHaveCat/status/2008168428746535412?s=20"
# data = get_x_media_v2(tweet_url)

# if data:
#     print(f"CAPTION: {data.get('caption')}")
#     print(f"MEDIA: {data.get('media_url')}")
    
# # --- Example Usage  Instagram ---
# url = "https://www.instagram.com/p/DQ8Pd_7jeMt/?igsh=MWQ5eTZwZWhtOTJ4ZQ=="
# data = get_insta_data(url)

# if data:
#     print(f"CAPTION: {data['caption']}")
#     print(f"URL: {data['media_url']}")
#     print(f"TYPE: {data['type']}")
    