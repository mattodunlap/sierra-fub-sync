# MAITTRIX HANDOFF — finish the go-live (written 2026-07-04)

You are Claude running LOCALLY on Matthew's Windows PC (on his Tailscale network).
Your job: finish bringing MAITTRIX (the automation on the DigitalOcean droplet) fully live,
then verify. Matthew is on vacation — do everything yourself; only ask him if a password
prompt physically blocks you.

## Access
- Droplet: `ssh matthew@100.96.93.82` (Tailscale IP; hostname `maittrix`).
  This PC may already have an authorized key from the 7/2 session — try plain ssh first.
- Fallback: the droplet's web terminal at `http://100.96.93.82:7681` (basic-auth creds
  Matthew knows — same as the droplet web-terminal login set up 6/22).
- Do NOT use the Vegas Mint laptop (100.126.114.101) — retired from the stack.

## Current state (verified 7/4 morning via Sierra/FUB APIs)
- ✅ TEXTS work: timezone-staggered release live (Eastern 5am PT → West), ~52 sent by 10am PT.
- ✅ Responders run and honor NO-AI stages.
- ✅ Domain warmup ticking (2/hr overnight).
- ❌ EMAILS dead: the 4am Haiku email run (claude-email-producer.timer) is NOT enabled.
  ANTHROPIC_API_KEY was added to `~/automation/.env` on 7/3 and tested (works, Haiku).
- ❌ Suppression sync stale → 7/3 12:20pm batch emailed contacts tagged Bounced/bad email.
- ❌ Watchdogs + twice-daily health report timers not confirmed enabled.

## Do these, in order, on the droplet (as user matthew)
```
export XDG_RUNTIME_DIR=/run/user/$(id -u)
cd ~/automation
# 1. caps + non-Google-only while Gmail reputation heals
sed -i -e 's/^TEXT_DAILY_CAP=.*/TEXT_DAILY_CAP=250/' -e 's/^EMAIL_DAILY_CAP=.*/EMAIL_DAILY_CAP=500/' .env
grep -q '^EMAIL_NONGMAIL_ONLY=' .env || echo 'EMAIL_NONGMAIL_ONLY=1' >> .env
# 2. refresh do-not-send list NOW and keep it fresh
systemctl --user start sendgrid-suppression-sync.service
systemctl --user enable --now sendgrid-suppression-sync.timer
# 3. tonight's Haiku email run (500 non-Google, generated ~4am, delivered 4-8am)
systemctl --user enable --now claude-email-producer.timer
# 4. self-healing + reporting
systemctl --user enable --now chatbot-heartbeat-watchdog.timer daily-health-report.timer
# 5. verify
systemctl --user is-active sierra-gateway pending-text-worker pending-email-worker sierra-inbox-responder chatbot-loop
systemctl --user list-timers --no-pager | head -12
```
Unit names may differ slightly post-migration — if one is MISSING, find its equivalent in
`~/automation/systemd_units/` or `~/.config/systemd/user/` and enable that.

## The wrong-people bug (fix after go-live, same session)
Outbound producers ignore the stage/tag gate that the responder honors.
Proof: Glover Keetin (FUB person 12559, stage "Contact-Junk-NO AI TEXT OR CALLS") was
texted 6/29 and 7/2, replied 7/3 15:37 UTC, and the responder (correctly) stayed silent.
Fix: every outbound path — claude_email_producer.py, claude_text_producer.py,
work_text_lists.py, instant_lane.py — must skip leads whose FUB stage contains "Junk" or
"NO AI", or whose tags include Bounced / bad email / Bad Number. Reuse the existing gate
(send_decision.py / do_not_autorespond.py) rather than writing a new one.

## Hard rules
- Do NOT touch Sierra settings, password, or account config. Sierra is the source of truth.
- Do NOT run senders on two boxes (the droplet is the only sender).
- Do NOT re-enable Gmail-targeted bulk email; non-Google only until reputation recovers
  (see EMAIL_REPUTATION_REBUILD_PLAN in Google Drive).
- Replies are uncapped by design; list-initiated sends respect the 250/500 caps.

## Success = tell Matthew exactly this
1. All five services active; 2. claude-email-producer timer scheduled ~4am; 3. suppression
list refreshed at <timestamp>; 4. watchdogs + 8am/8pm health email armed; 5. filter fix
applied & one skipped-lead example logged. After that the system reports to HIM by email —
he should never need to paste anything again.
