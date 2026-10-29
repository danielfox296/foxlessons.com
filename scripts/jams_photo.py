#!/usr/bin/env python3
"""Add a photo to a jam listing, or take one down.

    python3 scripts/jams_photo.py add <slug> <image url or file> \\
        --credit @handle --source <post url> [--kind night|venue] [--alt "..."]
    python3 scripts/jams_photo.py remove <slug>-<n>.jpg

add writes img/jams/<slug>-<n>.jpg, the copy on the card (560 px tall), and
<slug>-<n>-lg.jpg, the large copy it opens to (1280 px on the long side at
most, never enlarged), both stripped of metadata, then appends the photo to
the listing in the master list. kind says whether the photo is from the night
itself (the default) or of the venue; the card shows night photos first.
remove deletes both files and the master's entry. Photos come down whenever
the person credited asks (Daniel, 2026-10-28). Either way, finish with

    python3 scripts/jams_export.py && python3 build.py

LOCAL-only: needs Pillow, and the master list at ../jams-data/jams.json.
"""
import argparse
import io
import json
import os
import sys
import urllib.request

from PIL import Image, ImageOps

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from _src.lib import jams  # noqa: E402

PHOTO_DIR = os.path.join(REPO, 'img', 'jams')
CARD_HEIGHT = 560
LARGE_EDGE = 1280
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'


def load_master():
    with open(jams.MASTER_PATH, encoding='utf-8') as f:
        return json.load(f)


def save_master(master):
    with open(jams.MASTER_PATH, 'w', encoding='utf-8') as f:
        f.write(json.dumps(master, indent=2, ensure_ascii=False) + '\n')


def listing(master, slug):
    for rec in master['listings']:
        if rec['slug'] == slug:
            return rec
    sys.exit(f'jams_photo: no listing {slug!r} in the master')


def read_image(src):
    if src.startswith(('http://', 'https://')):
        req = urllib.request.Request(src, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
    else:
        with open(src, 'rb') as f:
            data = f.read()
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    return img.convert('RGB')


def save_scaled(img, path, scale, quality):
    if scale < 1:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    img.save(path, 'JPEG', quality=quality, optimize=True, progressive=True)


def add(args):
    master = load_master()
    rec = listing(master, args.slug)
    img = read_image(args.image)
    os.makedirs(PHOTO_DIR, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(PHOTO_DIR, f'{args.slug}-{n}.jpg')):
        n += 1
    name = f'{args.slug}-{n}.jpg'
    save_scaled(img, os.path.join(PHOTO_DIR, name), min(1, CARD_HEIGHT / img.height), 78)
    save_scaled(img, os.path.join(PHOTO_DIR, f'{args.slug}-{n}-lg.jpg'),
                min(1, LARGE_EDGE / max(img.size)), 82)
    photo = {'file': name, 'credit': args.credit, 'source_url': args.source, 'kind': args.kind}
    if args.alt:
        photo['alt'] = args.alt
    rec['photos'] = (rec.get('photos') or []) + [photo]
    save_master(master)
    print(f'jams_photo: {name} ({img.width}x{img.height} source) added to {args.slug}')


def remove(args):
    name = os.path.basename(args.file)
    stem, ext = os.path.splitext(name)
    master = load_master()
    hit = False
    for rec in master['listings']:
        kept = [p for p in rec.get('photos') or [] if p.get('file') != name]
        if len(kept) != len(rec.get('photos') or []):
            rec['photos'] = kept
            hit = True
    for f in (name, f'{stem}-lg{ext}'):
        path = os.path.join(PHOTO_DIR, f)
        if os.path.exists(path):
            os.remove(path)
            hit = True
    if not hit:
        sys.exit(f'jams_photo: no photo {name!r}')
    save_master(master)
    print(f'jams_photo: {name} removed')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('add')
    a.add_argument('slug')
    a.add_argument('image')
    a.add_argument('--credit', required=True)
    a.add_argument('--source', required=True)
    a.add_argument('--kind', choices=('night', 'venue'), default='night')
    a.add_argument('--alt')
    r = sub.add_parser('remove')
    r.add_argument('file')
    args = ap.parse_args()
    add(args) if args.cmd == 'add' else remove(args)


if __name__ == '__main__':
    main()
