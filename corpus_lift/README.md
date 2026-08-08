# Corpus Lift — get the whole corpus into Supabase

Goal: everything the system ever recorded — every message, lead touch, and
decision in `corpus.db` — copied into Supabase (project `rpbpktjpkhsjeeuwmdzu`),
so Supabase becomes the one brain. Read-only against the source; safe to re-run;
resumes where it left off if interrupted.

The corpus lives in TWO places. Lift both — the tool de-duplicates nothing
across machines, so they land in the same tables keyed by source rowid
(droplet first, then Fly's copy fills anything newer):

| Copy | Where | Path |
|---|---|---|
| Primary (468 MB) | DigitalOcean droplet | `~/automation/corpus.db` |
| Engine's copy | Fly machine `maittrix-engine` | `/data/corpus.db` and `/data/brain.db` |

## On the droplet (do this one first)

```bash
# 0) get these two scripts onto the box (either scp them, or:)
curl -sO https://raw.githubusercontent.com/mattodunlap/sierra-fub-sync/claude/haiku-messages-sierra-disappear-mrnknq/corpus_lift/inspect_corpus.py
curl -sO https://raw.githubusercontent.com/mattodunlap/sierra-fub-sync/claude/haiku-messages-sierra-disappear-mrnknq/corpus_lift/migrate_corpus.py

# 1) see what's inside (read-only; paste the output back to the cloud session)
python3 inspect_corpus.py

# 2) print the table definitions; paste corpus_schema.sql into
#    Supabase dashboard -> SQL Editor -> Run  (one time)
python3 migrate_corpus.py --emit-schema > corpus_schema.sql
cat corpus_schema.sql

# 3) find the Supabase key already on this box
grep -ri supabase ~/automation/.env ~/.config/systemd/user/ 2>/dev/null

# 4) move the data (add SUPABASE_SERVICE_KEY=... in front if step 3
#    found it somewhere other than ~/automation/.env)
python3 migrate_corpus.py --dry-run     # counts only, no writes
python3 migrate_corpus.py               # the real run
```

## On the Fly machine (after the droplet finishes)

```bash
fly ssh console -a maittrix-engine
# then inside:
python3 migrate_corpus.py --db /data/corpus.db
python3 migrate_corpus.py --db /data/brain.db
```

(Fly secrets already hold the Supabase key if the engine writes backups;
otherwise export SUPABASE_SERVICE_KEY first, same as the droplet.)

## What this does NOT cover (known corpus holes, patched separately)

1. **Email events were never recorded into the corpus** (two bugs, confirmed
   7/12) — email history gets backfilled from Sierra/FUB APIs afterward.
2. **Nothing engine-sent after July 12 00:26** was recorded (the event
   consumer died) — same patch source.
3. Anything only on the old May-era laptop.

After both lifts + the API patch pass, the cloud session verifies counts
(rows per table vs. source) before the droplet is retired.
