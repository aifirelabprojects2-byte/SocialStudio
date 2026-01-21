import httpx
import mimetypes
from typing import Optional, Union, List, Tuple
from urllib.parse import urlparse, quote
import os
import time
import concurrent.futures

LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_IMAGES_INIT_URL = "https://api.linkedin.com/rest/images?action=initializeUpload"
LINKEDIN_VIDEOS_INIT_URL = "https://api.linkedin.com/rest/videos?action=initializeUpload"
LINKEDIN_IMAGE_CHECK_URL = "https://api.linkedin.com/rest/images/{image_id}"  
LINKEDIN_VIDEO_CHECK_URL = "https://api.linkedin.com/rest/videos/{video_id}" 
def _get_linkedin_version() -> str:
    from datetime import datetime, timedelta
    target_date = datetime.now() - timedelta(days=60)
    return target_date.strftime("%Y%m")

DEFAULT_LINKEDIN_VERSION = _get_linkedin_version()


MAX_CONCURRENT_UPLOADS = 5
ASSET_POLL_INTERVAL = 2.0
ASSET_POLL_TIMEOUT = 120.0 


def _get_content_type_and_length(client: httpx.Client, url: str) -> Tuple[Optional[str], Optional[int]]:
    """Try HEAD to get content-type/length; fallback to small-range GET if HEAD is rejected."""
    try:
        r = client.head(url, follow_redirects=True, timeout=30.0)
        content_type = r.headers.get("content-type")
        length = r.headers.get("content-length")
        return (content_type, int(length)) if length and length.isdigit() else (content_type, None)
    except httpx.HTTPError:
        # Some hosts reject HEAD — try a small GET range
        try:
            r = client.get(url, headers={"Range": "bytes=0-1023"}, follow_redirects=True, timeout=30.0)
            content_type = r.headers.get("content-type")
            length = r.headers.get("content-length")
            return (content_type, int(length)) if length and length.isdigit() else (content_type, None)
        except httpx.HTTPError:
            return (None, None)


def _guess_type_from_extension(url: str) -> Optional[str]:
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if not ext:
        return None
    typ, _ = mimetypes.guess_type(f"file{ext}")
    return typ


def _is_video_mime(mime: Optional[str]) -> bool:
    if not mime:
        return False
    return mime.split("/")[0] == "video"


def _is_image_mime(mime: Optional[str]) -> bool:
    if not mime:
        return False
    return mime.split("/")[0] == "image"


def _download_bytes(client: httpx.Client, url: str) -> bytes:
    """
    Robust streaming downloader for large media.
    Safe for flaky CDNs and long transfers.
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
    }

    with client.stream(
        "GET",
        url,
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(
            connect=30.0,
            read=300.0,
            write=300.0,
            pool=30.0,
        ),
    ) as response:
        response.raise_for_status()
        chunks = []
        for chunk in response.iter_bytes():
            if chunk:
                chunks.append(chunk)
        return b"".join(chunks)



# --- new initialization / upload flows for images & videos -------------------
def _initialize_image_upload(client: httpx.Client, access_token: str, owner_urn: str, linkedin_version: str = DEFAULT_LINKEDIN_VERSION) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": linkedin_version,
    }
    body = {"initializeUploadRequest": {"owner": owner_urn}}
    resp = client.post(LINKEDIN_IMAGES_INIT_URL, json=body, headers=headers, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def _initialize_video_upload(
    client: httpx.Client,
    access_token: str,
    owner_urn: str,
    file_size: int,
    linkedin_version: str = DEFAULT_LINKEDIN_VERSION,  # Added param
) -> dict:
    if not file_size or file_size <= 0:
        raise ValueError("file_size is required for video upload")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": linkedin_version,  # Required header added
    }

    payload = {
        "initializeUploadRequest": {
            "owner": owner_urn,
            "fileSizeBytes": file_size,      # Fixed field name
            "uploadCaptions": False,         # Recommended
            "uploadThumbnail": False,        # Recommended
        }
    }

    resp = client.post(
        LINKEDIN_VIDEOS_INIT_URL,  # Use constant for consistency
        json=payload,
        headers=headers,
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()



def _put_to_upload_url(client: httpx.Client, upload_url: str, data: bytes, headers: Optional[dict] = None, auth_header: Optional[str] = None) -> httpx.Response:
    request_headers = headers.copy() if headers else {}
    if auth_header:
        request_headers["Authorization"] = auth_header
    resp = client.put(upload_url, content=data, headers=request_headers, timeout=300.0)
    resp.raise_for_status()
    return resp


def _check_image_available(client: httpx.Client, access_token: str, image_urn: str, linkedin_version: str = DEFAULT_LINKEDIN_VERSION, timeout: float = ASSET_POLL_TIMEOUT) -> None:
    """
    Poll image endpoint until available. Uses GET /rest/images/{id}.
    image_urn example: urn:li:image:C4D00... -> id is last part
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": linkedin_version,
    }
    if image_urn.startswith("urn:li:image:"):
        image_id = image_urn.split(":")[-1]
    else:
        image_id = image_urn
    url = LINKEDIN_IMAGE_CHECK_URL.format(image_id=image_id)
    deadline = time.monotonic() + timeout
    while True:
        resp = client.get(url, headers=headers, timeout=30.0)
        resp.raise_for_status()
        info = resp.json()
        # The exact field names can vary; check for status or recipes like previous code — be permissive.
        # Many image uploads are immediately available; return fast if no explicit status is present.
        # If 'status' exists, wait for AVAILABLE
        status = info.get("status") or info.get("processingStatus") or None
        if not status:
            return
        if status.upper() in ("AVAILABLE", "READY"):
            return
        if status.upper() in ("FAILED", "ERROR"):
            raise RuntimeError(f"Image processing failed, status: {status}, info: {info}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"Timed out waiting for image {image_urn} to become AVAILABLE; last status: {status}")
        time.sleep(ASSET_POLL_INTERVAL)


def _check_video_available(client: httpx.Client, access_token: str, video_urn: str, linkedin_version: str = DEFAULT_LINKEDIN_VERSION, timeout: float = ASSET_POLL_TIMEOUT) -> None:
    """
    Poll video endpoint until available.
    Requires full encoded URN: urn%3Ali%3Avideo%3A{ID}
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": linkedin_version,
    }

    # Ensure we have the full URN
    if not video_urn.startswith("urn:li:video:"):
        raise ValueError(f"Invalid video URN format: {video_urn}")

    # URL-encode the full URN (especially the colons)
    encoded_urn = quote(video_urn, safe='')

    url = f"https://api.linkedin.com/rest/videos/{encoded_urn}"

    deadline = time.monotonic() + timeout
    while True:
        resp = client.get(url, headers=headers, timeout=30.0)
        if resp.status_code == 404:
            # Temporary: video not yet indexed; continue polling
            time.sleep(ASSET_POLL_INTERVAL)
            continue

        resp.raise_for_status()  # Will raise on 400, 500, etc.

        info = resp.json()

        # Check status fields
        status = (
            info.get("status")
            or info.get("processingStatus")
            or info.get("lifecycleState")
            or info.get("serviceStatus")  # fallback
        )

        if status and isinstance(status, str):
            s = status.upper()
            if s in ("AVAILABLE", "READY", "PROCESSED", "PUBLISHED"):
                return
            if s in ("FAILED", "ERROR", "CLIENT_ERROR"):
                raise RuntimeError(f"Video processing failed: {status} | Details: {info}")

        # If no explicit status, assume ready (common after upload completes)
        if not status:
            return

        if time.monotonic() > deadline:
            raise TimeoutError(f"Timed out waiting for video {video_urn} to become available. Last response: {info}")

        time.sleep(ASSET_POLL_INTERVAL)

# --- main upload helper using new endpoints ---------------------------------
def _upload_single_media_from_url(client: httpx.Client, access_token: str, owner_urn: str, media_url: str, linkedin_version: str = DEFAULT_LINKEDIN_VERSION) -> str:

    content_type, content_length = _get_content_type_and_length(client, media_url)
    if not content_type:
        content_type = _guess_type_from_extension(media_url) or "application/octet-stream"

    is_image = _is_image_mime(content_type)
    is_video = _is_video_mime(content_type)

    # fallback to extension guess if uncertain
    if not (is_image or is_video):
        guessed = _guess_type_from_extension(media_url)
        is_image = _is_image_mime(guessed)
        is_video = _is_video_mime(guessed)

    if is_image:
        init_resp = _initialize_image_upload(
            client,
            access_token,
            owner_urn,
            linkedin_version=linkedin_version
        )

        value = init_resp.get("value") or {}
        upload_url = value.get("uploadUrl")
        image_urn = value.get("image")

        if not upload_url or not image_urn:
            raise RuntimeError(
                "initializeUpload (image) returned unexpected payload: " + str(init_resp)
            )

        media_bytes = _download_bytes(client, media_url)

        headers = {}
        if content_type:
            headers["Content-Type"] = content_type

        _put_to_upload_url(
            client,
            upload_url,
            media_bytes,
            headers=headers,
            auth_header=f"Bearer {access_token}"
        )

        return image_urn


    elif is_video:
        media_bytes = _download_bytes(client, media_url)
        file_size = len(media_bytes)

        if file_size <= 0:
            raise ValueError("Downloaded video is empty")

        if file_size > 200 * 1024 * 1024:
            raise NotImplementedError("Video > 200MB requires multi-part upload; not implemented.")

        # Initialize with version param
        init_resp = _initialize_video_upload(
            client, access_token, owner_urn, file_size=file_size, linkedin_version=linkedin_version
        )

        value = init_resp.get("value") or {}
        video_urn = value.get("video")
        upload_instructions = value.get("uploadInstructions") or []
        upload_token = value.get("uploadToken", "")  # Usually empty for single-part

        if not video_urn or not upload_instructions:
            raise RuntimeError("initializeUpload (video) returned unexpected payload: " + str(init_resp))

        if len(upload_instructions) != 1:
            raise NotImplementedError("Multi-part video upload not supported yet.")

        instr = upload_instructions[0]
        upload_url = instr.get("uploadUrl")
        if not upload_url:
            raise RuntimeError("No uploadUrl in instructions")

        # Upload full video
        headers = {"Content-Type": content_type or "application/octet-stream"}

        try:
            upload_resp = _put_to_upload_url(
                client,
                upload_url,
                media_bytes,
                headers=headers,
                auth_header=f"Bearer {access_token}",
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                upload_resp = _put_to_upload_url(
                    client,
                    upload_url,
                    media_bytes,
                    headers=headers,
                    auth_header=None,
                )
            else:
                raise

        # Capture ETag (or fallback to signed ID if no ETag)
        etag = upload_resp.headers.get("ETag")
        part_id = etag.strip('"') if etag else instr.get("signedId", "")

        if not part_id:
            raise RuntimeError("No ETag or signedId returned from upload PUT")

        # *** NEW: Finalize the upload ***
        _finalize_video_upload(
            client,
            access_token,
            video_urn,
            uploaded_part_ids=[part_id],
            upload_token=upload_token,
            linkedin_version=linkedin_version,
        )

        # Now poll for availability
        _check_video_available(
            client,
            access_token,
            video_urn,
            linkedin_version=linkedin_version,
        )

        return video_urn


    else:
        raise ValueError("Could not determine media type (image or video) for URL: " + media_url)

def _finalize_video_upload(
    client: httpx.Client,
    access_token: str,
    video_urn: str,
    uploaded_part_ids: List[str],
    upload_token: str = "",
    linkedin_version: str = DEFAULT_LINKEDIN_VERSION,
) -> None:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": linkedin_version,
    }

    payload = {
        "finalizeUploadRequest": {
            "video": video_urn,
            "uploadToken": upload_token,
            "uploadedPartIds": uploaded_part_ids,
        }
    }

    resp = client.post(
        "https://api.linkedin.com/rest/videos?action=finalizeUpload",
        json=payload,
        headers=headers,
        timeout=30.0,
    )
    resp.raise_for_status()


# --- public posting function (preserves original signature) -----------------
def post_to_linkedin(
    access_token: str,
    person_urn: str,
    text: str,
    media_url: Optional[Union[str, List[str]]] = None,
    linkedin_version: str = DEFAULT_LINKEDIN_VERSION,
) -> Optional[str]:
    headers_base = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": linkedin_version,
    }

    # Normalize media_url to list if needed
    if media_url is None:
        media_list: List[str] = []
    elif isinstance(media_url, str):
        media_list = [media_url]
    else:
        media_list = list(media_url)

    with httpx.Client() as client:
        try:
            # text-only -> identical behavior to your original
            if not media_list:
                resp = client.post(
                    LINKEDIN_POSTS_URL,
                    headers=headers_base,
                    json={
                        "author": person_urn,
                        "commentary": text,
                        "visibility": "PUBLIC",
                        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                        "lifecycleState": "PUBLISHED",
                        "isReshareDisabledByAuthor": False,
                    },
                    timeout=30.0,
                )
                if resp.status_code == 201:
                    post_id = resp.headers.get("x-restli-id")
                    print(f"Posted successfully! Post ID: {post_id}")
                    return post_id
                else:
                    print(f"Error: {resp.status_code} - {resp.text}")
                    resp.raise_for_status()

            # Discover mime types/lengths for each provided media URL concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {
                    executor.submit(_get_content_type_and_length, client, u): u for u in media_list
                }
                type_checks = [future.result() for future in concurrent.futures.as_completed(future_to_url)]
            mimes = [t for t, _ in type_checks]
            lengths = [l for _, l in type_checks]

            is_any_video = any(_is_video_mime(m) for m in mimes)
            is_any_image = any(_is_image_mime(m) for m in mimes)
            if not (is_any_video or is_any_image):
                for u in media_list:
                    ext_type = _guess_type_from_extension(u)
                    if _is_video_mime(ext_type):
                        is_any_video = True
                    if _is_image_mime(ext_type):
                        is_any_image = True

            if is_any_image and is_any_video:
                raise ValueError("Mixing images and video in a single post is not supported. Provide only images or a single video URL.")

            if is_any_video:
                if len(media_list) != 1:
                    raise ValueError("LinkedIn supports a single video per post in this helper. Provide exactly one video URL.")
                video_url = media_list[0]
                # Upload video and get URN
                video_urn = _upload_single_media_from_url(client, access_token, person_urn, video_url, linkedin_version=linkedin_version)
                title = os.path.basename(urlparse(video_url).path) or "video"
                post_body = {
                    "author": person_urn,
                    "commentary": text,
                    "visibility": "PUBLIC",
                    "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                    "content": {"media": {"title": title, "id": video_urn}},
                    "lifecycleState": "PUBLISHED",
                    "isReshareDisabledByAuthor": False,
                }
            else:
                # Images (single or multiple)
                sem = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_UPLOADS)

                def _worker_upload(u: str):
                    return _upload_single_media_from_url(client, access_token, person_urn, u, linkedin_version=linkedin_version)

                with sem as executor:
                    future_to_url = {executor.submit(_worker_upload, u): u for u in media_list}
                    asset_urns = [future.result() for future in concurrent.futures.as_completed(future_to_url)]

                if len(asset_urns) == 1:
                    post_body = {
                        "author": person_urn,
                        "commentary": text,
                        "visibility": "PUBLIC",
                        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                        "content": {"media": {"id": asset_urns[0]}},
                        "lifecycleState": "PUBLISHED",
                        "isReshareDisabledByAuthor": False,
                    }
                else:
                    images_array = [{"id": urn, "altText": ""} for urn in asset_urns]
                    post_body = {
                        "author": person_urn,
                        "commentary": text,
                        "visibility": "PUBLIC",
                        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                        "content": {"multiImage": {"images": images_array}},
                        "lifecycleState": "PUBLISHED",
                        "isReshareDisabledByAuthor": False,
                    }

            # Create the post
            resp = client.post(LINKEDIN_POSTS_URL, headers=headers_base, json=post_body, timeout=30.0)
            if resp.status_code == 201:
                post_id = resp.headers.get("x-restli-id")
                print(f"Posted successfully! Post ID: {post_id}")
                return post_id
            else:
                print(f"Error: {resp.status_code} - {resp.text}")
                resp.raise_for_status()

        except Exception as exc:
            print("Posting error:", repr(exc))
            raise

# post_to_linkedin(
#     access_token="AQXqNjFYpWPdP3JoexrT98xW1QINmvJlx4LbqIAJNTUFOFEzIasCpaNxqscZGWM1hMxiM8h9IP2p6f0DEL-2_3UCIkLI5F2i7d6Xg8VcR6vVguPj2Rbobk3vyW_t5t6YB75JU829MDSCo45xg-6F8g6YjHetz7LFylzfsb3WwpbHuqCLt-cI_5FvreaxEugJ2i2dBDQIR01DhIdDCIL-DfjSjaMQb-kueks3TBRGTpn1RwQATrzU2WgEceDcmQgbqHIE8hXb6Ubi-LdNtKd5gsWghByWJUYd834yvmXyfgTTMKPqZtYiMmZZmpCZkDXfKQDmqnYr2vKb2bAdnd9C9-CQXqwf1A", 
#     person_urn="urn:li:person:p64Y5G_e74",
#     text="Testing..",
#     media_url=["https://i.ibb.co/j9sFPfcG/5666109a-3a0b-4850-9d80-79b1a563dafd-20260102-210656.png","https://i.ibb.co/TMCdKSsS/31d737de-b27f-4656-993a-b3fab146d358-20260102-213656.png"]
# )