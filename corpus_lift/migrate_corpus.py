#!/usr/bin/env python3
"""
Step 2 of the corpus lift: copy every table of corpus.db into Supabase.

Python 3 standard library only — nothing to install. Reads the SQLite file,
mirrors each table into Supabase as corpus_<table>, streams rows in batches,
and can resume if interrupted (progress kept in .corpus_lift_state.json).
The source database is opened READ-ONLY; nothing on this machine is changed.

Two-step run:

  1) Emit the schema and create the tables (one paste in the Supabase
     dashboard -> SQL Editor -> Run):

        python3 migrate_corpus.py --emit-schema > corpus_schema.sql

  2) Move the data:

        python3 migrate_corpus.py

Credentials: the script needs SUPABASE_SERVICE_KEY (and optionally
SUPABASE_URL, default is the maittrix project). It looks in, in order:
  --key/--url flags, environment variables, then ~/automation/.env
On the droplet the key is already in the event-consumer's config — run
`grep -ri supabase ~/automation/.env ~/.config/systemd/user/ 2>/dev/null`
to see where it lives, and export it if it isn't in ~/automation/.env.

Options:
    --db PATH        source sqlite file      (default ~/automation/corpus.db)
    --tables a,b,c   only these tables       (default: all)
    --batch N        rows per request        (default 500)
    --dry-run        count + plan only, no writes
    --emit-schema    print CREATE TABLE SQL and exit
"""
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "https://rpbpktjpkhsjeeuwmdzu.supabase.co"
STATE_FILE = ".corpus_lift_state.json"

PG_TYPES = {"INTEGER": "bigint", "INT": "bigint", "REAL": "double precision",
            "TEXT": "text", "BLOB": "text", "NUMERIC": "numeric",
            "BOOLEAN": "boolean", "": "text"}


def pg_type(sqlite_type):
    t = (sqlite_type or "").upper()
    for k, v in PG_TYPES.items():
        if k and k in t:
            return v
    return "text"


def load_env_file(path):
    if not os.path.exists(path):
        return {}
    out = {}
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def get_creds(args):
    envfile = load_env_file(os.path.expanduser("~/automation/.env"))
    url = (args.url or os.environ.get("SUPABASE_URL") or envfile.get("SUPABASE_URL")
           or DEFAULT_URL).rstrip("/")
    key = (args.key or os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_KEY")
           or envfile.get("SUPABASE_SERVICE_KEY") or envfile.get("SUPABASE_KEY"))
    return url, key


def sanitize(name):
    return "corpus_" + "".join(c if c.isalnum() or c == "_" else "_" for c in name.lower())


def post_batch(url, key, table, rows, retries=5):
    body = json.dumps(rows, default=str).encode()
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}?on_conflict=src_rowid", data=body, method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=minimal"})
    delay = 2
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
            return
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:300]
            if e.code == 404:
                raise SystemExit(
                    f"Table {table} missing in Supabase (404). Run --emit-schema and "
                    f"paste corpus_schema.sql into the Supabase SQL Editor first.")
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise SystemExit(f"Supabase refused batch for {table}: HTTP {e.code} {detail}")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise SystemExit(f"Network failure pushing {table}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.expanduser("~/automation/corpus.db"))
    ap.add_argument("--url")
    ap.add_argument("--key")
    ap.add_argument("--tables")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--emit-schema", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"source db not found: {args.db}")
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    tables = [r["name"] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    if args.tables:
        want = {t.strip() for t in args.tables.split(",")}
        tables = [t for t in tables if t in want]

    if args.emit_schema:
        for t in tables:
            cols = list(con.execute(f'PRAGMA table_info("{t}")'))
            colsql = ",\n".join(f'  "{c["name"]}" {pg_type(c["type"])}' for c in cols)
            print(f'create table if not exists {sanitize(t)} (\n'
                  f'  src_rowid bigint primary key,\n{colsql}\n);')
        print("-- Paste this whole file into Supabase -> SQL Editor -> Run.")
        return

    url, key = get_creds(args)
    if not args.dry_run and not key:
        raise SystemExit(
            "No Supabase key found. Export SUPABASE_SERVICE_KEY=... (see the header "
            "of this file for where to find it on this machine) and re-run.")

    state = {}
    if os.path.exists(STATE_FILE):
        state = json.load(open(STATE_FILE))

    grand = 0
    for t in tables:
        cols = [c["name"] for c in con.execute(f'PRAGMA table_info("{t}")')]
        total = con.execute(f'SELECT COUNT(*) c FROM "{t}"').fetchone()["c"]
        done_upto = state.get(t, -1)
        print(f"{t}: {total} rows -> {sanitize(t)}"
              + (f" (resuming after rowid {done_upto})" if done_upto >= 0 else ""))
        if args.dry_run:
            grand += total
            continue
        colsel = ", ".join(f'"{c}"' for c in cols)
        while True:
            rows = list(con.execute(
                f'SELECT rowid AS src_rowid, {colsel} FROM "{t}" '
                f'WHERE rowid > ? ORDER BY rowid LIMIT ?', (done_upto, args.batch)))
            if not rows:
                break
            payload = []
            for r in rows:
                d = {}
                for k in r.keys():
                    v = r[k]
                    if isinstance(v, bytes):
                        v = v.hex()
                    d[k] = v
                payload.append(d)
            post_batch(url, key, sanitize(t), payload)
            done_upto = rows[-1]["src_rowid"]
            state[t] = done_upto
            json.dump(state, open(STATE_FILE, "w"))
            grand += len(rows)
            print(f"  ...{done_upto} ({grand} rows moved so far)", end="\r")
        print()
    print(("DRY RUN — would move" if args.dry_run else "DONE — moved"),
          grand, "rows into Supabase.")


if __name__ == "__main__":
    main()
