"""
List all FUB email and SMS templates. Helps identify which ones contain
links we should replace with the {{customSierraLoginURL}} merge tag.

Read-only - makes no changes.
"""

import os
import re
import requests
from pathlib import Path


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
URL_PATTERN = re.compile(r'https?://[^\s"\'<>]+', re.IGNORECASE)
YLOPO_TAG_PATTERN = re.compile(r'%custom_ylopo[^%]*%', re.IGNORECASE)
SIERRA_TAG_PATTERNS = [
    re.compile(r'%custom_sierra_login_url%', re.IGNORECASE),
    re.compile(r'\{\{customSierraLoginURL\}\}', re.IGNORECASE),
    re.compile(r'\[Sierra Login URL\]', re.IGNORECASE),
]


def fetch_paginated(endpoint):
    """Fetch all pages from a FUB list endpoint."""
    items = []
    next_url = f"{FUB_BASE}/{endpoint}?limit=100"
    while next_url:
        r = requests.get(next_url, auth=(FUB_API_KEY, ""), timeout=30)
        if r.status_code != 200:
            print(f"  ERROR fetching {endpoint}: {r.status_code} {r.text[:200]}")
            break
        data = r.json()
        possible_keys = ["templates", "textMessageTemplates", "textmessagetemplates", "items"]
        page_items = None
        for k in possible_keys:
            if k in data:
                page_items = data[k]
                break
        if page_items is None:
            print(f"  Unknown response shape for {endpoint}: {list(data.keys())}")
            break
        items.extend(page_items)
        meta = data.get("_metadata", {}) or data.get("metadata", {})
        next_url = meta.get("nextLink") or meta.get("next")
    return items


def find_sierra_links(text):
    """Pull out URLs from text that look like Sierra/agent-site links."""
    if not text:
        return []
    matches = URL_PATTERN.findall(text)
    sierra_links = [m for m in matches if "thevegasagent.com" in m.lower()]
    return sierra_links


def find_ylopo_tags(text):
    """Find Ylopo merge tag references like %custom_ylopo_listing_alert%."""
    if not text:
        return []
    return YLOPO_TAG_PATTERN.findall(text)


def already_has_sierra_tag(text):
    if not text:
        return False
    return any(p.search(text) for p in SIERRA_TAG_PATTERNS)


def show(label, templates, body_field, name_field="name"):
    print(f"\n{'='*70}")
    print(f"  {label} — {len(templates)} found")
    print(f"{'='*70}")
    for i, t in enumerate(templates, 1):
        name = t.get(name_field) or t.get("subject") or "(unnamed)"
        body = t.get(body_field) or ""
        sierra_links = find_sierra_links(body)
        ylopo_tags = find_ylopo_tags(body)
        has_sierra_tag = already_has_sierra_tag(body)
        markers = []
        if has_sierra_tag:
            markers.append("ALREADY HAS SIERRA TAG")
        if ylopo_tags:
            markers.append(f"{len(ylopo_tags)} YLOPO TAG(S) - candidate")
        if sierra_links:
            markers.append(f"{len(sierra_links)} hardcoded Sierra link(s)")
        marker_str = f" [{' | '.join(markers)}]" if markers else ""
        print(f"  {i:3}. id={t.get('id')} {name!r}{marker_str}")
        for link in sierra_links[:3]:
            print(f"       URL -> {link[:100]}")
        for tag in ylopo_tags[:3]:
            print(f"       YLOPO TAG -> {tag}")


def main():
    print("Fetching FUB email templates...")
    email_tpls = fetch_paginated("templates")
    show("EMAIL TEMPLATES", email_tpls, body_field="body")

    print("\nFetching FUB SMS templates...")
    sms_tpls = fetch_paginated("textMessageTemplates")
    show("SMS TEMPLATES", sms_tpls, body_field="message")

    # Summary
    email_ylopo = [t for t in email_tpls if find_ylopo_tags(t.get("body", ""))
                   and not already_has_sierra_tag(t.get("body", ""))]
    sms_ylopo = [t for t in sms_tpls if find_ylopo_tags(t.get("message", ""))
                 and not already_has_sierra_tag(t.get("message", ""))]
    email_links = [t for t in email_tpls if find_sierra_links(t.get("body", ""))
                   and not already_has_sierra_tag(t.get("body", ""))]
    sms_links = [t for t in sms_tpls if find_sierra_links(t.get("message", ""))
                 and not already_has_sierra_tag(t.get("message", ""))]
    print("\n" + "="*70)
    print(f"  SUMMARY")
    print("="*70)
    print(f"  Total emails: {len(email_tpls)}, Total SMS: {len(sms_tpls)}")
    print(f"  Email templates with Ylopo tags (replace candidates): {len(email_ylopo)}")
    print(f"  SMS templates with Ylopo tags (replace candidates):   {len(sms_ylopo)}")
    print(f"  Email templates with hardcoded Sierra links: {len(email_links)}")
    print(f"  SMS templates with hardcoded Sierra links:   {len(sms_links)}")
    print("\n  Paste this output to Claude to plan the replacement.")


if __name__ == "__main__":
    main()
