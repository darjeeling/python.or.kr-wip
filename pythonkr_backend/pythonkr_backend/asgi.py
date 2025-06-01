"""
ASGI config for pythonkr_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pythonkr_backend.settings')

# setup environment for logfire setup
os.environ['IS_ASGI_ENVIRONMENT'] = 'True'

application = get_asgi_application()
