#!/usr/bin/env bash

PID_FILE="/home/pk/pk.pid"
LOG_DIR="/home/pk/logs"

cd ~/
source .env
cd python.or.kr

# SHA 환경변수가 없으면 현재 git 커밋의 SHA 값을 가져와서 설정
if [ -z "${SHA}" ]; then
    export SHA=$(git rev-parse HEAD)
    echo "SHA 환경변수가 없어서 현재 git SHA로 설정: ${SHA}"
fi

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
./manage.py loaddata pythonkr/fixtures/pythonkr.json
./manage.py collectstatic  --clear --noinput
gunicorn --workers=2  \
    -b :2026 \
    --access-logfile ${LOG_DIR}/access.log \
    --error-logfile ${LOG_DIR}/error.log \
    --daemon \
    --pid ${PID_FILE} \
    pythonkr_backend.wsgi
