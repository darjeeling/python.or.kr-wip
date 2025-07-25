import os
import logfire
from celery import Celery
from celery.signals import worker_init, beat_init


# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pythonkr_backend.settings")

app = Celery("pythonkr_backend")


# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@worker_init.connect()
def init_worker(*args, **kwargs):
    logfire.configure(
        environment="prod",
        service_name="celery-worker",
        send_to_logfire="if-token-present",
    )
    logfire.instrument_celery()
    logfire.instrument_pydantic_ai()


@beat_init.connect()
def init_beat(*args, **kwargs):
    logfire.configure(
        environment="prod",
        service_name="celery-beat",
        send_to_logfire="if-token-present",
    )
    logfire.instrument_celery()
    logfire.instrument_pydantic_ai()
