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


LOGGING_CONFIG = None
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

import logging.config

logging.config.dictConfig(LOGGING)




logger = logging.getLogger('')

# service_version
sha_service_version = os.environ.get("SHA")

# check WSGI environment
IS_PRODUCTION_SERVER = os.environ.get('IS_WSGI_ENVIRONMENT', 'False') == 'True'

logger.info(os.environ)
logger.info(sys.argv)
logger.info(IS_PRODUCTION_SERVER)

# logfire settings
if IS_PRODUCTION_SERVER == 'True':
    logfire.configure(environment='prod', service_name="web", service_version=sha_service_version)
    logfire.instrument_system_metrics()
    logfire.instrument_django()
    logfire.instrument_psycopg('psycopg')

