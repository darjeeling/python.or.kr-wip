from pathlib import Path
import os
import logfire

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


# service_version
sha_service_version = os.environ.get("SHA")

# logfire settings
logfire.configure(environment='prod', service_name="web", service_version=sha_service_version)
logfire.instrument_system_metrics()
logfire.instrument_django()
logfire.instrument_psycopg('psycopg')