# Session `ab7ec22f-84ea-465f-be2d-ce1efba105d3`

- **Source file:** `/home/matthew/.claude/projects/-home-matthew-automation/ab7ec22f-84ea-465f-be2d-ce1efba105d3.jsonl`
- **Working dir:** `/home/matthew/automation`
- **Started:** 2026-05-22T17:01:04.795Z
- **Last activity:** 2026-05-22T17:01:06.598Z
- **Messages:** 1 user / 1 assistant

---

## user — 2026-05-22T17:01:04.971Z

Extract real estate search criteria from this lead's message. Return ONLY a JSON object (no preamble, no fences), with these optional keys (omit any that aren't mentioned):

  neighborhoods: array of neighborhood/community names (e.g. ["Summerlin", "Spanish Trail"])
  zips: array of zip strings
  cities: array of cities
  min_price: integer
  max_price: integer
  min_beds: integer
  min_baths: number
  min_sqft: integer
  min_year_built: integer
  min_garage: integer
  features: array of strings (pool, single-story, master-on-first-floor, golf-course, new-construction, view, gated, guard-gated, casita, RV-garage, etc.)
  schools: array of school names
  motivation: short string describing WHY they're moving

If the message has no clear search intent, return {}.

Message:
"""I'm not looking for a house"""

## assistant — 2026-05-22T17:01:06.598Z

{}
