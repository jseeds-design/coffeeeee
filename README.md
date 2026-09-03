# Botz Coffee checker

Watches https://botz-coffee.com/collections/coffee for new listings,
restocks, sold-outs, and price changes — via Shopify's public
`products.json` endpoint (structured data, no HTML-scraping noise).

## Setup (~5 minutes)

1. **Create a repo** on GitHub and push this folder to it (public or
   private — either works with GitHub Actions' free tier at this
   check frequency).

2. **Pick an ntfy.sh topic.** This is just a free push-notification
   channel — no signup required.
   - Choose an unguessable topic name, e.g. `botz-coffee-jonathan-x7f2`
     (treat it like a password — anyone who knows the exact topic name
     can read your alerts, since ntfy topics aren't private by
     default).
   - Install the [ntfy app](https://ntfy.sh/) (iOS/Android) or open
     `https://ntfy.sh/your-topic-name` in a browser tab, and subscribe
     to that topic.

3. **Add the topic as a GitHub secret:**
   - Repo → Settings → Secrets and variables → Actions → New repository secret
   - Name: `NTFY_TOPIC`
   - Value: `botz-coffee-jonathan-x7f2` (your topic name, not a URL)

4. **`state.json` is already included**, baselined as of when this was
   built (Marlon Bolaños sold out, gift card variants in stock) — so
   the very first scheduled run will already diff against real data
   instead of just baselining silently. If you want to force a fresh
   baseline instead (e.g. you're worried the included one is stale by
   the time you set this up), delete `state.json` before your first
   push; that first run will then baseline instead of notify.

5. It then runs automatically every 30 minutes via the cron schedule
   in `.github/workflows/botz-check.yml`. Change the cron expression
   there if you want a different cadence — GitHub Actions' free tier
   easily covers this (a run takes a few seconds, well under the
   2,000 free minutes/month for private repos, unlimited for public).

## What it actually detects

- New product added to the collection
- Product removed from the collection
- A variant flipping sold-out → available (restock/new drop) — this
  is almost certainly the one you actually care about
- A variant flipping available → sold-out
- Price changes

It deliberately does **not** diff the rendered HTML — that page has a
cart counter and a Bing translate widget that inject constantly-
changing markup unrelated to the coffee menu, which would produce
false-positive alerts on a raw HTML diff.

## Known limitations

- If Botz changes their theme away from Shopify's default
  `products.json` route (unlikely, but not impossible), this breaks
  silently-ish — you'd just stop getting the "first run" baseline
  message and start seeing errors in the Actions log. Worth an
  occasional glance at the Actions tab.
- ntfy.sh is a free third-party service with no delivery guarantee
  (no SLA). Fine for "notice a coffee restocked," not fine for
  anything you can't afford to miss — for that, add a second
  notification channel (e.g. email via a transactional email API) as
  a redundant path.
- 30-minute polling means up to a 30-minute lag between a real change
  and your notification — Botz Gesha drops in particular can sell out
  within that window if they're popular. Tighten the cron if that
  matters to you (down to every 5 minutes is reasonable at this
  scale); GitHub Actions' minimum cron granularity is 1 minute but
  scheduled jobs can lag by a few minutes at busy times regardless.
