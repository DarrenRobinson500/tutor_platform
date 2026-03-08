from celery import shared_task
from .message import process_sms_jobs

@shared_task
def run_sms_jobs():
    # print("Run sms jobs")
    process_sms_jobs()


