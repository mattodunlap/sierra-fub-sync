#!/usr/bin/env python3
"""url_populator.py — populate Sierra URLs on newly-created FUB leads.

Polls FUB every POLL_SECONDS for people created in the last LOOKBACK_MINUTES.
For each one missing customSierraSearchURL, derives the Sierra lead id and
runs the same populate logic as webhook_handler.process_lead (saved-search
deep-link + admin URL written to FUB).

This replaces the Sierra LeadRegistered webhook entirely: no public endpoint,
no webhook secret, no subscription for Sierra to ban. Runs as the Fly app's
main process. Idempotent — leads with current URLs are skipped.

One-shot repair mode (e.g. backfill after an outage):
    python url_populator.py --once --since-minutes 30000

Required env vars: SIERRA_API_KEY, FUB_API_KEY (same as webhook_handler).
Optional: POLL_SECONDS (default 60), LOOKBACK_MINUTES (default 30).
"""
import argparse
import datetime
import os
import re
import time

import requests

from webhook_handler import (
    FUB_API_KEY,
    FUB_BASE,
    FUB_HEADERS,
    FUB_SEARCH_URL_FIELD,
    SIERRA_BASE,
    SIERRA_HEADERS,
    process_lead_safe,
)

POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "60"))
LOOKBACK_MINUTES = int(os.environ.get("LOOKBACK_MINUTES", "30"))


def fetch_recent_fub_people(since_iso):
    """FUB people with created > since_iso, newest first."""
    out = []
    offset = 0
    while True:
        r = requests.get(
            f"{FUB_BASE}/people",
            auth=(FUB_API_KEY, ""),
            headers=FUB_HEADERS,
            params={"limit": 100, "offset": offset, "sort": "-created",
                    "fields": "allFields"},
            timeout=15,
        )
        if r.status_code != 200:
            print(f"FUB people HTTP {r.status_code}: {r.text[:200]}")
            break
        people = r.json().get("people", [])
        if not people:
            break
        for p in people:
            if (p.get("created") or "") < since_iso:
                return out
            out.append(p)
        if len(people) < 100:
            break
        offset += 100
        time.sleep(0.2)
    return out


def sierra_id_for(person):
    """Derive the Sierra lead id from URL fields, else Sierra email lookup."""
    for field in ("customSierraSearchURL", "customSierraLoginURL",
                  "customSierraAdminURL"):
        # Anchor on ? or & so e.g. "searchid=" can never match as "id="
        m = re.search(r"[?&](?:userid|id)=(\d+)", person.get(field) or "")
        if m:
            return int(m.group(1))
    emails = person.get("emails") or []
    email = emails[0].get("value") if emails else None
    if not email:
        return None
    try:
        r = requests.get(f"{SIERRA_BASE}/leads", headers=SIERRA_HEADERS,
                         params={"email": email}, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data") or {}
            leads = data.get("leads", []) if isinstance(data, dict) else []
            if leads:
                return int(leads[0].get("id") or leads[0].get("leadId"))
    except Exception:
        pass
    return None


def run_pass(since_minutes):
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(minutes=since_minutes))
    since_iso = cutoff.isoformat().replace("+00:00", "Z")
    people = fetch_recent_fub_people(since_iso)
    todo = [p for p in people
            if not (p.get(FUB_SEARCH_URL_FIELD) or "").strip()
            or "searchid=" not in (p.get(FUB_SEARCH_URL_FIELD) or "")]
    if todo:
        print(f"pass: {len(people)} recent FUB people, {len(todo)} need URLs")
    for p in todo:
        sid = sierra_id_for(p)
        if not sid:
            print(f"pid={p.get('id')}: no sierra id derivable, skipping")
            continue
        process_lead_safe(sid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true",
                    help="run a single pass and exit (repair/backfill mode)")
    ap.add_argument("--since-minutes", type=int, default=None,
                    help=f"lookback window (default {LOOKBACK_MINUTES})")
    args = ap.parse_args()

    lookback = args.since_minutes or LOOKBACK_MINUTES
    if args.once:
        run_pass(lookback)
        return
    print(f"url_populator: polling FUB every {POLL_SECONDS}s, "
          f"lookback {lookback} min")
    while True:
        try:
            run_pass(lookback)
        except Exception as e:
            print(f"pass failed: {e!r} — retrying next cycle")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
