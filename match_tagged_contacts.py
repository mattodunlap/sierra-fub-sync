"""
Find FUB contacts tagged with a specific tag, look each up in Sierra by
email then phone, and write the auto-login URL into the custom field.

Usage:
    python match_tagged_contacts.py "Needs Sierra URL"
    python match_tagged_contacts.py "Needs Sierra URL" --write

By default DRY RUN. Pass --write to actually push updates.
"""

import os
import re
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
from sierra_fub_sync import (  # noqa
    SIERRA_HEADERS, SIERRA_BASE, FUB_BASE, FUB_API_KEY, FUB_CUSTOM_FIELD,
    build_login_url, _fub_request_with_retry, update_fub_person,
)

SLEEP_BETWEEN_WRITES = 0.7


def normalize_phone(phone):
    """Strip all non-digits. Returns last 10 chars (US format) for comparison."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    return digits[-10:] if len(digits) >= 10 else digits


def fetch_fub_contacts_with_tag(tag):
    """Walk FUB people filtered by tag, paginated via nextLink."""
    contacts = []
    # FUB tags filter expects URL-encoded tag in 'tags' param
    next_url = f"{FUB_BASE}/people?limit=100&tags={requests.utils.quote(tag)}&fields=allFields"
    while next_url:
        r = requests.get(next_url, auth=(FUB_API_KEY, ""), timeout=30)
        if r.status_code != 200:
            print(f"  ERROR fetching FUB people: {r.status_code} {r.text[:200]}")
            break
        data = r.json()
        people = data.get("people", [])
        contacts.extend(people)
        meta = data.get("_metadata", {}) or data.get("metadata", {})
        next_url = meta.get("nextLink") or meta.get("next")
    return contacts


def find_sierra_by_email(email):
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
    return None


def find_sierra_by_phone(phone):
    if not phone:
        return None
    digits = normalize_phone(phone)
    if len(digits) < 10:
        return None
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params={"phone": digits, "pageNumber": 1, "pageSize": 5},
        timeout=15,
    )
    if r.status_code != 200:
        return None
    leads = r.json().get("data", {}).get("leads", [])
    for lead in leads:
        for p_field in ("phone", "phoneNumber", "mobilePhone", "homePhone"):
            lead_phone = normalize_phone(lead.get(p_field, ""))
            if lead_phone and lead_phone == digits:
                return lead
    # If only one lead returned, accept it
    if len(leads) == 1:
        return leads[0]
    return None


def best_phone_for_contact(person):
    """Return the first phone number on a FUB contact."""
    phones = person.get("phones") or []
    for p in phones:
        v = p.get("value") if isinstance(p, dict) else p
        if v:
            return v
    # Sometimes FUB returns a top-level phone field
    return person.get("phone") or ""


def best_email_for_contact(person):
    emails = person.get("emails") or []
    for e in emails:
        v = e.get("value") if isinstance(e, dict) else e
        if v:
            return v
    return person.get("email") or ""


GENERIC_FALLBACK_URL = "https://www.thevegasagent.com/?sentfrom=auto"


def main():
    if len(sys.argv) < 2:
        print('Usage: python match_tagged_contacts.py "Tag Name" [--write] [--fallback-generic]')
        sys.exit(1)
    tag = sys.argv[1]
    write_mode = "--write" in sys.argv
    fallback_generic = "--fallback-generic" in sys.argv

    print(f"Mode: {'LIVE WRITE' if write_mode else 'DRY RUN'}")
    print(f"Searching FUB for contacts tagged: {tag!r}")
    if fallback_generic:
        print(f"Fallback-generic ON: unmatched contacts get {GENERIC_FALLBACK_URL}")
    print()

    contacts = fetch_fub_contacts_with_tag(tag)
    print(f"Found {len(contacts)} FUB contacts with that tag.\n")

    matched_email = 0
    matched_phone = 0
    no_match = 0
    fallback_used = 0
    already_set = 0
    updated = 0
    no_email_no_phone = 0
    write_failed = 0
    unmatched_log = []

    for i, person in enumerate(contacts, 1):
        email = best_email_for_contact(person)
        phone = best_phone_for_contact(person)
        person_id = person.get("id")
        name = f"{person.get('firstName', '')} {person.get('lastName', '')}".strip() or "(no name)"

        if not email and not phone:
            no_email_no_phone += 1
            unmatched_log.append(f"id={person_id} {name!r} - no email or phone")
            continue

        # Try Sierra match by email first, then by phone
        lead = None
        match_method = None
        if email:
            lead = find_sierra_by_email(email)
            if lead:
                match_method = "email"
                matched_email += 1
        if not lead and phone:
            lead = find_sierra_by_phone(phone)
            if lead:
                match_method = "phone"
                matched_phone += 1

        if not lead:
            no_match += 1
            unmatched_log.append(f"id={person_id} {name!r} email={email} phone={phone}")
            if not fallback_generic:
                if i % 50 == 0:
                    print(f"  [{i}/{len(contacts)}] processed, unmatched={no_match}")
                continue
            # Fall through to fallback URL handling below
            login_url = GENERIC_FALLBACK_URL
            fallback_used += 1
        else:
            login_url = build_login_url(lead)
            if not login_url:
                no_match += 1
                unmatched_log.append(f"id={person_id} {name!r} - couldn't build URL from lead {lead.get('id')}")
                continue

        if person.get(FUB_CUSTOM_FIELD) == login_url:
            already_set += 1
            continue

        if write_mode:
            ok = update_fub_person(person_id, login_url, email_for_logs=email)
            if ok:
                updated += 1
                time.sleep(SLEEP_BETWEEN_WRITES)
            else:
                write_failed += 1
        else:
            print(f"  [DRY] {name!r} -> matched by {match_method}, would set: {login_url}")

        if i % 50 == 0:
            label = "Updated" if write_mode else "Would update"
            print(f"  [{i}/{len(contacts)}] {label.lower()}={updated}, "
                  f"matched_email={matched_email}, matched_phone={matched_phone}, "
                  f"no_match={no_match}")

    # Final summary - print AND write to file
    summary_lines = [
        "=" * 60,
        f"SUMMARY  ({'LIVE' if write_mode else 'DRY RUN'})",
        f"Tag: {tag!r}",
        f"Run timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        f"  Total tagged contacts: {len(contacts)}",
        f"  Matched by email:      {matched_email}",
        f"  Matched by phone:      {matched_phone}",
        f"  Generic fallback used: {fallback_used}",
        f"  Already had URL:       {already_set}",
        f"  No email or phone:     {no_email_no_phone}",
        f"  Could not match:       {no_match}",
    ]
    if write_mode:
        summary_lines.append(f"  Successfully updated:  {updated}")
        summary_lines.append(f"  Write failed:          {write_failed}")
    else:
        summary_lines.append(f"  Would update:          {updated}")
        summary_lines.append("")
        summary_lines.append("  This was a dry run. Re-run with --write to actually push.")

    summary_text = "\n".join(summary_lines)
    print("\n" + summary_text)

    # Save summary so Claude can read the result file directly
    summary_path = Path(__file__).parent / "match_summary.txt"
    summary_path.write_text(summary_text)
    print(f"\n  Summary saved to: {summary_path}")

    if unmatched_log:
        log_path = Path(__file__).parent / "unmatched_contacts.txt"
        log_path.write_text("\n".join(unmatched_log))
        print(f"  Unmatched contacts logged to: {log_path}")


if __name__ == "__main__":
    main()
