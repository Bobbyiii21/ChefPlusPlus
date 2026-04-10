# syntax=docker/dockerfile:1
# Build from repository root: docker build -t chefplusplus .
# Django code lives in ./app (WORKDIR /app in the image matches that layout).
FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=chefplusplus.settings

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

# collectstatic imports Django settings, which require a non-empty SECRET_KEY.
# Do not rely on settings defaults here: use a one-off value for this RUN only
# (not persisted as ENV) so builds stay valid if defaults are removed. Runtime
# (e.g. ECS) must set DJANGO_SECRET_KEY to a real secret.
RUN DJANGO_SECRET_KEY=build-only-collectstatic-placeholder python manage.py collectstatic --noinput

EXPOSE 8000

# Higher timeout / keep-alive than defaults: behind ALB or slow clients, sync workers
# can otherwise hit WORKER TIMEOUT while waiting to read a full request ("no URI read").
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py ensure_superuser && gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 120 --graceful-timeout 30 --keep-alive 75 chefplusplus.wsgi:application"]
