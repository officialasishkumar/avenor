"""Celery application — broker and result backend powered by Redis.

Start a worker with:
    celery -A avenor.tasks worker -l info -Q default,collection
"""
from __future__ import annotations

from celery import Celery

from avenor.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "avenor",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "avenor.tasks.collection.*": {"queue": "collection"},
    },
    task_default_queue="default",
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

celery_app.autodiscover_tasks(["avenor.tasks"])
