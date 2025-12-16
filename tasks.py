import traceback
import time
from datetime import datetime
from typing import Optional
import os
from dotenv import load_dotenv
import pytz
from celery import shared_task  # Back to shared_task—no app import needed
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from Database import (
    GeneratedContent,
    Task,
    TaskStatus,
    PlatformSelection,
    PublishStatus,
    OAuthToken,
    PostAttempt,
    AttemptStatus,
    ErrorLog,
    SyncSessionLocal,
)
from ThreadPoster import post_thread
from meta_poster import InstagramPoster, ThreadsPoster, FacebookPoster

load_dotenv()
ist = pytz.timezone("Asia/Kolkata")

@shared_task(bind=True, max_retries=3, default_retry_delay=60)  # Reverted to shared_task
def execute_posting(self, task_id: str) -> None:
    session = SyncSessionLocal()
    try:
        # Load task with relationships
        task = session.query(Task).options(
            selectinload(Task.platform_selections).selectinload(PlatformSelection.platform),
            selectinload(Task.generated_contents).selectinload(GeneratedContent.media),
        ).filter(Task.task_id == task_id).first()
       
        if not task:
            self.retry(countdown=300)  # Retry in 5 min if task missing (transient)
            return
        # Set to queued at start
        task.status = TaskStatus.queued
        session.commit()
        # Validate content exists
        if not task.generated_contents:
            raise ValueError("No generated content found for task")
        gen_content = task.generated_contents[0]  # Assume one
        caption = gen_content.caption or ""
        hashtags = gen_content.hashtags or []
        # Determine image
        imgUrl = None
        if gen_content.media and gen_content.media[0].is_generated:
            media = gen_content.media[0]
            imgUrl = media.img_url or media.storage_path  
        all_success = True
        for sel in task.platform_selections:
            if sel.publish_status != PublishStatus.scheduled:
                continue
            platform = sel.platform
            if not platform.api_name:
                # Error: missing api_name
                _handle_post_failure(session, task, platform, sel, "Missing API name configuration")
                all_success = False
                continue
            # Get OAuth token
            token = session.query(OAuthToken).filter(
                OAuthToken.platform_id == platform.platform_id,
                OAuthToken.organization_id == task.organization_id
            ).first()
            if not token or (token.expires_at and token.expires_at < datetime.now(ist)):
                # Transient if expired (retry might refresh), but for now permanent
                _handle_post_failure(session, task, platform, sel, "Invalid or expired OAuth token")
                all_success = False
                continue
            # Execute post
            start_time = time.time()
            attempt = PostAttempt(
                task_id=task.task_id,
                platform_id=platform.platform_id,
                attempted_at=datetime.now(ist),
                status=AttemptStatus.transient_failure,  # Default
                latency_ms=0,
            )
            session.add(attempt)
            session.flush()  # Get attempt_id
            try:
                if platform.api_name.lower() == "instagram":
                    poster = InstagramPoster()
                    poster.post(
                        caption=caption,
                        image_url=imgUrl,
                        hashtags=hashtags,
                    )
                elif platform.api_name.lower() == "threads":
                    poster = ThreadsPoster(
                            threads_user_id=os.getenv('THREADS_USER_ID'),  # thread user id
                            access_token=os.getenv('THREADS_LONG_LIVE_TOKEN'),  # long-lived token
                            username=os.getenv('THREAD_USERNAME')  # optional
                            )
                    if imgUrl:
                        poster.post(
                            text=caption,
                            image_url=imgUrl,
                            hashtags=hashtags,
                        )
                    else:
                        poster.post(
                            text=caption,
                            hashtags=hashtags,
                        )
                elif platform.api_name.lower() == "facebook":
                    poster = FacebookPoster(
                        page_id=os.getenv('PAGE_ID'),
                        page_access_token=os.getenv('PAGE_ACSESS_TOKEN')
                    )
                    if imgUrl:
                        poster.post_photo(
                            message=caption,
                            image=imgUrl,
                            hashtags=hashtags,
                        )
                    else:
                        poster.post_text(
                            message=caption,
                            link=None,
                            hashtags=hashtags,
                        )
                elif platform.api_name.lower() == "x":
                    if imgUrl:
                        post_thread(
                        captions= caption,
                        image_per_tweet=imgUrl,
                        hashtags= hashtags,
                        )

                    else:
                        post_thread(
                        captions=caption,
                        hashtags= hashtags,
                        )
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
        # Log DB error (in production, use logger)
        raise self.retry(exc=db_err, countdown=300)  # Retry on DB transient
    except Exception as e:
        session.rollback()
        # Permanent failure for unexpected errors
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
    """Helper to create ErrorLog and update selection."""
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
    session.flush()  # Get error_id
    return error_log


