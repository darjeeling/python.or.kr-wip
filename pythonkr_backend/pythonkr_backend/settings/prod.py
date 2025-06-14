import os
import sys
import logfire
import logging

from .base import *


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'pk',
    }
}

CSRF_TRUSTED_ORIGINS = ["https://pk.iz4u.net"]


# wagtail

STATIC_ROOT = "/home/pk/static"

MEDIA_ROOT = "/home/pk/data/media"

# bakery

BAKERY_MULTISITE = True
BUILD_DIR = os.path.join("/home/pk/bakery_static", "build")

# Django logging to file with rotation
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'apps_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/home/pk/logs/apps.log',
            'maxBytes': 5242880,  # 5MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        '': {
            'handlers': ['apps_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# service_version
sha_service_version = os.environ.get("SHA")

# check WSGI environment
IS_PRODUCTION_SERVER = os.environ.get('IS_WSGI_ENVIRONMENT', 'False') == 'True'

# logfire settings
if IS_PRODUCTION_SERVER:
    logfire.configure(environment='prod', service_name="web", service_version=sha_service_version)
    logfire.instrument_django()
    logfire.instrument_system_metrics()
#logfire.instrument_psycopg('psycopg')
print(f"sys.argv: {sys.argv}")

# celery 
CELERY_BROKER_PASSWORD = os.environ.get("CELERY_BROKER_PASSWORD","FALSE")
CELERY_BROKER_USERNAME = os.environ.get("CELERY_BROKER_USERNAME","FALSE")
CELERY_BROKER_VHOST = os.environ.get("CELERY_BROKER_VHOST","FALSE")
if "FALSE" in [CELERY_BROKER_PASSWORD, CELERY_BROKER_USERNAME, CELERY_BROKER_VHOST]:
    raise ValueError("CELERY_BROKER_PASSWORD, CELERY_BROKER_USERNAME, CELERY_BROKER_VHOST must be set")
# Celery Configuration Options
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_TIMEZONE = "Asia/Seoul"
CELERY_ENABLE_UTC = False
CELERY_TASK_TRACK_STARTED = True
CELERY_BROKER_URL = f"amqp://{CELERY_BROKER_USERNAME}:{CELERY_BROKER_PASSWORD}@localhost:5672/{CELERY_BROKER_VHOST}"
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_RESULT_BACKEND = 'django-db'


# django-celery-beat
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Celery Beat Schedule
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'crawl-rss-feeds': {
        'task': 'curation.tasks.crawl_rss',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
        'options': {'queue': 'celery'}
    },
    'crawl-rss-item-content': {
        'task': 'curation.tasks.crawl_rss_item_content',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
        'options': {'queue': 'celery'}
    },
}
