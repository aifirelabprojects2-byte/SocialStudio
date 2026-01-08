import traceback
import time
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
import pytz
from celery import shared_task 
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from Database import (
    GeneratedContent,
    Task,
    TaskStatus,
    PlatformSelection,
    PublishStatus,
    PostAttempt,
    AttemptStatus,
    ErrorLog,
    SyncSessionLocal,
    get_sync_db
)
from LinkedInPoster import post_to_linkedin
from PlatformTokenGen import get_platform_credentials_sync
from XPoster import post_to_x
from meta_poster import InstagramPoster, ThreadsPoster, FacebookPoster
from meta_poster.utils import build_caption


load_dotenv()
ist = pytz.timezone("Asia/Kolkata")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)  
def execute_posting(self, task_id: str) -> None:
    session = SyncSessionLocal()
    try:
        task = session.query(Task).options(
            selectinload(Task.platform_selections).selectinload(PlatformSelection.platform),
            selectinload(Task.generated_contents).selectinload(GeneratedContent.media),
        ).filter(Task.task_id == task_id).first()
       
        if not task:
            self.retry(countdown=300)  
            return
        task.status = TaskStatus.queued
        session.commit()
        if not task.generated_contents:
            raise ValueError("No generated content found for task")
        gen_content = task.generated_contents[0] 
        caption = gen_content.caption or ""
        hashtags = gen_content.hashtags or []
        media_urls = [
            media.img_url or media.storage_path
            for media in gen_content.media
            if media.is_generated and (media.img_url or media.storage_path)
        ]
        
        print("Media URLs:", media_urls)
        if len(media_urls) == 0:
            media_param = None
        elif len(media_urls) == 1:
            media_param = media_urls[0]
        else:
            media_param = media_urls
        all_success = True
        for sel in task.platform_selections:
            if sel.publish_status != PublishStatus.scheduled:
                continue
            platform = sel.platform
            if not platform.api_name:
                _handle_post_failure(session, task, platform, sel, "Missing API name configuration")
                all_success = False
                continue
            start_time = time.time()
            attempt = PostAttempt(
                task_id=task.task_id,
                platform_id=platform.platform_id,
                attempted_at=datetime.now(ist),
                status=AttemptStatus.transient_failure,  
                latency_ms=0,
            )
            session.add(attempt)
            session.flush()  
            try:
                if platform.api_name.lower() == "instagram":
                    InsTkn = get_platform_credentials_sync("instagram")

                    poster = InstagramPoster(
                        page_id=InsTkn.meta.get("PAGE_ID"),
                        access_token=InsTkn.access_token
                    )
                    post_type = "post"  

                    if task.notes:
                        notes_lower = task.notes.lower()
                        if "reel" in notes_lower:
                            post_type = "reel"
                        elif "story" in notes_lower:
                            post_type = "story"

                    poster.post(
                        caption=caption,
                        media_url=media_param,
                        hashtags=hashtags,
                        post_type=post_type
                    )

                elif platform.api_name.lower() == "threads":
                    ThrTkn=get_platform_credentials_sync("threads")
                    poster = ThreadsPoster(
                            threads_user_id=ThrTkn.account_id,
                            access_token=ThrTkn.meta.get("THREADS_LONG_LIVE_TOKEN"),
                            username=ThrTkn.account_name,
                            )
                    if media_param:
                        poster.post(
                            text=caption,
                            media_url=media_param, 
                            hashtags=hashtags,
                        )
                    else:
                        poster.post(
                            text=caption,
                            hashtags=hashtags,
                        )

                elif platform.api_name.lower() == "facebook":
                    FbTkn=get_platform_credentials_sync("facebook")
                    poster = FacebookPoster(
                        page_id=FbTkn.account_id,
                        page_access_token=FbTkn.access_token
                    )
                    if media_param:
                        poster.post_media(
                            message=caption,
                            media=media_param,  
                            hashtags=hashtags,
                        )
                    else:
                        poster.post_text(
                            message=caption,
                            link=None,
                            hashtags=hashtags,
                        )

                elif platform.api_name.lower() == "twitter":
                    final_text = build_caption(caption, hashtags)
                    if media_param:
                        ttt = post_to_x(
                            text=final_text,
                            media_url=media_param, 
                        )
                        print(ttt)
                    else:
                        sss = post_to_x(
                            text=final_text
                        )
                        print(sss)

                elif platform.api_name.lower() == "linkedin":
                    LnTkn=get_platform_credentials_sync("linkedin")
                    if media_param:
                        ttt = post_to_linkedin(
                            access_token=LnTkn.access_token,
                            person_urn=f"urn:li:person:{LnTkn.account_id}",
                            text=caption,
                            media_url=media_param, 
                        )
                        print(ttt)
                    else:
                        sss = post_to_linkedin(
                            access_token=LnTkn.access_token,
                            person_urn=f"urn:li:person:{LnTkn.account_id}",
                            text=caption,
                        )
                        print(sss)
                else:
                    raise ValueError(f"Unsupported platform: {platform.api_name}")
                # Success
                latency_ms = int((time.time() - start_time) * 1000)
                attempt.status = AttemptStatus.success
                attempt.response = {"status": "posted", "success": True}
                attempt.latency_ms = latency_ms
                sel.publish_status = PublishStatus.posted
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                attempt.status = AttemptStatus.permanent_failure 
                attempt.latency_ms = latency_ms
                attempt.response = {"status": "failed", "error": str(e)}
                error_log = _handle_post_failure(
                    session, task, platform, sel, str(e),
                    error_type=type(e).__name__,
                    error_code="POSTING_ERROR",  
                    details={"traceback": traceback.format_exc()},
                    attempt=attempt
                )
                attempt.error_log_id = error_log.error_id
                all_success = False
               
        # Update task status
        if all_success:
            task.status = TaskStatus.posted
        else:
            task.status = TaskStatus.failed
        session.commit()
    except SQLAlchemyError as db_err:
        session.rollback()
        raise self.retry(exc=db_err, countdown=300)  
    except Exception as e:
        session.rollback()
        raise self.update_state(state="FAILURE", meta={"exc": str(e)})
    finally:
        session.close()

def _handle_post_failure(
    session,
    task,
    platform,
    sel,
    message: str,
    error_type: Optional[str] = "RuntimeError",
    error_code: Optional[str] = "UNKNOWN",
    details: Optional[dict] = None,
    attempt: Optional[PostAttempt] = None,
) -> ErrorLog:
    sel.publish_status = PublishStatus.failed
    error_log = ErrorLog(
        task_id=task.task_id,
        platform_id=platform.platform_id,
        attempt_id=attempt.attempt_id if attempt else None,
        error_type=error_type,
        error_code=error_code,
        message=message,
        details=details or {},
        created_at=datetime.now(ist),
    )
    session.add(error_log)
    session.flush()
    return error_log
