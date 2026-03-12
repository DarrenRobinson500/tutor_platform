from .models import *
from .clicksend import *
SMS_PAUSE = timedelta(minutes=get_int("sms_pause", default=10))

def format_weekday(day_str):
    d = datetime.strptime(day_str, "%Y-%m-%d").date()
    return d.strftime("%A")

def format_time(t_str):
    t = datetime.strptime(t_str, "%H:%M").time()
    return t.strftime("%-I:%M%p").lower()

SMS_TEMPLATES = {
    # Student → Tutor
    "student_created": (
        "New booking request from {student_name}\n"
        "{weekday}, {start}–{end}\n"
        "Please confirm or edit this booking in your dashboard."
    ),

    "student_updated": (
        "Booking updated by {student_name}\n"
        "{weekday}, {start}–{end}\n"
        "Review the changes in your dashboard."
    ),

    "student_cancelled": (
        "Booking cancelled by {student_name}\n"
        "{weekday}, {start}–{end} has been cancelled."
    ),

    # Tutor → Student
    "tutor_created": ("Hi {student_name}, your booking has been created by {tutor_name}. We will see you {date_and_time}\n"),
    "tutor_created_weekly": ("Hi {student_name}, your weekly booking has been created by {tutor_name}. We will see you each week and the first booking is {date_and_time}\n"),
    "tutor_updated": ("Hi {student_name}, your booking has been updated by {tutor_name}. We will see you {date_and_time}\n"),
    "tutor_confirmed": ("Hi {student_name}, your booking has been confirmed by {tutor_name}. We will see you {date_and_time}\n"),
    "tutor_unconfirmed": ("Hi {student_name}, your booking has been unconfirmed by {tutor_name}. We will not see you {date_and_time} Please call {tutor_name} if this is unexpected.\n"),
    "tutor_skipped": ("Hi {student_name}, your weekly booking will be skipped this week. We will see you next week {date_and_time}\n"),
    "tutor_unskipped": ("Hi {student_name}, your booking has been updated by {tutor_name}. We will see you {date_and_time}\n"),
    "tutor_cancelled_weekly": ("Hi {student_name}, your weekly booking with {tutor_name} has been cancelled."),
    "tutor_cancelled_adhoc": ("Hi {student_name}, your booking with {tutor_name} has been cancelled."),
}

DEBOUNCE_TYPES = set(SMS_TEMPLATES.keys())

def create_sms_body(booking, message_type):
    if message_type not in SMS_TEMPLATES:
        raise ValueError(f"Unknown SMS message type: {message_type}")

    # print("Create sms body:", booking)

    weekday = booking["day_str"]
    date_and_time = format_sms_datetime(booking["start_iso"])
    start = booking["start_time"]
    end = booking["end_time"]

    context = {
        "date_and_time": date_and_time,
        "weekday": weekday,
        "start": start,
        "end": end,
        "student_name": booking.get("student_name"),
        "tutor_name": booking.get("tutor_name"),
    }

    template = SMS_TEMPLATES[message_type]
    return template.format(**context)

def sms_enqueue(booking, message_type):
    booking=booking.to_dict()
    tutor_id = booking["tutor_id"]
    student_id = booking["student_id"]
    conversation = get_or_create_conversation(User.objects.get(id=tutor_id), User.objects.get(id=student_id))
    body = create_sms_body(booking, message_type)
    now = timezone.now()
    scheduled_for = now + SMS_PAUSE

    job = SMSSendJob.objects.filter(
        conversation=conversation,
        cancelled=False
    ).first()

    if job:
        job.body = body
        job.scheduled_for = scheduled_for
        job.retry_count = 0
        job.save(update_fields=["body", "scheduled_for", "retry_count"])
        return job

    return SMSSendJob.objects.create(
        conversation=conversation,
        body=body,
        scheduled_for=scheduled_for
    )


def process_sms_jobs():
    now = timezone.now()
    jobs = SMSSendJob.objects.filter(
        scheduled_for__lte=now,
        cancelled=False,
        retry_count__lt=3
    )

    for job in jobs:
        conversation = job.conversation
        student = conversation.student

        try:
            # Attempt to send
            sms_send = get_bool("sms_send", default=False)
            print("SMS Send:", sms_send)

            if sms_send:
                provider_id = clicksend_send_sms(
                    student.student_profile.mobile,
                    job.body
                )
            else:
                print("SMS Fake Send:", job.body)
                provider_id = "FAKE-SEND"

            # Create the message only on success
            msg = SMSMessage.objects.create(
                direction="outbound",
                conversation=conversation,
                body=job.body,
                phone_number=student.student_profile.mobile,
                provider_message_id=provider_id,
                status="sent",
                sent_at=now
            )

            # Cancel the job
            job.cancelled = True
            job.last_error = None
            job.last_attempt_at = now
            job.save(update_fields=["cancelled", "last_error", "last_attempt_at"])

        except Exception as e:
            # Record failure on the job
            job.last_error = str(e)
            job.last_attempt_at = now
            job.retry_count += 1
            job.save(update_fields=["last_error", "last_attempt_at", "retry_count"])

            print("SMS sending failed:", e)