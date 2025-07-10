import os
from celery import Celery

# Setting default Django settings for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'covid19_project.settings')

app = Celery('covid19_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()