"""
Find out how Sierra exposes tags via the API. We know /leads/get/{id} doesn't
show them - tags must be on a separate endpoint or under a different name.

Tries:
  1. Sample lead detail - dumps every field looking for tag-shaped data
  2. /leads/{id}/tags variations
  3. /tags listing endpoints
  4. /leads/find with various tag filter param names
"""

import os
import json
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

import sys
sys.path.insert(0, str(Path(__file__).parent))
from sierra_fub_sync import SIERRA_BASE, SIERRA_HEADERS  # noqa


def hr(label):
    print("\n" + "=" * 70)
    print(label)
    print("=" * 70)


# Pick a recent lead (likely to have tags) - last page first lead
hr("Step 1: Get a sample recent lead")
r = requests.get(f"{SIERRA_BASE}/leads/find", headers=SIERRA_HEADERS,
                 params={"pageNumber": 1, "pageSize": 1}, timeout=30)
total_pages = r.json().get("data", {}).get("totalPages", 1)
print(f"Total pages: {total_pages}")
r = requests.get(f"{SIERRA_BASE}/leads/find", headers=SIERRA_HEADERS,
                 params={"pageNumber": total_pages, "pageSize": 1}, timeout=30)
leads = r.json().get("data", {}).get("leads", [])
if not leads:
    # fallback to first page
    r = requests.get(f"{SIERRA_BASE}/leads/find", headers=SIERRA_HEADERS,
                     params={"pageNumber": 1, "pageSize": 1}, timeout=30)
    leads = r.json().get("data", {}).get("leads", [])
sample_lead_id = leads[0]["id"]
print(f"Using sample lead id={sample_lead_id}")


# Get the full detail and dump everything
hr("Step 2: Full lead detail - look for tag-shaped fields")
r = requests.get(f"{SIERRA_BASE}/leads/get/{sample_lead_id}", headers=SIERRA_HEADERS, timeout=30)
detail = r.json().get("data") or r.json()
print(f"Top-level keys: {list(detail.keys())}")
for k, v in detail.items():
    if isinstance(v, list):
        print(f"  ARRAY '{k}' ({len(v)} items): {str(v)[:200]}")
    elif isinstance(v, str) and any(t in k.lower() for t in ("tag", "priority", "label", "categor")):
        print(f"  POSSIBLE TAG FIELD '{k}': {v}")


# Try lead-tags subendpoints
hr("Step 3: Probe lead-tag subendpoints")
candidates = [
    f"{SIERRA_BASE}/leads/get/{sample_lead_id}/tags",
    f"{SIERRA_BASE}/leads/{sample_lead_id}/tags",
    f"{SIERRA_BASE}/leads/tags/{sample_lead_id}",
    f"{SIERRA_BASE}/tags/{sample_lead_id}",
    f"{SIERRA_BASE}/leadTags/{sample_lead_id}",
    f"{SIERRA_BASE}/lead-tags?leadId={sample_lead_id}",
]
for url in candidates:
    try:
        r = requests.get(url, headers=SIERRA_HEADERS, timeout=15)
        snippet = r.text[:150].replace("\n", " ")
        marker = "OK" if r.status_code == 200 else "FAIL"
        print(f"  {marker} GET {url[len(SIERRA_BASE):]:60} -> {r.status_code}  {snippet}")
    except Exception as e:
        print(f"  ERR GET {url}: {e}")


# Try top-level tags endpoint
hr("Step 4: Probe global tag endpoints")
candidates = [
    f"{SIERRA_BASE}/tags",
    f"{SIERRA_BASE}/tags/list",
    f"{SIERRA_BASE}/leadTags",
    f"{SIERRA_BASE}/lead-tags",
    f"{SIERRA_BASE}/tag/list",
]
for url in candidates:
    try:
        r = requests.get(url, headers=SIERRA_HEADERS, timeout=15)
        snippet = r.text[:200].replace("\n", " ")
        marker = "OK" if r.status_code == 200 else "FAIL"
        print(f"  {marker} GET {url[len(SIERRA_BASE):]:30} -> {r.status_code}  {snippet}")
    except Exception as e:
        print(f"  ERR GET {url}: {e}")


# Try filtering /leads/find by tag-like params
hr("Step 5: Probe /leads/find filter params for tags")
filter_params = [
    {"tag": "S Priority"},
    {"tags": "S Priority"},
    {"tagName": "S Priority"},
    {"leadTag": "S Priority"},
    {"category": "S Priority"},
]
for params in filter_params:
    full = {**params, "pageNumber": 1, "pageSize": 1}
    r = requests.get(f"{SIERRA_BASE}/leads/find", headers=SIERRA_HEADERS, params=full, timeout=15)
    if r.status_code == 200:
        data = r.json().get("data", {})
        total = data.get("totalRecords", 0)
        first_lead_id = data.get("leads", [{}])[0].get("id") if data.get("leads") else None
        param_str = list(params.items())[0]
        print(f"  {param_str} -> totalRecords={total} firstLead={first_lead_id}")
    else:
        snippet = r.text[:150].replace("\n", " ")
        print(f"  {list(params.items())[0]} -> {r.status_code} {snippet}")


hr("DONE")
print("Look at what worked above. The tag location is likely:")
print("  - A field on lead detail you didn't notice (re-scan Step 2 carefully)")
print("  - A subendpoint that returned 200 in Step 3")
print("  - A filter param that returned > 0 totalRecords in Step 5")
