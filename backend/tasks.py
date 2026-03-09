from celery import shared_task
from .message import process_sms_jobs

@shared_task
def run_sms_jobs():
    try:
        process_sms_jobs()
    except Exception as e:
        print("RUN_SMS_JOBS: ERROR", e)
        raise


