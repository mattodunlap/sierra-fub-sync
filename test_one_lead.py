"""
Test the full sync flow on a single lead before running the big backfill.

Pass an email address as the argument:
    python test_one_lead.py someone@example.com

This script:
  1. Looks up that email in Sierra
  2. Constructs the auto-login URL
  3. Looks up that email in FUB
  4. In dry-run mode by default - prints what it WOULD do
  5. With --write flag, actually updates the FUB record

Examples:
    python test_one_lead.py matthew@teamdunlaprealty.com
    python test_one_lead.py matthew@teamdunlaprealty.com --write
"""

import sys
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

# Import shared logic from the main sync script
sys.path.insert(0, str(Path(__file__).parent))
from sierra_fub_sync import (  # noqa
    SIERRA_HEADERS, SIERRA_BASE, FUB_BASE, FUB_API_KEY, FUB_CUSTOM_FIELD,
    build_login_url, find_fub_person, update_fub_person,
)


def find_sierra_lead_by_email(email):
    """Search Sierra for a lead by email."""
    r = requests.get(
        f"{SIERRA_BASE}/leads/find",
        headers=SIERRA_HEADERS,
        params={"email": email, "pageNumber": 1, "pageSize": 5},
        timeout=15,
    )
    r.raise_for_status()
    leads = r.json().get("data", {}).get("leads", [])
    for lead in leads:
        if (lead.get("email") or "").lower() == email.lower():
            return lead
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_one_lead.py <email> [--write]")
        sys.exit(1)
    email = sys.argv[1]
    write_mode = "--write" in sys.argv

    print(f"\n--- Testing on {email} ---\n")

    print("Step 1: Looking up in Sierra...")
    lead = find_sierra_lead_by_email(email)
    if not lead:
        print(f"  No Sierra lead found with email {email}")
        sys.exit(1)
    assigned = lead.get("assignedTo") or {}
    print(f"  Found Sierra lead id={lead.get('id')} name={lead.get('firstName')} {lead.get('lastName')}")
    print(f"  Assigned to: {assigned.get('agentUserFirstName')} {assigned.get('agentUserLastName')}")

    print("\nStep 2: Constructing auto-login URL...")
    login_url = build_login_url(lead)
    print(f"  URL: {login_url}")

    print("\nStep 3: Looking up in FUB...")
    person = find_fub_person(email)
    if not person:
        print(f"  No FUB contact found with email {email}")
        sys.exit(1)
    current_value = person.get(FUB_CUSTOM_FIELD)
    print(f"  Found FUB person id={person.get('id')} name={person.get('firstName')} {person.get('lastName')}")
    print(f"  Current {FUB_CUSTOM_FIELD}: {current_value!r}")

    print("\nStep 4: Update FUB?")
    if current_value == login_url:
        print("  No change needed - field already matches.")
        return

    if not write_mode:
        print(f"  DRY RUN - would set {FUB_CUSTOM_FIELD} to:")
        print(f"    {login_url}")
        print("\n  Re-run with --write to actually update FUB.")
        return

    print(f"  Writing to FUB...")
    ok = update_fub_person(person["id"], login_url, email_for_logs=email)
    if ok:
        print("  SUCCESS - FUB record updated.")
        print("\n  Now go to FUB, open this contact, and verify the 'Sierra Login URL'")
        print("  custom field shows the URL above. Then click it to verify it logs you in.")
    else:
        print("  FAILED to update FUB.")


if __name__ == "__main__":
    main()
