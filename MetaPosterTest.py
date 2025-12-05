from meta_poster import InstagramPoster, ThreadsPoster, FacebookPoster
import os
from dotenv import load_dotenv


load_dotenv()
ig = InstagramPoster()


fb = FacebookPoster(
    page_id=os.getenv('PAGE_ID'), #Facebook Page ID
    page_access_token=os.getenv('PAGE_ACSESS_TOKEN')
    )


threads = ThreadsPoster(
    threads_user_id=os.getenv('THREADS_USER_ID'), #thread user id
    access_token=os.getenv('THREADS_LONG_LIVE_TOKEN'), #long-lived token
    username=os.getenv('THREAD_USERNAME')   #optional        
    )

# threads.post(
#     text="Just realized how fast 2025 is going...",
#     image_url="https://pub-582b7213209642b9b995c96c95a30381.r2.dev/flux-schnell-cf/prompt-1764858989983-291517.png",
#     hashtags=["DeepThoughts", "2025"]
# )

# Instagram 
# ig.post(
#     caption="Morning coffee ritual ",
#     image_url="https://pub-582b7213209642b9b995c96c95a30381.r2.dev/flux-schnell-cf/prompt-1764858989983-291517.png",
#     hashtags=["CoffeeLover", "MorningRoutine"],

# )

# # Facebook
# fb.post_text(message="We're hiring!", link="https://careers.example.com", hashtags=["NowHiring"])
# fb.post_photo(message="Morning coffee ritual ",image="https://pub-582b7213209642b9b995c96c95a30381.r2.dev/flux-schnell-cf/prompt-1764858989983-291517.png",hashtags=["CoffeeLover", "MorningRoutine"])