# Jams data: where it lives and which fields publish

`data/jams.json` is the public export the build reads. It holds only the
fields in `PUBLIC_FIELDS` (`_src/lib/jams.py`), for the nights confirmed
within the last 90 days. The master list, with the research behind it, lives
outside this public repo in `../jams-data/jams.json`. To change a listing,
edit the master, then run:

    python3 scripts/jams_export.py && python3 build.py

`scripts/jams_check.py --strict` fails CI if a field outside `PUBLIC_FIELDS`
ever appears in `data/jams.json`.

## Fields added after the original handoff

| Field | Meaning | Rendered? |
|---|---|---|
| `website_whose` | Whose site `website` is: `venue`, `jam` (the night's own site), `host`, or `listing` (a third-party event page). Sets the link label: "Venue's website", "Jam's website", "Host's website", "Event page". | as the label |
| `venue_website` | The venue's own site, set only when `website` belongs to someone else, so a card can link both. | yes |
| `known_date` | One date the night is known to run (`YYYY-MM-DD`). An every-other-week night needs it to have a next date; without it, the night stays on the page but gets no next date and no structured data. | no |
| `skip_months` | Months the night doesn't run, as numbers (`[10, 12]`), from its own cadence text. The next-date math steps past them. | no |

`cadence_rule` also takes `last` inside an ordinal list, for nights like
"1st and last Tuesday" (`nth:1,last`).

The card's next date ("Tonight", "Tomorrow", "Next: Thu, Nov 12") comes from
`js/jams.js`, which follows the same rules as `next_occurrence()` in
`_src/lib/jams.py`. Change one, change both.
