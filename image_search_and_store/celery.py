import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "image_search_and_store.settings")

app = Celery("image_search_and_store")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
