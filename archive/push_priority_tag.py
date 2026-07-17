"""
Push the 'S Priority' tag from Sierra to FUB for any contact where
Sierra has the tag but FUB doesn't.

Usage:
    python push_priority_tag.py "S Priority"          # DRY RUN
    python push_priority_tag.py "S Priority" --write  # actually update FUB

For each Sierra lead with the tag:
  1. Look up by email in FUB
  2. If found and tag is missing: add "S Priority" to FUB tags array (preserving existing)
  3. PUT update back to FUB
"""

import os
import sys
import time
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

FUB_API_KEY = os.environ["FUB_API_KEY"]
FUB_BASE = "https://api.followupboss.com/v1"
SLEEP_BETWEEN_WRITES = 0.7


def fetch_sierra_leads_by_tag(tag):
    leads = []
    page = 1
    while True:
        r = requests.get(
            f"{SIERRA_BASE}/leads/find",
            headers=SIERRA_HEADERS,
            params={"tags": tag, "pageNumber": page, "pageSize": 100},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        page_leads = data.get("leads", [])
        if not page_leads:
            break
        leads.extend(page_leads)
        if page >= data.get("totalPages", 1):
            break
        page += 1
    return leads


def find_fub_person(email):
    if not email:
        return None
    r = requests.get(
        f"{FUB_BASE}/people",
        auth=(FUB_API_KEY, ""),
        params={"email": email, "fields": "allFields"},
        timeout=15,
    )
    if r.status_code != 200:
        return None
    people = r.json().get("people", [])
    return people[0] if people else None


def add_tag_to_fub(person_id, current_tags, new_tag):
    """Add a tag to a FUB person, preserving existing tags."""
    if new_tag in current_tags:
        return True  # already there
    new_tags = list(current_tags) + [new_tag]
    r = requests.put(
        f"{FUB_BASE}/people/{person_id}",
        auth=(FUB_API_KEY, ""),
        json={"tags": new_tags},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  PUT failed for id={person_id}: {r.status_code} {r.text[:200]}")
        return False
    return True


def main():
    if len(sys.argv) < 2:
        print('Usage: python push_priority_tag.py "Tag Name" [--write]')
        sys.exit(1)
    tag = sys.argv[1]
    write_mode = "--write" in sys.argv

    print(f"Mode: {'LIVE WRITE' if write_mode else 'DRY RUN'}")
    print(f"Pushing Sierra tag {tag!r} into FUB where missing...\n")

    sierra_leads = fetch_sierra_leads_by_tag(tag)
    print(f"Sierra has {len(sierra_leads)} leads with this tag.\n")

    pushed = 0
    already_had = 0
    not_in_fub = 0
    write_failed = 0

    for i, lead in enumerate(sierra_leads, 1):
        email = lead.get("email") or ""
        name = f"{lead.get('firstName', '')} {lead.get('lastName', '')}".strip()
        if not email or "notvalidemail" in email.lower():
            not_in_fub += 1
            continue

        person = find_fub_person(email)
        if not person:
            not_in_fub += 1
            continue

        current_tags = person.get("tags") or []
        if tag in current_tags:
            already_had += 1
            continue

        if write_mode:
            if add_tag_to_fub(person["id"], current_tags, tag):
                pushed += 1
                print(f"  + Added '{tag}' to {name} ({email})")
                time.sleep(SLEEP_BETWEEN_WRITES)
            else:
                write_failed += 1
        else:
            pushed += 1
            print(f"  [DRY] Would add '{tag}' to {name} ({email})")

        if i % 20 == 0:
            print(f"  [{i}/{len(sierra_leads)}] processed: pushed={pushed}, "
                  f"already_had={already_had}, not_in_fub={not_in_fub}")

    summary_lines = [
        "",
        "=" * 60,
        f"SUMMARY  ({'LIVE' if write_mode else 'DRY RUN'})",
        f"Tag: {tag!r}",
        f"Run timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        f"  Sierra leads with tag:    {len(sierra_leads)}",
        f"  Already had tag in FUB:   {already_had}",
        f"  {'Pushed to FUB' if write_mode else 'Would push'}:        {pushed}",
        f"  Not in FUB:               {not_in_fub}",
    ]
    if write_mode:
        summary_lines.append(f"  Write failed:             {write_failed}")
    summary_text = "\n".join(summary_lines)
    print(summary_text)

    Path(__file__).parent.joinpath("priority_push_summary.txt").write_text(summary_text)
    print(f"\nSummary saved to: priority_push_summary.txt")


if __name__ == "__main__":
    main()
