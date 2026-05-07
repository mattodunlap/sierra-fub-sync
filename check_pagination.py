"""
Verify that Sierra's /leads/find pagination actually returns different leads
on different pages. Bug suspect: it might be returning the same 100 leads
every time.
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

import sys
sys.path.insert(0, str(Path(__file__).parent))
from sierra_fub_sync import SIERRA_BASE, SIERRA_HEADERS  # noqa


def fetch(page, page_size=100, **extra_params):
    params = {"page": page, "pageSize": page_size}
    params.update(extra_params)
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params=params,
        timeout=30,
    )
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    return r.json().get("data", {}), None


def main():
    print("Probing Sierra pagination behavior...\n")

    pages_to_check = [1, 2, 3, 5, 10, 50, 100]
    page_first_ids = {}
    page_last_ids = {}

    for p in pages_to_check:
        data, err = fetch(p)
        if err:
            print(f"page {p}: {err}")
            continue
        leads = data.get("leads", [])
        total_records = data.get("totalRecords")
        total_pages = data.get("totalPages")
        if not leads:
            print(f"page {p}: no leads returned (totalRecords={total_records})")
            continue
        first_id = leads[0].get("id")
        last_id = leads[-1].get("id")
        page_first_ids[p] = first_id
        page_last_ids[p] = last_id
        print(f"page {p:3}: {len(leads)} leads. first id={first_id}, last id={last_id}, totalRecords={total_records}")

    print("\nDiagnosis:")
    unique_first_ids = set(page_first_ids.values())
    if len(unique_first_ids) == 1:
        print("  BROKEN: every page returns the same lead as the first item.")
        print("  Sierra's `page` parameter is not being honored. Need a workaround.")
    elif len(unique_first_ids) == len(page_first_ids):
        print("  OK: pagination works - every page returns different first leads.")
    else:
        print(f"  PARTIAL: pages share some first-IDs. Unique first IDs: {unique_first_ids}")

    # Also try alternative parameter names that some APIs use
    print("\n--- Also probing alternative pagination parameter names ---")
    alternatives = [
        ("page", 5),
        ("pageNumber", 5),
        ("Page", 5),
        ("PageNumber", 5),
        ("offset", 500),
        ("skip", 500),
    ]
    for name, value in alternatives:
        params = {"pageSize": 100, name: value}
        r = requests.get(
            f"{SIERRA_BASE}/leads/find",
            headers=SIERRA_HEADERS,
            params=params,
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  {name}={value:5}: HTTP {r.status_code}")
            continue
        leads = r.json().get("data", {}).get("leads", [])
        first_id = leads[0].get("id") if leads else "(no leads)"
        print(f"  {name}={value:5}: first id={first_id}")


if __name__ == "__main__":
    main()
