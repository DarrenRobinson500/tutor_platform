# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development (run after every reboot)

```bash
# 1. Verify Redis/Memurai is running
memurai-cli ping   # should return PONG

# 2. Terminal 1 — Django dev server
python manage.py runserver

# 3. Terminal 2 — Celery worker
set DJANGO_SETTINGS_MODULE=main.settings
celery -A main worker --loglevel=info --pool=solo

# 4. Terminal 3 — Celery beat (scheduled tasks)
set DJANGO_SETTINGS_MODULE=main.settings
celery -A main beat --loglevel=info
```

### Database

```bash
python manage.py makemigrations
python manage.py migrate
```

### Tests

```bash
python manage.py test backend
```

The render engine has a standalone test script at `backend/render/test.py` that can be run directly with `python backend/render/test.py` (it uses relative imports so run from that directory).

## Architecture

This is a Django REST Framework backend for a tutoring platform. The single Django app is `backend/`; the project config lives in `main/` (settings, URLs, wsgi, celery).

### User Roles & Relationships

`User` (custom `AbstractUser`) has four roles: `tutor`, `student`, `parent`, `admin`. Key linking models:
- `TutorStudent` — maps a tutor to their students
- `ParentChild` — maps a parent to their child (student)
- `TutorProfile` / `StudentProfile` — extended profile data

`User.get_tutor()` and `User.get_tutor_profile()` traverse these links for any role.

### Booking System

Two booking types coexist:
- `BookingWeekly` — recurring weekly slot (weekday + time). Has skip/resume logic via `start_date`.
- `BookingAdhoc` — one-off datetime booking.

`User.booking_mode()` returns the current state (`weekly_booking`, `adhoc`, `weekly_booking_but_adhoc_this_week`, `weekly_booking_but_paused`, `no_booking`). Slot availability is computed in memory via `TutorProfile.appointment_status_fast()` using pre-fetched data to avoid N+1 queries. `User.generate_weekly_slots()` builds a full week view for the calendar.

### Template / Question Engine

`Template` stores question content as YAML text in the `content` field. Parameters use `{{ param_name }}` syntax with randomised ranges defined in a `parameters` block.

The rendering pipeline:
1. `backend/rendering.py` — `generate_param_values()` samples random values; `substitute_params_and_expressions()` evaluates `{{ expr }}` tokens
2. `backend/maths/maths_engine.py` — expression evaluation via sympy (`evaluate_number_expression`)
3. `backend/render/` — a newer, cleaner standalone render engine (`Render` class in `render.py`, `ExpressionNode` in `expr.py`, `RandomParameter`/`FractionParameter` in `param.py`)
4. `backend/template_utilities.py` — `generate_preview_from_content()` orchestrates parse → validate → render for API responses

`backend/engine.py` and `backend/render/engine.py` both contain expression evaluation; the `render/` package is the newer implementation.

### SMS / Messaging

Outbound SMS uses ClickSend (`backend/clicksend.py`). Messages are queued as `SMSSendJob` records and dispatched by a Celery beat task (`backend.tasks.run_sms_jobs`) every 30 seconds. `backend/message.py` contains SMS templates and `process_sms_jobs()`. The `GlobalSetting` model (with `get_bool`/`get_int` helpers) controls feature flags like `sms_pause`.

### AI Integration

`backend/ai.py` uses the OpenAI SDK to generate `Template` YAML content from prompts. The prompt schema enforces the same `{{ param }}` format used by the render engine.

### Caching

`backend/cache.py` uses a module-level `STUDENTS_CACHE` dict (not Django cache) to cache student summaries per tutor. Invalidate by deleting the tutor's entry. Django's cache framework (`django.core.cache`) is used for `GlobalSetting` lookups.

### API

All endpoints are DRF ViewSets registered in `backend/urls.py`. JWT auth via `djangorestframework-simplejwt` (tokens at `auth/jwt/login/` and `auth/jwt/refresh/`). A `dev_login` action exists on `AuthViewSet` for passwordless login in development.

### Infrastructure

- Database: SQLite locally; PostgreSQL (via `DATABASE_URL` env var) in production on Railway
- Redis (Memurai on Windows) required for Celery broker/backend
- Static files served by WhiteNoise
- Deployed to Railway; frontend (`greenlearning.vercel.app`) is a separate Vercel app
- Timezone: `Australia/Sydney` throughout
