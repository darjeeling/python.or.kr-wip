# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from django.conf import settings

# load when PROD environment
if settings.CELERY_ALWAYS_EAGER is False:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
else:
    __all__ = ()