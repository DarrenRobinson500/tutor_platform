from celery import shared_task
from .message import process_sms_jobs

@shared_task
def run_sms_jobs(self):
    print("RUN_SMS_JOBS: task started")
    try:
        process_sms_jobs()
        print("RUN_SMS_JOBS: task finished")
    except Exception as e:
        print("RUN_SMS_JOBS: ERROR", e)
        raise


