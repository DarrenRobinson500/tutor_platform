from .models import *
from .clicksend import *
SMS_PAUSE = timedelta(seconds=10)

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
    "tutor_confirmed": (
        "Your booking is confirmed\n"
        "{weekday}, {start}–{end}\n"
        "Your tutor: {tutor_name}"
    ),

    "tutor_created": (
        "A new booking has been scheduled for you\n"
        "{weekday}, {start}–{end}\n"
        "Created by {tutor_name}."
    ),

    "tutor_updated": (
        "Your booking has been updated\n"
        "{weekday}, {start}–{end}\n"
        "Updated by {tutor_name}."
    ),

    "tutor_cancelled": (
        "Your booking has been cancelled\n"
        "{weekday}, {start}–{end}\n"
        "Cancelled by {tutor_name}."
    ),
}
DEBOUNCE_TYPES = set(SMS_TEMPLATES.keys())

def sms_message(booking, message_type):
    if message_type not in SMS_TEMPLATES:
        raise ValueError(f"Unknown SMS message type: {message_type}")

    weekday = booking["day_str"]
    start = booking["start_time"]
    end = booking["end_time"]

    context = {
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

    body = sms_message(booking, message_type)
    now = timezone.now()
    scheduled_for = now + SMS_PAUSE

    job = SMSSendJob.objects.filter(
        tutor_id=tutor_id,
        student_id=student_id,
        cancelled=False
    ).first()

    if job:
        job.body = body
        job.scheduled_for = scheduled_for
        job.save(update_fields=["body", "scheduled_for"])
        return job

    return SMSSendJob.objects.create(
        tutor_id=tutor_id,
        student_id=student_id,
        body=body,
        scheduled_for=scheduled_for
    )

def process_sms_jobs():
    print("Process SMS Jobs")
    now = timezone.now()
    jobs = SMSSendJob.objects.filter(
        scheduled_for__lte=now,
        cancelled=False
    )

    print(f"PROCESS_SMS_JOBS: found {jobs.count()} jobs")
    for job in jobs:
        print(" - ", job)

    for job in jobs:
        tutor = User.objects.get(id=job.tutor_id)
        student = User.objects.get(id=job.student_id)

        # Send SMS
        msg = SMSMessage.objects.create(
            direction="outbound",
            conversation=get_or_create_conversation(tutor, student),
            body=job.body,
            phone_number=student.student_profile.mobile,
            status="queued"
        )
        print("Process sms jobs:", msg)
        try:
            if settings.SMS_Mock:
                print("SMS Sent:", job.body)
            else:
                msg.provider_message_id = clicksend_send_sms(msg.phone_number, job.body)
            msg.status = "sent"
            msg.sent_at = now
            msg.save(update_fields=["provider_message_id", "status", "sent_at"])

            job.cancelled = True
            job.save(update_fields=["cancelled"])

        except Exception as e:
            # Mark as failed but keep the job so it can be retried later
            msg.status = "failed"
            msg.save(update_fields=["status"])
            print("SMS sending failed:", e)


