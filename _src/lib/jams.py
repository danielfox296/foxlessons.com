"""Jams directory: load, validate, filter, sort, render.

Data layer for data/jams.json, the public export of the jams list, plus
the YAML under _src/jams/. The master list, with research notes that
never publish, lives outside this repo in ../jams-data/jams.json;
scripts/jams_export.py writes the public file from it and keeps only
PUBLIC_FIELDS. The render layer (render_page and friends) hooks into
build.py; scripts/jams_check.py imports the same functions so the publish
rule, the area table and the draft gate live in exactly one place.

Nothing here touches the network. The build must keep working offline.
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
from urllib.parse import quote_plus, urlparse

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(REPO, 'data', 'jams.json')
MASTER_PATH = (os.environ.get('JAMS_DATA')
               or os.path.join(os.path.dirname(REPO), 'jams-data', 'jams.json'))
JAMS_SRC = os.path.join(REPO, '_src', 'jams')

# The only listing fields that may leave the master for data/jams.json. The
# research fields (review, sources, web_check, social_check, browser_check,
# verified_how_raw) and hide stay in the master: this repo is public.
PUBLIC_FIELDS = (
    'slug', 'name', 'venue', 'address', 'city', 'format', 'genres',
    'day', 'cadence', 'cadence_rule', 'start', 'end', 'known_date', 'skip_months',
    'signup_time', 'signup_method', 'host', 'house_band', 'backline',
    'cover', 'age', 'parking', 'transit',
    'song_list_url', 'website', 'website_whose', 'venue_website', 'social',
    'notes_instrumentalists', 'notes_singers', 'notes_songwriters',
    'skill', 'first_timer_tip', 'firsthand_notes', 'firsthand_date', 'scene', 'photos',
    'verified_date', 'verified_how', 'status', 'lat', 'lng',
)
TEMPLATES = os.path.join(REPO, '_src', 'templates', 'jams')
SITE_URL = 'https://foxlessons.com'

# A listing publishes only while its newest dated confirmation (verified_date
# or firsthand_date) falls within this many days of the build date (handoff
# 4.3). Change the number here; everything else follows it.
PUBLISH_WINDOW_DAYS = 90

# A genre or area page is only built once it can seat this many published
# listings (handoff section 2).
MIN_PAGE_LISTINGS = 3

VALID_CADENCE_RULES = re.compile(r'^(weekly|biweekly|monthly|last|irregular|nth:([1-5]|last)(,([1-5]|last))*)$')
WEBSITE_OWNERS = ('venue', 'jam', 'host', 'listing')
# A photo's optional crop point when it fills the strip alone: "50% 25%".
PHOTO_FOCUS = re.compile(r'(100|[1-9]?[0-9])% (100|[1-9]?[0-9])%')

VERIFIED_HOW_DISPLAY = {
    'venue_site':     "the venue's calendar",
    'host_post':      "the host's post",
    'facebook_group': 'a Facebook group post',
    'facebook_event': 'a Facebook event',
    'facebook_post':  'a Facebook post',
    'instagram':      'an Instagram post',
    'ticket_page':    'a ticket page',
    'listing':        'a local events listing',
    'video':          'a video from the night',
    'daniel':         'Daniel being there',
}

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
FORMAT_SLUG = {'jam': 'jam', 'open mic': 'open-mic', 'songwriter night': 'songwriter-night'}

_cache = {}


def _read_yaml(path):
    import yaml
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_data():
    if 'data' not in _cache:
        with open(DATA_PATH, encoding='utf-8') as f:
            _cache['data'] = json.load(f)
    return _cache['data']


def listings():
    return load_data()['listings']


def load_jams_yaml(name, required=False):
    """One of the _src/jams/*.yaml files, cached; None when absent."""
    key = f'yaml:{name}'
    if key not in _cache:
        path = os.path.join(JAMS_SRC, f'{name}.yaml')
        if not os.path.exists(path):
            if required:
                raise SystemExit(f'jams: missing {path}')
            _cache[key] = None
        else:
            _cache[key] = _read_yaml(path)
    return _cache[key]


def strings():
    return load_jams_yaml('strings', required=True)


def parse_date(s):
    try:
        return datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def confirmation_date(rec):
    dates = [d for d in (parse_date(rec.get('verified_date')),
                         parse_date(rec.get('firsthand_date'))) if d]
    return max(dates) if dates else None


def publish_state(rec, today=None):
    """'published', or why the listing is held: 'hidden', 'ended',
    'no_address', 'unverified' (no parseable dated confirmation) or
    'stale' (confirmation older than PUBLISH_WINDOW_DAYS)."""
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
    if (today - conf).days > PUBLISH_WINDOW_DAYS:
        return 'stale'
    return 'published'


def published(today=None):
    today = today or datetime.date.today()
    return [r for r in listings() if publish_state(r, today) == 'published']


# --- areas -----------------------------------------------------------------

def areas():
    return load_jams_yaml('areas', required=True)['areas']


def town_to_area():
    if 'town_map' not in _cache:
        _cache['town_map'] = {t.lower(): a['key'] for a in areas() for t in a['towns']}
    return _cache['town_map']


def area_for(rec):
    return town_to_area().get((rec.get('city') or '').lower())


def unmapped_cities(recs):
    """Cities among `recs` that the area table doesn't place."""
    return sorted({r['city'] for r in recs if area_for(r) is None})


# --- genre pages -----------------------------------------------------------

def genre_pages():
    """Ordered [(page_key, cfg)] from genres.yaml; [] until it exists."""
    data = load_jams_yaml('genres')
    if not data:
        return []
    return [(g['key'], g) for g in data['genres']]


def genre_cfg(key):
    for k, cfg in genre_pages():
        if k == key:
            return cfg
    return None


def pages_for_listing(rec):
    """Genre/format page keys this listing appears on (handoff 2.1)."""
    keys = []
    rec_genres = {g.lower() for g in rec.get('genres') or []}
    is_jam = rec.get('format') == 'jam'
    for key, cfg in genre_pages():
        maps = {m.lower() for m in cfg.get('maps', [])}
        maps_jam_only = {m.lower() for m in cfg.get('maps_jam_only', [])}
        if rec_genres & maps or (is_jam and rec_genres & maps_jam_only):
            keys.append(key)
    if rec.get('format') in ('open mic', 'songwriter night') and 'open-mics' not in keys:
        keys.append('open-mics')
    return keys


def mapped_genre_values():
    vals = set()
    for _, cfg in genre_pages():
        vals |= {m.lower() for m in cfg.get('maps', [])}
        vals |= {m.lower() for m in cfg.get('maps_jam_only', [])}
    return vals


# --- drafts and the main-branch gate ---------------------------------------

def _walk_drafts(node, stem, here, found):
    if isinstance(node, dict):
        if node.get('draft') is True:
            found.append(f"{stem}:{node.get('key') or node.get('label') or here}")
        for k, v in node.items():
            _walk_drafts(v, stem, k, found)
    elif isinstance(node, list):
        for v in node:
            _walk_drafts(v, stem, here, found)


def drafts_present():
    """'file:block' for every block still marked draft: true in
    _src/jams/*.yaml, e.g. 'genres:blues' or 'strings:guide'."""
    found = []
    if not os.path.isdir(JAMS_SRC):
        return found
    for fn in sorted(os.listdir(JAMS_SRC)):
        if fn.endswith('.yaml'):
            stem = fn[:-len('.yaml')]
            _walk_drafts(_read_yaml(os.path.join(JAMS_SRC, fn)), stem, stem, found)
    return found


def current_branch():
    """Branch name: CI env first (detached checkouts), then git, else None."""
    if 'branch' in _cache:
        return _cache['branch']
    name = os.environ.get('GITHUB_REF_NAME')
    if not name:
        try:
            proc = subprocess.run(['git', '-C', REPO, 'rev-parse', '--abbrev-ref', 'HEAD'],
                                  capture_output=True, text=True, timeout=10)
            name = proc.stdout.strip() if proc.returncode == 0 else None
        except Exception:
            name = None
    _cache['branch'] = name or None
    return _cache['branch']


def refuse_drafts_on_main():
    """The build refuses to run on main while any jams block is still a
    draft (handoff 7.3). Branch previews render drafts with a marker."""
    if current_branch() == 'main':
        drafts = drafts_present()
        if drafts:
            raise SystemExit(
                'jams: refusing to build on main with draft blocks present: '
                + ', '.join(drafts))


# --- occurrence math (JSON-LD startDate) -----------------------------------

def _nth_weekday_dates(year, month, weekday, ns):
    """Dates in (year, month) falling on `weekday` whose ordinal is in `ns`;
    n == -1 means the last such weekday of the month."""
    first = datetime.date(year, month, 1)
    days = []
    d = first + datetime.timedelta(days=(weekday - first.weekday()) % 7)
    while d.month == month:
        days.append(d)
        d += datetime.timedelta(days=7)
    out = []
    for n in ns:
        if n == -1:
            out.append(days[-1])
        elif n - 1 < len(days):
            out.append(days[n - 1])
    return out


def _week_ordinals(rule):
    """'nth:1,3' -> [1, 3]; 'nth:1,last' -> [1, -1]; 'last' -> [-1]."""
    if rule == 'last':
        return [-1]
    return [-1 if x == 'last' else int(x) for x in rule[4:].split(',')]


def next_occurrence(rec, today=None):
    """Next date on or after `today` that day + cadence_rule pin down,
    stepping past any skip_months, or None when they can't: monthly with no
    fixed week, irregular, no fixed day, and a biweekly night with no
    known_date to say which week it's on."""
    today = today or datetime.date.today()
    day = rec.get('day')
    rule = rec.get('cadence_rule') or ''
    skip = set(rec.get('skip_months') or [])
    if day not in DAYS:
        return None
    weekday = DAYS.index(day)
    if rule in ('weekly', 'biweekly'):
        if rule == 'weekly':
            first, step = today + datetime.timedelta(days=(weekday - today.weekday()) % 7), 7
        else:
            known = parse_date(rec.get('known_date'))
            if not known or known.weekday() != weekday:
                return None
            first, step = known + datetime.timedelta(days=14 * -((known - today).days // 14)), 14
        for i in range(60):
            d = first + datetime.timedelta(days=step * i)
            if d.month not in skip:
                return d
        return None
    if rule == 'last' or rule.startswith('nth:'):
        ns = _week_ordinals(rule)
        y, m = today.year, today.month
        for _ in range(14):
            if m not in skip:
                hits = sorted(d for d in _nth_weekday_dates(y, m, weekday, ns) if d >= today)
                if hits:
                    return hits[0]
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return None


# ===========================================================================
# Render layer (hooked from build.py)
# ===========================================================================

def _env():
    if 'env' not in _cache:
        import jinja2
        _cache['env'] = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TEMPLATES),
            autoescape=True, trim_blocks=True, lstrip_blocks=True,
            undefined=jinja2.StrictUndefined)
    return _cache['env']


def _script_json(obj, indent=None):
    """JSON for an inline <script> block: markup-significant characters are
    unicode-escaped so no literal '</script' can appear (the same posture as
    build.py's _ldjson)."""
    text = json.dumps(obj, indent=indent, ensure_ascii=False,
                      separators=None if indent else (',', ':'))
    return (text.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            .replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))


def _markup(s):
    from markupsafe import Markup
    return Markup(s)


def _asset_version(rel):
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return '0'
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def display_date(d):
    return f'{d.strftime("%b")} {d.day}, {d.year}'


def _display_month(d):
    return f'{d.strftime("%b")} {d.year}'


def _time_minutes(s):
    m = re.match(r'\s*(\d{1,2}):(\d{2})\s*([AP]M)', s or '', re.I)
    if not m:
        return None
    h = int(m.group(1)) % 12
    if m.group(3).upper() == 'PM':
        h += 12
    return h * 60 + int(m.group(2))


def _time_24(s):
    mins = _time_minutes(s)
    return None if mins is None else f'{mins // 60:02d}:{mins % 60:02d}'


def skill_band(skill):
    if skill in (1, 2):
        return '1-2'
    if skill == 3:
        return '3'
    if skill in (4, 5):
        return '4-5'
    return None


def _cap_first(s):
    return s[:1].upper() + s[1:] if s else s


def when_line(rec):
    """'Tuesdays, 9:30 PM to 1:30 AM, weekly' (handoff 6.1). The cadence
    text renders whole, caveats included; when it already names the day it
    leads the line instead of repeating it."""
    w = strings()['when']
    day = rec.get('day')
    cadence = (rec.get('cadence') or '').strip()
    start, end = rec.get('start'), rec.get('end')
    if start and end:
        times = w['time_range'].format(start=start, end=end)
    elif start:
        times = w['time_from'].format(start=start)
    else:
        times = ''
    if day in DAYS and day.lower() not in cadence.lower():
        parts = [f'{day}s', times, cadence]
    else:
        parts = [_cap_first(cadence) or w['dates_vary'], times]
    return ', '.join(p for p in parts if p)


def when_parts(rec):
    """The card's when band: which nights ('Tuesdays, weekly', or the
    cadence text when it names the day itself) and the times, kept apart so
    the start time can lead."""
    w = strings()['when']
    day = rec.get('day')
    cadence = (rec.get('cadence') or '').strip()
    if day in DAYS and day.lower() not in cadence.lower():
        days = ', '.join(p for p in (f'{day}s', cadence) if p)
    else:
        days = _cap_first(cadence) or w['dates_vary']
    return {'days': days, 'start': rec.get('start') or '', 'end': rec.get('end') or '',
            'to': w['to_word'], 'from': w['from_word']}


# Facts short enough to read as a tile ("5:30 PM", "Free", "16+"); longer
# ones stay rows.
GLANCE_MAX_CHARS = 16


def _sort_key(rec):
    mins = _time_minutes(rec.get('start'))
    return (mins if mins is not None else 24 * 60, (rec.get('name') or '').lower())


def day_key(rec):
    day = rec.get('day')
    return DAY_KEYS[DAYS.index(day)] if day in DAYS else 'varies'


def group_by_night(recs):
    """[(label, key, [recs])] Monday..Sunday then Varies, each sorted by
    start time then name; empty nights are skipped (handoff 4.4)."""
    labels = strings()['labels']
    groups = []
    for day, key in list(zip(DAYS, DAY_KEYS)) + [(labels['varies'], 'varies')]:
        members = [r for r in recs if day_key(r) == key]
        if members:
            groups.append((day, key, sorted(members, key=_sort_key)))
    return groups


# --- built-page math ---------------------------------------------------------

def genre_page_listings(key, pub):
    return [r for r in pub if key in pages_for_listing(r)]


def area_page_listings(key, pub):
    return [r for r in pub if area_for(r) == key]


def built_genre_keys(today=None):
    pub = published(today)
    return {k for k, _ in genre_pages()
            if len(genre_page_listings(k, pub)) >= MIN_PAGE_LISTINGS}


def built_area_keys(today=None):
    pub = published(today)
    return {a['key'] for a in areas()
            if len(area_page_listings(a['key'], pub)) >= MIN_PAGE_LISTINGS}


def page_is_built(spec, today=None):
    """build.py asks this when writing the sitemap, so skipped pages never
    appear in it (handoff 4.5)."""
    t = spec.get('type')
    if t in ('hub', 'guide'):
        return True
    if t in ('genre', 'format'):
        return spec.get('key') in built_genre_keys(today)
    if t == 'area':
        return spec.get('key') in built_area_keys(today)
    return False


# --- card view-model ---------------------------------------------------------

def _gear_flag(backline):
    if not backline:
        return False
    low = backline.lower()
    return not (low.startswith('pa only') or 'no backline' in low)


def _allages_flag(age):
    low = (age or '').lower()
    return 'all ages' in low or 'family' in low


def _skill_link(rec, prefix, built_genres):
    """Where the card's skill line points: the prep section on the night's
    page (open-mics first for mics and songwriter nights, else the first
    mapped genre page), or the guide's definitions when no page is built."""
    band = skill_band(rec.get('skill'))
    anchor = f'#prep-{band}' if band else '#prep'
    page_keys = pages_for_listing(rec)
    if rec.get('format') != 'jam':
        page_keys = ['open-mics'] + [k for k in page_keys if k != 'open-mics']
    for key in page_keys:
        if key in built_genres:
            return f'{prefix}jams/{key}/{anchor}'
    return f'{prefix}jams/first-jam/#skill-levels'


def _confirmed_line(rec):
    """Footer line (handoff 6.1). The newer of verified_date and
    firsthand_date wins. A firsthand date with Daniel's own notes reads
    'Daniel was there'; a bare firsthand date is a confirmation Daniel gave,
    not a visit, and reads 'by Daniel'."""
    c = strings()['confirmed']
    v_date = parse_date(rec.get('verified_date'))
    fh_date = parse_date(rec.get('firsthand_date'))
    if fh_date and (not v_date or fh_date > v_date):
        key = 'daniel_was_there' if rec.get('firsthand_notes') else 'by_daniel'
        return c[key].format(date=display_date(fh_date))
    how = VERIFIED_HOW_DISPLAY.get(rec.get('verified_how'))
    if how:
        return c['from_source'].format(date=display_date(v_date), how=how)
    return c['plain'].format(date=display_date(v_date))


def card_ctx(rec, prefix, built_genres):
    s = strings()
    labels = s['labels']
    fmt_label = s['formats'].get(rec.get('format'), rec.get('format'))
    # Quick facts render as tiles when short, the rest as rows; the order
    # within each matches handoff 6.1's "How it works".
    glance, facts = [], []

    def place(label, value):
        (glance if len(value) <= GLANCE_MAX_CHARS else facts).append((label, _cap_first(value)))

    signup_time, signup_method = rec.get('signup_time'), rec.get('signup_method')
    if signup_time and len(signup_time) <= GLANCE_MAX_CHARS:
        glance.append((labels['signup'], signup_time))
        if signup_method:
            facts.append((labels['signup_how'], _cap_first(signup_method)))
    elif signup_time or signup_method:
        facts.append((labels['signup'], ', '.join(p for p in (signup_time, signup_method) if p)))
    if rec.get('host'):
        facts.append((labels['host'], rec['host']))
    if rec.get('house_band') is True:
        glance.append((labels['house_band'], labels['yes_word']))
    elif rec.get('house_band') is False:
        glance.append((labels['house_band'], labels['no_word']))
    if rec.get('backline'):
        facts.append((labels['gear'], _cap_first(rec['backline'])))
    for field in ('cover', 'age'):
        if rec.get(field):
            place(labels[field], rec[field])
    for field in ('parking', 'transit'):
        if rec.get(field):
            facts.append((labels[field], _cap_first(rec[field])))
    notes = [rec[k] for k in ('notes_instrumentalists', 'notes_singers', 'notes_songwriters')
             if rec.get(k)]
    # Links, grouped by whose they are (handoff 6.1): the night's own first,
    # then the host's, then the venue's, each owner's website after its
    # social accounts; a third-party event page comes last.
    links = []
    if rec.get('song_list_url'):
        links.append({'href': rec['song_list_url'], 'label': labels['song_list']})
    owner = {'jam': fmt_label, 'host': labels['owner_host'], 'venue': labels['owner_venue']}
    sites = {}
    if rec.get('website'):
        sites[rec.get('website_whose') or 'venue'] = rec['website']
    if rec.get('venue_website'):
        sites.setdefault('venue', rec['venue_website'])
    for who in ('jam', 'host', 'venue'):
        for soc in rec.get('social') or []:
            if soc.get('url') and (soc.get('whose') or 'venue') == who:
                links.append({'href': soc['url'], 'label': f"{owner[who]}'s {soc.get('platform') or 'page'}"})
        if who in sites:
            links.append({'href': sites[who], 'label': f"{owner[who]}'s {labels['website_word']}"})
    if 'listing' in sites:
        links.append({'href': sites['listing'], 'label': labels['event_page']})
    # Two hosts with an Instagram each would read "Host's Instagram" twice:
    # tell them apart by the account name in the link.
    counts = {}
    for link in links:
        counts[link['label']] = counts.get(link['label'], 0) + 1
    for link in links:
        if counts[link['label']] > 1:
            handle = urlparse(link['href']).path.strip('/').split('/')[0]
            if handle:
                link['label'] = f"{link['label']} (@{handle})"
    if rec.get('skill'):
        skill_text = f"{labels['skill']}: {rec['skill']} {labels['of_five']}"
    else:
        skill_text = f"{labels['skill']}: {labels['no_info']}"
    daniel = None
    fh_date = parse_date(rec.get('firsthand_date'))
    if rec.get('firsthand_notes') or rec.get('first_timer_tip'):
        daniel = {'notes': rec.get('firsthand_notes'), 'tip': rec.get('first_timer_tip'),
                  'sig': f'Daniel, {_display_month(fh_date)}' if fh_date else 'Daniel'}
    scene = []
    for q in rec.get('scene') or []:
        if not q.get('quote'):
            continue
        q_date = parse_date(q.get('date'))
        when = _display_month(q_date) if q_date else q.get('date')
        scene.append({'quote': q['quote'], 'url': q.get('url'),
                      'attribution': ', '.join(p for p in (q.get('who'), q.get('where'), when) if p)})
    # Photos from the night lead, the venue's follow (a stable sort keeps each
    # group in its listed order). <slug>-<n>-lg.jpg, when present, is the
    # large copy the photo opens to.
    photos = []
    for p in sorted(rec.get('photos') or [], key=lambda p: p.get('kind') == 'venue'):
        f = p.get('file') or ''
        if f and os.path.exists(os.path.join(REPO, 'img', 'jams', f)):
            stem, ext = os.path.splitext(f)
            lg = f'{stem}-lg{ext}'
            full = lg if os.path.exists(os.path.join(REPO, 'img', 'jams', lg)) else f
            photos.append({'src': f'{prefix}img/jams/{f}', 'full': f'{prefix}img/jams/{full}',
                           'alt': p.get('alt') or f"{rec.get('name')}, {rec.get('venue')}",
                           'credit': p.get('credit'), 'source_url': p.get('source_url'),
                           'focus': p.get('focus') if PHOTO_FOCUS.fullmatch(p.get('focus') or '') else None})
    genre_keys = [k for k in pages_for_listing(rec) if k != 'open-mics']
    # js/jams.js turns these into "Tonight", "Tomorrow" or "Next: Thu, Nov
    # 12" with the same rules as next_occurrence(); a night whose schedule
    # can't be pinned down gets no line.
    rule = rec.get('cadence_rule') or ''
    dated = bool(rec.get('day') in DAYS and rec.get('status') != 'paused'
                 and (rule == 'weekly' or rule == 'last' or rule.startswith('nth:')
                      or (rule == 'biweekly' and parse_date(rec.get('known_date')))))
    return {
        'r': rec,
        'labels': labels,
        'skill_text': skill_text,
        'skill_n': rec.get('skill') if rec.get('skill') in (1, 2, 3, 4, 5) else None,
        'skill_href': _skill_link(rec, prefix, built_genres),
        'when': when_parts(rec),
        'tags': [fmt_label] + [s['genre_labels'].get(g, g) for g in rec.get('genres') or []],
        'glance': glance,
        'facts': facts,
        'notes': notes,
        'links': links,
        'map_href': 'https://www.google.com/maps/search/?api=1&query='
                    + quote_plus(f"{rec.get('venue') or ''} {rec.get('address') or ''}".strip()),
        'daniel': daniel,
        'scene': scene,
        'photos': photos,
        'confirmed': _confirmed_line(rec),
        'contact_href': f"{prefix}contact/?jam={rec['slug']}",
        'data': {
            'day': day_key(rec),
            'format': FORMAT_SLUG.get(rec.get('format'), 'jam'),
            'genres': ' '.join(genre_keys),
            'area': area_for(rec) or '',
            'skill': str(rec['skill']) if rec.get('skill') else 'none',
            'houseband': '1' if rec.get('house_band') is True else '0',
            'gear': '1' if _gear_flag(rec.get('backline')) else '0',
            'songlist': '1' if rec.get('song_list_url') else '0',
            'allages': '1' if _allages_flag(rec.get('age')) else '0',
        },
        'next': {
            'rule': rule,
            'known': rec.get('known_date') or '',
            'skip': ','.join(str(m) for m in rec.get('skip_months') or []),
        } if dated else None,
    }


# --- JSON-LD (handoff section 10) -------------------------------------------

_ADDRESS_RE = re.compile(r'^(?P<street>.+?),\s*(?P<city>[^,]+),\s*(?P<state>[A-Z]{2})\s+(?P<zip>\d{5})(?:-\d{4})?$')
_ORG_WORDS = re.compile(r'\b(the|band|trio|quartet|collective|productions?|poetry|night|sessions?|'
                        r'music|society|club|theatre|theater|house|colorado|catz|honey|lillies|'
                        r'immersive|friends|holler|thieves|obsession|grass|lizards|rockers|'
                        r'school|district|instructors|people)\b', re.I)
_PERSON_RE = re.compile(r'^[A-Z][a-z][a-zA-Z\'.-]*(?: (?:"[^"]+"|[A-Z][a-zA-Z\'.-]+)){0,3}$')


def _postal_address(rec):
    addr = (rec.get('address') or '').strip()
    m = _ADDRESS_RE.match(addr)
    if not m:
        return {'@type': 'PostalAddress', 'streetAddress': addr}
    return {'@type': 'PostalAddress', 'streetAddress': m.group('street'),
            'addressLocality': m.group('city').strip(), 'addressRegion': m.group('state'),
            'postalCode': m.group('zip'), 'addressCountry': 'US'}


def _organizer(host):
    """Person, a list of Persons ('Phil and Alex'), or Organization for a
    host string; None when the field describes rather than names ('rotating
    weekly host'). Research annotations in parentheses stay out of the
    machine-readable name."""
    name = re.sub(r'\s*\([^)]*\)', '', host or '').strip()
    if not name or name[0].islower() or name.startswith('@'):
        return None
    parts = [p for p in re.split(r'\s+and\s+|\s*&\s*|\s*[,;/]\s*', name) if p]

    def is_person(p):
        return not _ORG_WORDS.search(p) and _PERSON_RE.match(p)

    if len(parts) > 1 and all(is_person(p) for p in parts):
        return [{'@type': 'Person', 'name': p} for p in parts]
    if len(parts) == 1 and is_person(name):
        return {'@type': 'Person', 'name': name}
    return {'@type': 'Organization', 'name': name}


def _start_iso(date, start):
    mins = _time_minutes(start)
    if mins is None:
        return date.isoformat()
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('America/Denver')
    except Exception:
        return date.isoformat()
    return datetime.datetime(date.year, date.month, date.day,
                             mins // 60, mins % 60, tzinfo=tz).isoformat()


def _is_free(cover):
    low = (cover or '').strip().lower()
    return low.startswith('free') or (low.startswith('no cover') and 'stated' not in low)


def event_items(recs, today=None):
    """Event objects for the listings whose next date can be computed."""
    today = today or datetime.date.today()
    fmt = strings()['formats']
    items = []
    for rec in recs:
        rule = rec.get('cadence_rule') or ''
        if rule in ('monthly', 'irregular'):
            continue
        start_date = next_occurrence(rec, today)
        if not start_date:
            continue
        ev = {
            '@type': 'Event',
            'name': rec.get('name'),
            'description': f"{fmt.get(rec.get('format'), 'Night')} at {rec.get('venue')} "
                           f"in {rec.get('city')}: {when_line(rec)}.",
            'startDate': _start_iso(start_date, rec.get('start')),
            'eventAttendanceMode': 'https://schema.org/OfflineEventAttendanceMode',
            'eventStatus': 'https://schema.org/EventScheduled',
            'url': f"{SITE_URL}/jams/#{rec['slug']}",
            'location': {'@type': 'Place', 'name': rec.get('venue'),
                         'address': _postal_address(rec)},
        }
        org = _organizer(rec.get('host'))
        if org:
            ev['organizer'] = org
        schedule = {'@type': 'Schedule', 'byDay': f"https://schema.org/{rec['day']}",
                    'repeatFrequency': {'weekly': 'P1W', 'biweekly': 'P2W'}.get(rule, 'P1M'),
                    'scheduleTimezone': 'America/Denver'}
        if rule.startswith('nth:') and 'last' not in rule:
            weeks = _week_ordinals(rule)
            schedule['byMonthWeek'] = weeks[0] if len(weeks) == 1 else weeks
        st, en = _time_24(rec.get('start')), _time_24(rec.get('end'))
        if st:
            schedule['startTime'] = st
        if en:
            schedule['endTime'] = en
        ev['eventSchedule'] = schedule
        if _is_free(rec.get('cover')):
            ev['isAccessibleForFree'] = True
        items.append(ev)
    return items


def _jsonld(recs, today):
    items = event_items(recs, today)
    if not items:
        return ''
    item_list = {'@context': 'https://schema.org', '@type': 'ItemList',
                 'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'item': ev}
                                     for i, ev in enumerate(items)]}
    return f'<script type="application/ld+json">{_script_json(item_list)}</script>'


# --- page rendering ----------------------------------------------------------

def _paragraphs(text):
    return [' '.join(p.split()) for p in re.split(r'\n\s*\n', (text or '').strip()) if p.strip()]


def _render_list(recs, prefix, built_genres, live=False):
    groups = [(label, key, [card_ctx(r, prefix, built_genres) for r in members])
              for label, key, members in group_by_night(recs)]
    return _env().get_template('list.html').render(
        groups=groups, live=live, labels=strings()['labels'], count=len(recs),
        next_tpl=strings()['when']['next'], photos_note=strings()['photos_note'],
        has_photos=any(c['photos'] for _, _, cards in groups for c in cards),
        contact_href=f'{prefix}contact/')


def _prep_ctx(cfg, prefix):
    """Instruments Daniel teaches get the block's lessons line and a link to
    the lesson page; every other block gets the teacher-referral line (open
    decision 4, Daniel 2026-10-27)."""
    lesson_links = strings()['lesson_links']
    blocks = []
    for block in cfg.get('prep') or []:
        page = block.get('lesson_page')
        if page and page not in lesson_links:
            raise SystemExit(f'jams: lesson_page {page!r} is not an instrument Daniel teaches')
        blocks.append({'label': block['label'], 'levels': block['levels'],
                       'lessons': block.get('lessons') if page else None,
                       'lesson_href': f'{prefix}{page}' if page else f'{prefix}contact/',
                       'lesson_label': lesson_links.get(page) if page else None})
    return blocks


def _cta_html(prefix, ground, material=None, guide_link=True, draft=False):
    s = strings()
    c = s['cta']
    body = c['body_before_material'] + (material or c['material']) + c['body_after_material']
    return _env().get_template('cta.html').render(
        cta=c, body=body, prefix=prefix, ground=ground, guide_link=guide_link,
        draft=draft, labels=s['labels'])


def render_page(spec, nav_prefix):
    """The page body for a jams page config, or None when the page is under
    the listing threshold and must not be built (handoff section 2)."""
    refuse_drafts_on_main()
    today = datetime.date.today()
    pub = published(today)
    built_genres = built_genre_keys(today)
    s = strings()
    env = _env()
    t = spec.get('type')
    common = {'s': s, 'labels': s['labels'], 'prefix': nav_prefix,
              'js_src': f"{nav_prefix}js/jams.js?v={_asset_version('js/jams.js')}"}

    if t == 'hub':
        built_areas = built_area_keys(today)
        browse_genres = [{'href': f'{nav_prefix}jams/{k}/', 'name': cfg['name'],
                          'count': len(genre_page_listings(k, pub))}
                         for k, cfg in genre_pages() if k in built_genres]
        browse_areas = [{'href': f"{nav_prefix}jams/{a['key']}/", 'name': a['name'],
                         'count': len(area_page_listings(a['key'], pub))}
                        for a in areas() if a['key'] in built_areas]
        genre_filters = [{'key': k, 'name': cfg['name']} for k, cfg in genre_pages()
                         if k != 'open-mics' and genre_page_listings(k, pub)]
        area_filters = [{'key': a['key'], 'name': a['name']} for a in areas()
                        if area_page_listings(a['key'], pub)]
        pins = [{'slug': r['slug'], 'name': r['name'], 'venue': r['venue'],
                 'when': when_line(r), 'lat': r['lat'], 'lng': r['lng']}
                for r in pub if r.get('lat') is not None and r.get('lng') is not None]
        labels = s['labels']
        stats = [(len(pub), labels['night_many']),
                 (len({(r.get('venue') or '').lower().strip() for r in pub}), labels['venue_many']),
                 (len({r.get('city') for r in pub}), labels['town_many'])]
        return env.get_template('hub.html').render(
            **common, count=len(pub), stats=stats,
            intro=s['hub']['intro'].format(count=len(pub), days=PUBLISH_WINDOW_DAYS),
            filters_html=_markup(env.get_template('filters.html').render(
                s=s, labels=s['labels'], count=len(pub),
                genre_filters=genre_filters, area_filters=area_filters)),
            list_html=_markup(_render_list(pub, nav_prefix, built_genres, live=True)),
            map_html=_markup(env.get_template('map.html').render(
                s=s, pins_json=_markup(_script_json(pins)))) if pins else '',
            browse_genres=browse_genres, browse_areas=browse_areas,
            cta_html=_markup(_cta_html(nav_prefix, 'dark', guide_link=False)),
            jsonld=_markup(_jsonld(pub, today)))

    if t in ('genre', 'format'):
        key = spec['key']
        cfg = genre_cfg(key)
        if cfg is None:
            raise SystemExit(f'jams: no genres.yaml entry for page {key!r}')
        recs = genre_page_listings(key, pub)
        if len(recs) < MIN_PAGE_LISTINGS:
            return None
        see_all = (f'{nav_prefix}jams/?type=open-mic,songwriter-night' if key == 'open-mics'
                   else f'{nav_prefix}jams/?genre={key}')
        return env.get_template('genre.html').render(
            **common, cfg=cfg, count=len(recs), draft=bool(cfg.get('draft')),
            eyebrow=s['genre_page']['eyebrow'].format(name=cfg['name']),
            list_html=_markup(_render_list(recs, nav_prefix, built_genres)),
            prep_html=_markup(env.get_template('prep.html').render(
                s=s, labels=s['labels'], cfg=cfg, prefix=nav_prefix,
                draft=bool(cfg.get('draft')), blocks=_prep_ctx(cfg, nav_prefix))),
            see_all=see_all,
            cta_html=_markup(_cta_html(nav_prefix, 'light', material=cfg.get('cta_material'),
                                       draft=bool(cfg.get('draft')))),
            jsonld=_markup(_jsonld(recs, today)))

    if t == 'area':
        key = spec['key']
        area = next((a for a in areas() if a['key'] == key), None)
        if area is None:
            raise SystemExit(f'jams: no areas.yaml entry for page {key!r}')
        recs = area_page_listings(key, pub)
        if len(recs) < MIN_PAGE_LISTINGS:
            return None
        return env.get_template('area.html').render(
            **common, area=area, count=len(recs), draft=bool(area.get('draft')),
            eyebrow=s['area_page']['eyebrow'].format(name=area['name']),
            sub=s['area_page']['sub'].format(days=PUBLISH_WINDOW_DAYS),
            list_html=_markup(_render_list(recs, nav_prefix, built_genres)),
            see_all=f'{nav_prefix}jams/?area={key}',
            cta_html=_markup(_cta_html(nav_prefix, 'dark')),
            jsonld=_markup(_jsonld(recs, today)))

    if t == 'guide':
        g = s['guide']
        sections = [{'heading': sec['heading'], 'paras': _paragraphs(sec['body'])}
                    for sec in g['sections']]
        return env.get_template('guide.html').render(
            **common, guide=g, draft=bool(g.get('draft')), sections=sections,
            open_mic_paras=_paragraphs(g['open_mic_body']),
            skill_levels=s['skill_levels'],
            cta_html=_markup(_cta_html(nav_prefix, 'dark', guide_link=False)))

    raise SystemExit(f'jams: unknown jams_page type {t!r}')


# --- build-wide outputs -------------------------------------------------------

def llms_section(today=None):
    """The Jams block for llms.txt: hub, each built genre and area page, the
    guide (handoff 4.5)."""
    today = today or datetime.date.today()
    s = strings()
    hub_line = ' '.join(s['llms']['hub'].split()).format(days=PUBLISH_WINDOW_DAYS)
    lines = [f"- [{s['hub']['h1']}]({SITE_URL}/jams/): {hub_line}"]
    built_g, built_a = built_genre_keys(today), built_area_keys(today)
    for k, cfg in genre_pages():
        if k in built_g:
            lines.append(f"- [{cfg['h1']}]({SITE_URL}/jams/{k}/): {s['llms']['genre']}")
    for a in areas():
        if a['key'] in built_a:
            towns = ', '.join(a['towns'][:-1]) + ' and ' + a['towns'][-1] if len(a['towns']) > 1 else a['towns'][0]
            lines.append(f"- [{a['h1']}]({SITE_URL}/jams/{a['key']}/): "
                         + s['llms']['area'].format(towns=towns))
    lines.append(f"- [{s['guide']['h1']}]({SITE_URL}/jams/first-jam/): {s['llms']['guide']}")
    return '\n## Jams\n\n' + '\n'.join(lines) + '\n'


def write_contact_js(today=None):
    """js/jams-contact.js: ?jam=<slug> prefills the contact note with the
    night's name and venue (handoff 6.5). Published slugs only."""
    entries = {r['slug']: f"{r['name']} at {r['venue']}" for r in published(today)}
    js = (
        '// Written by the build (jams directory). With ?jam=<slug> in the query\n'
        '// string, the note opens addressed to that night. Published slugs only.\n'
        '(function () {\n'
        '  var NIGHTS = ' + _script_json(entries) + ';\n'
        "  var slug = new URLSearchParams(window.location.search).get('jam');\n"
        '  if (!slug || !Object.prototype.hasOwnProperty.call(NIGHTS, slug)) return;\n'
        "  var field = document.querySelector('textarea[name=\"message\"]');\n"
        "  if (field && !field.value) field.value = 'About ' + NIGHTS[slug] + ': ';\n"
        '})();\n'
    )
    path = os.path.join(REPO, 'js', 'jams-contact.js')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(js)
    return path


def print_aging_report(today=None):
    """The monthly to-do list (handoff 4.3): what published, what was held
    and why, and what drops off within 14 days."""
    today = today or datetime.date.today()
    states = {}
    for r in listings():
        states.setdefault(publish_state(r, today), []).append(r)
    pub = states.get('published', [])
    print('\nJams aging report:')
    print(f'  published: {len(pub)} of {len(listings())} '
          f'(window {PUBLISH_WINDOW_DAYS} days, build date {today})')
    for reason in ('stale', 'unverified', 'no_address', 'ended', 'hidden'):
        if states.get(reason):
            print(f'  held, {reason}: {len(states[reason])}')
    horizon = today - datetime.timedelta(days=PUBLISH_WINDOW_DAYS - 14)
    dropping = sorted((confirmation_date(r), r['slug']) for r in pub
                      if confirmation_date(r) <= horizon)
    if dropping:
        print(f'  drops off within 14 days ({len(dropping)}):')
        for d, slug in dropping:
            gone = d + datetime.timedelta(days=PUBLISH_WINDOW_DAYS + 1)
            print(f'    {slug}: last confirmed {d}, off the site {gone}')
    else:
        print('  drops off within 14 days: none')
