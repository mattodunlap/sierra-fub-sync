"""
Replace `%custom_ylopo_listing_alert%` with `%custom_sierra_login_url%`
in all FUB email and SMS templates that contain it.

Safety features:
  - Default mode is DRY RUN. Pass --write to actually push changes to FUB.
  - Saves a backup of every template's original body to ./template_backups/
    before pushing changes (so we can restore if needed).
  - Only does an EXACT string replacement of `%custom_ylopo_listing_alert%`.
    Does not touch `%custom_ylopo_seller_report%` or any hardcoded URLs.
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime


def load_env():
    env_path = Path(__file__).parent / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


load_env()

FUB_API_KEY = os.environ["FUB_API_KEY"]
FUB_BASE = "https://api.followupboss.com/v1"

OLD_TAG = "%custom_ylopo_listing_alert%"
NEW_TAG = "%custom_sierra_login_url%"


def fetch_paginated(endpoint, items_keys):
    """Walk all pages of a FUB list endpoint."""
    items = []
    next_url = f"{FUB_BASE}/{endpoint}?limit=100"
    while next_url:
        r = requests.get(next_url, auth=(FUB_API_KEY, ""), timeout=30)
        if r.status_code != 200:
            print(f"ERROR fetching {endpoint}: {r.status_code} {r.text[:200]}")
            break
        data = r.json()
        page_items = None
        for k in items_keys:
            if k in data:
                page_items = data[k]
                break
        if page_items is None:
            print(f"Unknown response shape for {endpoint}: keys={list(data.keys())}")
            break
        items.extend(page_items)
        meta = data.get("_metadata", {}) or data.get("metadata", {})
        next_url = meta.get("nextLink") or meta.get("next")
    return items


def update_template(endpoint, template, field, new_value):
    """Fetch the full template fresh, swap the field, PUT it back.
    Listing endpoint sometimes returns stripped versions, so always
    re-fetch before update."""
    template_id = template["id"]
    # Re-fetch full template to ensure we have all required fields
    fetched = requests.get(
        f"{FUB_BASE}/{endpoint}/{template_id}",
        auth=(FUB_API_KEY, ""), timeout=30,
    )
    if fetched.status_code != 200:
        print(f"  Re-fetch failed: {fetched.status_code} {fetched.text[:200]}")
        return False
    full = fetched.json()
    # FUB is strict about which fields PUT accepts. Strip all read-only
    # metadata AND statistics fields it complains about.
    READ_ONLY = {
        # Generic metadata
        "id", "created", "updated", "createdById", "updatedById",
        "isEditable", "isShareable", "isDeletable",
        # Email template extras FUB rejects on PUT
        "imported", "isMobile", "actionPlans", "automations",
        # SMS template stats FUB rejects on PUT
        "totalSent", "totalReplies", "createdBy", "sentPeopleCount",
        "effectivenessScore", "windowedSent", "windowedReplies",
        "windowedOptOutRate", "totalOptOutRate",
    }
    payload = {k: v for k, v in full.items() if k not in READ_ONLY}
    payload[field] = new_value
    # Sanity check: name must not be blank
    if not payload.get("name"):
        print(f"  WARNING: template id={template_id} has no 'name'. "
              f"Available keys: {list(full.keys())}")
        return False

    r = requests.put(
        f"{FUB_BASE}/{endpoint}/{template_id}",
        auth=(FUB_API_KEY, ""), json=payload, timeout=30,
    )
    if r.status_code != 200:
        print(f"  PUT failed: {r.status_code} {r.text[:200]}")
        print(f"  Payload keys sent: {list(payload.keys())}")
        return False
    return True


def backup(folder, kind, tpl):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{kind}_{tpl.get('id')}.json"
    path.write_text(json.dumps(tpl, indent=2, default=str))


def process(label, endpoint, items_key, body_field, write_mode, backup_folder):
    print(f"\n{'='*70}\n  {label}\n{'='*70}")
    templates = fetch_paginated(endpoint, [items_key])
    candidates = [t for t in templates if OLD_TAG in (t.get(body_field) or "")]
    print(f"Total templates: {len(templates)}")
    print(f"Templates containing {OLD_TAG}: {len(candidates)}")

    updated = 0
    failed = 0
    for tpl in candidates:
        body = tpl.get(body_field) or ""
        new_body = body.replace(OLD_TAG, NEW_TAG)
        old_count = body.count(OLD_TAG)

        kind = "email" if body_field == "body" else "sms"
        print(f"\n  id={tpl.get('id')}: {tpl.get('name')!r}")
        print(f"    Replacing {old_count}x {OLD_TAG} -> {NEW_TAG}")

        if not write_mode:
            print(f"    [DRY RUN] would update.")
            continue

        # Save backup BEFORE writing
        backup(backup_folder, kind, tpl)
        ok = update_template(endpoint, tpl, body_field, new_body)
        if ok:
            updated += 1
            print(f"    SUCCESS - written.")
        else:
            failed += 1

    return len(candidates), updated, failed


def main():
    write_mode = "--write" in sys.argv

    print(f"\n{'!'*70}")
    print(f"  Mode: {'LIVE WRITE' if write_mode else 'DRY RUN (no changes will be made)'}")
    print(f"  Replacing: {OLD_TAG}")
    print(f"  With:      {NEW_TAG}")
    print(f"{'!'*70}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder = Path(__file__).parent / "template_backups" / timestamp

    email_count, email_updated, email_failed = process(
        "EMAIL TEMPLATES", "templates", "templates", "body",
        write_mode, backup_folder,
    )
    sms_count, sms_updated, sms_failed = process(
        "SMS TEMPLATES", "textMessageTemplates", "textmessagetemplates", "message",
        write_mode, backup_folder,
    )

    print(f"\n{'='*70}\n  SUMMARY\n{'='*70}")
    print(f"  Email templates: {email_count} candidates, "
          f"{email_updated} updated, {email_failed} failed")
    print(f"  SMS templates:   {sms_count} candidates, "
          f"{sms_updated} updated, {sms_failed} failed")
    if write_mode:
        print(f"\n  Backups saved to: {backup_folder}")
        print(f"  Keep them in case you ever want to roll back.")
    else:
        print(f"\n  DRY RUN COMPLETE - no changes made.")
        print(f"  Re-run with: python replace_ylopo_to_sierra.py --write")


if __name__ == "__main__":
    main()
