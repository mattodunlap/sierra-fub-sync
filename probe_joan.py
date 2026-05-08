"""
Find a specific Sierra lead by email and check whether they appear in
the /leads/find?tags=SPRIORITY filter results.

If the lead has SPRIORITY in their detail but doesn't show in the filter,
that confirms an indexing lag.

Usage:
    python probe_joan.py jnikolaus36@gmail.com
"""

import os
import sys
import requests
from pathlib import Path

# Make print() flush immediately so output is visible even if script crashes
import functools
print = functools.partial(print, flush=True)


def load_env():
    env_path = Path(__file__).parent / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


load_env()
sys.path.insert(0, str(Path(__file__).parent))
from sierra_fub_sync import SIERRA_BASE, SIERRA_HEADERS  # noqa


def main():
    if len(sys.argv) < 2:
        print('Usage: python probe_joan.py <email>')
        sys.exit(1)
    email = sys.argv[1]

    # Find lead by email
    print(f"Searching Sierra for {email!r}...")
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params={"email": email, "pageNumber": 1, "pageSize": 5},
        timeout=30,
    )
    r.raise_for_status()
    leads = r.json().get("data", {}).get("leads", [])
    matches = [l for l in leads if (l.get("email") or "").lower() == email.lower()]
    if not matches:
        print(f"No exact email match. Got {len(leads)} candidates from search:")
        for l in leads[:10]:
            print(f"  id={l.get('id')} {l.get('firstName')} {l.get('lastName')} <{l.get('email')}>")
        sys.exit(1)
    lead = matches[0]
    lead_id = lead["id"]
    print(f"Found: id={lead_id} {lead.get('firstName')} {lead.get('lastName')} <{lead.get('email')}>")
    print(f"  Created: {lead.get('creationDate')}")
    print(f"  Updated: {lead.get('updateDate')}\n")

    # Get full detail (note: Sierra's lead detail does NOT include tags directly;
    # earlier probe showed no 'tags' field on the detail object).
    print("Pulling full lead detail...")
    r = requests.get(
        f"{SIERRA_BASE}/leads/get/{lead_id}",
        headers=SIERRA_HEADERS, timeout=30,
    )
    detail = r.json().get("data") or r.json()
    print(f"Detail keys: {list(detail.keys())}\n")
    print("Note: Sierra lead detail does NOT include a tags field.")
    print("Tags are only accessible via the /leads/find?tags= filter.\n")

    # Now check the SPRIORITY filter for this lead
    print("=" * 70)
    print("Checking if SPRIORITY filter includes this lead...")
    print("=" * 70)
    page = 1
    found = False
    total = 0
    while True:
        r = requests.get(
            f"{SIERRA_BASE}/leads/find",
            headers=SIERRA_HEADERS,
            params={"tags": "SPRIORITY", "pageNumber": page, "pageSize": 100},
            timeout=30,
        )
        data = r.json().get("data", {})
        page_leads = data.get("leads", [])
        if not page_leads:
            break
        total += len(page_leads)
        if any(l.get("id") == lead_id for l in page_leads):
            found = True
            page_match = page
            break
        if page >= data.get("totalPages", 1):
            break
        page += 1

    if found:
        print(f"  YES - {email} IS in the SPRIORITY filter results (page {page_match}, total scanned {total}).")
        print("  Indexing is up-to-date for this lead.")
    else:
        print(f"  NO - {email} is NOT in the SPRIORITY filter (scanned {total} leads).")
        print("  This is strong evidence of indexing lag if Sierra UI shows the tag on this lead.")

    # Also check the legacy 'S Priority' filter just in case
    print("\nAlso checking 'S Priority' filter (the old tag name)...")
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params={"tags": "S Priority", "pageNumber": 1, "pageSize": 100},
        timeout=30,
    )
    legacy_leads = r.json().get("data", {}).get("leads", [])
    in_legacy = any(l.get("id") == lead_id for l in legacy_leads)
    print(f"  Lead in 'S Priority' filter? {in_legacy} (filter has {len(legacy_leads)} total)")


if __name__ == "__main__":
    main()
