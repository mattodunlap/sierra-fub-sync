"""
Sends a fake webhook POST to our deployed Render endpoint to verify it
processes a Sierra webhook payload correctly. Uses Leilani's lead id (2443063)
since we know her record well.
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

WEBHOOK_URL = "https://sierra-fub-sync.onrender.com/sierra-webhook"
WEBHOOK_SECRET = "a3f8e1b2-d4c5-4e6a-b7c8-9d0e1f2a3b4c"
TEST_LEAD_ID = 2443063  # Leilani Johnson - a known good lead

print(f"Sending test POST to: {WEBHOOK_URL}")
print(f"Payload: {{leadId: {TEST_LEAD_ID}}}")
print(f"Note: first request after a quiet period takes ~30s for Render cold start.\n")

r = requests.post(
    WEBHOOK_URL,
    headers={
        "Content-Type": "application/json",
        "X-Webhook-Secret": WEBHOOK_SECRET,
    },
    json={"leadId": TEST_LEAD_ID},
    timeout=90,
)

print(f"Status: {r.status_code}")
print(f"Response: {r.text}")

if r.status_code == 200:
    print("\nSUCCESS - webhook is processing payloads correctly.")
elif r.status_code == 401:
    print("\nFAIL - X-Webhook-Secret mismatch. Check Render env var.")
else:
    print(f"\nFAIL - unexpected status. Read response above.")
