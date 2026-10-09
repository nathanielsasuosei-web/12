# Beat Store

A website for a music producer. Visitors listen to previews and watch videos. Artists create an account and buy beats with mobile money or a bank account through Paystack. After payment, the full files are emailed to the buyer and are also available in their account. The producer uploads beats and videos in the Django admin, and receives sale and contact emails.

- Red and black theme with an animated hero
- Admin uploads for beats (preview MP3, full file, cover) and videos (YouTube link or file)
- Artist accounts with sign-up and sign-in by email
- Paystack checkout with mobile money and bank, verified server-side and by signed webhook
- Paid-only downloads with a per-order download limit
- Email for receipts, download links, sale alerts, welcome, and contact messages

## Run it locally

Requires Python 3.12 (3.11 works too).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=1            # development only
python manage.py migrate
python manage.py createsuperuser --username producer@example.com --email producer@example.com
python manage.py runserver
```

Open http://localhost:8000. Emails print to the terminal in development. Purchases use a test checkout, so no real money moves. Set `DJANGO_DEBUG=1` only on your own machine.

## Producer: upload beats and videos

1. Go to `/admin/` and sign in with the superuser account.
2. **Beats → Add beat.** Fill in the title, genre, BPM, key, and price in GHS. Upload:
   - **Preview audio** (MP3). This is public, so keep it short.
   - **Full audio** (WAV, MP3, FLAC, or ZIP). Only paying buyers get this. It is stored outside the public media folder.
   - **Cover image** (optional).
   Tick **Is published** to show it on the site.
3. **Videos → Add video.** Paste a YouTube link or upload an MP4, WebM, or MOV file. Tick **Is published**.
4. **Orders** lists every sale. Use the *Resend download email* action if a buyer loses their email.
5. **Contact messages** lists messages sent from the contact page. Replies also arrive in your inbox, because the reply-to address is the sender.

## Payments with Paystack

1. Create a Paystack account and enable mobile money and bank payments for Ghana.
2. Put your secret key in `PAYSTACK_SECRET_KEY`. Use `sk_test_…` while testing and `sk_live_…` when you go live.
3. In the Paystack dashboard, set the webhook URL to `https://YOUR-DOMAIN/orders/paystack/webhook/`.
4. Buyers choose mobile money or bank on the Paystack checkout page. The channels are set by `PAYSTACK_CHANNELS`.

Payment is confirmed in two ways. The buyer is sent back to the site, and the site verifies the transaction with Paystack. Paystack also sends a signed webhook. An order is marked paid only once, and only when the amount and currency match the order.

## Deploy with Docker (recommended)

1. On a server with Docker and a domain pointing at it, copy `.env.example` to `.env` and fill in every value. Generate the secret key with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
2. Start the stack:

   ```bash
   docker compose up -d --build
   docker compose exec app python manage.py createsuperuser --username producer@example.com --email producer@example.com
   ```

Caddy gets an HTTPS certificate for `SITE_DOMAIN` automatically. The app runs migrations on start.

The app refuses to start in production (`DJANGO_DEBUG=0`) unless it has a real secret key, your domain in `DJANGO_ALLOWED_HOSTS`, an `https://` `SITE_URL`, `PAYMENT_PROVIDER=paystack`, a Paystack key, a producer email, and SMTP settings. The error message lists everything that is missing.

Data lives in Docker volumes: `app-data` (database), `media` (public uploads), and `private` (full beat files). Back them up together.

## Customise

- **Name and contact:** `SITE_NAME` and `PRODUCER_EMAIL`.
- **Colours:** the variables at the top of `static/css/site.css` (`--red`, `--ink`, and so on).
- **Hero text:** `templates/catalog/home.html`.
- **Emails:** the plain-text templates in `templates/emails/`.

## Tests

```bash
python manage.py test
```

The suite covers the catalog, sign-up and sign-in, the payment flow with a mocked Paystack (signature checks, amount checks, idempotent webhooks), paid-only downloads and limits, the contact form and honeypot, and production safety checks.

## Project layout

```
config/        settings, URLs, WSGI, production safety checks
catalog/       beats, videos, home and browse pages (admin uploads)
orders/        orders, Paystack and mock payments, webhook, downloads, emails
accounts/      sign-up and sign-in
contact/       contact form, emailed to the producer
core/          shared email helper
templates/     HTML and email templates
static/        CSS theme and hero animation
```

## Limits to know about

- **Previews are not watermarked.** Anyone can download the public preview MP3. Keep previews short and low quality.
- **SQLite** is fine for one producer. For heavy traffic, move `DATABASES` to PostgreSQL.
- **Refunds** are handled in the Paystack dashboard. The site does not revoke downloads automatically.
