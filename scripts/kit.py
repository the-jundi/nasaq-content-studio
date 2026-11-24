"""Brand-aware slide kit (nasaq-content-studio; generalised from the tech brand «طبقة التوجيه» kit): one self-contained
HTML page per slide from a spec dict + a brand profile (brand.json). Every text element is a real DOM node with a
known class, so qa_slides.py can measure it, and the page is kept next to its PNG so a slide can be re-shot later
(subset_carousel.py, last-minute fixes).

Spec keys (all optional except w/h):
  w, h, bg (token name or hex), dark (white type + white logo)
  plate      {src, x, y, w, h, fit, pos, filter}                      image, square corners, no shadow
  blocks     [{x, y, w, html, cls:'display|title|body|micro', size, color, align, lh}]   absolute text blocks
  stacks     [{x, y0, y1, w, anchor:'top|center|bottom', gap, items:[{cls, size, html, color}]}]
             a column of text blocks that flows (no guessing line counts); y0..y1 is the region it sits in
  crop       [x, y, w, h] or True (around the plate)                    printer's crop marks
  circles    [{cx, cy, rx, ry, seed}] · arrows [{x0, y0, x1, y1, seed, bend}] · underlines [{x0, x1, y, seed}]
  strikes    [{x0, y0, x1, y1, seed}] · ticks [{x, y, s, seed}]        hand marks in the accent colour
  notes      [{x (edge the note hangs from), y, text, size, rot}]       the human's handwritten-style note, no box
  stamp      {x, y, rot, scale, date}                                    the brand's trust seal (last slide only)
  logo (bool), logo_h, tag, counter, footer (bool), example (bool), decor (bool), margin, logo_top, foot_bottom, micro,
  extra_html, css, layout + fam (set by layouts.make; they become classes on the canvas)
Brand furniture (brand.json → furniture) shapes every slide without code: footer, disclosure, stamp_lines (optional seal),
logo_pos (start|center|end), tag_style (chip|plain|none), bullet (dot|square|dash|tick|none), crop_marks (bool, off by
default), bg_css ({token: CSS background}, e.g. a gradient for "dark"), plate_window ({family: [x, y, w, h]}),
cta_footer (auto|true|false), css (extra rules), decor_html (the signature layer under the type: one string, or
{layout: html, "*": html}; placeholders {W} {H} {m} {start} {end} {accent} {ink} {bg} {dark} {alt} {logo} {logo_white}
{mark}). The canvas div carries classes `bg-<token> lay-<layout> fam-<family>` (+ `dark`), so brand css can target a
slide type cleanly (.c.lay-cta .foot{...}) — see references/03-design-identity.md for recipes.
Import: from kit import load_brand, page"""
import json
from pathlib import Path

import marks

DEFAULT_TOK = {'bg': '#f6f7f8', 'surface': '#ffffff', 'alt': '#eef1f3', 'ink': '#14181c', 'ink_soft': '#3d464f',
               'sub': '#5d6771', 'accent': '#c8572b', 'link': '#9c3f1b', 'note': '#8a3a17', 'plate_bg': '#efe9df',
               'line': '#dde3e8', 'dark': '#14181c', 'sub_dark': '#b9bdc3', 'link_dark': '#ffffff'}
WEIGHTS = ('300', '400', '500', '700', '900')

def load_brand(path):
    """Read brand.json; resolve its relative paths against the file's folder; fill token defaults."""
    p = Path(path).resolve()
    b = json.loads(p.read_text(encoding='utf-8'))
    base = p.parent

    def uri(x):
        q = Path(x)
        return (q if q.is_absolute() else (base / q)).resolve().as_uri()

    def have(x, what):
        # a brand file still holding a <...> placeholder, or a path that is not there yet, is skipped with one warning
        # (the slide falls back to the system font and carries no logo) instead of a broken-image icon on every slide
        q = Path(str(x))
        try:
            ok = (q if q.is_absolute() else (base / q)).exists()
        except OSError:
            ok = False
        if not ok and (what, str(x)) not in _MISSING:
            _MISSING.add((what, str(x)))
            import sys
            print(f'kit: {what} not found, skipped: {x}', file=sys.stderr)
        return ok
    b['_dir'] = str(base)
    b['tokens'] = {**DEFAULT_TOK, **b.get('tokens', {})}
    f = b.setdefault('font', {})
    f['_uris'] = {w: uri(x) for w, x in f.get('files', {}).items() if have(x, f'font {w}')}
    lg = b.setdefault('logo', {})
    for k in ('color', 'white', 'mark_white'):
        if lg.get(k) and have(lg[k], f'logo.{k}'):
            lg['_' + k] = uri(lg[k])
    b.setdefault('furniture', {})
    b.setdefault('lang', 'ar')
    b.setdefault('dir', 'rtl' if b['lang'] in ('ar', 'fa', 'ur', 'he') else 'ltr')
    return b

_MISSING = set()

def rgba(hexc, a):
    h = hexc.lstrip('#')
    return f'rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})'

def nb(s):
    """Keep a phrase on one line (names, «30 دقيقة», compound terms): the cure for orphans and split names."""
    return f'<span style="white-space:nowrap">{s}</span>'

def ltr(s, color=None, bold=False):
    """Latin/number run inside Arabic: domain, email, model name, counter."""
    st = (f'color:{color};' if color else '') + ('font-weight:700;' if bold else '')
    return f'<bdi dir="ltr" style="{st}">{s}</bdi>'

BULLETS = {   # furniture.bullet: the marker in front of each list point. 'tick' is the tech brand hand tick, one choice among many
    'dot': ".tk::before{{content:'';display:inline-block;width:.38em;height:.38em;border-radius:50%;background:{a};margin-inline-end:.55em;vertical-align:.12em}}",
    'square': ".tk::before{{content:'';display:inline-block;width:.38em;height:.38em;background:{a};margin-inline-end:.55em;vertical-align:.12em}}",
    'dash': ".tk::before{{content:'';display:inline-block;width:.8em;height:.12em;background:{a};margin-inline-end:.5em;vertical-align:.3em}}",
    'none': '',
}

def css(b):
    T = b['tokens']
    A = T['accent'].replace('#', '%23')
    bullet = b['furniture'].get('bullet', 'dot')
    tk = (f""".tk{{padding-inline-start:1.25em;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E%3Cpath d='M5,22 L15,32 L35,6' fill='none' stroke='{A}' stroke-width='5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") {'right' if b['dir'] == 'rtl' else 'left'} .35em/.85em no-repeat}}"""
          if bullet == 'tick' else BULLETS.get(bullet, BULLETS['dot']).format(a=T['accent']))
    fam = b['font'].get('family_css', 'BrandFont')
    faces = ''.join(f'@font-face{{font-family:{fam};src:url({u});font-weight:{w}}}' for w, u in b['font']['_uris'].items())
    fallback = b['font'].get('fallback', 'sans-serif')
    return f"""{faces}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:transparent}}
.c{{position:relative;overflow:hidden;font-family:{fam},{fallback};color:{T['ink']};direction:{b['dir']}}}
.plate{{position:absolute;overflow:hidden;background:{T['plate_bg']}}} .plate img{{width:100%;height:100%;display:block}}
.blk{{position:absolute;letter-spacing:0;text-wrap:balance}}
.stack{{position:absolute;display:flex;flex-direction:column}} .stack>.blk{{position:static}}
.display{{font-weight:900;line-height:{b.get('type', {}).get('lh_display', 1.35)}}}
.title{{font-weight:700;line-height:{b.get('type', {}).get('lh_title', 1.45)}}}
.body{{font-weight:500;line-height:{b.get('type', {}).get('lh_body', 1.9)}}}
.micro{{font-weight:500;line-height:1.6}}
.note{{position:absolute;font-weight:300;color:{T['note']};white-space:nowrap;line-height:1.6}}
.hu{{background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 20' preserveAspectRatio='none'%3E%3Cpath d='M198,7 Q150,3 104,9 T2,14' fill='none' stroke='{A}' stroke-width='7' stroke-linecap='round' vector-effect='non-scaling-stroke'/%3E%3C/svg%3E") left bottom/100% .32em no-repeat;padding-bottom:.12em}}
.hs{{background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 20' preserveAspectRatio='none'%3E%3Cpath d='M198,13 Q110,6 2,9' fill='none' stroke='{A}' stroke-width='7' stroke-linecap='round' vector-effect='non-scaling-stroke'/%3E%3C/svg%3E") left 58%/100% .3em no-repeat}}
{tk}
.tag{{position:absolute;font-weight:500;letter-spacing:0;display:flex;gap:14px;align-items:center;padding:4px 14px;margin:-4px -14px}}
.tag .dot{{width:10px;height:10px;background:{T['accent']};display:inline-block}}
.foot{{position:absolute;font-weight:700;letter-spacing:.02em;direction:ltr}}
.ex{{position:absolute;font-weight:500;padding:2px 12px;margin:-2px -12px}}
svg.ov{{position:absolute;inset:0;pointer-events:none}}
"""

GRAIN = ('<filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="1.4" numOctaves="2" seed="7"/>'
         '<feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.0 1.4"/>'
         '<feComposite in="SourceGraphic" operator="in"/></filter>')

def stamp_svg(s, b):
    """Trust seal: double-ruled box, the brand mark (white-on-transparent file, recoloured through a mask), the
    brand's stamp lines, the publishing date. Rotated a few degrees with grain, like a real rubber stamp."""
    A = b['tokens']['accent']
    fam = b['font'].get('family_css', 'BrandFont')
    lines = b['furniture'].get('stamp_lines', [])
    sc = s.get('scale', 1)
    w, h = 360 * sc, 204 * sc
    mark = b['logo'].get('_mark_white')
    mh = 46 * sc
    g = [f'<g transform="translate({s["x"]},{s["y"]}) rotate({s.get("rot", -5)}) translate({-w / 2},{-h / 2})" filter="url(#grain)" opacity=".92">',
         f'<rect x="0" y="0" width="{w}" height="{h}" fill="none" stroke="{A}" stroke-width="{4.5 * sc}"/>',
         f'<rect x="{8 * sc}" y="{8 * sc}" width="{w - 16 * sc}" height="{h - 16 * sc}" fill="none" stroke="{A}" stroke-width="{1.6 * sc}"/>']
    if mark:
        g.append(f'<mask id="stmk" maskUnits="userSpaceOnUse" x="0" y="0" width="{w}" height="{h}">'
                 f'<image href="{mark}" x="0" y="{16 * sc}" width="{w}" height="{mh}" preserveAspectRatio="xMidYMid meet"/></mask>'
                 f'<rect x="0" y="0" width="{w}" height="{h}" fill="{A}" mask="url(#stmk)"/>')
    ys = (0.53, 0.745) if mark else (0.4, 0.62)
    for t, y in zip(lines[:2], ys):
        g.append(f'<text x="{w / 2}" y="{h * y}" text-anchor="middle" font-family="{fam}" font-weight="900" font-size="{33 * sc}" fill="{A}" direction="{b["dir"]}">{t}</text>')
    if s.get('date'):
        g.append(f'<text x="{w / 2}" y="{h * 0.9}" text-anchor="middle" font-family="{fam}" font-weight="700" font-size="{17 * sc}" fill="{A}" direction="ltr">{s["date"]}</text>')
    g.append('</g>')
    return ''.join(g)

def marks_svg(spec, W, H, sw, A):
    """All accent strokes for a slide as (id, kind, svg) so a reel engine can animate them one by one."""
    out = []
    pen = f'fill="none" stroke="{A}" stroke-linecap="round" stroke-linejoin="round"'
    crop = spec.get('crop')
    if crop is True and spec.get('plate'):
        p = spec['plate']
        crop = [p.get('x', 0), p.get('y', 0), p.get('w', W), p.get('h', H)]
    if crop:
        x, y, w, h = crop
        if x <= 0 or y <= 0:   # full-bleed plate: marks sit inside the canvas corners
            out.append(('crop', 'crop', f'<path d="{marks.cropmarks(48, 48, W - 96, H - 96, gap=-26, arm=26)}" {pen} stroke-width="{sw * 0.5}"/>'))
        else:
            out.append(('crop', 'crop', f'<path d="{marks.cropmarks(x, y, w, h)}" {pen} stroke-width="{sw * 0.5}"/>'))
    for i, c in enumerate(spec.get('circles', [])):
        d = marks.circle(c['cx'], c['cy'], c['rx'], c['ry'], c.get('seed', 1), c.get('overshoot', 22), c.get('start', 200), c.get('tilt', -6))
        out.append((f'c{i}', 'circle', f'<path class="draw" d="{d}" {pen} stroke-width="{sw * 2.2}"/>'
                    f'<path class="draw" d="{d}" {pen} stroke-width="{sw * 0.9}" transform="translate(2,-2)" opacity=".55"/>'))
    for i, a in enumerate(spec.get('arrows', [])):
        bd, hd = marks.arrow(a['x0'], a['y0'], a['x1'], a['y1'], a.get('seed', 2), a.get('bend', 0.22))
        out.append((f'a{i}', 'arrow', f'<path class="draw" d="{bd}" {pen} stroke-width="{sw * 1.6}"/><path class="draw" d="{hd}" {pen} stroke-width="{sw * 1.6}"/>'))
    for i, u in enumerate(spec.get('underlines', [])):
        out.append((f'u{i}', 'underline', f'<path class="draw" d="{marks.underline(u["x0"], u["x1"], u["y"], u.get("seed", 3))}" {pen} stroke-width="{sw * 1.8}"/>'))
    for i, s in enumerate(spec.get('strikes', [])):
        out.append((f's{i}', 'strike', f'<path class="draw" d="{marks.strike(s["x0"], s["y0"], s["x1"], s["y1"], s.get("seed", 4))}" {pen} stroke-width="{sw * 1.8}"/>'))
    for i, t in enumerate(spec.get('ticks', [])):
        out.append((f't{i}', 'tick', f'<path class="draw" d="{marks.tick(t["x"], t["y"], t.get("s", 34), t.get("seed", 5))}" {pen} stroke-width="{sw * 1.6}"/>'))
    return out

def page(spec, b):
    T = b['tokens']
    W, H = spec['w'], spec['h']
    rtl = b['dir'] == 'rtl'
    start, end = ('right', 'left') if rtl else ('left', 'right')     # logo sits on the reading start side
    bgname = spec.get('bg', 'bg')
    bg = T.get(bgname, bgname)
    fu = b['furniture']
    bgfill = fu.get('bg_css', {}).get(bgname, bg)        # e.g. {"dark": "linear-gradient(180deg,#16171A 40%,#000)"}
    dark = spec.get('dark', False)
    ink = '#ffffff' if dark else T['ink']
    chip = rgba(T['dark'] if dark else T['bg'], .9)
    sw = spec.get('stroke', 3.2 if H <= 1350 else 4.2)
    m = spec.get('margin', 72)
    micro = spec.get('micro', 26)
    parts = []
    p = spec.get('plate')
    if p:
        parts.append(f'<div class="plate" id="plate" style="left:{p.get("x", 0)}px;top:{p.get("y", 0)}px;width:{p.get("w", W)}px;height:{p.get("h", H)}px">'
                     f'<img src="{Path(p["src"]).resolve().as_uri()}" style="object-fit:{p.get("fit", "cover")};object-position:{p.get("pos", "50% 50%")};filter:{p.get("filter", "none")}"></div>')
    parts.append(spec.get('under_html', ''))
    d = fu.get('decor_html')
    if isinstance(d, dict):                                   # a decor per slide type: {"cover": ..., "cta": ..., "*": ...}
        d = d.get(spec.get('layout', ''), d.get('*'))
    if d and spec.get('decor', True):                         # the brand's signature layer, under the type
        for key, val in (('{W}', W), ('{H}', H), ('{m}', m), ('{start}', start), ('{end}', end), ('{accent}', T['accent']), ('{ink}', T['ink']), ('{bg}', bg),
                         ('{dark}', T['dark']), ('{alt}', T['alt']), ('{logo}', b['logo'].get('_color', '')),
                         ('{logo_white}', b['logo'].get('_white', '')), ('{mark}', b['logo'].get('_mark_white', ''))):
            d = d.replace(key, str(val))
        parts.append(f'<div id="decor" style="position:absolute;inset:0;pointer-events:none">{d}</div>')
    k = 0
    for bl in spec.get('blocks', []):
        st = (f'left:{bl.get("x", m)}px;top:{bl["y"]}px;width:{bl.get("w", W - 2 * m)}px;font-size:{bl.get("size", 40)}px;'
              f'color:{bl.get("color", ink)};text-align:{bl.get("align", start)}' + (f';line-height:{bl["lh"]}' if bl.get('lh') else ''))
        parts.append(f'<div class="blk {bl.get("cls", "body")}" id="b{k}" style="{st}">{bl["html"]}</div>')
        k += 1
    for si, s in enumerate(spec.get('stacks', [])):
        y0, y1 = s.get('y0', m), s.get('y1', H - m)
        jc = {'top': 'flex-start', 'center': 'center', 'bottom': 'flex-end'}[s.get('anchor', 'top')]
        items = []
        for it in s['items']:
            st = f'font-size:{it.get("size", 40)}px;color:{it.get("color", ink)};text-align:{it.get("align", start)}'
            if it.get('mt') is not None:
                st += f';margin-top:{it["mt"]}px'
            items.append(f'<div class="blk {it.get("cls", "body")}" id="b{k}" style="{st}">{it["html"]}</div>')
            k += 1
        parts.append(f'<div class="stack" id="s{si}" style="left:{s.get("x", m)}px;top:{y0}px;width:{s.get("w", W - 2 * m)}px;'
                     f'height:{y1 - y0}px;justify-content:{jc};gap:{s.get("gap", 24)}px">{"".join(items)}</div>')
    svg = [f'<svg class="ov" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs>{GRAIN}</defs>']
    for mid, kind, s in marks_svg(spec, W, H, sw, T['accent']):
        svg.append(f'<g id="m-{mid}" data-kind="{kind}">{s}</g>')
    if spec.get('stamp') and b['furniture'].get('stamp_lines'):
        svg.append(f'<g id="stamp">{stamp_svg(spec["stamp"], b)}</g>')
    svg.append('</svg>')
    parts.append(''.join(svg))
    for i, n in enumerate(spec.get('notes', [])):
        parts.append(f'<div class="note" id="n{i}" style="{start}:{W - n["x"] if rtl else n["x"]}px;top:{n["y"]}px;font-size:{n.get("size", 34)}px;'
                     f'transform-origin:{start} center;transform:rotate({n.get("rot", -1)}deg)">{n["text"]}</div>')
    lg = b['logo']
    src = lg.get('_white') if dark else lg.get('_color')
    lh = spec.get('logo_h', lg.get('height', 58))
    if isinstance(lh, dict):                                  # {"portrait": 84, "landscape": 64, "*": 72}
        lh = lh.get(spec.get('fam', ''), lh.get('*', 58))
    if spec.get('logo', True) and src:
        pos = f'{start}:{m}px' if fu.get('logo_pos', 'start') == 'start' else (
            f'{end}:{m}px' if fu['logo_pos'] == 'end' else 'left:50%;transform:translateX(-50%)')
        parts.append(f'<img id="logo" src="{src}" style="position:absolute;{pos};top:{spec.get("logo_top", m)}px;height:{lh}px">')
    ts = fu.get('tag_style', 'chip')
    if spec.get('tag') and ts != 'none':
        tchip = 'transparent' if ts == 'plain' else chip
        cnt = f'<bdi dir="ltr" style="opacity:.6">{spec["counter"]}</bdi>' if spec.get('counter') else ''
        parts.append(f'<div class="tag" id="tag" style="background:{tchip};{end}:{spec.get("tag_x", m)}px;top:{spec.get("logo_top", m) + 12}px;'
                     f'font-size:{micro}px;color:{ink};direction:{b["dir"]}"><span class="dot"></span><span>{spec["tag"]}</span>{cnt}</div>')
    ft = fu.get('footer')
    if spec.get('footer', True) and ft:
        parts.append(f'<div class="foot" id="foot" style="{end}:{spec.get("foot_x", m)}px;bottom:{spec.get("foot_bottom", m)}px;font-size:{micro}px;color:{ink}">{ft}</div>')
    if spec.get('example'):
        parts.append(f'<div class="ex" id="ex" style="background:{chip};{start}:{spec.get("ex_x", m)}px;bottom:{spec.get("foot_bottom", m)}px;'
                     f'font-size:{micro}px;color:{ink}">{b["furniture"].get("disclosure", "مثال توضيحي")}</div>')
    parts.append(spec.get('extra_html', ''))
    cls = ' '.join(['c', f'bg-{bgname}' if bgname in T else 'bg-custom', f'lay-{spec.get("layout", "raw")}', f'fam-{spec.get("fam", "")}'] + (['dark'] if dark else []))
    return (f'<!doctype html><html lang="{b["lang"]}" dir="{b["dir"]}"><head><meta charset="utf-8"><style>{css(b)}{fu.get("css", "")}{spec.get("css", "")}</style></head>'
            f'<body><div class="{cls}" id="cv" style="width:{W}px;height:{H}px;background:{bgfill}">{"".join(parts)}</div>{spec.get("script", "")}</body></html>')
