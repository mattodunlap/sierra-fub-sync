"""
Probes a bunch of FUB endpoint names to find which ones work for templates.
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
FUB_BASE = "https://api.followupboss.com/v1"

candidates = [
    # Email templates
    "templates",
    "emailTemplates",
    "emailtemplates",
    # SMS templates
    "textMessageTemplates",
    "textmessagetemplates",
    "textTemplates",
    "texttemplates",
    "smsTemplates",
    "smstemplates",
    "actionPlans",
    "actionplans",
]

print(f"{'ENDPOINT':<30} {'STATUS':<10} {'KEYS / ERROR'}")
print("-" * 100)

for ep in candidates:
    url = f"{FUB_BASE}/{ep}?limit=1"
    r = requests.get(url, auth=(FUB_API_KEY, ""), timeout=15)
    status = r.status_code
    if status == 200:
        try:
            data = r.json()
            keys = list(data.keys())
            # Find the items array key
            items_key = None
            for k in keys:
                if isinstance(data.get(k), list):
                    items_key = k
                    break
            if items_key:
                count = len(data[items_key])
                info = f"keys={keys}, items in '{items_key}': {count}"
            else:
                info = f"keys={keys}"
        except Exception as e:
            info = f"OK 200 but parse failed: {e}"
    else:
        info = r.text[:120]
    print(f"{ep:<30} {status:<10} {info}")
