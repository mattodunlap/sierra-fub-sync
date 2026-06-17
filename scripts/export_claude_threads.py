#!/usr/bin/env python3
"""
Export Claude Code session transcripts to readable markdown.

Run this on the machine where the sessions actually happened (e.g. the
local Linux box). Each .jsonl session file in
  ~/.claude/projects/<encoded-project-path>/
becomes one markdown file in
  <repo>/claude-threads/<encoded-project-path>/<session-uuid>.md

After running, commit + push the claude-threads/ folder so other machines
(and other Claude Code sessions) can read your history.

Usage:
    python3 scripts/export_claude_threads.py             # exports ALL projects
    python3 scripts/export_claude_threads.py automation  # only projects matching 'automation'

The substring filter matches against the encoded project directory name,
e.g. '-home-mattodunlap-automation'.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
OUT_ROOT = Path(__file__).resolve().parent.parent / "claude-threads"


def extract_text(content):
    """Pull human-readable text out of a message.content value.

    Claude Code stores .message.content as either a string (older format)
    or a list of typed blocks (text/tool_use/tool_result/thinking/image)."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            parts.append(block.get("text", ""))
        elif btype == "thinking":
            text = block.get("thinking") or block.get("text") or ""
            if text:
                parts.append(f"<details><summary>thinking</summary>\n\n{text}\n\n</details>")
        elif btype == "tool_use":
            name = block.get("name", "?")
            inp = block.get("input", {})
            try:
                inp_str = json.dumps(inp, indent=2, default=str)
            except Exception:
                inp_str = str(inp)
            parts.append(f"**tool_use: `{name}`**\n```json\n{inp_str}\n```")
        elif btype == "tool_result":
            tc = block.get("content")
            tc_text = extract_text(tc) if not isinstance(tc, str) else tc
            if tc_text:
                parts.append(f"**tool_result**\n```\n{tc_text}\n```")
        elif btype == "image":
            parts.append("*(image omitted)*")
    return "\n\n".join(p for p in parts if p)


def session_to_markdown(jsonl_path: Path) -> tuple[str, dict]:
    """Convert one session .jsonl to a markdown string + metadata summary."""
    lines = jsonl_path.read_text(errors="replace").splitlines()
    rows = []
    first_ts = last_ts = None
    user_msgs = assistant_msgs = 0
    cwd = None
    summary_text = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        ts = obj.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        cwd = obj.get("cwd") or cwd

        rtype = obj.get("type")
        if rtype == "summary":
            summary_text = obj.get("summary") or summary_text
            continue
        if rtype not in ("user", "assistant"):
            continue

        msg = obj.get("message") or {}
        role = msg.get("role") or rtype
        text = extract_text(msg.get("content"))
        if not text.strip():
            continue
        if role == "user":
            user_msgs += 1
        elif role == "assistant":
            assistant_msgs += 1

        rows.append((ts or "", role, text))

    out = []
    out.append(f"# Session `{jsonl_path.stem}`\n")
    if summary_text:
        out.append(f"**Summary:** {summary_text}\n")
    out.append(f"- **Source file:** `{jsonl_path}`")
    if cwd:
        out.append(f"- **Working dir:** `{cwd}`")
    if first_ts:
        out.append(f"- **Started:** {first_ts}")
    if last_ts:
        out.append(f"- **Last activity:** {last_ts}")
    out.append(f"- **Messages:** {user_msgs} user / {assistant_msgs} assistant")
    out.append("\n---\n")

    for ts, role, text in rows:
        header = f"## {role}"
        if ts:
            header += f" — {ts}"
        out.append(header)
        out.append("")
        out.append(text)
        out.append("")

    meta = {
        "first_ts": first_ts, "last_ts": last_ts, "cwd": cwd,
        "user_msgs": user_msgs, "assistant_msgs": assistant_msgs,
        "summary": summary_text,
    }
    return "\n".join(out), meta


def main():
    if not PROJECTS_DIR.exists():
        print(f"FATAL: no Claude Code project history at {PROJECTS_DIR}")
        sys.exit(1)

    filter_str = sys.argv[1] if len(sys.argv) > 1 else None
    project_dirs = sorted(p for p in PROJECTS_DIR.iterdir() if p.is_dir())
    if filter_str:
        project_dirs = [p for p in project_dirs if filter_str in p.name]
    if not project_dirs:
        print(f"No project dirs found in {PROJECTS_DIR}"
              + (f" matching {filter_str!r}" if filter_str else ""))
        print("Existing project dirs:")
        for p in sorted(PROJECTS_DIR.iterdir()):
            print(f"  {p.name}")
        sys.exit(1)

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    index_lines = ["# Claude Code Thread Export Index\n",
                   f"Generated: {datetime.now().isoformat(timespec='seconds')}\n"]

    total_sessions = 0
    for proj in project_dirs:
        sessions = sorted(proj.glob("*.jsonl"))
        if not sessions:
            continue
        out_proj = OUT_ROOT / proj.name
        out_proj.mkdir(parents=True, exist_ok=True)

        index_lines.append(f"## `{proj.name}` — {len(sessions)} sessions\n")
        for sess in sessions:
            md, meta = session_to_markdown(sess)
            out_path = out_proj / f"{sess.stem}.md"
            out_path.write_text(md)
            total_sessions += 1
            label = (meta["summary"] or "(no summary)")[:80]
            ts = meta["first_ts"] or "?"
            index_lines.append(
                f"- [{sess.stem}](./{proj.name}/{sess.stem}.md) "
                f"— {ts} — {meta['user_msgs']}u/{meta['assistant_msgs']}a — {label}"
            )
            print(f"  wrote {out_path.relative_to(OUT_ROOT.parent)}  "
                  f"({meta['user_msgs']}u/{meta['assistant_msgs']}a, "
                  f"{out_path.stat().st_size:,} bytes)")
        index_lines.append("")

    (OUT_ROOT / "README.md").write_text("\n".join(index_lines))
    print(f"\nDone. {total_sessions} sessions exported to {OUT_ROOT}")
    print(f"\nNext steps (from inside this repo):")
    print(f"  git add claude-threads/")
    print(f"  git commit -m 'Export Claude Code thread transcripts'")
    print(f"  git push")


if __name__ == "__main__":
    main()
