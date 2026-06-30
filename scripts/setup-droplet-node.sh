#!/usr/bin/env bash
#
# setup-droplet-node.sh
# Turn a fresh Ubuntu droplet into a permanent, always-on Claude Code node.
#
# Goal: after this runs, "popping in" from any device is two taps with no
# auth dance -- Tailscale SSH handles login by tailnet identity, and Claude
# stays authenticated across reboots so you log in to it only once.
#
# Usage (run as root on the NEW droplet):
#   sudo bash setup-droplet-node.sh <TAILSCALE_AUTHKEY> [HOSTNAME]
#
#   <TAILSCALE_AUTHKEY>  A reusable, NON-ephemeral auth key from
#                        https://login.tailscale.com/admin/settings/keys
#                        (non-ephemeral so the node is permanent).
#   [HOSTNAME]           Optional tailnet name for the node. Default: claude-node
#
set -euo pipefail

TS_AUTHKEY="${1:-${TS_AUTHKEY:-}}"
NODE_HOSTNAME="${2:-claude-node}"

log() { printf '\n>> %s\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root (sudo bash setup-droplet-node.sh ...)." >&2
  exit 1
fi

log "Updating system & installing base packages (git, tmux, curl)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl git tmux ca-certificates

log "Installing Node.js LTS (if missing)..."
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
  apt-get install -y nodejs
fi

log "Installing Claude Code CLI..."
npm install -g @anthropic-ai/claude-code

log "Installing Tailscale (if missing)..."
if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

log "Bringing up Tailscale with Tailscale SSH enabled..."
# --ssh lets you SSH in using your tailnet identity (no SSH keys/passwords).
# A non-ephemeral key keeps this a permanent node in your tailnet.
if [ -n "$TS_AUTHKEY" ]; then
  tailscale up --ssh --hostname "$NODE_HOSTNAME" --authkey "$TS_AUTHKEY"
else
  echo "No auth key passed -- starting interactive Tailscale login..."
  tailscale up --ssh --hostname "$NODE_HOSTNAME"
fi

TS_IP="$(tailscale ip -4 2>/dev/null | head -1 || true)"
log "Tailscale IPv4: ${TS_IP:-<pending>}"

log "Installing the persistent, self-restarting Claude session service..."
cat > /etc/systemd/system/claude-session.service <<'EOF'
[Unit]
Description=Persistent self-restarting Claude Code session in tmux
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
Type=forking
User=root
WorkingDirectory=/root
# login shell (-l) loads PATH so `claude` resolves; while-loop relaunches it if it ever exits
ExecStart=/bin/bash -lc "tmux new-session -d -s claude 'while true; do claude; sleep 2; done'"
ExecStop=/bin/bash -lc "tmux kill-session -t claude"
RemainAfterExit=yes
KillMode=none

[Install]
WantedBy=multi-user.target
EOF

log "Setting up persistent tmux logging..."
mkdir -p /root/claude-logs
cat > /root/.tmux.conf <<'EOF'
# auto-log every pane to /root/claude-logs/<session>.log
set-hook -g session-created 'pipe-pane -o "cat >> /root/claude-logs/#{session_name}.log"'
set-hook -g pane-focus-in   'pipe-pane -o "cat >> /root/claude-logs/#{session_name}.log"'
EOF

log "Adding the 'cc' shortcut (attach-or-create the claude session)..."
if ! grep -q "alias cc=" /root/.bashrc 2>/dev/null; then
  echo "alias cc='tmux attach -t claude || tmux new -s claude'" >> /root/.bashrc
fi

log "Enabling and starting the service..."
systemctl daemon-reload
systemctl enable --now claude-session.service

cat <<EOF

==================================================================
 Node is up and the Claude session is running & self-restarting.

 ONE-TIME: authenticate Claude once, then never again:
     ssh root@${NODE_HOSTNAME}        # Tailscale SSH, no keys needed
     cc                               # attach to the live session
     # complete the Claude login prompt inside the session

 After that login, credentials persist in ~/.claude and auto-refresh,
 so reboots and self-restarts keep you logged in.

 EVERY TIME AFTER:
     ssh root@${NODE_HOSTNAME}
     cc                               # straight into the live Claude

 Tailscale IPv4: ${TS_IP:-<run: tailscale ip -4>}
==================================================================
EOF
