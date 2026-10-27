"""Jams section: guides to how Denver jams and open mics work.

VOICE.md §4 stands (Daniel, 2026-10-27): specific jams, venues and nights
never publish, copy speaks of Denver jams generically, and the match is
person to person. So the public pages are guides rendered from the copy in
_src/jams/*.yaml, and nothing here reads the listings (the internal match
list lives outside this repo; scripts/jams_data.py serves the tools that use it).

Nothing here touches the network. The build must keep working offline.
"""
import os
import re
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JAMS_SRC = os.path.join(REPO, '_src', 'jams')
TEMPLATES = os.path.join(REPO, '_src', 'templates', 'jams')
SITE_URL = 'https://foxlessons.com'

_cache = {}


def _read_yaml(path):
    import yaml
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


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


def genre_pages():
    """Ordered [(page_key, cfg)] from genres.yaml."""
    data = load_jams_yaml('genres')
    return [(g['key'], g) for g in data['genres']] if data else []


def genre_cfg(key):
    return next((cfg for k, cfg in genre_pages() if k == key), None)


def mapped_genre_values():
    """Data genre values the guide styles cover; jams_check reports the rest."""
    vals = set()
    for _, cfg in genre_pages():
        vals |= {m.lower() for m in cfg.get('maps', []) + cfg.get('maps_jam_only', [])}
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
    """The build refuses to run on main while any jams copy is still a draft
    (handoff 7.3). Branch previews render drafts with a marker."""
    if current_branch() == 'main':
        drafts = drafts_present()
        if drafts:
            raise SystemExit('jams: refusing to build on main with draft blocks present: '
                             + ', '.join(drafts))


# --- rendering ----------------------------------------------------------------

def _env():
    if 'env' not in _cache:
        import jinja2
        _cache['env'] = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TEMPLATES),
            autoescape=True, trim_blocks=True, lstrip_blocks=True,
            undefined=jinja2.StrictUndefined)
    return _cache['env']


def _markup(s):
    from markupsafe import Markup
    return Markup(s)


def _paragraphs(text):
    return [' '.join(p.split()) for p in re.split(r'\n\s*\n', (text or '').strip()) if p.strip()]


def _first_sentence(text):
    text = ' '.join((text or '').split())
    m = re.match(r'(.+?[.!?])(\s|$)', text)
    return m.group(1) if m else text


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
    """The page body for a jams page config: the guides index, a style guide,
    or the first-jam guide."""
    refuse_drafts_on_main()
    s = strings()
    env = _env()
    t = spec.get('type')
    common = {'s': s, 'labels': s['labels'], 'prefix': nav_prefix}

    if t == 'hub':
        guides = [{'href': f'{nav_prefix}jams/{k}/', 'name': cfg['name'],
                   'blurb': _first_sentence(cfg['intro'])} for k, cfg in genre_pages()]
        return env.get_template('hub.html').render(
            **common, guides=guides, draft=bool(s['hub'].get('draft')),
            cta_html=_markup(_cta_html(nav_prefix, 'light', guide_link=False)))

    if t in ('genre', 'format'):
        cfg = genre_cfg(spec['key'])
        if cfg is None:
            raise SystemExit(f"jams: no genres.yaml entry for page {spec['key']!r}")
        draft = bool(cfg.get('draft'))
        return env.get_template('genre.html').render(
            **common, cfg=cfg, draft=draft,
            eyebrow=s['genre_page']['eyebrow'].format(name=cfg['name']),
            prep_html=_markup(env.get_template('prep.html').render(
                s=s, labels=s['labels'], cfg=cfg, prefix=nav_prefix, draft=draft,
                blocks=_prep_ctx(cfg, nav_prefix))),
            cta_html=_markup(_cta_html(nav_prefix, 'light', material=cfg.get('cta_material'),
                                       draft=draft)))

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


def llms_section():
    """The Jams block for llms.txt: the index, each style guide, the
    first-jam guide (handoff 4.5)."""
    s = strings()
    lines = [f"- [{s['hub']['h1']}]({SITE_URL}/jams/): {s['llms']['hub']}"]
    for k, cfg in genre_pages():
        lines.append(f"- [{cfg['h1']}]({SITE_URL}/jams/{k}/): {s['llms']['genre']}")
    lines.append(f"- [{s['guide']['h1']}]({SITE_URL}/jams/first-jam/): {s['llms']['guide']}")
    return '\n## Jams\n\n' + '\n'.join(lines) + '\n'
