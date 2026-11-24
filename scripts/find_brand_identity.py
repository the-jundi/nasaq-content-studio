#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find a brand's visual identity in the working environment before asking the owner for it (stage 0).
Read-only. It looks for what already exists on this machine: logo files, brand guides, fonts, colour sources and
earlier designs, and it reads the colours out of SVG logos and CSS / token files. Standard library only.

  python find_brand_identity.py "<brand name>" ["<latin name>" ...] [--roots <dir> ...] [--out identity-found.json]

Roots default to the current folder and its parent. Add --roots for the brand's own folders (site repo, design files,
a synced drive). What it finds is a lead, not a verdict: confirm with the owner that each file is the CURRENT official
one before it enters brand.json. Guide: references/03-design-identity.md"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next', '.cache', 'out',
             'AppData', 'Library', '$RECYCLE.BIN', 'site-packages', '.idea', '.vscode'}
LOGO_EXT = {'.svg', '.png', '.pdf', '.ai', '.eps', '.webp', '.jpg', '.jpeg'}
FONT_EXT = {'.woff2', '.woff', '.ttf', '.otf'}
GUIDE_EXT = {'.pdf', '.pptx', '.key', '.docx', '.md', '.fig'}
STYLE_EXT = {'.css', '.scss', '.less'}
LOGO_WORDS = ('logo', 'logotype', 'lockup', 'wordmark', 'brandmark', 'شعار', 'الشعار', 'لوقو', 'لوجو')
GUIDE_WORDS = ('brand', 'guideline', 'guidelines', 'identity', 'styleguide', 'style-guide', 'brandbook', 'brand-book',
               'هوية', 'الهوية', 'دليل', 'ارشادات', 'إرشادات')
TOKEN_FILES = ('tokens.json', 'design-tokens.json', 'theme.json', 'tailwind.config.js', 'tailwind.config.ts',
               'tailwind.config.cjs', 'tailwind.config.mjs')
HEX = re.compile(r'#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b')
CSS_VAR = re.compile(r'--([A-Za-z0-9_-]+)\s*:\s*(#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3}))\b')
MAX_FILES = 60000
MAX_TEXT = 2_000_000


def norm_hex(h):
    h = h.lower()
    return '#' + ''.join(c * 2 for c in h[1:]) if len(h) == 4 else h


def neutral(h):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return max(r, g, b) - min(r, g, b) < 18          # white, black and greys


def read_text(p):
    try:
        if p.stat().st_size > MAX_TEXT:
            return ''
        return p.read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return ''


def scan(roots, names):
    keys = [n.lower() for n in names if n]
    found = {'logos': [], 'guides': [], 'fonts': [], 'style_files': [], 'token_files': [], 'content_systems': [], 'design_folders': {}}
    seen = 0
    for root in roots:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith('.')]
            d = Path(dp)
            for fn in fns:
                seen += 1
                if seen > MAX_FILES:
                    return found, seen, True
                p = d / fn
                low, ext = fn.lower(), p.suffix.lower()
                path_low = str(p).lower()
                named = any(k in path_low for k in keys) if keys else True
                if ext in LOGO_EXT and any(w in low for w in LOGO_WORDS):
                    found['logos'].append({'path': str(p), 'named_for_brand': named, 'vector': ext in ('.svg', '.ai', '.eps', '.pdf')})
                elif ext in GUIDE_EXT and any(w in low for w in GUIDE_WORDS) and low not in ('readme.md',):
                    try:
                        size = p.stat().st_size
                    except OSError:
                        size = 0
                    found['guides'].append({'path': str(p), 'named_for_brand': named, 'bytes': size})
                elif ext in FONT_EXT:
                    found['fonts'].append(str(p))
                elif low in TOKEN_FILES:
                    found['token_files'].append(str(p))
                elif ext in STYLE_EXT:
                    found['style_files'].append({'path': str(p), 'named_for_brand': named})
                elif low in ('brand.json', 'design-system.md') or low.startswith('design-identity'):
                    found['content_systems'].append(str(p))
                elif ext in ('.png', '.jpg', '.jpeg') and any(w in d.name.lower() for w in ('post', 'social', 'instagram', 'carousel', 'منشور', 'سوشل')):
                    found['design_folders'][str(d)] = found['design_folders'].get(str(d), 0) + 1
    return found, seen, False


def colours_from(paths, limit=40):
    """hex colours by how often they appear; CSS custom properties keep their names"""
    count, named = Counter(), {}
    for p in paths[:limit]:
        text = read_text(Path(p))
        for h in HEX.findall(text):
            count[norm_hex(h)] += 1
        for name, h in CSS_VAR.findall(text):
            named.setdefault(norm_hex(h), name)
    return count, named


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('names', nargs='*', help='brand name as written, plus its Latin form if any')
    ap.add_argument('--roots', nargs='+')
    ap.add_argument('--out')
    a = ap.parse_args()
    roots = [Path(r) for r in (a.roots or [Path.cwd(), Path.cwd().parent])]
    roots = [r for r in dict.fromkeys(roots) if r.exists()]
    found, seen, cut = scan(roots, a.names)

    logos = sorted(found['logos'], key=lambda x: (not x['named_for_brand'], not x['vector'], len(x['path'])))
    own = any(x['named_for_brand'] for x in logos) and bool(a.names)       # other brands' logos often sit in the same folder
    svg = [x['path'] for x in logos if x['path'].lower().endswith('.svg') and (x['named_for_brand'] or not own)]
    logo_count, _ = colours_from(svg)
    # the site's CSS often carries the brand colours under a file name that does not mention the brand
    css_all = sorted(found['style_files'], key=lambda x: not x['named_for_brand'])
    css_own = [x['path'] for x in css_all if x['named_for_brand']] or [x['path'] for x in css_all]
    css_count, css_named = colours_from(css_own + found['token_files'])
    brand_cols = [h for h, _ in logo_count.most_common(12) if not neutral(h)][:6]
    site_cols = [h for h, _ in css_count.most_common(30) if not neutral(h)][:8]
    families = Counter(re.split(r'[-_ ](?=(?:thin|extralight|light|regular|medium|semibold|bold|extrabold|black|italic)\b)', Path(f).stem, flags=re.I)[0]
                       for f in found['fonts'])
    report = {
        'searched': [str(r) for r in roots], 'files_seen': seen, 'stopped_early': cut,
        'logos': logos[:20], 'guides': sorted(found['guides'], key=lambda x: not x['named_for_brand'])[:15],
        'font_families': [{'family': k, 'files': v} for k, v in families.most_common(10)],
        'colours_from_logo_svg': brand_cols,
        'colours_from_css': [{'hex': h, 'css_name': css_named.get(h, '')} for h in site_cols],
        'content_systems': found['content_systems'][:15],
        'earlier_design_folders': sorted(found['design_folders'].items(), key=lambda kv: -kv[1])[:10],
    }
    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    print(f"searched: {', '.join(report['searched'])}  ({seen} files{', stopped early: narrow --roots' if cut else ''})")

    def block(title, items, fmt):
        print(f'\n{title}: {len(items)}')
        for x in items[:8]:
            print('  -', fmt(x))

    block('logo files', report['logos'], lambda x: f"{x['path']}{'  [vector]' if x['vector'] else ''}{'' if x['named_for_brand'] else '  (name not matched: check it is this brand)'}")
    block('brand guides', report['guides'], lambda x: x['path'] + ('  (only %d bytes: probably empty or broken, ask for a good copy)' % x['bytes'] if x.get('bytes', 9999) < 2000 else ''))
    block('font families', report['font_families'], lambda x: f"{x['family']} ({x['files']} files)")
    print('\ncolours inside the SVG logo(s):', ', '.join(report['colours_from_logo_svg']) or 'none read (no SVG logo found)')
    print('colours in CSS / token files:', ', '.join(f"{c['hex']}{' --' + c['css_name'] if c['css_name'] else ''}" for c in report['colours_from_css']) or 'none')
    block('earlier content systems (brand.json / design-system.md)', report['content_systems'], str)
    block('folders of earlier designs', report['earlier_design_folders'], lambda kv: f'{kv[0]} ({kv[1]} images)')
    if a.names and all(ord(c) > 127 or not c.isalnum() for n in a.names for c in n) and not any(x['named_for_brand'] for x in logos):
        print('\ntip: file names are usually Latin. Pass the Latin name too, e.g. find_brand_identity.py "<الاسم>" "<latin name>".')
    if not (report['logos'] or report['guides'] or report['content_systems']):
        print('\n-> nothing official found here. Ask the owner where the logo and the brand guide live (interview question 3),')
        print('   or pass their folders with --roots. Never redraw a logo and never guess the colours.')
    else:
        print('\n-> leads, not verdicts: confirm with the owner that each file is the CURRENT official one (interview question 3).')
        print('   The official identity (logo, colours, font) stays fixed; the content style is explored on top of it (references/03).')
    if a.out:
        print('saved:', a.out)


if __name__ == '__main__':
    main()
