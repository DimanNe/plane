# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import gc
import os
import sys
import logging
from functools import partialmethod
from datetime import timedelta

# Third party imports
from celery import Celery
from kombu.transport import redis as redis_transport
from pythonjsonlogger.json import JsonFormatter
from celery.signals import after_setup_logger, after_setup_task_logger, beat_init, worker_ready, worker_shutdown
from celery.schedules import crontab, schedule

# Module imports
from plane.settings.redis import redis_instance

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plane.settings.production")

ri = redis_instance()

# Configurable metrics push interval (in minutes)
# Default: 360 (6 hours), set to 5 for development/testing
def _get_metrics_push_interval_minutes() -> int:
    raw = os.environ.get("METRICS_PUSH_INTERVAL_MINUTES", "360")
    try:
        value = int(raw)
        # Cap at 10,000,000 minutes to prevent timedelta(minutes=...) OverflowError
        # on arbitrarily large inputs while still allowing multi-year intervals.
        return value if 0 < value <= 10_000_000 else 360
    except (ValueError, OverflowError):
        return 360

METRICS_PUSH_INTERVAL_MINUTES = _get_metrics_push_interval_minutes()

# A worker that stops first waits for its pending blocking read of the queue to return, so that a
# task Redis hands over at that instant is not lost. kombu fixes the timeout of that read at one
# second and has no setting for it; a shorter one lets a stopping worker exit that much sooner.
redis_transport.Channel._brpop_start = partialmethod(redis_transport.Channel._brpop_start, timeout=0.01)

app = Celery("plane")

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.beat_schedule = {
    # Intra day recurring jobs
    "check-every-five-minutes-to-send-email-notifications": {
        "task": "plane.bgtasks.email_notification_task.stack_email_notification",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "push-instance-metrics": {
        "task": "plane.license.bgtasks.telemetry_metrics.push_instance_metrics",
        "schedule": schedule(run_every=timedelta(minutes=METRICS_PUSH_INTERVAL_MINUTES)),
    },
    # Occurs once every day
    "check-every-day-to-delete-hard-delete": {
        "task": "plane.bgtasks.deletion_task.hard_delete",
        "schedule": crontab(hour=0, minute=0),  # UTC 00:00
    },
    "check-every-day-to-archive-and-close": {
        "task": "plane.bgtasks.issue_automation_task.archive_and_close_old_issues",
        "schedule": crontab(hour=1, minute=0),  # UTC 01:00
    },
    "check-every-day-to-delete_exporter_history": {
        "task": "plane.bgtasks.exporter_expired_task.delete_old_s3_link",
        "schedule": crontab(hour=1, minute=30),  # UTC 01:30
    },
    "check-every-day-to-delete-file-asset": {
        "task": "plane.bgtasks.file_asset_task.delete_unuploaded_file_asset",
        "schedule": crontab(hour=2, minute=0),  # UTC 02:00
    },
    "check-every-day-to-delete-api-logs": {
        "task": "plane.bgtasks.cleanup_task.delete_api_logs",
        "schedule": crontab(hour=2, minute=30),  # UTC 02:30
    },
    "check-every-day-to-delete-email-notification-logs": {
        "task": "plane.bgtasks.cleanup_task.delete_email_notification_logs",
        "schedule": crontab(hour=2, minute=45),  # UTC 02:45
    },
    "check-every-day-to-delete-page-versions": {
        "task": "plane.bgtasks.cleanup_task.delete_page_versions",
        "schedule": crontab(hour=3, minute=0),  # UTC 03:00
    },
    "check-every-day-to-delete-issue-description-versions": {
        "task": "plane.bgtasks.cleanup_task.delete_issue_description_versions",
        "schedule": crontab(hour=3, minute=15),  # UTC 03:15
    },
    "check-every-day-to-delete-webhook-logs": {
        "task": "plane.bgtasks.cleanup_task.delete_webhook_logs",
        "schedule": crontab(hour=3, minute=30),  # UTC 03:30
    },
    "check-every-day-to-delete-exporter-history": {
        "task": "plane.bgtasks.exporter_expired_task.delete_old_s3_link",
        "schedule": crontab(hour=3, minute=45),  # UTC 03:45
    },
}


# Setup logging
@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    formatter = JsonFormatter('"%(levelname)s %(asctime)s %(module)s %(name)s %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(fmt=formatter)
    logger.addHandler(handler)


@after_setup_task_logger.connect
def setup_task_loggers(logger, *args, **kwargs):
    formatter = JsonFormatter('"%(levelname)s %(asctime)s %(module)s %(name)s %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(fmt=formatter)
    logger.addHandler(handler)


# The script that starts the services waits for these lines
@worker_ready.connect
def announce_worker_ready(sender, *args, **kwargs):
    print(f"Plane worker ready: {sender.hostname}", file=sys.__stderr__, flush=True)


# When this signal is sent a stopping worker has finished its task and closed its connections. The
# interpreter would then spend longer than all of that on collecting garbage in memory that the
# exit frees anyway; frozen objects are left out of those collections.
@worker_shutdown.connect
def skip_garbage_collection_at_exit(sender, *args, **kwargs):
    gc.freeze()


@beat_init.connect
def announce_beat_ready(sender, *args, **kwargs):
    sender.scheduler  # loads the schedule, so that the line below is printed only after it
    print("Plane beat ready:", file=sys.__stderr__, flush=True)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.beat_scheduler = "django_celery_beat.schedulers.DatabaseScheduler"
