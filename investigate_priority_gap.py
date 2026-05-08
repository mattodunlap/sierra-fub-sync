"""
Why does Sierra UI show 116 SPRIORITY but API filter returns 98?

Possible causes (in order of likelihood):
  1. There are similarly-named tags (S Priority vs SPRIORITY etc) in
     different leads that the UI tag count merges but the API filter doesn't
  2. Sierra's API filter is case- or whitespace-sensitive
  3. Indexing lag

This script:
  - Pulls all 687 lead-tag definitions from /leadTags
  - Filters to ones containing 'PRIORITY' (case-insensitive)
  - Tries `/leads/find?tags=` for each variant to count leads
  - Reports any tags that come close to S/SPRIORITY in spelling
"""

import os
import sys
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
sys.path.insert(0, str(Path(__file__).parent))
from sierra_fub_sync import SIERRA_BASE, SIERRA_HEADERS  # noqa


# Pull all lead-tag definitions
print("Pulling all Sierra lead tag definitions...")
all_tags = []
page = 1
while True:
    r = requests.get(
        f"{SIERRA_BASE}/leadTags",
        headers=SIERRA_HEADERS,
        params={"pageNumber": page, "pageSize": 100},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json().get("data", {})
    records = data.get("records", [])
    if not records:
        break
    all_tags.extend(records)
    if page >= data.get("totalPages", 1):
        break
    page += 1
print(f"Got {len(all_tags)} tag definitions.\n")


# Find any tag with 'priority' in the name
priority_tags = [t for t in all_tags if "priority" in (t.get("name") or "").lower()]
print(f"Found {len(priority_tags)} tag(s) containing 'priority':\n")
for t in priority_tags:
    print(f"  id={t.get('id')}  name={t.get('name')!r}  description={t.get('description', '')!r}")


# Get count of leads per priority tag via /leads/find filter
print("\n" + "=" * 70)
print("Lead count via /leads/find?tags=<name> for each priority tag")
print("=" * 70)
for t in priority_tags:
    name = t.get("name")
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params={"tags": name, "pageNumber": 1, "pageSize": 1},
        timeout=30,
    )
    if r.status_code == 200:
        total = r.json().get("data", {}).get("totalRecords", 0)
        print(f"  {name!r:<40} -> {total} leads")
    else:
        print(f"  {name!r:<40} -> ERROR {r.status_code}")


# Also try variations on SPRIORITY case/whitespace
print("\n" + "=" * 70)
print("Variations on SPRIORITY")
print("=" * 70)
variations = ["SPRIORITY", "Spriority", "spriority", "sPriority",
              " SPRIORITY", "SPRIORITY ", "S Priority",
              "S priority", "S-Priority", "S_Priority"]
for var in variations:
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params={"tags": var, "pageNumber": 1, "pageSize": 1},
        timeout=30,
    )
    if r.status_code == 200:
        total = r.json().get("data", {}).get("totalRecords", 0)
        print(f"  {var!r:<25} -> {total} leads")
    else:
        print(f"  {var!r:<25} -> ERROR {r.status_code}")
