"""
Probe FUB Smart Lists -- find the "Claude 1-14" lists and dump what they are.

Run this ON THE DROPLET (where .env with FUB_API_KEY lives):
    python3 probe_smartlists.py

It will:
  1. List ALL FUB smart lists (id, name, and size if the API returns it),
     across both FUB Classic and the current UI (all=true).
  2. Highlight any whose name contains "claude".
  3. Dump the full JSON detail for each matched list so we can see its
     filters and anything attached to it (this is how we tell whether each
     list is actually wired up to send a text/email).

Nothing is written or changed -- read-only.
"""

import json
import os
import sys
import requests
from pathlib import Path


def load_env():
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("No .env found next to this script. Run it on the droplet, or set "
              "FUB_API_KEY in the environment.", file=sys.stderr)
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

FUB_API_KEY = os.environ.get("FUB_API_KEY")
if not FUB_API_KEY:
    print("FUB_API_KEY is not set. Cannot continue.", file=sys.stderr)
    sys.exit(1)

FUB_BASE = "https://api.followupboss.com/v1"
AUTH = (FUB_API_KEY, "")


def get(path, **params):
    r = requests.get(f"{FUB_BASE}{path}", auth=AUTH, params=params, timeout=30)
    return r


def list_all_smartlists():
    """Page through every smart list (classic + current UI)."""
    lists = []
    offset = 0
    while True:
        r = get("/smartLists", all="true", limit=100, offset=offset)
        if r.status_code != 200:
            print(f"  /smartLists failed: HTTP {r.status_code} {r.text[:200]}")
            break
        data = r.json()
        # FUB usually wraps collections as {"smartlists":[...]} or {"smartLists":[...]}
        batch = (data.get("smartlists") or data.get("smartLists")
                 or data.get("items") or [])
        if not batch:
            # if the shape is unexpected, show it once so we can adapt
            if offset == 0:
                print("  (Unexpected response shape; raw keys: "
                      f"{list(data.keys())})")
            break
        lists.extend(batch)
        meta = data.get("_metadata", {})
        total = meta.get("total")
        offset += len(batch)
        if total is not None and offset >= total:
            break
        if len(batch) < 100:
            break
    return lists


def size_of(sl):
    """Best-effort: pull a count-like field from a smart list object."""
    for k in ("count", "size", "total", "peopleCount", "contactCount"):
        if k in sl and isinstance(sl[k], int):
            return sl[k]
    return None


def main():
    print("Fetching all FUB smart lists...\n")
    lists = list_all_smartlists()
    print(f"Total smart lists found: {len(lists)}\n")

    print("=== ALL SMART LISTS ===")
    for sl in sorted(lists, key=lambda s: (s.get("name") or "").lower()):
        size = size_of(sl)
        size_str = f"  [{size} people]" if size is not None else ""
        print(f"  id={sl.get('id')}  {sl.get('name')!r}{size_str}")

    claude = [sl for sl in lists
              if "claude" in (sl.get("name") or "").lower()]
    print(f"\n=== MATCHED 'Claude' LISTS: {len(claude)} ===")
    if not claude:
        print("  No FUB smart lists contain 'Claude' in the name.")
        print("  -> If you built them in Sierra, they will NOT show up here:")
        print("     Sierra's API has no smart-list endpoint, so they can only")
        print("     be managed in the Sierra web UI.")
        return

    for sl in sorted(claude, key=lambda s: (s.get("name") or "")):
        sid = sl.get("id")
        print(f"\n----- {sl.get('name')!r} (id={sid}) -----")
        r = get(f"/smartLists/{sid}")
        if r.status_code == 200:
            print(json.dumps(r.json(), indent=2)[:4000])
        else:
            print(f"  detail fetch failed: HTTP {r.status_code} {r.text[:200]}")


if __name__ == "__main__":
    main()
