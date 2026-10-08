FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect fingerprinted static assets at build time. These build-only values are
# not persisted as runtime environment variables or used for payment requests.
RUN DJANGO_DEBUG=0 \
    DJANGO_SECRET_KEY=build-only-placeholder-secret-key-not-for-runtime \
    PAYSTACK_SECRET_KEY=sk_test_build_only \
    python manage.py collectstatic --noinput \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home app \
    && mkdir -p /data/media \
    && chown -R app:app /app /data/media

USER app

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
