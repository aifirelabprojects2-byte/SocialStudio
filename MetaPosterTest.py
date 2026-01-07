import asyncio
from PlatformTokenGen import get_platform_credentials_sync
# from XPoster import post_to_x
from meta_poster import InstagramPoster, ThreadsPoster, FacebookPoster
import os

# InsTkn=get_platform_credentials_sync("instagram")
poster = InstagramPoster(
    page_id="905767789286116",
    access_token="EAAaBgZB079rABQYExfnfVNjORbh75bhbT2eg3K4vNcuYReKagUG4CJAPFHZC4ZAZBmGsydNSfNnPlq2VIEyi3FrlZBkrXdJcEEi22G7Jh2iLV8TGc1o9hLeHs8qmD0h64zZBXmxA39UCgGBtibKuZANCRKBU2tkhwCuMTRRX3ymCnvPwIlePO1AAsEfWkeAFQg9ICTKkXTq189Mjvp1"
)


# fb = FacebookPoster(
#     page_id=InsTkn.page_id, #Facebook Page ID
#     page_access_token=InsTkn.page_access_token
#     )



# threads = ThreadsPoster(
#     threads_user_id=InsTkn.threads_user_id, #thread user id
#     access_token=InsTkn.ll_user_access_token, #long-lived token
#     username=InsTkn.threads_username   #optional        
#     )

# threads.post(
#     text="Just realized how fast 2025 is going...",
#     media_url="https://files.catbox.moe/fgly20.mp4",
#     hashtags=["DeepThoughts", "2025"]
# )

# ttt = post_to_x(
#         captions="Just realized how fast 2025 is going...",
#         media_input="https://files.catbox.moe/fgly20.mp4",
#         hashtags=["DeepThoughts", "2025"],
#         )
# print(ttt)

# Instagram 
# poster.post(
#     caption="Testing",
#     media_url="https://pub-582b7213209642b9b995c96c95a30381.r2.dev/flux-schnell-cf/prompt-1765086317630-41419.png",
#     hashtags=["Testing", "Automation"],
# )

# # Facebook
# fb.post_text(message="We're hiring!", link="https://careers.example.com", hashtags=["NowHiring"])
# fb.post_media(message="Morning coffee ritual ",media="https://pub-582b7213209642b9b995c96c95a30381.r2.dev/flux-schnell-cf/prompt-1765086317630-41419.png",hashtags=["CoffeeLover", "MorningRoutine"])
#
