"""The jams match list, ../jams-data/jams.json, kept to match students to
nights person to person.

VOICE.md §4 stands (Daniel, 2026-10-27): specific jams, venues and nights
never publish, so the list lives outside this public repo, in ../jams-data/,
and the site build never reads it. scripts/jams_check.py and
scripts/geocode_jams.py use these helpers; JAMS_DATA points them elsewhere.
"""
import datetime
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.environ.get('JAMS_DATA') or os.path.join(os.path.dirname(REPO), 'jams-data', 'jams.json')
AREAS_PATH = os.path.join(REPO, '_src', 'jams', 'areas.yaml')

# A night counts as current while its newest dated confirmation
# (verified_date or firsthand_date) is at most this many days old.
CURRENT_WINDOW_DAYS = 90

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
VALID_CADENCE_RULES = re.compile(r'^(weekly|biweekly|monthly|last|irregular|nth:([1-5]|last)(,([1-5]|last))*)$')
WEBSITE_OWNERS = ('venue', 'jam', 'host', 'listing')
VERIFIED_HOW = ('venue_site', 'host_post', 'facebook_group', 'facebook_event', 'facebook_post',
                'instagram', 'ticket_page', 'listing', 'video', 'daniel')

_cache = {}


def available():
    return os.path.exists(DATA_PATH)


def listings():
    if 'data' not in _cache:
        with open(DATA_PATH, encoding='utf-8') as f:
            _cache['data'] = json.load(f)
    return _cache['data']['listings']


def parse_date(s):
    try:
        return datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def confirmation_date(rec):
    dates = [d for d in (parse_date(rec.get('verified_date')),
                         parse_date(rec.get('firsthand_date'))) if d]
    return max(dates) if dates else None


def state(rec, today=None):
    """'current', or why a night is set aside: 'hidden', 'ended',
    'no_address', 'unverified' (no dated confirmation) or 'stale' (newest
    confirmation older than CURRENT_WINDOW_DAYS)."""
    today = today or datetime.date.today()
    if rec.get('hide'):
        return 'hidden'
    if rec.get('status') == 'ended':
        return 'ended'
    if not (rec.get('address') or '').strip():
        return 'no_address'
    conf = confirmation_date(rec)
    if not conf:
        return 'unverified'
    if (today - conf).days > CURRENT_WINDOW_DAYS:
        return 'stale'
    return 'current'


def areas():
    if 'areas' not in _cache:
        import yaml
        with open(AREAS_PATH, encoding='utf-8') as f:
            _cache['areas'] = yaml.safe_load(f)['areas']
    return _cache['areas']


def area_for(rec):
    towns = {t.lower(): a['key'] for a in areas() for t in a['towns']}
    return towns.get((rec.get('city') or '').lower())
