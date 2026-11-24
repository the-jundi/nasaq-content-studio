"""Moodboard sheet (nasaq-content-studio): groups of reference images, each with the ONE thing to take from it, rendered
through HTML + Chromium so Arabic captions shape correctly (PIL breaks Arabic joining). One group per candidate
direction, plus an «تجنّب» group of anti-references.

  python moodboard.py moodboard.json out.png [--font path/to/Arabic.woff2] [--width 2400] [--ratio 1.333]

moodboard.json: {"title": "اتجاهات «…» البصرية", "groups": [
   {"name": "الاتجاه أ: …", "note": "سطر يشرح الاتجاه", "items": [{"img": "refs/01.jpg", "take": "ما نأخذه", "src": "pinterest.com/pin/…",
                                                              "fit": "cover", "n": "12", "who": "@account · إنستقرام · 311 إعجابًا"}]},
   # fit: contain (default, the whole reference) | cover (photos). Optional "n" = a number badge that the .md table
   # cites; optional "who" = a small source line under the take (account · platform · the signal that made it a reference);
   # wrap a Latin handle in <bdi> so the Arabic line keeps its order.
   # A text post (an X thread, a LinkedIn text post) or any post whose visual shows people: give "quote" (≤ 15 words of
   # the hook) instead of "img". It renders as a text card in the same window, so no avatar or face reaches the board.
   {"name": "تجنّب", "avoid": true, "items": [...]}]}
Every tile has the same 4:3 window, so rows stay even whatever the source sizes (--ratio 1 for square tiles);
the whole reference shows inside it unless an item asks for "fit": "cover".
Image paths resolve against moodboard.json. Sources stay in the JSON (and moodboard.md); the board is for internal
review only — references are study material, never published."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

def build(js, out, font=None, width=2400, ratio=4 / 3):
    jp = Path(js).resolve()
    d = json.loads(jp.read_text(encoding='utf-8'))
    face = f'@font-face{{font-family:F;src:url({Path(font).resolve().as_uri()})}}' if font else ''
    cols = 5
    cell = (width - 80 - (cols - 1) * 16) // cols
    groups = []
    for g in d['groups']:
        items = ''.join(
            f'<figure>{"<b class=n>" + str(it["n"]) + "</b>" if it.get("n") else ""}'
            + (f'<div class=q><span>{it["quote"]}</span></div>' if it.get("quote") and not it.get("img") else
               f'<img src="{(jp.parent / it["img"]).resolve().as_uri()}" style="object-fit:{it.get("fit", "contain")}">')
            + f'<figcaption>{it.get("take", "")}{"<small>" + it["who"] + "</small>" if it.get("who") else ""}</figcaption></figure>'
            for it in g['items'])
        groups.append(f'<section class="{"avoid" if g.get("avoid") else ""}"><h2>{g["name"]}</h2>'
                      f'{"<p>" + g["note"] + "</p>" if g.get("note") else ""}<div class="grid">{items}</div></section>')
    html = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{face}
*{{margin:0;padding:0;box-sizing:border-box}} body{{font-family:F,'Segoe UI',Tahoma,sans-serif;background:#f4f4f2;color:#1b1b1b;width:{width}px;padding:40px}}
h1{{font-size:44px;line-height:1.5;margin-bottom:24px}} h2{{font-size:30px;line-height:1.6;margin:28px 0 6px}}
p{{font-size:22px;line-height:1.9;color:#555;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:repeat({cols},{cell}px);gap:16px;align-items:stretch}}
figure{{background:#fff;padding:8px}} img{{width:100%;display:block;aspect-ratio:{ratio};background:#ecebe8}}
figcaption{{font-size:20px;line-height:1.9;padding:8px 4px 2px}}
h1,h2,p,figcaption,.q span{{text-wrap:pretty}}
figcaption small{{display:block;font-size:16px;line-height:1.7;color:#6b6b6b;margin-top:4px}}
figure{{position:relative}} .q{{aspect-ratio:{ratio};background:#ecebe8;display:flex;align-items:center;padding:24px 28px;font-size:26px;line-height:1.9;color:#1b1b1b}}
.q span{{unicode-bidi:plaintext}} .q span::before{{content:'«'}} .q span::after{{content:'»'}} b.n{{position:absolute;top:14px;right:14px;min-width:40px;height:40px;padding:0 8px;border-radius:20px;background:#1b1b1b;color:#fff;font-size:20px;line-height:40px;text-align:center}}
section.avoid h2{{color:#b3261e}} section.avoid img{{filter:grayscale(.6)}}
</style></head><body><h1>{d.get('title', 'Moodboard')}</h1>{''.join(groups)}</body></html>"""
    hp = Path(out).with_suffix('.html')
    hp.write_text(html, encoding='utf-8')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': width, 'height': 1000})
        pg.goto(hp.resolve().as_uri()); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(600)
        pg.screenshot(path=str(out), full_page=True)
        b.close()
    print(out)

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')     # Arabic paths and help text on a Windows console
    except Exception:  # noqa: BLE001
        pass
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__); sys.exit(2)
    opt = lambda k: a[a.index(k) + 1] if k in a else None  # noqa: E731
    build(a[0], a[1], opt('--font'), int(opt('--width') or 2400), float(opt('--ratio') or 4 / 3))
