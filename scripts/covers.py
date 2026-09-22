#!/usr/bin/env python3
"""Cover-art modules for the instrument pages (drums, guitar, bass, piano).

One source of truth: the MANIFEST below holds every module (eyebrow, h2, intro
copy) and every cover (player credit, act, album, iTunes search hints).

    python3 scripts/covers.py pull    # fetch art via the iTunes Search API
                                      #   -> img/covers/<page>/<slug>.jpg (600x600)
                                      #   -> img/covers/SOURCES.md (provenance)
    python3 scripts/covers.py emit    # write _src/pages/<page>/sections/02-covers.html
    python3 scripts/covers.py pull --force   # re-download existing files too

Pull is idempotent (existing files are skipped) and prints a match report so
every hit can be eyeballed: page/slug -> matched artist | collection. A cover
that can't be confidently matched is SKIPPED and flagged, never guessed.

Art source: Deezer album search (no key, liberal rate limits), cover_big
500x500 — plenty for ~170-260px display tiles at 2x. iTunes Search API is the
fallback (it 403s bursts from scripts, so it's tried once, politely). Editorial
use on lesson pages; provenance (source + id) recorded in SOURCES.md.
"""

import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COVERS_DIR = os.path.join(ROOT, 'img', 'covers')
SEARCH_URL = 'https://itunes.apple.com/search?{q}'
# The search API 403s non-browser UAs from python; a plain browser UA passes.
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15'}


def C(slug, player, act, album, search=None, match_artist=None, match_album=None,
      deezer_id=None):
    """One cover. player = the credit line (why this record is on this page),
    act = the name on the spine, album = display title (short, no reissue tags).
    deezer_id pins a specific Deezer album when search can't surface the real
    release (e.g. buried under tribute records)."""
    return {
        'slug': slug, 'player': player, 'act': act, 'album': album,
        'search': search or f'{act} {album}',
        'match_artist': match_artist or act,
        'match_album': match_album or album,
        'deezer_id': deezer_id,
    }


MANIFEST = {
    'drums': [
        {
            'eyebrow': 'The play-along shelf',
            'h2': 'The records from the basement.',
            'intro': "The story above is real, so here's the actual shelf. The box set, the Beatles, and the two that showed up a few years later. Put one on, put headphones on, and play along. Then bring it to a lesson and we'll work on what your ears missed.",
            'covers': [
                C('led-zeppelin-iv', 'John Bonham', 'Led Zeppelin', 'Led Zeppelin IV'),
                C('abbey-road', 'Ringo Starr', 'The Beatles', 'Abbey Road'),
                C('core', 'Eric Kretz', 'Stone Temple Pilots', 'Core'),
                C('ten', 'Dave Krusen', 'Pearl Jam', 'Ten'),
            ],
        },
        {
            'eyebrow': 'Rock, four decades of it',
            'h2': 'Drummers who serve the song.',
            'intro': "Different eras, same job: make the band feel good. Moon plays wild, Copeland plays tight, Barker plays fast, and every one of them plays for the song. Pick the one that sounds like where you want to go, and we'll start there.",
            'covers': [
                C('whos-next', 'Keith Moon', 'The Who', "Who's Next"),
                C('nevermind', 'Dave Grohl', 'Nirvana', 'Nevermind', deezer_id=1252978),
                C('moving-pictures', 'Neil Peart', 'Rush', 'Moving Pictures'),
                C('synchronicity', 'Stewart Copeland', 'The Police', 'Synchronicity'),
                C('lateralus', 'Danny Carey', 'Tool', 'Lateralus'),
                C('enema-of-the-state', 'Travis Barker', 'blink-182', 'Enema of the State'),
            ],
        },
        {
            'eyebrow': 'Pocket and groove',
            'h2': 'Where the pocket lives.',
            'intro': "Funk, soul, and hip-hop are the deepest listening a drummer can do. Most of it sounds simple and none of it is easy, which is the point. This is the shelf that teaches time and feel.",
            'covers': [
                C('in-the-jungle-groove', 'Clyde Stubblefield', 'James Brown', 'In the Jungle Groove'),
                C('green-onions', 'Al Jackson Jr.', "Booker T. & The M.G.'s", 'Green Onions',
                  search='booker t green onions', match_artist='booker t'),
                C('aja', 'Steve Gadd and Bernard Purdie', 'Steely Dan', 'Aja'),
                C('things-fall-apart', 'Questlove', 'The Roots', 'Things Fall Apart'),
                C('the-glamorous-life', 'Sheila E.', 'Sheila E.', 'The Glamorous Life'),
                C('malibu', 'Anderson .Paak', 'Anderson .Paak', 'Malibu', match_artist='paak'),
            ],
        },
        {
            'eyebrow': 'Swing and the source',
            'h2': "I don't teach jazz drumming. Hear it anyway.",
            'intro': "The honest scope from up the page holds: jazz drumming is not what I teach. Listen to it anyway, because this is where groove came from, and it will change how you hear everything else on this page.",
            'covers': [
                C('carnegie-hall-1938', 'Gene Krupa', 'Benny Goodman', 'Carnegie Hall, 1938',
                  search='benny goodman carnegie hall 1938', match_album='Carnegie Hall',
                  deezer_id=6942624),
                C('moanin', 'Art Blakey', "Art Blakey & The Jazz Messengers", "Moanin'",
                  search='art blakey moanin', match_artist='blakey'),
                C('a-love-supreme', 'Elvin Jones', 'John Coltrane', 'A Love Supreme'),
                C('big-swing-face', 'Buddy Rich', 'Buddy Rich', 'Big Swing Face'),
                C('we-like-it-here', 'Larnell Lewis', 'Snarky Puppy', 'We Like It Here'),
            ],
        },
    ],

    'guitar': [
        {
            'eyebrow': 'Jazz and melody',
            'h2': 'Where guitar lives for me.',
            'intro': "Guitar is my instrument for exploring jazz and melody, and these five are the deep end of that. Warm tone, clear lines, chords that tell you exactly what they're doing. If we work on jazz together, this is the listening.",
            'covers': [
                C('idle-moments', 'Grant Green', 'Grant Green', 'Idle Moments'),
                C('incredible-jazz-guitar', 'Wes Montgomery', 'Wes Montgomery', 'The Incredible Jazz Guitar of Wes Montgomery'),
                C('djangology', 'Django Reinhardt', 'Django Reinhardt', 'Djangology'),
                C('breezin', 'George Benson', 'George Benson', "Breezin'"),
                C('virtuoso', 'Joe Pass', 'Joe Pass', 'Virtuoso'),
            ],
        },
        {
            'eyebrow': 'The rock canon',
            'h2': 'The reason most people pick up a guitar.',
            'intro': "Somebody on this shelf is why you're here. That's not a guess, it's just the odds. Every one of these records has songs we can start on early, from chord charts and by ear.",
            'covers': [
                C('are-you-experienced', 'Jimi Hendrix', 'The Jimi Hendrix Experience', 'Are You Experienced',
                  search='jimi hendrix are you experienced', match_artist='hendrix'),
                C('van-halen', 'Eddie Van Halen', 'Van Halen', 'Van Halen'),
                C('appetite-for-destruction', 'Slash', "Guns N' Roses", 'Appetite for Destruction'),
                C('master-of-puppets', 'James Hetfield and Kirk Hammett', 'Metallica', 'Master of Puppets',
                  deezer_id=51188172),
                C('purple-rain', 'Prince', 'Prince', 'Purple Rain', match_artist='prince'),
                C('american-beauty', 'Jerry Garcia', 'Grateful Dead', 'American Beauty'),
            ],
        },
        {
            'eyebrow': 'Blues and roots',
            'h2': 'Three chords, all the feeling.',
            'intro': "Everything on the rock shelf came from this one. A few chords in, blues turns into real music faster than anything else I teach, and Sister Rosetta Tharpe had the whole thing figured out before rock and roll had a name.",
            'covers': [
                C('king-of-the-delta-blues', 'Robert Johnson', 'Robert Johnson', 'King of the Delta Blues Singers'),
                C('live-at-the-regal', 'B.B. King', 'B.B. King', 'Live at the Regal'),
                C('texas-flood', 'Stevie Ray Vaughan', 'Stevie Ray Vaughan & Double Trouble', 'Texas Flood',
                  search='stevie ray vaughan texas flood', match_artist='stevie ray vaughan'),
                C('gospel-train', 'Sister Rosetta Tharpe', 'Sister Rosetta Tharpe', 'Gospel Train'),
                C('berry-is-on-top', 'Chuck Berry', 'Chuck Berry', 'Berry Is On Top'),
            ],
        },
        {
            'eyebrow': 'Rhythm and other colors',
            'h2': 'The palettes most players skip.',
            'intro': "Funk rhythm, flamenco, fingerstyle, and one ten-minute solo that earns it. Same theory underneath all of them. Jazz is one palette of colors, and so are these, and we can pull from any of them.",
            'covers': [
                C('maggot-brain', 'Eddie Hazel', 'Funkadelic', 'Maggot Brain'),
                C('cest-chic', 'Nile Rodgers', 'Chic', "C'est Chic"),
                C('pink-moon', 'Nick Drake', 'Nick Drake', 'Pink Moon'),
                C('fuente-y-caudal', 'Paco de Lucía', 'Paco de Lucía', 'Fuente y Caudal'),
                C('continuum', 'John Mayer', 'John Mayer', 'Continuum'),
                C('strange-mercy', 'Annie Clark', 'St. Vincent', 'Strange Mercy'),
            ],
        },
    ],

    'bass': [
        {
            'eyebrow': 'The pocket, defined',
            'h2': 'What the bass is for.',
            'intro': "The page above says it: the root, the structure, the thing everyone else stands on. These five records are that job done perfectly. If you only listen to one shelf here, make it this one.",
            'covers': [
                C('whats-going-on', 'James Jamerson', 'Marvin Gaye', "What's Going On"),
                C('otis-blue', 'Donald "Duck" Dunn', 'Otis Redding', 'Otis Blue'),
                C('stand', 'Larry Graham', 'Sly & The Family Stone', 'Stand!',
                  search='sly and the family stone stand', match_artist='sly'),
                C('mothership-connection', 'Bootsy Collins', 'Parliament', 'Mothership Connection'),
                C('voodoo', 'Pino Palladino', "D'Angelo", 'Voodoo'),
            ],
        },
        {
            'eyebrow': "Rock's engine room",
            'h2': 'Loud bands, run from the back.',
            'intro': "Every band here is steered by its bass player, whether the crowd knew it or not. McCartney wrote counter-melodies, Entwistle played lead from the back seat, and Geddy did both at once. Bring any of these songs to a lesson.",
            'covers': [
                C('sgt-pepper', 'Paul McCartney', 'The Beatles', "Sgt. Pepper's Lonely Hearts Club Band",
                  deezer_id=12047960),
                C('live-at-leeds', 'John Entwistle', 'The Who', 'Live at Leeds'),
                C('permanent-waves', 'Geddy Lee', 'Rush', 'Permanent Waves'),
                C('paranoid', 'Geezer Butler', 'Black Sabbath', 'Paranoid', deezer_id=7308090),
                C('ride-the-lightning', 'Cliff Burton', 'Metallica', 'Ride the Lightning'),
                C('blood-sugar-sex-magik', 'Flea', 'Red Hot Chili Peppers', 'Blood Sugar Sex Magik'),
            ],
        },
        {
            'eyebrow': 'Jazz, upright and electric',
            'h2': "The deep water I'm still swimming in.",
            'intro': "I'm still a student of jazz and the upright, and I say so up the page. This shelf is why. Mingus the composer, Ron Carter the anchor, Jaco the revolution. Walking lines and jazz vocabulary start here when you're ready for them.",
            'covers': [
                C('mingus-ah-um', 'Charles Mingus', 'Charles Mingus', 'Mingus Ah Um'),
                C('maiden-voyage', 'Ron Carter', 'Herbie Hancock', 'Maiden Voyage'),
                C('jaco-pastorius', 'Jaco Pastorius', 'Jaco Pastorius', 'Jaco Pastorius'),
                C('tutu', 'Marcus Miller', 'Miles Davis', 'Tutu'),
                C('esperanza', 'Esperanza Spalding', 'Esperanza Spalding', 'Esperanza'),
            ],
        },
        {
            'eyebrow': 'Left turns and secret weapons',
            'h2': 'Bass players hiding in plain sight.',
            'intro': "Carol Kaye on Pet Sounds. Tina Weymouth making art school funky. Thundercat turning the bass into a lead voice. Some of the best bass ever recorded hides inside records people file under something else.",
            'covers': [
                C('drunk', 'Thundercat', 'Thundercat', 'Drunk'),
                C('remain-in-light', 'Tina Weymouth', 'Talking Heads', 'Remain in Light'),
                C('pet-sounds', 'Carol Kaye', 'The Beach Boys', 'Pet Sounds'),
                C('flight-of-the-cosmic-hippo', 'Victor Wooten', 'Béla Fleck & The Flecktones', 'Flight of the Cosmic Hippo',
                  search='bela fleck flight of the cosmic hippo', match_artist='fleck'),
                C('thats-the-way-of-the-world', 'Verdine White', 'Earth, Wind & Fire', "That's the Way of the World",
                  search='earth wind and fire thats the way of the world', match_artist='earth'),
            ],
        },
    ],

    'piano': [
        {
            'eyebrow': 'Singers at the piano',
            'h2': 'The chord-chart hall of fame.',
            'intro': "This is exactly the piano I teach: sit down, read the chart, hear the song, play it. Carole King and Billy Joel built careers on it. Aretha played her own piano, and it's half the reason those records hit.",
            'covers': [
                C('tapestry', 'Carole King', 'Carole King', 'Tapestry'),
                C('goodbye-yellow-brick-road', 'Elton John', 'Elton John', 'Goodbye Yellow Brick Road'),
                C('the-stranger', 'Billy Joel', 'Billy Joel', 'The Stranger'),
                C('innervisions', 'Stevie Wonder', 'Stevie Wonder', 'Innervisions'),
                C('songs-in-a-minor', 'Alicia Keys', 'Alicia Keys', 'Songs in A Minor'),
                C('i-never-loved-a-man', 'Aretha Franklin', 'Aretha Franklin', 'I Never Loved a Man the Way I Love You'),
            ],
        },
        {
            'eyebrow': 'Jazz to sit inside',
            'h2': 'Slower, simpler, deeper.',
            'intro': "I teach slower, simpler jazz, and that's not a consolation prize. Bill Evans and Monk prove a few right notes beat a hundred fast ones. The Köln Concert is one man improvising for an hour, and people have loved it for fifty years.",
            'covers': [
                C('night-train', 'Oscar Peterson', 'Oscar Peterson Trio', 'Night Train',
                  search='oscar peterson night train', match_artist='oscar peterson'),
                C('waltz-for-debby', 'Bill Evans', 'Bill Evans Trio', 'Waltz for Debby',
                  search='bill evans waltz for debby', match_artist='bill evans',
                  deezer_id=126240),
                C('monks-dream', 'Thelonious Monk', 'Thelonious Monk Quartet', "Monk's Dream",
                  search='thelonious monk monks dream', match_artist='monk'),
                C('the-real-mccoy', 'McCoy Tyner', 'McCoy Tyner', 'The Real McCoy'),
                C('koln-concert', 'Keith Jarrett', 'Keith Jarrett', 'The Köln Concert',
                  search='keith jarrett koln concert'),
                C('light-as-a-feather', 'Chick Corea', 'Return to Forever', 'Light as a Feather',
                  search='return to forever light as a feather',
                  match_artist=['return to forever', 'chick corea']),
            ],
        },
        {
            'eyebrow': 'Soul, roots, and funk',
            'h2': 'The piano that makes rooms move.',
            'intro': "Little Richard invented a whole job with this instrument. Ray, Nina, and Dr. John each took it somewhere different, and Herbie plugged it in. When you can play from a chart, every one of these doors is open.",
            'covers': [
                C('heres-little-richard', 'Little Richard', 'Little Richard', "Here's Little Richard"),
                C('genius-of-ray-charles', 'Ray Charles', 'Ray Charles', 'The Genius of Ray Charles'),
                C('little-girl-blue', 'Nina Simone', 'Nina Simone', 'Little Girl Blue'),
                C('in-the-right-place', 'Dr. John', 'Dr. John', 'In the Right Place'),
                C('head-hunters', 'Herbie Hancock', 'Herbie Hancock', 'Head Hunters'),
            ],
        },
        {
            'eyebrow': 'The quiet hours',
            'h2': 'Why people buy a piano in the first place.',
            'intro': "Playing at home for yourself is a complete destination. These are the records for that, songs for the end of a day. Charlie Brown counts. It has always counted.",
            'covers': [
                C('come-away-with-me', 'Norah Jones', 'Norah Jones', 'Come Away with Me'),
                C('charlie-brown-christmas', 'Vince Guaraldi', 'Vince Guaraldi Trio', 'A Charlie Brown Christmas',
                  search='vince guaraldi a charlie brown christmas', match_artist='guaraldi'),
                C('tidal', 'Fiona Apple', 'Fiona Apple', 'Tidal'),
                C('a-rush-of-blood', 'Chris Martin', 'Coldplay', 'A Rush of Blood to the Head'),
                C('black-radio', 'Robert Glasper', 'Robert Glasper Experiment', 'Black Radio',
                  search='robert glasper black radio', match_artist='glasper'),
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

def norm(s):
    """Lowercase, strip accents and punctuation, drop a leading 'the '."""
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace('&', ' and ')
    s = re.sub(r'[^a-z0-9 ]+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    if s.startswith('the '):
        s = s[4:]
    return s


def clean_title(title):
    """Drop reissue tags: (Remastered), [Deluxe Edition], 'Remastered 2011' etc."""
    t = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', title)
    return t.strip(' :-')


def score(cover, hit):
    """0 = no match. Artist must match (any listed alias); album scored
    exact > prefix > substring against the reissue-tag-stripped title.
    Live/tribute/karaoke releases the manifest didn't ask for are demoted so
    the studio art wins ties (Paranoid vs 'Paranoid (Live at ...)')."""
    aliases = cover['match_artist']
    if isinstance(aliases, str):
        aliases = [aliases]
    if not any(norm(a) in norm(hit['artist']) for a in aliases):
        return 0
    cand = norm(clean_title(hit['title']))
    target = norm(cover['match_album'])
    if not cand or not target:
        return 0
    s = 0
    if cand == target:
        s = 30
    elif cand.startswith(target):
        s = 20
    elif target in cand:
        s = 10
    if s:
        full = norm(hit['title'])
        for bad in ('live', 'tribute', 'karaoke', 'in the style of', 'cover'):
            if bad in full and bad not in target:
                s -= 15
    return max(s, 0)


def http_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


def search_deezer(term, limit=10):
    """Hits normalized to {artist, title, art, id, source}."""
    q = urllib.parse.urlencode({'q': term, 'limit': limit})
    rows = http_json('https://api.deezer.com/search/album?' + q).get('data', [])
    return [{'artist': a['artist']['name'], 'title': a['title'],
             'art': a.get('cover_big') or a.get('cover_medium'),
             'art_xl': a.get('cover_xl'),
             'id': f"deezer {a['id']}", 'source': 'deezer'} for a in rows if a.get('cover_big')]


def search_itunes(term, limit=10):
    """Fallback only: this API 403s scripted bursts, so one polite try."""
    q = urllib.parse.urlencode({
        'term': term, 'entity': 'album', 'limit': limit, 'country': 'US'})
    try:
        rows = http_json(SEARCH_URL.format(q=q)).get('results', [])
    except Exception:
        return []
    return [{'artist': r.get('artistName', ''), 'title': r.get('collectionName', ''),
             'art': r['artworkUrl100'].replace('100x100bb', '600x600bb'),
             'id': f"itunes {r.get('collectionId', '?')}", 'source': 'itunes'}
            for r in rows if r.get('artworkUrl100')]


def best_hit(cover):
    if cover.get('deezer_id'):
        a = http_json(f"https://api.deezer.com/album/{cover['deezer_id']}")
        return {'artist': a['artist']['name'], 'title': a['title'],
                'art': a['cover_big'], 'art_xl': a.get('cover_xl'),
                'id': f"deezer {a['id']} (pinned)",
                'source': 'deezer'}, 30
    for search in (search_deezer, search_itunes):
        hits = search(cover['search'])
        time.sleep(0.25)
        best, best_key = None, (0,)
        for h in hits:
            s = score(cover, h)
            # tie-break toward the shortest raw title: plain releases beat
            # anniversary/deluxe editions whose art often adds trade dress
            key = (s, -len(h['title']))
            if s and key > best_key:
                best, best_key = h, key
        if best:
            return best, best_key[0]
    return None, 0


def pull(force=False):
    report, misses, sources = [], [], []
    for page, modules in MANIFEST.items():
        page_dir = os.path.join(COVERS_DIR, page)
        os.makedirs(page_dir, exist_ok=True)
        for mod in modules:
            for j, cover in enumerate(mod['covers']):
                dest = os.path.join(page_dir, cover['slug'] + '.jpg')
                if os.path.exists(dest) and not force:
                    report.append(f"  = {page}/{cover['slug']}  (already on disk)")
                    continue
                best, best_s = best_hit(cover)
                if not best:
                    misses.append(f"  ! {page}/{cover['slug']}  NO MATCH for term '{cover['search']}'")
                    continue
                # first cover of each module is the 2x2 feature tile: renders
                # up to ~500 CSS px, so take the 1000px art when Deezer has it
                art = (best.get('art_xl') if j == 0 else None) or best['art']
                req = urllib.request.Request(art, headers=UA)
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                with open(dest, 'wb') as f:
                    f.write(data)
                kb = len(data) // 1024
                report.append(
                    f"  + {page}/{cover['slug']}  [{best_s}] {best['artist']} | "
                    f"{best['title']} ({kb}KB, {best['source']})")
                sources.append((page, cover, best))
                time.sleep(0.15)
    print('\n'.join(report))
    if misses:
        print('\nMISSES (nothing downloaded, fix search terms):')
        print('\n'.join(misses))
    if sources:
        write_sources(sources)
    print(f"\n{len(report)} handled, {len(misses)} misses.")
    return not misses


def write_sources(new_rows):
    """Append provenance rows to img/covers/SOURCES.md (created on first run)."""
    path = os.path.join(COVERS_DIR, 'SOURCES.md')
    exists = os.path.exists(path)
    with open(path, 'a', encoding='utf-8') as f:
        if not exists:
            f.write(
                '# img/covers sources — pulled by scripts/covers.py\n\n'
                'Album cover art for the instrument-page listening modules (Deezer\n'
                'album search primary, iTunes Search API fallback; ~500px). Editorial\n'
                'use: identifying the records discussed on the page.\n'
                'Rows: page/slug — matched artist — matched album — source id.\n\n')
        for page, cover, best in new_rows:
            f.write(
                f"{page}/{cover['slug']}.jpg — {best['artist']} — "
                f"{best['title']} — {best['id']}\n")


# ---------------------------------------------------------------------------
# emit — full-bleed parallax cover walls
# ---------------------------------------------------------------------------
# Each module renders as a 10-column, 3-row tile wall that spans the whole
# viewport (no .container around the grid). The text block is an island
# carved out of the grid (4 cols x 2 rows), alternating left/right per
# module. Tiles are placed by the hand-drawn maps below; unplaced cells stay
# empty on purpose — the missing squares let the ink ground (and the
# cymatics canvas) read through. Below 1100px the maps collapse to a packed
# dense grid and the parallax stands down.

COLS = 10
# (col, row, colspan, rowspan) in island-LEFT orientation; the first tile of
# every module is the 2x2 feature. Maps are mirrored for island-right walls.
LAYOUTS = {
    4: [(6, 1, 2, 2), (9, 1, 1, 1), (3, 3, 1, 1), (7, 3, 1, 1)],
    5: [(6, 1, 2, 2), (9, 1, 1, 1), (5, 2, 1, 1), (2, 3, 1, 1), (8, 3, 1, 1)],
    6: [(6, 1, 2, 2), (9, 1, 1, 1), (5, 2, 1, 1), (10, 2, 1, 1), (2, 3, 1, 1), (7, 3, 1, 1)],
}
DEPTHS = (0.3, 0.5, 0.7, 0.9, 1.0)   # parallax rates; sign flips by slug hash


def _hash(s):
    return sum(ord(c) for c in s)


def tile(page, cover, place, feature):
    e = html.escape
    act, album, player = cover['act'], cover['album'], cover['player']
    line2 = album if (act == player or act == album) else f'{act} · {album}'
    col, row, cs, rs = place
    h = _hash(cover['slug'])
    depth = 0.22 if feature else DEPTHS[h % len(DEPTHS)] * (1 if (h >> 1) % 2 else -1)
    z = 2 + (h % 3)
    style = f'--c:{col};--r:{row};--cs:{cs};--rs:{rs};--d:{depth:g};--z:{z}'
    return (
        f'    <figure class="wall-tile" style="{style}">\n'
        f'      <img src="{{{{css_path}}}}img/covers/{page}/{cover["slug"]}.jpg" '
        f'alt="{e(album)} album cover, {e(act)}" loading="lazy" decoding="async">\n'
        f'      <figcaption><span class="wall-player">{e(player)}</span>'
        f'<span class="wall-album">{e(line2)}</span></figcaption>\n'
        f'    </figure>\n')


PARALLAX_JS = """<script>
  // Cover-wall parallax: every sleeve drifts at its own rate (--d) against
  // scroll. Desktop-map layouts only (>=1100px; the packed grids hold still),
  // reduced motion wins outright, and with JS off the walls are simply
  // static — placement never depends on this script.
  (function () {
    var mm = window.matchMedia;
    if (!mm || mm('(prefers-reduced-motion: reduce)').matches) return;
    var tiles = [];
    document.querySelectorAll('.cover-wall .wall-tile').forEach(function (t) {
      tiles.push({ el: t, d: parseFloat(t.style.getPropertyValue('--d')) || 0 });
    });
    if (!tiles.length) return;
    var MAX = 96, wide = mm('(min-width: 1100px)').matches, ticking = false;
    function frame() {
      ticking = false;
      var vh = window.innerHeight;
      var shifts = tiles.map(function (t) {
        var r = t.el.getBoundingClientRect();          // read phase
        if (r.bottom < -MAX || r.top > vh + MAX) return null;
        return ((r.top + r.height / 2 - vh / 2) / vh) * t.d * -MAX;
      });
      shifts.forEach(function (y, i) {                 // write phase
        if (y !== null) tiles[i].el.style.transform = 'translate3d(0,' + y.toFixed(1) + 'px,0)';
      });
    }
    function onScroll() {
      if (!wide || ticking) return;
      ticking = true;
      requestAnimationFrame(frame);
    }
    mm('(min-width: 1100px)').addEventListener('change', function (e) {
      wide = e.matches;
      if (!wide) tiles.forEach(function (t) { t.el.style.transform = ''; });
      else onScroll();
    });
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    onScroll();
  })();
</script>
"""


def emit():
    for page, modules in MANIFEST.items():
        out = []
        for i, mod in enumerate(modules):
            n = len(mod['covers'])
            if n not in LAYOUTS:
                raise SystemExit(f'{page} module {i}: no layout map for {n} covers')
            flip = i % 2 == 1
            places = LAYOUTS[n]
            if flip:
                places = [(COLS + 2 - c - cs, r, cs, rs) for (c, r, cs, rs) in places]
            cls = 'cover-wall cover-wall--flip' if flip else 'cover-wall'
            out.append(f'<section class="section--dark {cls}">\n')
            out.append('  <div class="wall-grid">\n')
            out.append('    <div class="wall-text">\n')
            out.append(f'      <span class="eyebrow">{html.escape(mod["eyebrow"])}</span>\n')
            out.append(f'      <h2>{html.escape(mod["h2"])}</h2>\n')
            out.append(f'      <p>{html.escape(mod["intro"])}</p>\n')
            if i == len(modules) - 1:
                out.append('      <p class="wall-cta"><a class="btn-primary" '
                           'href="{{css_path}}book/">Book your first lesson</a></p>\n')
            out.append('    </div>\n')
            for j, cover in enumerate(mod['covers']):
                out.append(tile(page, cover, places[j], feature=(j == 0)))
            out.append('  </div>\n')
            notes = ' · '.join(
                f"{c['player']}, {c['album']}" for c in mod['covers'])
            out.append(f'  <div class="container"><p class="wall-notes">{html.escape(notes)}</p></div>\n')
            out.append('</section>\n')
            if i < len(modules) - 1:
                out.append('\n')
        out.append('\n')
        out.append(PARALLAX_JS)
        dest = os.path.join(ROOT, '_src', 'pages', page, 'sections', '02-covers.html')
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(''.join(out))
        n = sum(len(m['covers']) for m in modules)
        print(f'wrote {os.path.relpath(dest, ROOT)} ({len(modules)} walls, {n} covers)')


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] not in ('pull', 'emit'):
        print(__doc__)
        sys.exit(1)
    if args[0] == 'pull':
        ok = pull(force='--force' in args)
        sys.exit(0 if ok else 1)
    emit()
