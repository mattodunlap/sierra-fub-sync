"""
Pulls one specific FUB template's body so we can see the exact merge tag format.
Defaults to template id 256 (Matthew's "99 Sierra Test" template).
"""

import os
import sys
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
FUB_BASE = "https://api.followupboss.com/v1"

template_id = sys.argv[1] if len(sys.argv) > 1 else "256"

r = requests.get(
    f"{FUB_BASE}/templates/{template_id}",
    auth=(FUB_API_KEY, ""),
    timeout=15,
)
print(f"Status: {r.status_code}\n")
if r.status_code == 200:
    data = r.json()
    print(f"Name: {data.get('name')}")
    print(f"Subject: {data.get('subject')}")
    print(f"\n----- BODY -----")
    print(data.get("body", "(empty)"))
    print(f"----- END BODY -----\n")
    print(f"Available keys on response: {list(data.keys())}")
else:
    print(r.text)
