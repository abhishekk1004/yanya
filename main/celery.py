"""Celery application. Beat schedule ships with the code (nightly jobs)."""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

app = Celery("nepal_travel")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Nightly: rebuild popularity scores and behavioural taste vectors.
app.conf.beat_schedule = {
    "refresh-popularity-nightly": {
        "task": "travel.tasks.refresh_popularity",
        "schedule": crontab(hour=2, minute=0),
    },
    "rebuild-taste-nightly": {
        "task": "travel.tasks.rebuild_behavioural_taste",
        "schedule": crontab(hour=2, minute=30),
    },
}
