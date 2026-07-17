"""
Walks the entire FUB contacts list via API and counts how many have the
Sierra Login URL custom field populated. This is the authoritative source of
truth - bypasses any FUB smart list / UI quirks.
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
FUB_CUSTOM_FIELD = os.environ.get("FUB_CUSTOM_FIELD", "customSierraLoginURL")
FUB_BASE = "https://api.followupboss.com/v1"


def main():
    print(f"Counting FUB contacts with '{FUB_CUSTOM_FIELD}' populated...\n")

    populated = 0
    total = 0
    offset = 0
    limit = 100  # FUB max per page
    page = 1

    while True:
        r = requests.get(
            f"{FUB_BASE}/people",
            auth=(FUB_API_KEY, ""),
            params={"limit": limit, "offset": offset, "fields": "allFields"},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"FUB returned {r.status_code}: {r.text[:200]}")
            break
        data = r.json()
        people = data.get("people", [])
        if not people:
            break

        for p in people:
            total += 1
            val = p.get(FUB_CUSTOM_FIELD)
            if val:
                populated += 1

        # Show progress every 10 pages
        if page % 10 == 0 or len(people) < limit:
            print(f"  Page {page}: total seen={total}, populated={populated}")

        if len(people) < limit:
            break
        offset += limit
        page += 1

    print(f"\n{'='*50}")
    print(f"  Total FUB contacts: {total}")
    print(f"  With '{FUB_CUSTOM_FIELD}' populated: {populated}")
    print(f"  Population rate: {(populated/total*100) if total else 0:.1f}%")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
