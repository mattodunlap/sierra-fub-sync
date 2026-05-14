"""
Multi-tag PUSH (Sierra -> FUB only, no delete):
For each tag in tags_to_push.txt, query Sierra and add tag to FUB
contacts that don't already have it. Existing FUB tags preserved.

Default mode is DRY RUN. Pass --write to actually modify FUB.
"""

import os
import sys
import time
import requests
from pathlib import Path


def load_env():
    """Load .env if present (local dev). In CI, env vars are already set."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

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
    if new_tag in current_tags:
        return True
    r = requests.put(
        f"{FUB_BASE}/people/{person_id}",
        auth=(FUB_API_KEY, ""),
        json={"tags": list(current_tags) + [new_tag]},
        timeout=30,
    )
    return r.status_code == 200


def process_tag(tag, write_mode):
    print(f"\n{'='*70}\n  TAG: {tag!r}\n{'='*70}")
    leads = fetch_sierra_leads_by_tag(tag)
    print(f"  Sierra returned {len(leads)} leads with this tag.")

    pushed = 0
    already_had = 0
    not_in_fub = 0
    write_failed = 0

    for i, lead in enumerate(leads, 1):
        email = lead.get("email") or ""
        if not email or "notvalidemail" in email.lower():
            not_in_fub += 1
            continue
        person = find_fub_person(email)
        if not person:
            not_in_fub += 1
            continue
        current = person.get("tags") or []
        if tag in current:
            already_had += 1
            continue
        if write_mode:
            if add_tag_to_fub(person["id"], current, tag):
                pushed += 1
                time.sleep(SLEEP_BETWEEN_WRITES)
            else:
                write_failed += 1
        else:
            pushed += 1
        if i % 25 == 0:
            print(f"    [{i}/{len(leads)}] pushed={pushed}, already={already_had}, no_match={not_in_fub}")

    print(f"\n  Result for {tag!r}:")
    label = "Pushed" if write_mode else "Would push"
    print(f"    Sierra count:           {len(leads)}")
    print(f"    Already in FUB:         {already_had}")
    print(f"    {label}:           {pushed}")
    print(f"    Not in FUB:             {not_in_fub}")
    return {
        "tag": tag, "sierra_count": len(leads),
        "already_had": already_had, "pushed": pushed,
        "not_in_fub": not_in_fub,
    }


def main():
    write_mode = "--write" in sys.argv
    tags_file = Path(__file__).parent / "tags_to_push.txt"
    tags = [line.strip() for line in tags_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")]

    print(f"Mode: {'LIVE WRITE' if write_mode else 'DRY RUN'}")
    print(f"Tags to push: {tags}\n")

    results = [process_tag(tag, write_mode) for tag in tags]

    print(f"\n{'='*70}\n  MASTER SUMMARY  ({'LIVE' if write_mode else 'DRY RUN'})\n{'='*70}")
    for r in results:
        action = "Pushed" if write_mode else "Would push"
        print(f"  {r['tag']!r}: sierra={r['sierra_count']}, "
              f"already_in_fub={r['already_had']}, "
              f"{action.lower()}={r['pushed']}, no_match={r['not_in_fub']}")

    summary_text = "\n".join([
        f"BATCH TAG PUSH SUMMARY ({'LIVE' if write_mode else 'DRY RUN'})",
        f"Run timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 70,
    ] + [
        f"  {r['tag']!r}: sierra={r['sierra_count']}, already={r['already_had']}, "
        f"{'pushed' if write_mode else 'would_push'}={r['pushed']}, "
        f"not_in_fub={r['not_in_fub']}"
        for r in results
    ])
    Path(__file__).parent.joinpath("tag_push_batch_summary.txt").write_text(summary_text)


if __name__ == "__main__":
    main()
