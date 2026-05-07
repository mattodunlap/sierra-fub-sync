"""
Sierra -> FUB auto-login URL sync (polling version)

Runs on a schedule (e.g. every 30 min via GitHub Actions). Pulls all leads
from Sierra, constructs each lead's auto-login URL from the lead ID and
assigned agent, finds the matching FUB contact by email, and writes the
URL into a FUB custom field.

URL format:  https://{agent}.thevegasagent.com/?userid={lead_id}&sentfrom=auto

Required env vars:
    SIERRA_API_KEY               Sierra Interactive Direct API key
    FUB_API_KEY                  Follow Up Boss API key (account-owner key)
    FUB_CUSTOM_FIELD             FUB custom field API name (e.g. customSierraLoginURL)
    SIERRA_ORIGINATING_SYSTEM    (optional) Name to send as Sierra-OriginatingSystemName
"""

import os
import time
import requests
from pathlib import Path


def _load_env_file():
    """Load .env from the script's folder if it exists. No-op in production
    (GitHub Actions / Render) where env vars are already set."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Only set if not already in environment - real env vars take priority
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()

SIERRA_API_KEY = os.environ["SIERRA_API_KEY"]
FUB_API_KEY = os.environ["FUB_API_KEY"]
FUB_CUSTOM_FIELD = os.environ.get("FUB_CUSTOM_FIELD", "customSierraLoginURL")
SIERRA_ORIGINATING_SYSTEM = os.environ.get(
    "SIERRA_ORIGINATING_SYSTEM", "FUB-AutoLogin-Sync"
)

SIERRA_BASE = "https://api.sierrainteractivedev.com"
FUB_BASE = "https://api.followupboss.com/v1"

SIERRA_HEADERS = {
    "Sierra-ApiKey": SIERRA_API_KEY,
    "Sierra-OriginatingSystemName": SIERRA_ORIGINATING_SYSTEM,
}

# Per-agent subdomain map. Lookup is by lowercased first name.
# Matthew is the team leader, so his URL is the main team site (www).
AGENT_SUBDOMAINS = {
    "matthew": "www",
    "adrianne": "adrianne",
}
# Fallback subdomain when a lead's agent isn't in the map (or has no agent).
DEFAULT_SUBDOMAIN = "www"
SITE_DOMAIN = "thevegasagent.com"

# FUB rate limit is 1000 requests / 10 minutes per API key.
SLEEP_BETWEEN_WRITES = 0.7


def build_login_url(lead):
    """Construct the Sierra auto-login URL for a lead."""
    assigned = lead.get("assignedTo") or {}
    first_name = (assigned.get("agentUserFirstName") or "").lower().strip()
    subdomain = AGENT_SUBDOMAINS.get(first_name, DEFAULT_SUBDOMAIN)
    lead_id = lead.get("id")
    if not lead_id:
        return None
    return f"https://{subdomain}.{SITE_DOMAIN}/?userid={lead_id}&sentfrom=auto"


def get_sierra_leads(page=1, page_size=100):
    """Pull a page of leads from Sierra.

    NOTE: Sierra's API expects 'pageNumber', not 'page'. Using 'page' is
    silently ignored and always returns page 1.
    """
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params={"pageNumber": page, "pageSize": page_size},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", {}).get("leads", [])


def get_sierra_total_pages(page_size=100):
    """Find the total number of pages in /leads/find."""
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params={"pageNumber": 1, "pageSize": page_size},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", {}).get("totalPages", 1)


def sync_recent(num_recent_pages=2):
    """Incremental sync - only checks the last few pages of Sierra
    (where the newest leads live, since pagination is ascending by lead ID).
    Designed for high-frequency cron runs."""
    from datetime import datetime
    start = datetime.now()
    print(f"[{start:%H:%M:%S}] Starting INCREMENTAL sync (last {num_recent_pages} pages)")

    total_pages = get_sierra_total_pages()
    print(f"  Sierra reports {total_pages} total pages.")
    pages_to_check = list(range(max(1, total_pages - num_recent_pages + 1), total_pages + 1))
    print(f"  Checking pages: {pages_to_check}")

    updated = 0
    skipped_already_set = 0
    skipped_no_match = 0
    skipped_missing_data = 0

    for p in pages_to_check:
        leads = get_sierra_leads(page=p)
        for lead in leads:
            email = lead.get("email")
            login_url = build_login_url(lead)
            if not email or not login_url:
                skipped_missing_data += 1
                continue
            person = find_fub_person(email)
            if not person:
                skipped_no_match += 1
                continue
            if person.get(FUB_CUSTOM_FIELD) == login_url:
                skipped_already_set += 1
                continue
            if update_fub_person(person["id"], login_url, email_for_logs=email):
                updated += 1
            time.sleep(SLEEP_BETWEEN_WRITES)

    elapsed = (datetime.now() - start).total_seconds()
    print(
        f"\n=== Incremental sync done ===\n"
        f"Updated: {updated}\n"
        f"Already set: {skipped_already_set}\n"
        f"No FUB match: {skipped_no_match}\n"
        f"Missing data: {skipped_missing_data}\n"
        f"Elapsed: {int(elapsed//60)}m{int(elapsed%60)}s"
    )


def _fub_request_with_retry(method, url, **kwargs):
    """Make a FUB request with automatic 429 retry (up to 3 attempts)."""
    for attempt in range(3):
        r = requests.request(method, url, auth=(FUB_API_KEY, ""), timeout=30, **kwargs)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 15))
            print(f"  [429 rate limited, waiting {wait}s before retry {attempt+1}/3]")
            time.sleep(wait)
            continue
        return r
    return r  # final response, even if still 429


def find_fub_person(email):
    """Find a FUB person by email. Returns dict or None."""
    r = _fub_request_with_retry(
        "GET",
        f"{FUB_BASE}/people",
        params={"email": email, "fields": "allFields"},
    )
    if r.status_code != 200:
        print(f"  FUB find failed for {email}: HTTP {r.status_code} {r.text[:120]}")
        return None
    people = r.json().get("people", [])
    return people[0] if people else None


def update_fub_person(person_id, login_url, email_for_logs=""):
    """Push the Sierra login URL into the FUB custom field."""
    r = _fub_request_with_retry(
        "PUT",
        f"{FUB_BASE}/people/{person_id}",
        json={FUB_CUSTOM_FIELD: login_url},
    )
    if r.status_code != 200:
        print(f"  FUB update failed for {email_for_logs} (id={person_id}): "
              f"HTTP {r.status_code} {r.text[:200]}")
        return False
    return True


def sync(limit=None, dry_run=False):
    """
    Run the sync.

    Args:
        limit: Optional. If set, stop after processing this many leads.
        dry_run: If True, don't actually write to FUB - just print what would happen.
    """
    from datetime import datetime
    start = datetime.now()
    page = 1
    processed = 0
    updated = 0
    skipped_no_match = 0
    skipped_already_set = 0
    skipped_missing_data = 0

    print(f"[{start:%H:%M:%S}] Starting sync ({'DRY RUN' if dry_run else 'LIVE'})")

    while True:
        leads = get_sierra_leads(page=page)
        if not leads:
            break

        for lead in leads:
            email = lead.get("email")
            login_url = build_login_url(lead)

            if not email or not login_url:
                skipped_missing_data += 1
                continue

            person = find_fub_person(email)
            if not person:
                skipped_no_match += 1
                continue

            if person.get(FUB_CUSTOM_FIELD) == login_url:
                skipped_already_set += 1
            elif dry_run:
                print(f"[DRY RUN] would set {email} -> {login_url}")
                updated += 1
            else:
                if update_fub_person(person["id"], login_url, email_for_logs=email):
                    updated += 1
                time.sleep(SLEEP_BETWEEN_WRITES)

            processed += 1
            if limit and processed >= limit:
                _print_summary(updated, skipped_already_set, skipped_no_match,
                               skipped_missing_data, dry_run, start)
                return

        # End-of-page progress report
        elapsed = (datetime.now() - start).total_seconds()
        print(
            f"[{datetime.now():%H:%M:%S}] page {page} done. "
            f"updated={updated} matched={updated+skipped_already_set} "
            f"no_match={skipped_no_match} no_data={skipped_missing_data} "
            f"elapsed={int(elapsed//60)}m{int(elapsed%60)}s"
        )
        page += 1

    _print_summary(updated, skipped_already_set, skipped_no_match,
                   skipped_missing_data, dry_run, start)


def _print_summary(updated, already_set, no_match, missing, dry_run, start=None):
    label = "Would update" if dry_run else "Updated"
    line = (
        f"\n=== Summary ===\n"
        f"{label}: {updated}\n"
        f"Already set (skipped): {already_set}\n"
        f"No FUB match: {no_match}\n"
        f"Missing data (skipped): {missing}"
    )
    if start is not None:
        from datetime import datetime
        elapsed = (datetime.now() - start).total_seconds()
        line += f"\nTotal time: {int(elapsed//60)}m{int(elapsed%60)}s"
    print(line)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    if "--recent" in args:
        # Incremental mode - just check the last few pages where new leads live
        pages = 2
        for a in args:
            if a.startswith("--recent-pages="):
                pages = int(a.split("=", 1)[1])
        sync_recent(num_recent_pages=pages)
    else:
        limit = None
        for a in args:
            if a.startswith("--limit="):
                limit = int(a.split("=", 1)[1])
        sync(limit=limit, dry_run=dry_run)
