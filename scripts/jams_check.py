#!/usr/bin/env python3
"""Checks for the jams section.

The public pages are guides, and VOICE.md §4 keeps every jam, venue and
night off the site (Daniel, 2026-10-27), so the one thing that can block a
deploy is jams copy still marked draft: true on main. With --strict (CI runs
this before the build) that exits 1.

Everything else here is a report on the internal match list,
../jams-data/jams.json beside the repo (or the copy JAMS_DATA points at): which nights are current, which go stale
within 14 days, duplicate nights, and data that needs a person's eyes. Those
are warnings and never block a deploy. Without the data file, the report is
skipped.

Run from the repo root: python3 scripts/jams_check.py [--strict]
"""
import datetime
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'scripts'))
from _src.lib import jams  # noqa: E402
import jams_data as data  # noqa: E402

VALID_STATUS = {'active', 'unknown', 'paused', 'ended'}
VALID_FORMAT = {'jam', 'open mic', 'songwriter night'}
VALID_DAY = set(data.DAYS) | {'varies'}
SLUG_RE = re.compile(r'^[a-z0-9-]+$')


def check_listings(today, warns):
    recs = data.listings()
    seen = set()
    for r in recs:
        s = r.get('slug') or ''
        if s in seen:
            warns.append(f'duplicate slug: {s}')
        seen.add(s)
        if not SLUG_RE.fullmatch(s):
            warns.append(f'slug not anchor-safe: {s!r}')
        if r.get('status') not in VALID_STATUS:
            warns.append(f'{s}: status {r.get("status")!r}')
        if r.get('format') not in VALID_FORMAT:
            warns.append(f'{s}: format {r.get("format")!r}')
        if r.get('day') not in VALID_DAY:
            warns.append(f'{s}: day {r.get("day")!r}')
        rule = r.get('cadence_rule')
        if not rule or not data.VALID_CADENCE_RULES.match(rule):
            warns.append(f'{s}: cadence_rule {rule!r} (cadence: {r.get("cadence")!r})')
        if r.get('skill') is not None and r.get('skill') not in (1, 2, 3, 4, 5):
            warns.append(f'{s}: skill {r.get("skill")!r} (1-5 or null)')
        if r.get('website') and r.get('website_whose') not in data.WEBSITE_OWNERS:
            warns.append(f'{s}: website_whose {r.get("website_whose")!r}')
        if r.get('venue_website') and r.get('website_whose') == 'venue':
            warns.append(f"{s}: venue_website set while website is already the venue's")
        known = data.parse_date(r.get('known_date'))
        if r.get('known_date') and not known:
            warns.append(f'{s}: known_date {r.get("known_date")!r} is not a YYYY-MM-DD date')
        elif known and r.get('day') in data.DAYS and known.weekday() != data.DAYS.index(r['day']):
            warns.append(f'{s}: known_date {known} is not a {r["day"]}')
        skip = r.get('skip_months')
        if skip is not None and (not isinstance(skip, list) or
                                 not all(isinstance(m, int) and 1 <= m <= 12 for m in skip)):
            warns.append(f'{s}: skip_months {skip!r} (a list of month numbers, 1 to 12)')
        for field in ('verified_date', 'firsthand_date'):
            d = data.parse_date(r.get(field))
            if r.get(field) and not d:
                warns.append(f'{s}: {field} {r.get(field)!r} is not a YYYY-MM-DD date')
            elif d and d > today:
                warns.append(f'{s}: {field} {d} is in the future (the date of the check belongs here)')
        if r.get('verified_how') is not None and r.get('verified_how') not in data.VERIFIED_HOW:
            warns.append(f'{s}: verified_how {r.get("verified_how")!r}')

    states = {}
    for r in recs:
        states.setdefault(data.state(r, today), []).append(r)
    current = states.get('current', [])
    for city in sorted({r['city'] for r in current if data.area_for(r) is None}):
        warns.append(f'city not in areas.yaml: {city!r}')

    print(f'match list: {len(recs)} nights, {len(current)} current ({today})')
    print('  set aside: ' + (', '.join(f'{k} {len(v)}' for k, v in sorted(states.items())
                                        if k != 'current') or 'none'))
    horizon = today - datetime.timedelta(days=data.CURRENT_WINDOW_DAYS - 14)
    stale_soon = sorted((data.confirmation_date(r), r['slug']) for r in current
                        if data.confirmation_date(r) <= horizon)
    if stale_soon:
        print(f'  going stale within 14 days, re-confirm or let go ({len(stale_soon)}):')
        for d, s in stale_soon:
            print(f'    {s}: last confirmed {d}')
    groups = {}
    for r in current:
        key = ((r.get('venue') or '').lower().strip(), r.get('day'), r.get('format'))
        groups.setdefault(key, []).append(r['slug'])
    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    if dupes:
        print(f'  same venue, day and format ({len(dupes)} groups; never merged automatically):')
        for k, v in sorted(dupes.items()):
            print(f'    {k}: {v}')
    mapped = jams.mapped_genre_values()
    unmapped = {}
    for r in recs:
        for g in r.get('genres') or []:
            if g.lower() not in mapped:
                unmapped[g] = unmapped.get(g, 0) + 1
    if unmapped:
        print('  genre values no style guide covers: '
              + ', '.join(f'{g} {n}' for g, n in sorted(unmapped.items(), key=lambda x: -x[1])))


def main():
    strict = '--strict' in sys.argv
    today = datetime.date.today()
    warns, fatals = [], []

    drafts = jams.drafts_present()
    branch = jams.current_branch()
    print(f'jams_check: branch {branch or "unknown"}')
    if drafts:
        print(f'  draft copy ({len(drafts)}): ' + ', '.join(drafts))
        if branch == 'main':
            fatals.append(f'draft copy present on main: {", ".join(drafts)}')

    if data.available():
        check_listings(today, warns)
    else:
        print(f'  no match list at {data.DATA_PATH}; listing report skipped')

    if warns:
        print(f'\nWarnings ({len(warns)}):')
        for w in warns:
            print(f'  {w}')
    if fatals:
        print(f'\nFATAL ({len(fatals)}):')
        for f in fatals:
            print(f'  {f}')
        if strict:
            return 1
    if not fatals and not warns:
        print('\nAll checks clean.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
