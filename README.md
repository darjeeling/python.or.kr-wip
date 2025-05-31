# python.or.kr-wip

## 개발 환경 구축

### 1. Docker compose 이용 

테스트용 계정 정보
 - id: test
 - password: test

```
$ docker-compose up
```
 - 접속 URL: http://localhost:8080/cms/


### 2. Django runserver 이용

```
$ source .venv/bin/activate
$ cd pythonkr_backend
$ python manage.py migrate
$ python manage.py runserver
```

Tailwind CSS 작업을 위해 다른 창에서 다음을 실행
```
$ python manage.py tailwind start
```

## Django settings
- pythonkr_backend.settings # local sqlite testing
- pythonkr_backend.settings.localtesting  # docker compose testing
- pythonkr_backend.settings.prod # production
