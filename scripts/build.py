"""Build a batch of posts from one JSON file (nasaq-content-studio): HTML per slide (kept next to its PNG), render,
then optional QA, LinkedIn PDF documents and a contact sheet.

  python build.py posts.json [--brand brand.json] [--only post03,post07] [--qa [--masks masks/]] [--pdf] [--sheet] [--html-only]

posts.json:
  {"brand": "brand.json", "out": "out",
   "posts": [{"id": "post01", "series": "دليل المتجر", "date": "4.11.2026",
              "formats": {"ig": [1080, 1350], "w": [1600, 900]},
              "slides": [{"layout": "cover", "display": {"ig": "سطر الغلاف بالعامية", "*": "سطر محايد"}, "title": "..."},
                         {"layout": "list", "title": "...", "list": ["...", "..."]},
                         {"layout": "cta", "display": "...", "title": "...", "only": ["ig"]}]}]}
Any slide value may be {"<format>": value, "*": default}: one source, a wording per platform (dialect on the IG cover,
neutral Arabic on the shared landscape image). "only": [formats] keeps a slide out of the others.
A post may name a content style: {"id": ..., "style": "<name>"} lays brand.json -> styles.<name> (tokens, furniture, type)
over the brand for that post only, so one batch can explore several styles on the same official identity. Relative paths
(brand, out, plate) resolve against posts.json. Output: out/<id>/<format>/<id>-<format>-<k>.{html,png}; the counter
reads «k / n» per format, which subset_carousel.py relies on."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kit import load_brand, page  # noqa: E402
from layouts import make  # noqa: E402

def pick(v, fmt):
    if isinstance(v, dict) and ('*' in v or fmt in v) and all(isinstance(k, str) for k in v):
        if fmt in v or '*' in v:
            return v.get(fmt, v.get('*'))
    return v

def style_brand(b, post, cache):
    """the brand as this post's content style sees it: brand.json -> styles.<name> laid over tokens, furniture and type"""
    name = post.get('style')
    if not name:
        return b
    if name not in cache:
        st = (b.get('styles') or {}).get(name)
        if st is None:
            raise SystemExit(f"post {post['id']}: style «{name}» is not defined in brand.json -> styles "
                             f"(defined: {', '.join(b.get('styles') or {}) or 'none'})")
        bs = copy.deepcopy(b)
        for key in ('tokens', 'furniture', 'type'):
            if isinstance(st.get(key), dict):
                bs[key] = {**bs.get(key, {}), **st[key]}
        cache[name] = bs
    return cache[name]


def build(posts_path, brand_path=None, only=None, html_only=False, qa=False, pdf=False, sheet=False, masks=None):
    pp = Path(posts_path).resolve()
    doc = json.loads(pp.read_text(encoding='utf-8'))
    base = pp.parent
    b = load_brand(brand_path or (base / doc['brand']))
    out = (base / doc.get('out', 'out')).resolve()
    items, by_var, styled = [], {}, {}
    for post in doc['posts']:
        if only and post['id'] not in only:
            continue
        bp = style_brand(b, post, styled)
        for fmt, (W, H) in post.get('formats', {'ig': [1080, 1350]}).items():
            slides = [s for s in post['slides'] if fmt in s.get('only', [fmt])]
            d = out / post['id'] / fmt
            d.mkdir(parents=True, exist_ok=True)
            for old in list(d.glob('*.png')) + list(d.glob('*.html')):   # stale slides from an earlier, longer version
                old.unlink()
            n = len(slides)
            for k, s in enumerate(slides, 1):
                sl = {key: pick(v, fmt) for key, v in s.items()}
                if sl.get('plate'):
                    sl['plate'] = str((base / sl['plate']).resolve())
                spec = make(sl, bp, W, H, tag=pick(post.get('series'), fmt), counter=f'{k} / {n}' if n > 1 else None,
                            date=post.get('date'))
                html = d / f'{post["id"]}-{fmt}-{k}.html'
                html.write_text(page(spec, bp), encoding='utf-8')
                items.append((str(html), str(html.with_suffix('.png')), W, H))
                by_var.setdefault((post['id'], fmt), []).append(html.with_suffix('.png'))
    print(f'{len(items)} slide pages written under {out}')
    if html_only:
        return items
    from shot import render_all
    render_all(items)
    if pdf:
        from PIL import Image
        Image.init()                             # registers the JPEG writer the PDF plugin uses for its pages
        for (pid, fmt), pngs in by_var.items():
            W, H = Image.open(pngs[0]).size
            if len(pngs) > 1 and W > H:          # LinkedIn carousel = one landscape PDF uploaded as a Document
                ims = [Image.open(p).convert('RGB') for p in pngs]
                dst = out / pid / f'{pid}-{fmt}.pdf'
                ims[0].save(dst, save_all=True, append_images=ims[1:], resolution=150, quality=92)
                print('pdf', dst)
    if qa:
        from qa_slides import check
        md = masks or doc.get('masks')      # object masks (white = object) named after each plate image
        qa_path = out / 'qa.json'
        tmp = out / 'qa.partial.json' if only else qa_path
        check([i[0] for i in items], out_json=tmp, masks=str((base / md).resolve()) if md else None)
        if only:   # a partial rebuild replaces its own posts' rows and keeps the rest (it used to overwrite the whole report)
            new = json.loads(tmp.read_text(encoding='utf-8'))
            old = json.loads(qa_path.read_text(encoding='utf-8')) if qa_path.exists() else []
            keep = [r for r in old if not any(str(r.get('page', '')).startswith(p + '-') for p in only)]
            qa_path.write_text(json.dumps(keep + new, ensure_ascii=False, indent=1), encoding='utf-8')
            tmp.unlink()
            print(f'qa.json merged: {len(keep)} rows kept + {len(new)} rebuilt, {sum(1 for r in keep + new if r.get("issue"))} failing in all')
    if sheet:
        from contact_sheet import sheet as mk
        if only:   # sheets always show the whole batch, in posts.json order, not just the posts rebuilt now
            variants = [(p['id'], f) for p in doc['posts'] for f in p.get('formats', {'ig': [1080, 1350]}) if (out / p['id'] / f).is_dir()]
        else:
            variants = list(by_var)
        for fmt in sorted({f for _, f in variants}):
            dirs = [str(out / pid / f) for pid, f in variants if f == fmt]
            mk(str(out / f'sheet-{fmt}.jpg'), dirs, 240 if fmt != 'w' else 320, head=True, rtl=b['dir'] == 'rtl')
    return items

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    a = sys.argv[1:]
    if not a or a[0].startswith('--'):
        print(__doc__); sys.exit(2)
    opt = lambda k: a[a.index(k) + 1] if k in a else None  # noqa: E731
    build(a[0], opt('--brand'), set(opt('--only').split(',')) if opt('--only') else None,
          '--html-only' in a, '--qa' in a, '--pdf' in a, '--sheet' in a, opt('--masks'))
