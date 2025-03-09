#!/usr/bin/env bash

PID_FILE="/home/pk/pk.pid"
LOG_DIR="/home/pk/logs"

cd ~/
cd python.or.kr
# shutdown exist gunicorn
if [ -f ${PID_FILE} ]; then
        PID=$(cat $PID_FILE)
        kill -TERM $PID
        rm ${PID_FILE}
fi

mkdir -p ${LOG_DIR}

# update changes before update
# git pull
source .venv/bin/activate
uv sync
cd pythonkr_backend
export DJANGO_SETTINGS_MODULE="pythonkr_backend.settings.prod"
./manage.py migrate --no-input
./manage.py collectstatic  --clear --noinput
gunicorn --workers=2  \
    -b :2026 \
    --access-logfile ${LOG_DIR}/access.log \
    --error-logfile ${LOG_DIR}/error.log \
    --daemon \
    --pid ${PID_FILE} \
    pythonkr_backend.wsgi
