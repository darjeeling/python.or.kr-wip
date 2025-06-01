import logfire
from celery import Celery
from celery.signals import worker_init, beat_init

app = Celery('proj')


# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@worker_init.connect()  
def init_worker(*args, **kwargs):
    logfire.configure(service_name="celery-worker")  
    logfire.instrument_celery()

@beat_init.connect()  
def init_beat(*args, **kwargs):
    logfire.configure(service_name="celery-beat")  
    logfire.instrument_celery()

@app.task
def add(x: int, y: int):
    return x + y

add.delay(42, 50)


app.conf.beat_schedule = {  
    "add-every-30-seconds": {
        "task": "tasks.add",
        "schedule": 30.0,
        "args": (16, 16),
    },
}