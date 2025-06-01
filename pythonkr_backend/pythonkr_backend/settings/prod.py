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


logger = logging.getLogger(__name__)

# service_version
sha_service_version = os.environ.get("SHA")

# check WSGI/ASGI environment
IS_PRODUCTION_SERVER = os.environ.get('IS_WSGI_ENVIRONMENT') == 'True' or \
                       os.environ.get('IS_ASGI_ENVIRONMENT') == 'True'

logger.info(os.environ)
logger.info(sys.argv)

# logfire settings
if IS_PRODUCTION_SERVER:
    logfire.configure(environment='prod', service_name="web", service_version=sha_service_version)
    logfire.instrument_system_metrics()
    logfire.instrument_django()
    logfire.instrument_psycopg('psycopg')