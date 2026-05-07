"""
Pre-flight check for the Sierra <-> FUB sync.

Reads .env in the same folder and confirms:
  1. Sierra API key works (lists 1 lead)
  2. The auto-login URL field exists and probes common names if SIERRA_LOGIN_FIELD misses
  3. FUB API key works
  4. The FUB custom field exists with the name you provided

Run:
    python test_connections.py

This script makes ZERO writes. Safe to run any number of times.
"""

import os
import sys
import requests
from pathlib import Path


def load_env():
    """Tiny .env loader so we don't need python-dotenv."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("FAIL: .env file not found in project folder.")
        sys.exit(1)
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def green(s): return f"\033[92m{s}\033[0m"
def red(s): return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"


def sierra_headers():
    return {
        "Sierra-ApiKey": os.environ["SIERRA_API_KEY"],
        "Sierra-OriginatingSystemName": os.environ.get(
            "SIERRA_ORIGINATING_SYSTEM", "FUB-AutoLogin-Sync"
        ),
    }


def test_sierra():
    print("\n[1/4] Testing Sierra API key...")
    r = requests.get(
        "https://api.sierrainteractivedev.com/leads/find",
        headers=sierra_headers(),
        params={"page": 1, "pageSize": 1},
        timeout=15,
    )
    if r.status_code != 200:
        print(red(f"  FAIL: Sierra returned {r.status_code}: {r.text[:200]}"))
        return None
    leads = r.json().get("data", {}).get("leads", [])
    if not leads:
        print(yellow("  WARN: Sierra responded OK but returned no leads."))
        return None
    lead = leads[0]
    print(green(f"  OK: pulled lead id={lead.get('id')} email={lead.get('email')}"))
    return lead


def test_sierra_field(lead):
    print("\n[2/4] Locating the auto-login URL field on a lead...")
    if not lead:
        print(yellow("  SKIP: no sample lead from step 1"))
        return None
    # /leads/find returns full lead detail in the listing, so we can inspect directly
    detail = lead

    configured = os.environ.get("SIERRA_LOGIN_FIELD", "siteLoginUrl")
    if detail.get(configured):
        url = detail[configured]
        print(green(f"  OK: field '{configured}' contains: {url[:80]}..."))
        return configured

    # Probe likely names if the configured one is empty
    print(yellow(f"  '{configured}' was empty. Probing other common names..."))
    candidates = [
        "siteLoginUrl", "autoLoginUrl", "loginUrl", "autologinUrl",
        "siteAutoLoginUrl", "autoLoginLink", "loginLink", "siteAccessUrl",
    ]
    for c in candidates:
        if c == configured:
            continue
        if detail.get(c):
            print(green(f"  FOUND: try setting SIERRA_LOGIN_FIELD={c}"))
            print(green(f"    value: {detail[c][:80]}..."))
            return c

    # Fallback: list any field containing 'login' or 'url' to help us spot it
    print(yellow("  No common names matched. Fields containing 'login' or 'url':"))
    matches = {k: v for k, v in detail.items()
               if isinstance(v, str) and ("login" in k.lower() or "url" in k.lower())}
    if matches:
        for k, v in matches.items():
            print(f"    {k}: {str(v)[:80]}")
    else:
        print(red("  No login/url-shaped fields found at all. Email Sierra support."))
    return None


def test_fub():
    print("\n[3/4] Testing FUB API key...")
    r = requests.get(
        "https://api.followupboss.com/v1/identity",
        auth=(os.environ["FUB_API_KEY"], ""),
        timeout=15,
    )
    if r.status_code != 200:
        print(red(f"  FAIL: FUB returned {r.status_code}: {r.text[:200]}"))
        return False
    me = r.json()
    print(green(f"  OK: authenticated as {me.get('name', '?')} ({me.get('email', '?')})"))
    return True


def test_fub_field():
    print("\n[4/4] Confirming FUB custom field exists...")
    target = os.environ.get("FUB_CUSTOM_FIELD", "")
    r = requests.get(
        "https://api.followupboss.com/v1/customFields",
        auth=(os.environ["FUB_API_KEY"], ""),
        timeout=15,
    )
    if r.status_code != 200:
        print(red(f"  FAIL: FUB customFields returned {r.status_code}"))
        return False
    fields = r.json().get("customfields", []) or r.json().get("customFields", [])
    names = [f.get("name") for f in fields]
    if target in names:
        match = next(f for f in fields if f.get("name") == target)
        print(green(f"  OK: '{target}' exists (label: {match.get('label')})"))
        return True
    print(red(f"  FAIL: no custom field named '{target}'"))
    print("  Available custom fields:")
    for f in fields:
        print(f"    {f.get('name'):40} (label: {f.get('label')})")
    return False


if __name__ == "__main__":
    load_env()
    lead = test_sierra()
    found_field = test_sierra_field(lead)
    fub_ok = test_fub()
    fub_field_ok = test_fub_field()
    print("\n" + "=" * 60)
    if lead and found_field and fub_ok and fub_field_ok:
        print(green("ALL CHECKS PASSED. Safe to run the real sync."))
    else:
        print(yellow("Some checks need attention. Fix above, then re-run."))
