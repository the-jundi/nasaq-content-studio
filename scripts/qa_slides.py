"""Slide QA (nasaq-content-studio; from the tech brand rule of 2026-11-01: «no headline over an object, readable contrast
everywhere»). For each kit HTML slide it screenshots (1) the background with all text and marks hidden and (2) when an
object mask exists for the plate image, the mask in place of the plate. Then for every text element (.blk .note .tag
.foot .ex) it reports:
  TEXT COLLISION        two text boxes overlap (> 2% of the smaller)
  TEXT OVER FURNITURE   a text block or note overlaps the tag, footer, disclosure chip or logo; the brand's own
                        furniture css (a bar drawn with a block ::before, a padded chip) counts as part of it
  OFF-CANVAS            the element is outside the canvas
  LOW CONTRAST          5th-percentile WCAG ratio vs the pixels under it < 4.5 (3.0 for large text)
  TEXT/FURNITURE OVER OBJECT   > 1% of the box covers the object mask (masks/<plate stem>.png, white = object)
  OUTSIDE MARGIN        a text block or note closer than --margin px to the side edges
  SMALL ON PHONE        (warning) text that renders under --min-px CSS px when the image is shown --phone px wide
  CLOSE TO OBJECT       (warning) the box grown by --pad px (24) touches the object: text crowding the subject
  CLOSE TO FURNITURE    (warning) text within 12px of the tag, footer, chip or logo: it reads as one crowded block
  TEXT CROSSES ZONE     a text block sits partly on and partly off a zone (the image window #plate, a news .panel):
                        a source line running into the panel, a title clipping the image edge. Fully inside is fine
                        (type on a full-bleed image, the «what it means» text in its panel)
  TEXT OVERFLOWS AREA   (warning) a stack's text runs more than 8px past the region its layout gave it; harmless when
                        it only reaches an empty margin, so read it with the image

  python qa_slides.py slide1.html [slide2.html ...] [--masks DIR] [--margin 60] [--phone 390] [--min-px 9] [--pad 24]
Writes qa.json next to the first slide (or out_json). Exit 1 if any FAIL. Warnings do not fail the run.
Set CHROME_PATH to use a Chromium already on the machine (as shot.py does)."""
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HIDE = '.blk,.note,.tag,.foot,.ex,svg.ov,#logo{visibility:hidden !important}'

def lum(rgb):
    c = rgb / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]

def ratio(l1, l2):
    hi, lo = np.maximum(l1, l2), np.minimum(l1, l2)
    return (hi + 0.05) / (lo + 0.05)

def parse_color(s):
    s = s.strip()
    if s.startswith('rgb'):
        return np.array([float(x) for x in s[s.index('(') + 1:s.index(')')].split(',')[:3]])
    return np.array([0, 0, 0])

JS = """() => [...document.querySelectorAll('.blk,.note,.tag,.foot,.ex')].map(e => {
  let r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
  if (e.classList.contains('blk') || e.classList.contains('note')) { const rg = document.createRange(); rg.selectNodeContents(e);
    const rs = [...rg.getClientRects()].filter(q => q.width > 1);
    if (rs.length) { const x0 = Math.min(...rs.map(q => q.left)), y0 = Math.min(...rs.map(q => q.top)),
      x1 = Math.max(...rs.map(q => q.right)), y1 = Math.max(...rs.map(q => q.bottom)); r = {x: x0, y: y0, width: x1 - x0, height: y1 - y0}; } }
  return {id: e.id, cls: e.className, text: e.innerText.slice(0, 40), x: r.x, y: r.y, w: r.width, h: r.height, color: cs.color,
          bg: cs.backgroundColor, size: parseFloat(cs.fontSize), weight: parseInt(cs.fontWeight)}; })"""

STACKS = """() => [...document.querySelectorAll('.stack')].map(s => { const r = s.getBoundingClientRect();
  const k = [...s.children].map(c => c.getBoundingClientRect()).filter(q => q.height > 0); if (!k.length) return null;
  return {id: s.id, text: (s.innerText || '').slice(0, 30), over: Math.max(r.top - Math.min(...k.map(q => q.top)),
          Math.max(...k.map(q => q.bottom)) - r.bottom)}; }).filter(Boolean)"""

ZONES = """() => [...document.querySelectorAll('#plate,.panel')].map(e => { const r = e.getBoundingClientRect();
  return {id: e.id, x: r.left, y: r.top, w: r.width, h: r.height}; })"""

FURN = """() => [...document.querySelectorAll('.tag,.foot,.ex,#logo')].map(e => { const r = e.getBoundingClientRect();
  return {id: e.id, x: r.left, y: r.top, w: r.width, h: r.height}; })"""   # a block ::before bar (a brand footer rule) sits inside the box

def overlap(a, c, grow=0):
    ix = max(0, min(a['x'] + a['w'], c['x'] + c['w'] + grow) - max(a['x'], c['x'] - grow))
    iy = max(0, min(a['y'] + a['h'], c['y'] + c['h'] + grow) - max(a['y'], c['y'] - grow))
    return ix * iy

def check(pages, out_json=None, masks=None, margin=60, phone=390, min_px=9, pad=24):
    from playwright.sync_api import sync_playwright
    report = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get('CHROME_PATH') or None)
        for html in pages:
            html = Path(html).resolve()
            pg = b.new_page(viewport={'width': 1920, 'height': 1920})
            pg.goto(html.as_uri()); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(300)
            bb = pg.query_selector('#cv').bounding_box()
            W, H = int(bb['width']), int(bb['height'])
            pg.set_viewport_size({'width': W, 'height': H})
            els = pg.evaluate(JS)
            furn_boxes = [f for f in pg.evaluate(FURN) if f['w'] > 1 and f['h'] > 1]
            for st in pg.evaluate(STACKS):
                if st['over'] > 8:
                    report.append({'page': html.name, 'el': st['id'], 'text': st['text'], 'warn': f"TEXT OVERFLOWS AREA ({st['over']:.0f}px)"})
            zones = [z for z in pg.evaluate(ZONES) if z['w'] > 1 and z['h'] > 1]
            pg.add_style_tag(content=HIDE)
            bgimg = np.asarray(Image.open(io.BytesIO(pg.screenshot())).convert('RGB')).astype(float)
            mask = None
            src = pg.evaluate("() => { const i = document.querySelector('#plate img'); return i ? i.src : null }")
            if src and masks:
                mp = Path(masks) / f'{Path(src.split("/")[-1]).stem}.png'
                if mp.exists():
                    pg.evaluate(f"() => {{ const i=document.querySelector('#plate img'); i.style.filter='none'; i.src='{mp.resolve().as_uri()}'; }}")
                    pg.add_style_tag(content='.c>*:not(#plate){visibility:hidden !important} .c,body{background:#000 !important}')
                    pg.wait_for_timeout(300)
                    mask = np.asarray(Image.open(io.BytesIO(pg.screenshot())).convert('L')).astype(float) / 255
            pg.close()
            txt = [e for e in els if ('blk' in e['cls'] or 'note' in e['cls']) and e['w'] > 2]
            for i in range(len(txt)):
                for j in range(i + 1, len(txt)):
                    a, c = txt[i], txt[j]
                    ix = max(0, min(a['x'] + a['w'], c['x'] + c['w']) - max(a['x'], c['x']))
                    iy = max(0, min(a['y'] + a['h'], c['y'] + c['h']) - max(a['y'], c['y']))
                    if ix * iy > 0.02 * min(a['w'] * a['h'], c['w'] * c['h']):
                        report.append({'page': html.name, 'el': f"{a['id']}+{c['id']}", 'text': a['text'][:20] + ' / ' + c['text'][:20], 'issue': 'TEXT COLLISION'})
            for a in txt:                     # a block half on a zone (image window, news panel) has crossed its edge
                for z in zones:
                    ov = overlap(a, z)
                    if 0 < ov < 0.98 * a['w'] * a['h'] and min(a['y'] + a['h'], z['y'] + z['h']) - max(a['y'], z['y']) > 4:
                        report.append({'page': html.name, 'el': f"{a['id']}+{z['id']}", 'text': a['text'][:30], 'issue': 'TEXT CROSSES ZONE'})
            for a in txt:                     # content text must keep clear of the brand furniture (tag, footer, logo, chip)
                for fb in furn_boxes:
                    if overlap(a, fb) > 0:
                        report.append({'page': html.name, 'el': f"{a['id']}+{fb['id']}", 'text': a['text'][:30], 'issue': 'TEXT OVER FURNITURE'})
                    elif overlap(a, fb, 12) > 0:
                        report.append({'page': html.name, 'el': f"{a['id']}+{fb['id']}", 'text': a['text'][:30], 'warn': 'CLOSE TO FURNITURE (within 12px)'})
            for e in els:
                x0, y0 = max(0, int(e['x'])), max(0, int(e['y']))
                x1, y1 = min(W, int(e['x'] + e['w'])), min(H, int(e['y'] + e['h']))
                if x1 <= x0 or y1 <= y0:
                    report.append({'page': html.name, 'el': e['id'], 'text': e['text'], 'issue': 'OFF-CANVAS'})
                    continue
                region = bgimg[y0:y1, x0:x1].reshape(-1, 3)
                bgc = e.get('bg', '')
                if bgc.startswith('rgba') and float(bgc[bgc.index('(') + 1:-1].split(',')[3]) >= 0.85:
                    al = float(bgc[bgc.index('(') + 1:-1].split(',')[3])
                    region = region * (1 - al) + parse_color(bgc)[None, :] * al
                elif bgc.startswith('rgb(') and bgc != 'rgb(0, 0, 0)':
                    region = np.repeat(parse_color(bgc)[None, :], len(region), 0)
                worst = float(np.percentile(ratio(lum(parse_color(e['color'])[None, :])[0], lum(region)), 5))
                large = e['size'] >= 32 or (e['size'] >= 18.66 and e['weight'] >= 700)
                need = 3.0 if large else 4.5
                item = {'page': html.name, 'el': e['id'], 'cls': e['cls'], 'text': e['text'], 'contrast_p5': round(worst, 2), 'need': need}
                issues, warns = [], []
                furn = any(c in e['cls'].split() for c in ('tag', 'foot', 'ex'))
                if ('blk' in e['cls'] or furn) and mask is not None:
                    cover = float((mask[y0:y1, x0:x1] > 0.5).mean())
                    item['over_object'] = round(cover, 3)
                    if cover > 0.01:
                        issues.append('FURNITURE OVER OBJECT' if furn else 'TEXT OVER OBJECT')
                    else:                     # breathing room: the box grown by `pad` px should not reach the object either
                        near = float((mask[max(0, y0 - pad):min(H, y1 + pad), max(0, x0 - pad):min(W, x1 + pad)] > 0.5).mean())
                        if near > 0.01:
                            warns.append(f'CLOSE TO OBJECT (within {pad}px)')
                if worst < need:
                    issues.append('LOW CONTRAST')
                if ('blk' in e['cls'] or 'note' in e['cls']) and (e['x'] < margin or e['x'] + e['w'] > W - margin):
                    issues.append('OUTSIDE MARGIN')
                if 'blk' in e['cls'] and e['size'] * phone / W < min_px:     # content text only; furniture is allowed to be small
                    warns.append(f'SMALL ON PHONE ({e["size"] * phone / W:.1f}px at {phone}px wide)')
                if issues:
                    item['issue'] = ' '.join(issues)
                if warns:
                    item['warn'] = ' '.join(warns)
                report.append(item)
        b.close()
    fails = [r for r in report if r.get('issue')]
    for f in fails:
        print('FAIL', f['page'], f.get('el'), f['issue'], f.get('contrast_p5', ''), f.get('over_object', ''), f['text'][:30].replace('\n', ' '))
    for w in (r for r in report if r.get('warn')):
        print('warn', w['page'], w.get('el'), w['warn'], w['text'][:30].replace('\n', ' '))
    print(f'{len(report)} text elements, {len(fails)} failing')
    if out_json:
        Path(out_json).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    return fails

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    a = sys.argv[1:]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d  # noqa: E731
    vals = {a[a.index(k) + 1] for k in ('--masks', '--margin', '--phone', '--min-px', '--pad') if k in a}
    pages = [x for x in a if not x.startswith('--') and x not in vals]
    if not pages:
        print(__doc__); sys.exit(2)
    fl = check(pages, Path(pages[0]).parent / 'qa.json', opt('--masks', '') or None, opt('--margin', 60), opt('--phone', 390), opt('--min-px', 9.0), opt('--pad', 24))
    sys.exit(1 if fl else 0)
