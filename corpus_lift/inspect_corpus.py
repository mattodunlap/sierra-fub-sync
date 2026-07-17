#!/usr/bin/env python3
"""
Step 1 of the corpus lift: look inside corpus.db and report what's there.

Read-only. Prints every table, its columns, its row count, and date ranges
where a created/timestamp-looking column exists. Paste the output back to
the cloud session (or save with:  python3 inspect_corpus.py > corpus_inventory.txt).

Usage:
    python3 inspect_corpus.py [/path/to/corpus.db]

Default path is ~/automation/corpus.db (the droplet location). On the Fly
machine use /data/corpus.db and /data/brain.db.
"""
import json
import os
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/automation/corpus.db")

TIMEISH = ("created", "timestamp", "time", "date", "sent", "received", "updated")


def main():
    if not os.path.exists(DB):
        print(f"NOT FOUND: {DB}")
        print("Try: find ~ /data -maxdepth 3 -name '*.db' -size +1M 2>/dev/null")
        sys.exit(1)

    size_mb = os.path.getsize(DB) / 1e6
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out = {"db": DB, "size_mb": round(size_mb, 1), "tables": []}

    tables = [r["name"] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

    for t in tables:
        cols = [dict(name=r["name"], type=r["type"]) for r in con.execute(f'PRAGMA table_info("{t}")')]
        try:
            n = con.execute(f'SELECT COUNT(*) c FROM "{t}"').fetchone()["c"]
        except Exception as e:
            n = f"error: {e}"
        entry = {"table": t, "rows": n, "columns": cols}
        # date range on the first time-ish column
        for c in cols:
            if any(k in c["name"].lower() for k in TIMEISH):
                try:
                    r = con.execute(
                        f'SELECT MIN("{c["name"]}") lo, MAX("{c["name"]}") hi FROM "{t}"').fetchone()
                    entry["time_column"] = c["name"]
                    entry["earliest"] = r["lo"]
                    entry["latest"] = r["hi"]
                except Exception:
                    pass
                break
        # 1 sample row, truncated, so the schema is unambiguous
        try:
            row = con.execute(f'SELECT * FROM "{t}" LIMIT 1').fetchone()
            if row:
                entry["sample"] = {k: (str(row[k])[:120] if row[k] is not None else None)
                                   for k in row.keys()}
        except Exception:
            pass
        out["tables"].append(entry)

    print(json.dumps(out, indent=2, default=str))
    print(f"\n# {len(tables)} tables, {size_mb:.0f} MB — paste ALL of the above back.", file=sys.stderr)


if __name__ == "__main__":
    main()
