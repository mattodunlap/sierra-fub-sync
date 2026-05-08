"""
Scan all FUB contacts and report duplicates by email and phone.
Helps clean up imports where the same person ended up as multiple contacts.

Read-only - identifies dupes only, makes no changes.
Output is written to fub_duplicates.txt with grouped dupe sets.
"""

import os
import re
import requests
from collections import defaultdict
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
FUB_BASE = "https://api.followupboss.com/v1"


def normalize_phone(phone):
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    return digits[-10:] if len(digits) >= 10 else digits


def first_email(person):
    emails = person.get("emails") or []
    for e in emails:
        v = e.get("value") if isinstance(e, dict) else e
        if v:
            return v.lower().strip()
    return ""


def first_phone(person):
    phones = person.get("phones") or []
    for p in phones:
        v = p.get("value") if isinstance(p, dict) else p
        if v:
            return normalize_phone(v)
    return ""


def main():
    print("Walking all FUB contacts (this can take a few minutes)...\n")
    by_email = defaultdict(list)
    by_phone = defaultdict(list)
    total = 0
    next_url = f"{FUB_BASE}/people?limit=100&fields=allFields"
    while next_url:
        r = requests.get(next_url, auth=(FUB_API_KEY, ""), timeout=30)
        if r.status_code != 200:
            print(f"FUB returned {r.status_code}: {r.text[:200]}")
            break
        data = r.json()
        people = data.get("people", [])
        for p in people:
            total += 1
            email = first_email(p)
            phone = first_phone(p)
            if email:
                by_email[email].append(p)
            if phone:
                by_phone[phone].append(p)
        if total % 1000 == 0:
            print(f"  ... {total} contacts walked")
        meta = data.get("_metadata", {}) or data.get("metadata", {})
        next_url = meta.get("nextLink") or meta.get("next")

    # Find duplicates
    email_dupes = {k: v for k, v in by_email.items() if len(v) > 1}
    phone_dupes = {k: v for k, v in by_phone.items() if len(v) > 1}

    print(f"\nTotal FUB contacts: {total}")
    print(f"Distinct emails: {len(by_email)}, dupes (same email on >1 contact): {len(email_dupes)}")
    print(f"Distinct phones: {len(by_phone)}, dupes (same phone on >1 contact): {len(phone_dupes)}")

    out_path = Path(__file__).parent / "fub_duplicates.txt"
    lines = ["FUB DUPLICATES REPORT"]
    lines.append(f"Total contacts: {total}")
    lines.append(f"Email duplicate sets: {len(email_dupes)}")
    lines.append(f"Phone duplicate sets: {len(phone_dupes)}")
    lines.append("")
    lines.append("=" * 60)
    lines.append("DUPLICATES BY EMAIL")
    lines.append("=" * 60)
    for email, group in sorted(email_dupes.items()):
        lines.append(f"\n{email!r}  ({len(group)} contacts)")
        for p in group:
            name = f"{p.get('firstName','')} {p.get('lastName','')}".strip()
            lines.append(f"  id={p.get('id')}  {name!r}  created={p.get('created')}")
    lines.append("")
    lines.append("=" * 60)
    lines.append("DUPLICATES BY PHONE")
    lines.append("=" * 60)
    for phone, group in sorted(phone_dupes.items()):
        lines.append(f"\nphone={phone}  ({len(group)} contacts)")
        for p in group:
            name = f"{p.get('firstName','')} {p.get('lastName','')}".strip()
            lines.append(f"  id={p.get('id')}  {name!r}  created={p.get('created')}")

    out_path.write_text("\n".join(lines))
    print(f"\nFull report saved to: {out_path}")


if __name__ == "__main__":
    main()
