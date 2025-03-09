#!/usr/bin/env bash


cd /app
source .venv/bin/activate
cd /app/pythonkr_backend
export DJANGO_SETTINGS_MODULE="pythonkr_backend.settings.localtesting"
./manage.py migrate --no-input
./manage.py collectstatic  --clear --noinput
gunicorn --workers=2  \
    -b :8080 \
    --access-logfile - \
    --error-logfile - \
    pythonkr_backend.wsgi