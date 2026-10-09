FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Collect static files at build time. The values below are placeholders used only for this
# step. The running container reads its real settings from .env.
RUN DJANGO_DEBUG=0 \
    DJANGO_SECRET_KEY=build-only-placeholder-not-used-at-runtime-0123456789-abcdefghijklmnopqrstuvwxyz \
    DJANGO_ALLOWED_HOSTS=build.local \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/data /app/media /app/private_media \
    && chown -R app:app /app/data /app/media /app/private_media
USER app

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
