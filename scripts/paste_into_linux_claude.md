Please export all my completed Claude Code sessions from this machine
(`~/.claude/projects/`) into readable markdown, then commit and push
them to the `sierra-fub-sync` repo on the
`claude/threads-markdown-export-4liRc` branch.

Steps:

1. Find a working directory. If `~/sierra-fub-sync` already exists as a
   clone, use it. Otherwise clone it fresh:
   ```
   git clone https://github.com/mattodunlap/sierra-fub-sync.git ~/sierra-fub-sync
   ```
   Either way: `cd ~/sierra-fub-sync && git fetch origin && git checkout claude/threads-markdown-export-4liRc && git pull`

2. Run the export script that already exists in the repo:
   ```
   python3 scripts/export_claude_threads.py
   ```
   (No filter argument — I want **every** project's sessions, not just
   one. The script writes one markdown file per session into
   `claude-threads/<encoded-project-path>/<session-uuid>.md` and a top-level
   `claude-threads/README.md` index.)

3. Commit and push:
   ```
   git add claude-threads/
   git commit -m "Export local Linux Claude Code threads"
   git push
   ```

4. After the push, tell me:
   - How many sessions were exported in total
   - The list of project directories that had sessions
   - The total size on disk of `claude-threads/`
   - The PR URL (PR #2 — it should pick up the new commit automatically)

If anything goes wrong (script not found after `git pull`, no sessions
in `~/.claude/projects/`, push rejected, etc.) — stop and tell me what
you saw rather than guessing a fix.

Commit everything no matter how large — no size cap, I want the
complete transcripts. If git push complains about large files, switch
to `git lfs` (install it, `git lfs install`, `git lfs track
"claude-threads/**/*.md"`, then re-add and commit) and push again.
