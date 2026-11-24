"""Contact sheet: one row per post folder, its slides left to right (nasaq-content-studio skill). Use it to SEE a whole
week (or one platform's set) at a glance before delivery: repeated layouts, a cover that does not stop the scroll,
a counter that does not match, a crop.

--head adds, above each thumbnail, the slide's top band at twice the thumbnail scale (split in two halves, start side
first), so counters and series labels are readable. It is a zoom, not part of the slide: a sheet with --head shows the
tag twice on purpose. Row height follows each row's own aspect ratio (portrait, square and landscape all fit), and a
folder with more than --wrap images wraps onto further rows instead of one endless strip.

  python contact_sheet.py out.jpg "<folder with post subfolders>" [--thumb 240] [--head] [--wrap 8] [--ltr]
  python contact_sheet.py out.jpg post1/ post2/ ...          explicit post folders"""
import sys
from pathlib import Path

IMG = {'.png', '.jpg', '.jpeg', '.webp'}
LABEL = 120

def _head(im, tw, rtl=True):
    """The slide's top band (11% of a portrait/square slide, 17% of a landscape one: logo, tag and counter) at 2x the
    thumbnail scale, cut into two halves stacked (start half first)."""
    from PIL import Image
    band = im.crop((0, 0, im.width, max(1, int(im.height * (.17 if im.width > im.height * 1.2 else .11)))))
    band = band.resize((2 * tw, max(1, int(band.height * 2 * tw / im.width))), Image.LANCZOS)
    halves = [band.crop((tw, 0, 2 * tw, band.height)), band.crop((0, 0, tw, band.height))]
    if not rtl:
        halves.reverse()
    out = Image.new('RGB', (tw, 2 * band.height + 2), '#d9d9d9')
    out.paste(halves[0], (0, 0))
    out.paste(halves[1], (0, band.height + 2))
    return out

def sheet(out, folders, thumb=240, head=False, wrap=8, rtl=True):
    from PIL import Image, ImageDraw
    rows = []
    for f in folders:
        imgs = sorted(p for p in Path(f).iterdir() if p.suffix.lower() in IMG and 'sheet' not in p.stem)
        for i in range(0, len(imgs), wrap):
            rows.append((Path(f).name + ('' if i == 0 else ' …'), imgs[i:i + wrap]))
    if not rows:
        raise SystemExit('no images found')
    cols = max(len(r[1]) for r in rows)
    tw = thumb - 6
    gap = 8 if head else 0
    plan = []
    for name, imgs in rows:
        ims = [Image.open(p).convert('RGB') for p in imgs]
        th = max(int(tw * im.height / im.width) for im in ims)
        heads = [_head(im, tw, rtl) for im in ims] if head else []
        plan.append((name, ims, heads, th, max((h.height for h in heads), default=0)))
    S = Image.new('RGB', (LABEL + cols * thumb, sum(th + hh + gap + 14 for *_, th, hh in plan)), 'white')
    d = ImageDraw.Draw(S)
    y = 0
    for name, ims, heads, th, hh in plan:
        d.text((6, y + 6), name[:18], fill='black')
        for j, im in enumerate(ims):
            x = LABEL + j * thumb
            if head:
                S.paste(heads[j], (x, y))
            im.thumbnail((tw, th), Image.LANCZOS)
            S.paste(im, (x, y + hh + gap))
        y += th + hh + gap + 14
    S.save(out, quality=85)
    print(out, S.size)

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')     # Arabic paths and help text on a Windows console
    except Exception:  # noqa: BLE001
        pass
    a = sys.argv[1:]
    opt = lambda k, dflt: int(a[a.index(k) + 1]) if k in a else dflt  # noqa: E731
    vals = {a[a.index(k) + 1] for k in ('--thumb', '--wrap') if k in a}
    pos = [x for x in a if not x.startswith('--') and x not in vals]
    if len(pos) < 2:
        print(__doc__); sys.exit(2)
    fs = pos[1:]
    if len(fs) == 1 and any(p.is_dir() for p in Path(fs[0]).iterdir()):
        fs = sorted(str(p) for p in Path(fs[0]).rglob('*') if p.is_dir() and any(q.suffix.lower() in IMG for q in p.iterdir()))
    sheet(pos[0], fs, opt('--thumb', 240), '--head' in a, opt('--wrap', 8), '--ltr' not in a)
