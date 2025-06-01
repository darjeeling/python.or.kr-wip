# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
import os

DJANGO_SETTINGS_MODULE=os.environ.get("DJANGO_SETTINGS_MODULE")

if "prod" in DJANGO_SETTINGS_MODULE:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
else:
    __all__ = ()