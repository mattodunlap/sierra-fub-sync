#!/usr/bin/env bash
# Deploy the Sierra->FUB URL populator to Fly.io.
#
# Run from a machine with flyctl installed and logged in to the `personal`
# Fly org (e.g. Matthew's laptop). Idempotent and safe to re-run. Deploys
# ONLY the `sierra-fub-sync` app defined in fly.toml — it never touches
# maittrix-engine, dunlap-automation, or any other app.
#
#   ./deploy_fly.sh
#
# Secrets (SIERRA_API_KEY, FUB_API_KEY) are read, in order, from: the current
# environment, ./.env, then ~/automation/.env (or /home/matthew/automation/.env).
# They are never printed. Optionally set FUB_SYSTEM / FUB_SYSTEM_KEY too.
set -euo pipefail
cd "$(dirname "$0")"

APP="$(grep -E '^[[:space:]]*app[[:space:]]*=' fly.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/')"
echo "==> Target Fly app (from fly.toml): $APP"
case "$APP" in
  maittrix-engine|dunlap-automation|"")
    echo "REFUSING: fly.toml app is '$APP'. This script only deploys the dedicated poller app." >&2
    exit 1 ;;
esac

if ! command -v flyctl >/dev/null 2>&1; then
  echo "flyctl not found. Install:  curl -L https://fly.io/install.sh | sh" >&2
  echo "then:  export PATH=\"\$HOME/.fly/bin:\$PATH\" && fly auth login" >&2
  exit 1
fi

if ! flyctl auth whoami >/dev/null 2>&1; then
  echo "Not logged in to Fly. Run:  fly auth login   (choose the 'personal' org)" >&2
  exit 1
fi
echo "==> Fly user: $(flyctl auth whoami 2>/dev/null || echo unknown)"

load_env_file() {
  local f="$1"; [ -f "$f" ] || return 0
  # shellcheck disable=SC1090
  set -a; . "$f"; set +a
}
have_keys() { [ -n "${SIERRA_API_KEY:-}" ] && [ -n "${FUB_API_KEY:-}" ]; }
have_keys || load_env_file "./.env"
have_keys || load_env_file "$HOME/automation/.env"
have_keys || load_env_file "/home/matthew/automation/.env"
if ! have_keys; then
  echo "SIERRA_API_KEY and/or FUB_API_KEY not found in env, ./.env, or automation/.env." >&2
  echo "Re-run with them set, e.g.:  SIERRA_API_KEY=... FUB_API_KEY=... ./deploy_fly.sh" >&2
  exit 1
fi

# Ensure the app exists (no-op if it does; harmless if a deploy-scoped token can't create it).
flyctl apps create "$APP" 2>/dev/null || true

echo "==> Staging Fly secrets on $APP"
SECRET_ARGS=(SIERRA_API_KEY="$SIERRA_API_KEY" FUB_API_KEY="$FUB_API_KEY")
[ -n "${FUB_SYSTEM:-}" ]     && SECRET_ARGS+=(FUB_SYSTEM="$FUB_SYSTEM")
[ -n "${FUB_SYSTEM_KEY:-}" ] && SECRET_ARGS+=(FUB_SYSTEM_KEY="$FUB_SYSTEM_KEY")
flyctl secrets set --app "$APP" --stage "${SECRET_ARGS[@]}" || true

echo "==> Deploying $APP"
flyctl deploy --app "$APP" --remote-only --ha=false

echo "==> Status:"
flyctl status --app "$APP" || true
echo "==> Recent logs (auto-stops after ~90s):"
timeout 90 flyctl logs --app "$APP" || true

cat <<EOF

Deploy complete. In the logs you should see, once a minute:
  url_populator: polling FUB every 60s, lookback 30 min
  pass: N recent FUB people, M need URLs   (only when there are new leads)

Manual cutover follow-ups (NOT done by this script):
  1. On the droplet:  systemctl --user disable --now new-lead-url-populate.timer
  2. Delete the old Render service in the Render dashboard.
  3. One-time URL repair for the WAF-blocked weeks:
       flyctl ssh console --app $APP -C 'python url_populator.py --once --since-minutes 30000'
EOF
