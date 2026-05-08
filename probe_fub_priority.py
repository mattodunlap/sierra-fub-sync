"""
Investigate the FUB UI count (45) vs API discrepancy.
Pulls contacts via /people?tags=S Priority filter and compares to UI count.
"""

import os
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


# Approach 1: filter by tag using FUB's tag query param
print("=" * 70)
print("Approach 1: FUB /people?tags=S Priority")
print("=" * 70)
contacts = []
next_url = f"{FUB_BASE}/people?limit=100&tags={requests.utils.quote('S Priority')}&fields=allFields"
while next_url:
    r = requests.get(next_url, auth=(FUB_API_KEY, ""), timeout=30)
    if r.status_code != 200:
        print(f"  ERROR: {r.status_code} {r.text[:200]}")
        break
    data = r.json()
    page = data.get("people", [])
    contacts.extend(page)
    meta = data.get("_metadata", {}) or data.get("metadata", {})
    next_url = meta.get("nextLink")
print(f"\nFound {len(contacts)} contacts via FUB tags filter.\n")


# Approach 2: Show a few samples with their raw tags array (look for casing)
print("=" * 70)
print("Approach 2: Sample 5 contacts - show raw tags array as returned by FUB")
print("=" * 70)
for c in contacts[:5]:
    name = f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
    print(f"\n{name} (id={c.get('id')}):")
    print(f"  raw tags: {c.get('tags')}")
    # Look for any tag that case-insensitively contains 'priority'
    priority_tags = [t for t in (c.get('tags') or []) if 'priority' in str(t).lower()]
    print(f"  priority-ish tags: {priority_tags}")


# Approach 3: Look for emails in our previous 97 Sierra leads to see if they match
print("\n" + "=" * 70)
print("Approach 3: First 5 contact emails from FUB tag filter")
print("=" * 70)
for c in contacts[:10]:
    emails = c.get("emails") or []
    email = emails[0].get("value") if emails else "(no email)"
    name = f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
    print(f"  id={c.get('id')} {name} <{email}>")
