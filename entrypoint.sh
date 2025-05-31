#!/usr/bin/env bash


cd /app
npm install
source .venv/bin/activate
uv sync
cd /app/pythonkr_backend
export DJANGO_SETTINGS_MODULE="pythonkr_backend.settings.localtesting"
./manage.py migrate --no-input
./manage.py tailwind build
./manage.py loaddata fixtures.json
./manage.py collectstatic  --clear --noinput
export DJANGO_SUPERUSER_PASSWORD=test
./manage.py createsuperuser --username test --email testing@testing.com --noinput
gunicorn --workers=2  \
    -b :8080 \
    --access-logfile - \
    --error-logfile - \
    pythonkr_backend.wsgi
