"""
Compares tags between FUB and Sierra for a sample of contacts.
Helps figure out what the native Sierra-FUB integration actually syncs.

Read-only - makes no changes. Output saved to tag_comparison.txt.
"""

import os
import requests
from pathlib import Path
import random


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

FUB_API_KEY = os.environ["FUB_API_KEY"]
FUB_BASE = "https://api.followupboss.com/v1"

SAMPLE_SIZE = 15


def fetch_fub_sample():
    """Pull a sample of FUB contacts that have email + tags."""
    contacts = []
    next_url = f"{FUB_BASE}/people?limit=100&fields=allFields"
    while next_url and len(contacts) < 500:
        r = requests.get(next_url, auth=(FUB_API_KEY, ""), timeout=30)
        if r.status_code != 200:
            break
        data = r.json()
        for p in data.get("people", []):
            tags = p.get("tags") or []
            emails = p.get("emails") or []
            if tags and emails:
                contacts.append(p)
        meta = data.get("_metadata", {}) or data.get("metadata", {})
        next_url = meta.get("nextLink") or meta.get("next")
    return contacts


def find_sierra_lead(email):
    if not email:
        return None
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params={"email": email, "pageNumber": 1, "pageSize": 5},
        timeout=15,
    )
    if r.status_code != 200:
        return None
    leads = r.json().get("data", {}).get("leads", [])
    for lead in leads:
        if (lead.get("email") or "").lower() == email.lower():
            return lead
    return leads[0] if leads else None


def get_sierra_lead_detail(lead_id):
    """Pull the full lead detail (tags etc are on detail endpoint)."""
    r = requests.get(
        f"{SIERRA_BASE}/leads/get/{lead_id}",
        headers=SIERRA_HEADERS,
        timeout=15,
    )
    if r.status_code != 200:
        return None
    return r.json().get("data") or r.json()


def main():
    print("Pulling FUB contacts with tags...")
    contacts = fetch_fub_sample()
    print(f"Found {len(contacts)} candidates with both tags and email.\n")

    if len(contacts) > SAMPLE_SIZE:
        sample = random.sample(contacts, SAMPLE_SIZE)
    else:
        sample = contacts

    output = ["TAG COMPARISON - FUB vs Sierra (random sample)"]
    output.append(f"Sample size: {len(sample)}")
    output.append("=" * 80)

    matched = 0
    for i, p in enumerate(sample, 1):
        name = f"{p.get('firstName','')} {p.get('lastName','')}".strip()
        emails = p.get("emails") or []
        email = emails[0].get("value") if emails else ""
        fub_tags = sorted(p.get("tags") or [])

        sierra_lead = find_sierra_lead(email)
        if not sierra_lead:
            output.append(f"\n{i}. {name} ({email})")
            output.append(f"   FUB tags: {fub_tags}")
            output.append(f"   Sierra: NOT FOUND")
            continue

        matched += 1
        sierra_detail = get_sierra_lead_detail(sierra_lead["id"]) or sierra_lead
        # Sierra might have 'tags' or 'leadTags' or similar
        sierra_tags = []
        for k in ("tags", "leadTags", "Tags"):
            if k in sierra_detail and isinstance(sierra_detail[k], list):
                sierra_tags = sierra_detail[k]
                break
        # Tags may be objects with name field, or strings
        sierra_tag_names = sorted([
            t.get("name") if isinstance(t, dict) else t
            for t in sierra_tags if t
        ])

        only_in_fub = set(fub_tags) - set(sierra_tag_names)
        only_in_sierra = set(sierra_tag_names) - set(fub_tags)
        in_both = set(fub_tags) & set(sierra_tag_names)

        output.append(f"\n{i}. {name} ({email})")
        output.append(f"   FUB tags ({len(fub_tags)}): {fub_tags}")
        output.append(f"   Sierra tags ({len(sierra_tag_names)}): {sierra_tag_names}")
        output.append(f"   In both: {sorted(in_both)}")
        output.append(f"   Only in FUB: {sorted(only_in_fub)}")
        output.append(f"   Only in Sierra: {sorted(only_in_sierra)}")

    output.append("\n" + "=" * 80)
    output.append(f"Sample matched in Sierra: {matched}/{len(sample)}")
    output.append("\nIf 'Only in FUB' or 'Only in Sierra' columns are populated,")
    output.append("the native integration is NOT keeping tags in sync.")

    out_path = Path(__file__).parent / "tag_comparison.txt"
    out_path.write_text("\n".join(output))
    print(f"\nReport saved to: {out_path}")
    print("\n" + "\n".join(output))


if __name__ == "__main__":
    main()
