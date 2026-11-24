"""Platform-only subset of a carousel (nasaq-content-studio skill): X takes at most 4 media in one post, so a longer
carousel gets its own set of N of the same slides, re-shot unchanged except for the slide counter («k / N»).
The other platforms keep the full carousel; what was dropped must be carried by the post text or its reply.

  python subset_carousel.py <out dir> <keep e.g. 2,3,4,5> slide-1.html slide-2.html ... [--size 1080x1350]
Slides are the carousel's own HTML pages in order; each must contain its counter exactly once as «i / total»
(spaces around the slash). Output: <out dir>/x-1.png ... x-N.png (+ the edited HTML). Then pixel-diff against the
originals: only the counter strip may differ."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shot import render_all  # noqa: E402

def subset(out, keep, slides, size=(1080, 1350)):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    total, items = len(slides), []
    for k, s in enumerate(keep, 1):
        t = Path(slides[s - 1]).read_text(encoding='utf-8')
        pat = re.compile(rf'(?<![\d/]){s} / {total}(?![\d/])')
        hits = list(pat.finditer(t))
        if len(hits) != 1:
            raise SystemExit(f'slide {s}: found the counter «{s} / {total}» {len(hits)} times (need exactly 1)')
        html = out / f'x-{k}.html'      # asset URIs must be absolute (file:///...) for the copy to render the same
        html.write_text(t[:hits[0].start()] + f'{k} / {len(keep)}' + t[hits[0].end():], encoding='utf-8')
        items.append((str(html), str(out / f'x-{k}.png'), *size))
    render_all(items)

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')     # Arabic paths and help text on a Windows console
    except Exception:  # noqa: BLE001
        pass
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if len(a) < 3:
        print(__doc__); sys.exit(2)
    size = (1080, 1350)
    if '--size' in sys.argv:
        size = tuple(int(v) for v in sys.argv[sys.argv.index('--size') + 1].split('x'))
        a = [x for x in a if x != sys.argv[sys.argv.index('--size') + 1]]
    subset(a[0], [int(v) for v in a[1].split(',')], a[2:], size)
