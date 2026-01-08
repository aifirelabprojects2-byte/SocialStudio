import time
from typing import Optional, List, Union
from .base import BaseMetaPoster
from .utils import build_caption
from .exceptions import MetaAPIError

class InstagramPoster(BaseMetaPoster):
    def __init__(self, page_id: str = None, access_token: str = None):
        super().__init__(page_id, access_token)
        self.ig_user_id = self._get_ig_business_id()

    def _get_ig_business_id(self) -> str:
        url = f"{self.BASE_URL}/{self.page_id}"
        params = {"fields": "instagram_business_account", "access_token": self.access_token}
        data = self._request("GET", url, params=params)
        ig_account = data.get("instagram_business_account")
        if not ig_account:
            raise MetaAPIError("No Instagram Business Account linked to this Page")
        return ig_account["id"]

    def _get_container_status(self, container_id: str) -> dict:
        """Poll the container status to check if media processing is complete."""
        url = f"{self.BASE_URL}/{container_id}"
        params = {
            # docs show status_code values like IN_PROGRESS / FINISHED / ERROR / EXPIRED
            "fields": "status_code",
            "access_token": self.access_token
        }
        return self._request("GET", url, params=params)

    def _create_child_container(self, media_url: str, is_video: bool = False) -> str:
        """
        Create a child container for carousel items.
        Note: use 'is_carousel_item' per common examples and community posts.
        """
        url = f"{self.BASE_URL}/{self.ig_user_id}/media"
        payload = {
            "access_token": self.access_token,
            "is_carousel_item": True,   # required for carousel children
        }
        if is_video:
            payload.update({"video_url": media_url})
            # For child video you might need 'media_type' set to VIDEO/REELS depending on API version;
            # we'll omit it here so API infers, or set to 'VIDEO' if required by your app/version.
            # Some docs prefer REELS for reels, STORIES for story uploads.
        else:
            payload.update({"image_url": media_url})

        data = self._request("POST", url, data=payload)
        return data["id"]

    def _create_container(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        caption: str = "",
        is_reel: bool = False,
        post_type: str = "post",
        children: Optional[List[str]] = None
    ) -> str:
        """
        Creates a container depending on post_type:
         - 'post' : single-image, single-video or carousel (if children provided)
         - 'reel' : REELS (video only)
         - 'story': STORIES (image or video)
        """
        url = f"{self.BASE_URL}/{self.ig_user_id}/media"
        payload = {"caption": caption, "access_token": self.access_token}

        # Story publishing: media_type = STORIES (image_url|video_url)
        if post_type == "story":
            if video_url:
                payload.update({"media_type": "STORIES", "video_url": video_url})
            elif image_url:
                payload.update({"media_type": "STORIES", "image_url": image_url})
            else:
                raise ValueError("Stories must include image_url or video_url")

        # Reel publishing: media_type = REELS (video required)
        elif post_type == "reel":
            if not video_url:
                raise ValueError("Reel posts require a video_url")
            payload.update({"media_type": "REELS", "video_url": video_url})

        # Regular feed post
        else:  # post_type == "post"
            # Carousel (children) — must supply children IDs (created beforehand)
            if children:
                # API expects a children parameter: comma separated ids (examples/docs/clients use this)
                payload.update({
                    "media_type": "CAROUSEL",
                    "children": ",".join(children)
                })
            else:
                if video_url:
                    # Single video feed post - depending on API version you might need 'VIDEO' or 'REELS'.
                    # Many guides/doc updates use 'REELS' for videos; if your app/version requires
                    # 'VIDEO', change accordingly — I've kept 'VIDEO' for single feed video here.
                    payload.update({"media_type": "VIDEO", "video_url": video_url})
                elif image_url:
                    payload.update({"image_url": image_url, "media_type": "IMAGE"})
                else:
                    # As a fallback treat caption-only posts as TEXT (if API supports it)
                    payload.update({"media_type": "TEXT", "text": caption})

        data = self._request("POST", url, data=payload)
        return data["id"]

    def _publish(self, creation_id: str) -> str:
        url = f"{self.BASE_URL}/{self.ig_user_id}/media_publish"
        data = self._request("POST", url, data={
            "creation_id": creation_id,
            "access_token": self.access_token
        })
        return data["id"]

    def post(
        self,
        caption: str,
        media_url: Optional[Union[str, List[str]]] = None,
        hashtags: Optional[List[str]] = None,
        post_type: str = "post"  # "post" | "reel" | "story"
    ) -> str:
        """
        post_type:
          - 'post'  => feed post (single image, single video, or carousel if media_url is list)
          - 'reel'  => Reels (video only)
          - 'story' => Story (single image or video)
        media_url:
          - string: single image or single video URL
          - list: for 'post' => treated as carousel of images (or mixed where supported)
        """
        final_caption = build_caption(caption, hashtags)

        # normalize media input
        image_url = None
        video_url = None
        children_ids = None

        # If user passed list -> carousel (only valid for feed 'post')
        if isinstance(media_url, list):
            if post_type != "post":
                raise ValueError("lists of media are only supported for feed posts (post_type='post')")
            # Create child containers for each URL
            children_ids = []
            for m in media_url:
                is_video = m.lower().endswith(('.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv'))
                child_id = self._create_child_container(m, is_video=is_video)
                # If child is a video we should poll its status before composing the parent carousel
                if is_video:
                    # wait for child to be ready
                    max_wait_seconds = 600
                    poll_interval = 5
                    elapsed = 0
                    while elapsed < max_wait_seconds:
                        st = self._get_container_status(child_id).get("status_code")
                        if st == "FINISHED":
                            break
                        if st == "ERROR":
                            raise MetaAPIError(f"Child video processing failed (id={child_id})")
                        if st == "EXPIRED":
                            raise MetaAPIError(f"Child media expired before processing completed (id={child_id})")
                        time.sleep(poll_interval)
                        elapsed += poll_interval
                        poll_interval = min(poll_interval * 2, 60)
                    else:
                        raise MetaAPIError("Timeout: child video processing took too long (>10 minutes)")
                children_ids.append(child_id)

            # create the carousel parent container using children ids
            container_id = self._create_container(
                caption=final_caption,
                post_type="post",
                children=children_ids
            )

            post_id = self._publish(container_id)
            print(f"Instagram carousel post successful: {post_id}")
            return post_id

        # single media (string) or no media
        if media_url and isinstance(media_url, str):
            if post_type == "reel":
                video_url = media_url
            elif post_type == "story":
                # stories accept image or video
                if media_url.lower().endswith(('.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv')):
                    video_url = media_url
                else:
                    image_url = media_url
            else:  # feed post
                if media_url.lower().endswith(('.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv')):
                    video_url = media_url
                else:
                    image_url = media_url

        # Create main container
        container_id = self._create_container(
            image_url=image_url,
            video_url=video_url,
            caption=final_caption,
            is_reel=(post_type == "reel"),
            post_type=post_type,
            children=None
        )

        # If it's a video/reel or story video we usually need to poll for processing completion
        if video_url:
            # --- Polling for processing completion ---
            max_wait_seconds = 600  # 10 minutes max
            poll_interval = 10
            elapsed = 0

            print(f"Polling container {container_id} for FINISHED status...")

            while elapsed < max_wait_seconds:
                status_data = self._get_container_status(container_id)
                status_code = status_data.get("status_code")

                print(f"Current status_code: {status_code}")

                if status_code == "FINISHED":
                    print("Video processing finished!")
                    break
                elif status_code == "ERROR":
                    raise MetaAPIError("Video processing failed (status_code: ERROR)")
                elif status_code == "EXPIRED":
                    raise MetaAPIError("Media container expired before processing completed")

                time.sleep(poll_interval)
                elapsed += poll_interval
                poll_interval = min(poll_interval * 2, 60)
            else:
                raise MetaAPIError("Timeout: Video processing took too long (>10 minutes)")

            # --- Retry logic for publish (handles transient "not ready" even after FINISHED) ---
            max_publish_retries = 8
            publish_delay = 5

            for attempt in range(1, max_publish_retries + 1):
                try:
                    post_id = self._publish(container_id)
                    print(f"Instagram post successful (publish attempt {attempt}): {post_id}")
                    return post_id
                except MetaAPIError as e:
                    error_str = str(e).lower()
                    if ("media is not ready" in error_str or
                        "2207027" in error_str or
                        "9007" in error_str or
                        "media id is not available" in error_str):
                        if attempt < max_publish_retries:
                            print(f"Transient 'not ready' error – retrying publish in {publish_delay}s (attempt {attempt + 1}/{max_publish_retries})")
                            time.sleep(publish_delay)
                            publish_delay = min(publish_delay * 2, 60)
                            continue
                    raise

            raise MetaAPIError("Failed to publish media after maximum retries")

        else:
            # Images or story images are synchronous for the most part
            post_id = self._publish(container_id)
            print(f"Instagram post successful: {post_id}")
            return post_id
