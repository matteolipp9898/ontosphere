"""Celery application configuration for OntoSphere.

Provides the shared ``celery_app`` instance used by all task modules.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("ontosphere")

celery_app.config_from_object(
    {
        "broker_url": settings.REDIS_URL,
        "result_backend": settings.REDIS_URL,
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "UTC",
        "enable_utc": True,
        "task_track_started": True,
        "task_acks_late": True,
        "worker_prefetch_multiplier": 1,
        "task_default_queue": "ontosphere",
        "task_routes": {
            "app.tasks.processing.process_ontology_task": {"queue": "ontosphere"},
        },
    }
)

# Auto-discover task modules
celery_app.autodiscover_tasks(["app.tasks"])
