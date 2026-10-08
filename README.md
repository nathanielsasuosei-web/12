# 12 — Beat & Video Store

A storefront for a music producer, built with Django.

- **Admin (producer):** upload beats (full audio + optional streamable preview + cover, price, BPM, key) and videos (file or YouTube/Vimeo link) at `/admin/`. Every purchase appears under *Orders* and every artist message under *Contact messages*.
- **Artists (customers):** sign up, log in, browse beats and videos, stream previews, and buy beats.
- **Payments:** Paystack checkout with **mobile money** and **bank** channels. Payments are verified server-side and via Paystack webhooks, and each order is fulfilled exactly once.
- **Delivery:** after payment, the buyer gets an email with a receipt, a download link, and the beat attached when it is under the size limit. The producer gets a "new sale" email. Buyers can also see their purchases at `/dashboard/`.
- **Messages by email:** the `/contact/` page forwards artist messages to the producer's inbox and sends the artist a confirmation email.
- **Animated red hero** on the home page (glowing canvas equalizer, floating notes, shimmer text, scrolling ticker), with reduced-motion support.

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser        # producer/admin account
python manage.py runserver 0.0.0.0:8000
```

Open http://localhost:8000 (admin at `/admin/`).

Optional demo content (covers, previews, beats, a video) for a first look:

```bash
python manage.py seed_demo
```

This also creates a producer login (`producer` / `producer123`) if one does not exist yet.

With no `PAYSTACK_SECRET_KEY` set, checkout runs in **test mode**: a local page lets you simulate a mobile-money or bank payment, which exercises the full fulfilment and email flow. No money moves.

## Production deployment (Docker Compose)

The repository includes a production Docker image, PostgreSQL, and Caddy for automatic HTTPS. This is a single-host/VPS deployment: point a domain at the host, allow inbound ports 80 and 443, and install Docker Engine with the Compose plugin. No cloud account or deployment credentials are needed by the app itself.

1. Copy `.env.example` to `.env`. Set `DOMAIN`, `SITE_URL`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` to your real domain. Generate two different random values with `python3 -c 'import secrets; print(secrets.token_hex(32))'` for `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`.
2. Set a live `PAYSTACK_SECRET_KEY`, the currency configured in Paystack, SMTP credentials, `DEFAULT_FROM_EMAIL`, and `PRODUCER_EMAIL`. Production refuses to start with the development secret, a missing Paystack key, or mock payments enabled.
3. Build the image, start PostgreSQL, apply migrations, then bring up the site and HTTPS proxy:

   ```bash
   docker compose build
   docker compose up -d db
   docker compose run --rm web python manage.py migrate --noinput
   docker compose up -d web caddy
   docker compose run --rm web python manage.py createsuperuser
   ```

4. In Paystack, set the webhook URL to `https://yourdomain.com/payments/webhook/`.

For later releases, run `docker compose build web`, `docker compose run --rm web python manage.py migrate --noinput`, then `docker compose up -d web caddy`. PostgreSQL and uploaded media live in named Docker volumes; back them up independently and do not use `docker compose down -v` unless you intend to delete that data. Caddy serves public covers/videos, while paid beat files are only delivered through the existing Django download endpoint. This starter is intended for one host; use managed database/object storage and an external backup plan before scaling out.

### Alternative: Vercel

`vercel.json` pins the Framework Preset to Django, avoiding the Next.js build. Vercel detects `manage.py`, loads `config/wsgi.py`, runs `collectstatic` automatically, and serves collected static files from its CDN. Deploy a commit containing `vercel.json`, set Vercel's Root Directory to the repository root, and clear any manual `next build` command or Next.js Output Directory override.

Set these variables in every Vercel environment you deploy to (including Preview if used). Vercel makes a variable available only to the environments it is scoped to, so a variable added only to Production is missing from preview builds:

- `DJANGO_DEBUG=0` and a random `DJANGO_SECRET_KEY` of at least 32 characters
- `DATABASE_URL` for a managed PostgreSQL database
- `PAYSTACK_SECRET_KEY`, `PAYMENT_CURRENCY`, and `SITE_URL`
- `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` for your custom domain
- SMTP settings and `PRODUCER_EMAIL`

The app adds Vercel's deployment hostnames to the allowed-host and CSRF lists automatically. Run `python manage.py migrate` against the configured database before serving real orders. Vercel functions have an ephemeral filesystem and a 4.5 MB request/response body limit: this project currently stores uploads on the local filesystem, so beat, cover, and video uploads won't persist there. Add an object-storage backend before using admin uploads on Vercel. The Docker Compose setup above supports persistent media volumes on a single host.

`vercel.json` runs `python manage.py check_production` as the build command. If a required variable is missing or unsafe for that environment, the build stops and lists every problem. The app runs the same checks when it starts, so it never serves with an incomplete configuration. To check before deploying, export the same variables locally and run `python manage.py check_production`. Builds from before this check existed failed with `Failed to read Django application settings from .../manage.py`; the lines under that message name the missing variable.

## Tests

```bash
python manage.py test store
```

The tests cover signup, purchases in test mode, Paystack initialise and verify, amount mismatch rejection, webhook signature checks, one-time fulfilment, and download access control.

## Project layout

```
Dockerfile         production Django image
compose.yaml       PostgreSQL, web app, HTTPS proxy
Caddyfile          TLS reverse proxy + public media routing
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
