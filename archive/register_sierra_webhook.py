#!/usr/bin/env python3
"""register_sierra_webhook.py — register the Fly-hosted webhook handler
with Sierra so they fire LeadRegistered events to it.

Run AFTER `fly deploy` succeeds and `https://sierra-fub-webhook.fly.dev/`
returns {"status":"ok"}:

    python3 register_sierra_webhook.py --url "https://sierra-fub-webhook.fly.dev/sierra-webhook?secret=YOUR_WEBHOOK_SECRET"

API registration can't attach custom headers, so pass the webhook secret as
the ?secret= query param — the handler accepts it there or in the
X-Webhook-Secret header.

Also lists existing webhooks via --list. Needs SIERRA_API_KEY in .env or env.

NOTE: Sierra silently bans a subscription after 4 failed/slow deliveries.
If webhooks stop arriving, run --list to check, then re-register with --url.
"""
import argparse
import os
import sys
from pathlib import Path

import requests

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

SIERRA = "https://api.sierrainteractivedev.com"
H = {
    "Sierra-ApiKey": os.environ["SIERRA_API_KEY"],
    "Sierra-OriginatingSystemName": os.environ.get(
        "SIERRA_ORIGINATING_SYSTEM", "TeamDunlap"
    ),
    "Content-Type": "application/json",
}


def list_webhooks():
    r = requests.get(f"{SIERRA}/webhook", headers=H, timeout=10)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        # Try common envelope shapes
        hooks = data.get("data") or data.get("webhooks") or data
        if isinstance(hooks, dict):
            hooks = hooks.get("webhooks", [])
        print(f"Existing webhooks ({len(hooks)}):")
        for h in hooks:
            print(f'  id={h.get("id")} url={h.get("url")} events={h.get("eventTypes")}')
    else:
        print(r.text[:300])


def register(url, events):
    r = requests.post(
        f"{SIERRA}/webhook",
        headers=H,
        json={"url": url, "eventTypes": events},
        timeout=15,
    )
    print(f"POST /webhook -> HTTP {r.status_code}: {r.text[:400]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--url", help="full webhook URL including /sierra-webhook path")
    ap.add_argument(
        "--events",
        default="LeadRegistered",
        help="comma-separated event types (default: LeadRegistered)",
    )
    args = ap.parse_args()
    if args.list:
        list_webhooks()
        return
    if not args.url:
        ap.error("--url is required (or use --list)")
    register(args.url, [e.strip() for e in args.events.split(",")])
    print()
    list_webhooks()


if __name__ == "__main__":
    main()
