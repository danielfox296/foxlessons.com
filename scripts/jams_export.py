#!/usr/bin/env python3
"""Write data/jams.json, the public part of the jams list.

Reads the master at ../jams-data/jams.json (or the file JAMS_DATA names),
keeps the listings that publish today under the 90-day rule, and copies only
jams.PUBLIC_FIELDS from each, so the research notes never enter this public
repo. Run it from the repo root after any change to the master, then build:

    python3 scripts/jams_export.py && python3 build.py
"""
import datetime
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from _src.lib import jams  # noqa: E402


def public_listing(rec):
    return {k: rec[k] for k in jams.PUBLIC_FIELDS if rec.get(k) not in (None, '', [], {})}


def export(master, today):
    return {'listings': [public_listing(r) for r in master['listings']
                         if jams.publish_state(r, today) == 'published']}


def dumps(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + '\n'


def main():
    if not os.path.exists(jams.MASTER_PATH):
        sys.exit(f'jams_export: no master list at {jams.MASTER_PATH}')
    with open(jams.MASTER_PATH, encoding='utf-8') as f:
        master = json.load(f)
    today = datetime.date.today()
    out = export(master, today)
    os.makedirs(os.path.dirname(jams.DATA_PATH), exist_ok=True)
    with open(jams.DATA_PATH, 'w', encoding='utf-8') as f:
        f.write(dumps(out))
    print(f'jams_export: {len(out["listings"])} of {len(master["listings"])} listings publish '
          f'today ({today}); wrote {os.path.relpath(jams.DATA_PATH, REPO)}')


if __name__ == '__main__':
    main()
