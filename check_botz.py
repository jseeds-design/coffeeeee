#!/usr/bin/env python3
"""
Botz Coffee collection watcher.

Watches https://botz-coffee.com/collections/coffee via Shopify's public
products.json endpoint (structured data, not HTML scraping — avoids false
positives from cart counters, session tokens, and the translate widget).

Detects:
  - new products added to the collection
  - products removed from the collection
  - a variant going from sold out -> available (restock / new drop)
  - a variant going from available -> sold out
  - price changes

State is persisted in state.json (committed back to the repo by the
GitHub Actions workflow) so the diff works across separate runs.
"""

import json
import os
import sys
import urllib.request

COLLECTION_URL = "https://botz-coffee.com/collections/coffee/products.json"
STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")

# ntfy.sh topic — set NTFY_TOPIC as a secret/env var. Treat the topic name
# like a password: anyone who knows it can read your notifications, since
# ntfy topics are unauthenticated by default.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")


def fetch_all_products():
    """Fetch every product in the collection, paginating if needed."""
    products = []
    page = 1
    while True:
        url = f"{COLLECTION_URL}?limit=250&page={page}"
        req = urllib.request.Request(url, headers={"User-Agent": "botz-checker/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
        batch = data.get("products", [])
        if not batch:
            break
        products.extend(batch)
        if len(batch) < 250:
            break
        page += 1
    return products


def build_snapshot(products):
    """Flatten into {variant_id: record} for easy diffing."""
    snapshot = {}
    for p in products:
        for v in p.get("variants", []):
            snapshot[str(v["id"])] = {
                "product_id": p["id"],
                "product_title": p["title"],
                "handle": p["handle"],
                "variant_title": v.get("title", ""),
                "price": v.get("price"),
                "available": v.get("available"),
            }
    return snapshot


def load_previous_state():
    if not os.path.exists(STATE_PATH):
        return None
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def save_state(snapshot):
    with open(STATE_PATH, "w") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)


def diff_snapshots(old, new):
    """Return a list of human-readable change lines."""
    changes = []
    old_ids, new_ids = set(old), set(new)

    for vid in sorted(new_ids - old_ids):
        r = new[vid]
        changes.append(
            f"🆕 New listing: {r['product_title']} ({r['variant_title']}) — ${r['price']}"
        )

    for vid in sorted(old_ids - new_ids):
        r = old[vid]
        changes.append(f"❌ Removed: {r['product_title']} ({r['variant_title']})")

    for vid in sorted(old_ids & new_ids):
        o, n = old[vid], new[vid]
        if o["available"] != n["available"]:
            if n["available"]:
                changes.append(f"✅ Back in stock: {n['product_title']} ({n['variant_title']})")
            else:
                changes.append(f"⛔ Sold out: {n['product_title']} ({n['variant_title']})")
        if o["price"] != n["price"]:
            changes.append(
                f"💲 Price change: {n['product_title']} ({n['variant_title']}) "
                f"${o['price']} → ${n['price']}"
            )

    return changes


def notify(message):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC not set — skipping push notification. Message was:")
        print(message)
        return
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={
            "Title": "Botz Coffee update",
            "Tags": "coffee",
            "Click": COLLECTION_URL.replace("/products.json", "").replace(
                "collections/coffee", "collections/coffee"
            ),
        },
        method="POST",
    )
    # Actual page users should visit, not the .json endpoint:
    req.add_header("Click", "https://botz-coffee.com/collections/coffee")
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Failed to send ntfy notification: {e}", file=sys.stderr)


def main():
    products = fetch_all_products()
    new_snapshot = build_snapshot(products)
    old_snapshot = load_previous_state()

    if old_snapshot is None:
        print(f"First run — baselined {len(new_snapshot)} variants across "
              f"{len(products)} products. No notification sent.")
        save_state(new_snapshot)
        return

    changes = diff_snapshots(old_snapshot, new_snapshot)

    if changes:
        message = "\n".join(changes)
        print("Changes detected:\n" + message)
        notify(message)
        save_state(new_snapshot)
    else:
        print("No changes.")


if __name__ == "__main__":
    main()
