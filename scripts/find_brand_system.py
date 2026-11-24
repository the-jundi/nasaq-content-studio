"""Find a brand's existing design system before building a new one (nasaq-content-studio, stage 0).

  python find_brand_system.py "<brand name, Arabic or Latin>" [--roots DIR ...] [--notes DIR ...] [--depth 5] [--json]

Scans the roots (default: the current folder, its parent, Desktop and Documents) for project folders that hold a
brand.json, design-system*.md, design-identity*.md, posts.json or a moodboard, keeps the ones whose brand.json names, hashtag, domain or folder
path match the query, and lists what each one holds (generator, posts, captions, moodboard, feedback log, delivery
notes, image prompt base), newest first. --notes greps brand-note folders (*.md) for the name as well.
The first row is the system to inherit: copy its files into the new project instead of starting from scratch,
unless the owner asked for a new identity. Read-only: nothing is copied or changed.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

ANCHORS = re.compile(r'^(brand\.json|design-system[\w\-]*\.md|design-identity[\w\-]*\.md|posts\.json|moodboard\.(md|json))$', re.I)
MARKERS = {   # label -> filename regex, searched in the project folder and up to two levels below it
    'brand.json': r'^brand\.json$',
    'design-system': r'^design-(system|identity)[\w\-]*\.md$',
    'generator': r'^(make_posts|blog_posts|mock)\.py$',
    'posts.json': r'^posts\.json$',
    'captions.json': r'^captions\.json$',
    'moodboard': r'^(moodboard\.(md|json)|00-moodboard\.png)$',
    'feedback-log': r'^feedback-log\.md$',
    'brand-notes': r'^brand-notes\.md$',
    'delivery-notes': r'^README-delivery\.md$',
    'prompt-base': r'^PROMPT-BASE\.txt$',
    'plan': r'^(plan[\w\-]*|v\d[\w\-]*)\.md$',
}
SKIP = {'node_modules', '.git', '__pycache__', 'out', 'gen', 'img', 'shots', 'plates', 'masks', 'video', 'refs', 'posts',
        'devices', 'blog-src', 'venv', '.venv', 'AppData', 'site-packages'}
DIAC = re.compile('[ً-ْٰـ]')   # harakat + tatweel

def norm(s):
    s = DIAC.sub('', str(s or '')).lower()
    for a, b in (('أ', 'ا'), ('إ', 'ا'), ('آ', 'ا'), ('ة', 'ه'), ('ى', 'ي'), ('#', ''), ('_', ' '), ('-', ' ')):
        s = s.replace(a, b)
    return re.sub(r'\s+', ' ', s).strip()

def walk(root, depth):
    root = Path(root)
    base = len(root.parts)
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP and not x.startswith('.') and len(Path(d).parts) - base < depth]
        yield Path(d), files

def has_anchor(d):
    try:
        return any(ANCHORS.match(f) for f in os.listdir(d))
    except OSError:
        return False

def markers(proj):
    found, newest = {}, 0.0
    base = len(proj.parts)
    for d, dirs, files in os.walk(proj):
        # a subfolder with its own brand.json / design-system is a separate project (a later version), never part of this one
        dirs[:] = [x for x in dirs if x not in SKIP and len(Path(d).parts) - base < 2 and not has_anchor(Path(d) / x)]
        for f in files:
            for k, rx in MARKERS.items():
                if re.match(rx, f, re.I):
                    p = Path(d) / f
                    found.setdefault(k, []).append(str(p.relative_to(proj)))
                    try:
                        newest = max(newest, p.stat().st_mtime)
                    except OSError:
                        pass
    return found, newest

def brand_names(proj):
    p = proj / 'brand.json'
    if not p.exists():
        return [], ''
    try:
        b = json.loads(p.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return [], ''
    return [str(b.get(k)) for k in ('name', 'name_in_text', 'name_latin', 'hashtag') if b.get(k)], str(b.get('domain') or '')

def main(a):
    if not a or a[0].startswith('--'):
        print(__doc__)
        return 2
    q = norm(a[0])
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d  # noqa: E731

    def many(k):
        if k not in a:
            return []
        i, out = a.index(k) + 1, []
        while i < len(a) and not a[i].startswith('--'):
            out.append(a[i]); i += 1
        return out
    home = Path.home()
    roots = many('--roots') or [Path.cwd(), Path.cwd().parent, home / 'Desktop', home / 'Documents']
    depth = int(opt('--depth', 5))
    seen, rows = set(), []
    for r in roots:
        if not Path(r).exists():
            continue
        for d, files in walk(r, depth):
            if not any(ANCHORS.match(f) for f in files):
                continue
            key = str(d.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            names, domain = brand_names(d)
            # folder match: the project's own name, plus its parent's only when the parent is itself a project (a v2 folder inside the first week's project);
            # a shared workspace folder (one holding several brands) must not make every project inside it match
            folders = [d.name] + ([d.parent.name] if has_anchor(d.parent) else [])
            # match strength: 3 = the brand's own name or hashtag, 2 = folder name, 1 = only inside a domain (a sister brand's subdomain)
            score = 3 if any(q in norm(n) for n in names) else 2 if any(q in norm(x) for x in folders) else 1 if q in norm(domain) else 0
            if not score:
                continue
            found, newest = markers(d)
            rows.append({'path': str(d), 'brand': names[:3], 'match': {3: 'name', 2: 'folder', 1: 'domain only'}[score], 'score': score,
                         'updated': time.strftime('%Y-%m-%d %H:%M', time.localtime(newest)) if newest else '',
                         'ts': newest, 'has': sorted(found), 'files': found})
    rows.sort(key=lambda x: (x['score'], x['ts'], len(x['has'])), reverse=True)
    notes = []
    for nd in many('--notes'):
        for f in sorted(Path(nd).glob('*.md')):
            try:
                for i, line in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
                    if q and q in norm(line):
                        notes.append({'file': str(f), 'line': i, 'text': line.strip()[:160]})
            except Exception:  # noqa: BLE001
                pass
    if '--json' in a:
        print(json.dumps({'query': a[0], 'projects': [{k: v for k, v in r.items() if k not in ('ts', 'score')} for r in rows], 'notes': notes}, ensure_ascii=False, indent=1))
        return 0 if rows else 1
    if not rows:
        print(f'No earlier project or design system found for «{a[0]}» under: ' + ', '.join(map(str, roots)))
        print('-> a new brand (exit code 1 here is normal): run the first interview (references/00-onboarding-interview.md),')
        print('   then build its design system: research, moodboard, design-system.md, 3 sample slides for approval (SKILL.md section 1).')
    for i, r in enumerate(rows, 1):
        print(f'{i}. {r["path"]}\n   brand: {" / ".join(r["brand"]) or "(no brand.json)"} | match: {r["match"]} | updated {r["updated"]} | has: {", ".join(r["has"])}')
    if rows:
        top = rows[0]
        print('\nInherit from #1 unless the owner asked for a new identity. Read first:')
        for k in ('design-system', 'brand.json', 'feedback-log', 'delivery-notes', 'generator', 'prompt-base', 'moodboard'):
            for f in top['files'].get(k, [])[:3]:
                print('  -', Path(top['path']) / f)
    if notes:
        print(f'\nBrand notes mentioning «{a[0]}» ({len(notes)} lines):')
        for n in notes[:12]:
            print(f'  {Path(n["file"]).name}:{n["line"]}  {n["text"]}')
    return 0 if rows else 1

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main(sys.argv[1:]))
