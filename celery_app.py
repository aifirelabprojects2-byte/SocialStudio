# celery_app.py
from celery import Celery
import os

broker_url = os.getenv("CELERY_BROKER_URL", "sqla+sqlite:///celerymq.db")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "db+sqlite:///celery_results.db")

celery_app = Celery("meta_poster_tasks", broker=broker_url, backend=result_backend)  # Unique name

celery_app.conf.update(
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_time_limit=300,  # 5 min timeout
    task_soft_time_limit=280,
    worker_prefetch_multiplier=1,  # Conservative for DB
)

# Import tasks module to register tasks with this app (uses current app context for @shared_task)
import tasks