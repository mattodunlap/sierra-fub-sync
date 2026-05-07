"""
Debug: pull page 2 from Sierra, print what we'd compute for each lead vs
what FUB actually returns. Lets us see whether the script's "already set"
verdict is correct.
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
from sierra_fub_sync import (  # noqa
    SIERRA_BASE, SIERRA_HEADERS, FUB_BASE, FUB_API_KEY, FUB_CUSTOM_FIELD,
    build_login_url,
)


def get_page(page_num):
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params={"pageNumber": page_num, "pageSize": 100},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", {}).get("leads", [])


def fub_lookup(email):
    r = requests.get(
        f"{FUB_BASE}/people",
        auth=(FUB_API_KEY, ""),
        params={"email": email, "fields": "allFields"},
        timeout=30,
    )
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    people = r.json().get("people", [])
    if not people:
        return None, "no match in FUB"
    return people[0], None


def main():
    print("Pulling Sierra page 2...")
    leads = get_page(2)
    print(f"Got {len(leads)} leads.\n")

    # Diagnostic counters
    already_set_correctly = 0
    already_set_wrongly = 0  # script would skip but FUB has different/no value
    needs_write = 0
    no_match = 0

    print(f"{'#':<4} {'EMAIL':<35} {'FUB VALUE':<60} {'OUR URL':<60} VERDICT")
    print("-" * 200)

    for i, lead in enumerate(leads[:20]):  # only show first 20 in detail
        email = lead.get("email") or ""
        our_url = build_login_url(lead) or ""
        person, err = fub_lookup(email)
        if not person:
            verdict = f"NO MATCH ({err})"
            no_match += 1
            fub_val = "-"
        else:
            fub_val = person.get(FUB_CUSTOM_FIELD)
            if fub_val == our_url:
                if fub_val:
                    verdict = "OK (already set, matches)"
                    already_set_correctly += 1
                else:
                    verdict = "BUG! (both None - script would skip)"
                    already_set_wrongly += 1
            else:
                verdict = "NEEDS WRITE"
                needs_write += 1
        # truncate for display
        fub_display = (str(fub_val)[:58] + "..") if fub_val and len(str(fub_val)) > 58 else str(fub_val)
        our_display = (our_url[:58] + "..") if len(our_url) > 58 else our_url
        print(f"{i+1:<4} {email[:33]:<35} {fub_display:<60} {our_display:<60} {verdict}")

    # Quick scan of remaining leads (no per-row output)
    for lead in leads[20:]:
        email = lead.get("email") or ""
        our_url = build_login_url(lead) or ""
        person, _ = fub_lookup(email)
        if not person:
            no_match += 1
        else:
            fub_val = person.get(FUB_CUSTOM_FIELD)
            if fub_val == our_url:
                if fub_val:
                    already_set_correctly += 1
                else:
                    already_set_wrongly += 1
            else:
                needs_write += 1

    print("\n" + "=" * 50)
    print("Summary across all 100 leads on page 2:")
    print(f"  Already set correctly (URL matches): {already_set_correctly}")
    print(f"  BUG - both None (script wrongly skips): {already_set_wrongly}")
    print(f"  Needs write: {needs_write}")
    print(f"  No FUB match: {no_match}")


if __name__ == "__main__":
    main()
