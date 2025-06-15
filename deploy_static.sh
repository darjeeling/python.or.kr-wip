#!/usr/bin/env bash

# run on the server side 
# you can run in on the action

cd ~/
# to load logfire
source .env
cd python.or.kr
# SHA 환경변수가 없으면 현재 git 커밋의 SHA 값을 가져와서 설정
if [ -z "${SHA}" ]; then
    export SHA=$(git rev-parse HEAD)
    echo "SHA 환경변수가 없어서 현재 git SHA로 설정: ${SHA}"
fi
source .venv/bin/activate
uv sync
cd pythonkr_backend
export DJANGO_SETTINGS_MODULE="pythonkr_backend.settings.prod"
./manage.py build

cd ~/bakery_static/build
rsync -arv \
  --exclude='tr/' \
  --exclude='rssitem-crawling/' \
  --delete-excluded \
  ./ ~/git-python.or.kr/web/
cd ~/git-python.or.kr/web
git add ./
git commit -m "upload"
git push 
