# User CLAUDE.md — Matthew Dunlap

Auto-loaded by Claude Code at the start of every session on this machine.
Lives at `~/.claude/CLAUDE.md`. Applies to every project unless the
project's own `CLAUDE.md` overrides it.

---

## Who I am

I'm **Matthew Dunlap** (matthew@teamdunlaprealty.com), team leader of
Dunlap Realty in Las Vegas. I'm not a professional programmer — I run
the team and use code/automation to make the business move faster.
Explain what you're doing in plain English, but **always show me the
actual commands and file paths** so I can keep records and re-run things
later.

## My machines

| Machine | Where Claude Code runs | What lives there |
|---|---|---|
| Linux desktop | local CLI, often inside `tmux` | `~/automation/` (FUB texts, systemd timers), `~/sierra-fub-sync/` (Sierra↔FUB bridge) |
| Windows box | local CLI | `C:\Users\matto\OneDrive\Documents\Claude\Projects\Auto Login Link From Sierra To FUB\` (same sierra-fub-sync repo) |
| Cloud (claude.ai/code) | ephemeral containers, one per session | sessions cloned fresh each time, torn down on idle |

**Critical implication:** sessions in the cloud don't share state with
each other or with my local boxes. Per-project `CLAUDE.md` files
(committed to the repo) are the only thing that survives across sessions.
**When I tell you something new — about my CRMs, my workflow, an API
gotcha, anything — append it to the project's `CLAUDE.md` and commit it.**
That is the mechanism that prevents the next session from starting blind.

## My stack

- **Sierra Interactive** — IDX/lead-generation, source of truth for leads.
- **Follow Up Boss (FUB)** — working CRM, daily contact/email/SMS work.
- **Render** — hosts the webhook for the sierra-fub-sync project (free tier, cold-starts).
- **GitHub Actions** — runs scheduled syncs (cron jobs) for free.
- **Python** for nearly all automation. `requests`, `fastapi`. No fancy frameworks.
- **Bash + systemd** on the Linux box for scheduled jobs that aren't on GitHub Actions.

When in doubt about an API quirk for Sierra or FUB, check
`~/sierra-fub-sync/CLAUDE.md` first — most of it has been figured out
the hard way already.

## How I want you to work

- **Be honest about what you can and can't do.** If you can't reach
  another machine, say so. If you can't access old session transcripts,
  say so. Don't fake it. I'd rather hear "I can't" and have a workaround
  than chase ghosts.
- **No "starting from scratch" answers.** If you genuinely don't know
  something, ask. If a previous session figured something out and it's
  not in a CLAUDE.md, ask me where it lives so we can write it down.
- **Default to dry-run for anything that writes** to Sierra, FUB,
  GitHub, or my filesystem outside the repo. Show me what you'd do, then
  ask before doing it. The exception is the obvious safe stuff (reads,
  greps, status checks, building/testing).
- **Use `tmux` on this Linux box** so your session survives my SSH/phone
  disconnects. If I start a session and you notice you're not in `tmux`,
  flag it — don't just silently roll the dice.
- **Commit with a clear message** so I can scroll the git log later and
  understand what changed and why. The "why" matters more than the "what."

## When making changes

- Make a new branch named `claude/<short-description>` for non-trivial
  work, not `main` directly. Open a draft PR so I can see the diff in
  GitHub on my phone.
- Run the actual tests / probe scripts before claiming something works.
  If the project has no tests, say so explicitly — don't pretend.
- Don't commit `.env` files or anything that looks like a secret. The
  `.gitignore` in my repos already covers this; respect it.

## Don't

- Don't push to `main` without my say-so.
- Don't run destructive ops (`rm -rf`, `git reset --hard`, `git push
  --force`, dropping FUB contacts, deleting Sierra leads) without
  explicit confirmation in the current conversation.
- Don't invent answers about Sierra or FUB API behavior. If it's not in
  the project's `CLAUDE.md` and not in the codebase, probe with a
  read-only script (there are several `probe_*.py` examples in
  sierra-fub-sync) and tell me what you found.
