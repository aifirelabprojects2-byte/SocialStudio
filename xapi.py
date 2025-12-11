import json
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

TWEET_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:twitter\.com|x\.com)/"
    r"(?:[A-Za-z0-9_]{1,15}/status/)"
    r"(\d+)"
)

def extract_tweet_id_from_url(url: str) -> str | None:
    match = TWEET_URL_PATTERN.search(url.strip())
    return match.group(1) if match else None


def fetch_tweet_by_id(tweet_id: str):
    url = f"https://api.twitter.com/2/tweets/{tweet_id}"
    
    params = {
        "expansions": "attachments.media_keys,author_id",
        "media.fields": "url,preview_image_url",
        "tweet.fields": "text,created_at",
        "user.fields": "name,username"
    }
    
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if "data" not in data:
            print("Error: No tweet data returned.")
            print(json.dumps(data, indent=2))
            return None
        
        tweet = data["data"]
        caption = tweet.get("text", "No caption available")
        
        # Get author username if available
        author = "Unknown"
        if "includes" in data and "users" in data["includes"]:
            for user in data["includes"]["users"]:
                if user["id"] == tweet["author_id"]:
                    author = f"@{user['username']}"
                    break

        images = []
        if "includes" in data and "media" in data["includes"]:
            for media in data["includes"]["media"]:
                if media.get("type") == "photo" and "url" in media:
                    # Use full image URL (remove :large if you want original, but :large is high-res)
                    img_url = media["url"]
                    if not img_url.startswith("http"):
                        img_url = media["url"]
                    images.append(img_url)
        
        return {
            "tweet_id": tweet_id,
            "author": author,
            "caption": caption,
            "images": images,
            "tweet_url": f"https://x.com/i/status/{tweet_id}"
        }
    
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP Error: {http_err}")
        try:
            print(f"Response: {response.json()}")
        except:
            print(f"Response: {response.text}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


# Interactive usage
if __name__ == "__main__":
    while True:
        user_input = input("Enter tweet URL (or 'quit' to exit): ").strip()
        
        if user_input.lower() in ["quit", "q", "exit", ""]:
            print("Goodbye!")
            break

        tweet_id = extract_tweet_id_from_url(user_input)
        
        if not tweet_id:
            print("Invalid or unsupported tweet URL. Please try again.\n")
            continue
        
        print(f"Fetching tweet {tweet_id}...\n")
        
        result = fetch_tweet_by_id(tweet_id)
        if result:
            print(f"Author: {result['author']}")
            print(f"Link: {result['tweet_url']}")
            print("\nCaption:")
            print(result["caption"])
            print("\nImages:")
            if result["images"]:
                for i, img in enumerate(result["images"], 1):
                    full_res = img.split(":large")[0] + "?format=jpg&name=orig"
                    print(f"{i}. {img}")
                    print(f"   Full: {full_res}")
            else:
                print("No images found.")
            print("\n" + "-" * 70 + "\n")
        else:
            print("Failed to fetch tweet. Check your bearer token or rate limits.\n")
            
#1998456096365678834