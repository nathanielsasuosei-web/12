# 12 — Beat & Video Store

A storefront for a music producer, built with Django.

- **Admin (producer):** upload beats (audio + cover, price, BPM, key) and videos (file or YouTube/Vimeo link) at `/admin/`. Every purchase appears under *Orders*.
- **Artists (customers):** sign up, log in, browse beats and videos, and buy beats.
- **Payments:** Paystack checkout with **mobile money** and **bank** channels. Payments are verified server-side and via Paystack webhooks, and each order is fulfilled exactly once.
- **Delivery:** after payment, the buyer gets an email with a receipt, a download link, and the beat attached when it is under the size limit. The producer gets a "new sale" email. Buyers can also see their purchases at `/dashboard/`.
- **Animated hero** on the home page (canvas equalizer + shimmer text), with reduced-motion support.

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser        # producer/admin account
python manage.py runserver 0.0.0.0:8000
```

Open http://localhost:8000 (admin at `/admin/`).

With no `PAYSTACK_SECRET_KEY` set, checkout runs in **test mode**: a local page lets you simulate a mobile-money or bank payment, which exercises the full fulfilment and email flow. No money moves.

## Go live

1. Create a Paystack account and set `PAYSTACK_SECRET_KEY` (and `PAYMENT_CURRENCY`, for example `GHS`, `NGN`, `KES`, or `ZAR`, matching your Paystack account).
2. In the Paystack dashboard, set the webhook URL to `https://yourdomain.com/payments/webhook/`.
3. Set `SITE_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECRET_KEY`, and `DJANGO_DEBUG=0`. See `.env.example`.
4. Configure SMTP (`EMAIL_BACKEND`, `EMAIL_HOST`, …) and `PRODUCER_EMAIL`.
5. Serve with a WSGI server (for example gunicorn) behind HTTPS. For production media, move `MEDIA_ROOT` to object storage such as S3 or DigitalOcean Spaces. Media is served by Django only in DEBUG mode.

## Tests

```bash
python manage.py test store
```

The tests cover signup, purchases in test mode, Paystack initialise and verify, amount mismatch rejection, webhook signature checks, one-time fulfilment, and download access control.

## Project layout

```
config/            settings, root URLs
store/
  models.py        Beat, Video, Order
  payments.py      Paystack client + webhook signature check
  services.py      fulfil_order / confirm_payment (single source of truth for "paid")
  emails.py        buyer receipt + beat, producer notification
  views.py         catalogue, checkout, payment return, webhook, download, dashboard
  tests/           test suite
templates/         Django templates (hero on home.html)
static/            CSS and hero animation (js/hero.js)
```
