#!/usr/bin/env python3
"""Geocode jams listings into the match list, ../jams-data/jams.json (handoff 6.4).

Run by hand, never at build time:

    python3 scripts/geocode_jams.py [--dry-run] [--limit N]

Looks addresses up with the public Nominatim API (OpenStreetMap) at no more
than one request per second, with a descriptive User-Agent, per its usage
policy. Skips listings that already have coordinates, and ended or hidden
ones. A result outside the Front Range is rejected rather than trusted.
Writes lat/lng back after each hit, so an interrupted run keeps its
progress. Prints every address it couldn't place.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get('JAMS_DATA') or os.path.join(os.path.dirname(REPO), 'jams-data', 'jams.json')
ENDPOINT = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'foxlessons-jams-geocoder/1.0 (+https://foxlessons.com/contact/)'
MIN_INTERVAL = 1.1  # seconds between requests; the policy maximum is 1/s
# Fort Collins to south of Castle Rock, the high foothills to the plains.
LAT_RANGE, LNG_RANGE = (38.9, 40.8), (-105.9, -104.0)

UNIT = re.compile(r',?\s*(?:suite|ste\.?|unit|apt\.?|bldg\.?|building|#)\s*[\w-]+', re.I)
ADDRESS = re.compile(r'^(?P<street>.+?),\s*(?P<city>[^,]+),\s*(?P<state>[A-Z]{2})\s*(?P<zip>\d{5})?')

_last_request = [0.0]


class StopRun(Exception):
    pass


def lookup(params):
    """(lat, lng), 'outside' for a hit beyond the Front Range, or None."""
    wait = MIN_INTERVAL - (time.monotonic() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    query = dict(params, format='jsonv2', limit='1', countrycodes='us')
    req = urllib.request.Request(f'{ENDPOINT}?{urllib.parse.urlencode(query)}',
                                 headers={'User-Agent': USER_AGENT, 'Accept-Language': 'en'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            hits = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise StopRun(f'Nominatim answered {e.code}; stopping to respect its limits')
        raise
    finally:
        _last_request[0] = time.monotonic()
    if not hits:
        return None
    lat, lng = float(hits[0]['lat']), float(hits[0]['lon'])
    if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LNG_RANGE[0] <= lng <= LNG_RANGE[1]):
        return 'outside'
    return round(lat, 6), round(lng, 6)


def full_address(rec):
    """The address as stored, with the listing's own city and state added
    when the stored address stops at the street number and name."""
    address = rec['address'].strip()
    if not ADDRESS.match(address) and rec.get('city'):
        address = f"{address}, {rec['city']}, CO"
    return address


def attempts(address):
    """The full address, then without a suite or unit, then structured."""
    yield {'q': address}
    bare = UNIT.sub('', address).strip(' ,')
    if bare != address:
        yield {'q': bare}
    m = ADDRESS.match(bare)
    if m:
        params = {'street': m.group('street').split(',')[-1].strip(),
                  'city': m.group('city').strip(), 'state': m.group('state')}
        if m.group('zip'):
            params['postalcode'] = m.group('zip')
        yield params


def save(data):
    tmp = DATA + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    os.replace(tmp, DATA)


def main():
    dry = '--dry-run' in sys.argv
    limit = None
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
    with open(DATA, encoding='utf-8') as f:
        data = json.load(f)
    todo = [r for r in data['listings']
            if r.get('lat') is None and (r.get('address') or '').strip()
            and r.get('status') != 'ended' and not r.get('hide')]
    print(f'{len(todo)} listings need coordinates.')
    found, failed, cache, lookups = 0, [], {}, 0
    try:
        for r in todo:
            address = full_address(r)
            if address not in cache:
                result = None
                for params in attempts(address):
                    if limit is not None and lookups >= limit:
                        raise StopRun(f'--limit {limit} reached')
                    lookups += 1
                    result = lookup(params)
                    if isinstance(result, tuple):
                        break
                cache[address] = result
            result = cache[address]
            if isinstance(result, tuple):
                r['lat'], r['lng'] = result
                found += 1
                print(f'  ok   {r["slug"]}: {result[0]}, {result[1]}')
                if not dry:
                    save(data)
            else:
                why = 'outside the Front Range' if result == 'outside' else 'no match'
                failed.append((r['slug'], address, why))
    except StopRun as e:
        print(f'\nStopped: {e}')
    print(f'\n{found} placed, {len(failed)} not placed, {lookups} requests.')
    if failed:
        print('Couldn\'t place:')
        for slug, address, why in failed:
            print(f'  {slug}: {address} ({why})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
