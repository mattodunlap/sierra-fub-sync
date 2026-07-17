"""
Compare 'S Priority' tag between Sierra and FUB.
Pulls all Sierra leads with the tag, checks each one's FUB status.
Outputs a report so we can see exactly where the sync gap is.

Read-only - makes no changes.
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

FUB_API_KEY = os.environ["FUB_API_KEY"]
FUB_BASE = "https://api.followupboss.com/v1"
TAG_NAME = sys.argv[1] if len(sys.argv) > 1 else "S Priority"


def fetch_sierra_leads_by_tag(tag):
    """Walk all pages of /leads/find filtered by tag."""
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
        total_pages = data.get("totalPages", 1)
        if page >= total_pages:
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


def main():
    print(f"Pulling all Sierra leads tagged {TAG_NAME!r}...")
    sierra_leads = fetch_sierra_leads_by_tag(TAG_NAME)
    print(f"Sierra returned {len(sierra_leads)} leads with that tag.\n")

    in_fub_with_tag = []
    in_fub_missing_tag = []
    not_in_fub = []

    for i, lead in enumerate(sierra_leads, 1):
        email = lead.get("email") or ""
        sierra_id = lead.get("id")
        name = f"{lead.get('firstName', '')} {lead.get('lastName', '')}".strip()

        if not email or "notvalidemail" in email.lower():
            not_in_fub.append((sierra_id, name, email, "no real email"))
            continue

        person = find_fub_person(email)
        if not person:
            not_in_fub.append((sierra_id, name, email, "no FUB match"))
            continue

        fub_tags = person.get("tags") or []
        if TAG_NAME in fub_tags:
            in_fub_with_tag.append((sierra_id, name, email, person.get("id")))
        else:
            in_fub_missing_tag.append((sierra_id, name, email, person.get("id"), fub_tags))

        if i % 20 == 0:
            print(f"  [{i}/{len(sierra_leads)}] processed: "
                  f"with_tag={len(in_fub_with_tag)}, "
                  f"missing_tag={len(in_fub_missing_tag)}, "
                  f"not_in_fub={len(not_in_fub)}")

    # Build report
    out = []
    out.append(f"=== '{TAG_NAME}' TAG COMPARISON ===\n")
    out.append(f"Sierra leads with tag: {len(sierra_leads)}")
    out.append(f"In FUB with tag (synced):     {len(in_fub_with_tag)}")
    out.append(f"In FUB but missing tag:       {len(in_fub_missing_tag)}")
    out.append(f"Not in FUB at all:            {len(not_in_fub)}")

    if in_fub_missing_tag:
        out.append(f"\n=== IN FUB BUT MISSING '{TAG_NAME}' TAG (the sync gap) ===")
        for sierra_id, name, email, fub_id, fub_tags in in_fub_missing_tag[:50]:
            out.append(f"  Sierra id={sierra_id} | FUB id={fub_id} | {name} | {email}")
            if fub_tags:
                out.append(f"     FUB has these tags instead: {sorted(fub_tags)}")
        if len(in_fub_missing_tag) > 50:
            out.append(f"  ... and {len(in_fub_missing_tag) - 50} more")

    if not_in_fub:
        out.append(f"\n=== SIERRA LEADS NOT IN FUB AT ALL ===")
        for sierra_id, name, email, reason in not_in_fub[:30]:
            out.append(f"  Sierra id={sierra_id} | {name} | {email} | reason: {reason}")
        if len(not_in_fub) > 30:
            out.append(f"  ... and {len(not_in_fub) - 30} more")

    report = "\n".join(out)
    print("\n" + report)

    out_path = Path(__file__).parent / "priority_tag_compare.txt"
    out_path.write_text(report)
    print(f"\nReport saved to: {out_path}")


if __name__ == "__main__":
    main()
