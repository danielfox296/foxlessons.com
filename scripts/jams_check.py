#!/usr/bin/env python3
"""Data checks for the jams directory (handoff sections 3 and 9).

Always checks data/jams.json, the public export the build reads. With
--strict (CI runs this before the build) it exits 1 only on the fatal
classes: a field outside jams.PUBLIC_FIELDS in the export, a duplicate slug,
a published listing whose city the area table doesn't place, or a draft
block present on main. Everything else is a warning.

When the master list is on this machine (../jams-data/jams.json, or the file
JAMS_DATA names), the field checks and the report run on the master instead,
and a stale export is a warning. CI never has the master.

Run from the repo root: python3 scripts/jams_check.py [--strict]
"""
import datetime
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'scripts'))
from _src.lib import jams  # noqa: E402
import jams_export  # noqa: E402

VALID_STATUS = {'active', 'unknown', 'paused', 'ended'}
VALID_FORMAT = {'jam', 'open mic', 'songwriter night'}
VALID_DAY = set(jams.DAYS) | {'varies'}
SLUG_RE = re.compile(r'^[a-z0-9-]+$')


def validate(recs, today, warns):
    for r in recs:
        s = r.get('slug')
        if not SLUG_RE.fullmatch(s or ''):
            warns.append(f'slug not anchor-safe: {s!r}')
        if r.get('status') not in VALID_STATUS:
            warns.append(f'{s}: status {r.get("status")!r}')
        if r.get('format') not in VALID_FORMAT:
            warns.append(f'{s}: format {r.get("format")!r}')
        if r.get('day') not in VALID_DAY:
            warns.append(f'{s}: day {r.get("day")!r}')
        rule = r.get('cadence_rule')
        if not rule or not jams.VALID_CADENCE_RULES.match(rule):
            warns.append(f'{s}: cadence_rule {rule!r} (cadence: {r.get("cadence")!r})')
        skill = r.get('skill')
        if skill is not None and skill not in (1, 2, 3, 4, 5):
            warns.append(f'{s}: skill {skill!r} (1-5 or null)')
        if r.get('website') and r.get('website_whose') not in jams.WEBSITE_OWNERS:
            warns.append(f'{s}: website_whose {r.get("website_whose")!r} '
                         f'(one of {", ".join(jams.WEBSITE_OWNERS)})')
        if r.get('venue_website') and r.get('website_whose') == 'venue':
            warns.append(f'{s}: venue_website set while website is already the venue\'s')
        known = jams.parse_date(r.get('known_date'))
        if r.get('known_date') and not known:
            warns.append(f'{s}: known_date {r.get("known_date")!r} is not a YYYY-MM-DD date')
        elif known and r.get('day') in jams.DAYS and known.weekday() != jams.DAYS.index(r['day']):
            warns.append(f'{s}: known_date {known} is not a {r["day"]}')
        skip = r.get('skip_months')
        if skip is not None and (not isinstance(skip, list) or
                                 not all(isinstance(m, int) and 1 <= m <= 12 for m in skip)):
            warns.append(f'{s}: skip_months {skip!r} (a list of month numbers, 1 to 12)')
        if rule == 'biweekly' and not known and jams.publish_state(r, today) == 'published':
            warns.append(f'{s}: every other week with no known_date, so it stays out of the structured data')
        for field in ('verified_date', 'firsthand_date'):
            d = jams.parse_date(r.get(field))
            if r.get(field) and not d:
                warns.append(f'{s}: {field} {r.get(field)!r} is not a YYYY-MM-DD date')
            elif d and d > today:
                warns.append(f'{s}: {field} {d} is in the future (the date of the check, '
                             'not of the night it found, belongs here)')
        vh = r.get('verified_how')
        if vh is not None and vh not in jams.VERIFIED_HOW_DISPLAY:
            warns.append(f'{s}: verified_how {vh!r}')
        if r.get('verified_how_raw') and not vh:
            warns.append(f'{s}: verified_how_raw matched no normalized value: '
                         f'{r["verified_how_raw"]!r}')
        for q in r.get('scene') or []:
            if not q.get('quote') or not q.get('who'):
                warns.append(f'{s}: scene item missing quote or who')
            elif len(q['quote'].split()) > 25:
                warns.append(f'{s}: scene quote over 25 words')
        for p in r.get('photos') or []:
            f = p.get('file') or ''
            if not os.path.exists(os.path.join(REPO, 'img', 'jams', f)):
                warns.append(f'{s}: photo file missing: img/jams/{f}')
            if not p.get('credit') or not p.get('source_url'):
                warns.append(f'{s}: photo {f} needs a credit and a source_url')
            if p.get('kind') not in ('night', 'venue'):
                warns.append(f'{s}: photo {f} kind {p.get("kind")!r} (night or venue)')
            if p.get('focus') and not jams.PHOTO_FOCUS.fullmatch(p['focus']):
                warns.append(f'{s}: photo {f} focus {p["focus"]!r} (like "50% 25%")')


def report(recs, today, label):
    state = {}
    for r in recs:
        state.setdefault(jams.publish_state(r, today), []).append(r)
    pub = state.get('published', [])
    print(f'{label}: {len(recs)} listings, {len(pub)} publish today ({today})')
    held = {k: len(v) for k, v in state.items() if k != 'published'}
    print('  held: ' + (', '.join(f'{k} {n}' for k, n in sorted(held.items())) or 'none'))
    cutoff = today - datetime.timedelta(days=jams.PUBLISH_WINDOW_DAYS - 14)
    dropping = sorted((jams.confirmation_date(r), r['slug']) for r in pub
                      if jams.confirmation_date(r) <= cutoff)
    if dropping:
        print(f'  dropping off within 14 days ({len(dropping)}):')
        for d, s in dropping:
            print(f'    {d}  {s}')
    groups = {}
    for r in pub:
        groups.setdefault(((r.get('venue') or '').lower().strip(),
                           r.get('day'), r.get('format')), []).append(r['slug'])
    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    if dupes:
        print(f'  same venue + day + format among published ({len(dupes)} groups, never merged):')
        for k, v in sorted(dupes.items()):
            print(f'    {k}: {v}')
    if jams.genre_pages():
        mapped = jams.mapped_genre_values()
        unmapped = {}
        for r in recs:
            for g in r.get('genres') or []:
                if g.lower() not in mapped:
                    unmapped[g] = unmapped.get(g, 0) + 1
        if unmapped:
            print('  genre values mapped to no page (tags still render): '
                  + ', '.join(f'{g} {n}' for g, n in sorted(unmapped.items(), key=lambda x: -x[1])))


def main():
    strict = '--strict' in sys.argv
    today = datetime.date.today()
    fatals, warns = [], []

    data = jams.load_data()
    recs = data['listings']
    allowed = set(jams.PUBLIC_FIELDS)
    if set(data) - {'listings'}:
        fatals.append(f'data/jams.json top-level keys beyond listings: {sorted(set(data) - {"listings"})}')
    for r in recs:
        extra = set(r) - allowed
        if extra:
            fatals.append(f'data/jams.json {r.get("slug")}: fields outside PUBLIC_FIELDS: {sorted(extra)}')
    seen = set()
    for r in recs:
        if r.get('slug') in seen:
            fatals.append(f'duplicate slug: {r.get("slug")}')
        seen.add(r.get('slug'))
    pub = [r for r in recs if jams.publish_state(r, today) == 'published']
    for city in jams.unmapped_cities(pub):
        fatals.append(f'published listing city not in areas.yaml: {city!r}')
    drafts = jams.drafts_present()
    branch = jams.current_branch()
    if drafts and branch == 'main':
        fatals.append(f'draft blocks present on main: {", ".join(drafts)}')

    print(f'jams_check: branch {branch or "unknown"}')
    if drafts:
        print(f'  draft blocks ({len(drafts)}): ' + ', '.join(drafts))
    if os.path.exists(jams.MASTER_PATH):
        with open(jams.MASTER_PATH, encoding='utf-8') as f:
            master = json.load(f)
        validate(master['listings'], today, warns)
        report(master['listings'], today, 'master')
        print(f'export: {len(recs)} listings in data/jams.json, {len(pub)} publish today')
        with open(jams.DATA_PATH, encoding='utf-8') as f:
            if f.read() != jams_export.dumps(jams_export.export(master, today)):
                warns.append('data/jams.json is out of date with the master: '
                             'run python3 scripts/jams_export.py')
    else:
        validate(recs, today, warns)
        report(recs, today, 'export')
        print(f'  no master list at {jams.MASTER_PATH}; checked the export only')

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
