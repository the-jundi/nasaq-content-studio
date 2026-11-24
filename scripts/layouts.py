"""Slide layouts on top of kit.page (nasaq-content-studio). One call turns a plain slide dict into a kit spec at the
right type scale and safe zones for its canvas:

  cover / typo   type only (display, title, body, list, source) on a flat brand colour
  plate_full     full-bleed image, type in its clean top band
  plate_top      image on top (portrait/tall) or an image column (landscape), type beside it
  number         one big sourced number + what it means
  list           a heading + ticked points (checklists, «قبل أن…» carousels)
  news           a news card: kicker, number, title, source on top; «ماذا يعني لك؟» + means in a panel (below on
                 portrait/square/tall, an end-side column on landscape). Label: slide means_label > brand news.question;
                 panel colour: slide panel > furniture.news_panel > dark (alt on a dark slide); split (portrait .6)
  cta            the offer + the brand's literal contact line (+ the seal, only if the brand has stamp_lines)
  raw            {"spec": {...}} passed straight to kit.page

Slide keys: layout, display, title, body, list [..], source, plate (path), pos_y (0-100), plate_h, bg, dark, anchor
(top|center|bottom), example (demo disclosure chip), sizes {display: 110, ...}, notes/circles/arrows/underlines/
strikes/ticks (canvas coordinates), extra_html, css. Text values are HTML: use kit.nb()/kit.ltr() patterns
(<span style="white-space:nowrap">…</span>, <bdi dir="ltr">…</bdi>) and the inline marks .hu / .hs / .tk.
Brand-level type: brand.json -> type.scale (multiplies every type size: 0.88 suits wide Arabic faces such as Montserrat
Arabic or DIN Next) and type.sizes {family: {display: 80, ...}}; a slide's own "sizes" wins over both. Brand furniture
read here: plate_window {family: [x, y, w, h]} (the image window of plate_top; text flows beside or under it),
crop_marks (default off), cta_footer (auto|true|false). See kit.py for the rest."""
from kit import ltr

# type scale and safe zones per canvas family (measured on the tech brand weeks; Arabic at Thmanyah-like widths)
FMT = {
    'portrait':  dict(m=72, logo_top=72, top=230, foot=72, display=96, title=60, body=42, micro=30, source=30, number=190),   # 1080x1350
    'square':    dict(m=72, logo_top=72, top=220, foot=72, display=88, title=56, body=40, micro=30, source=30, number=180),   # 1080x1080
    'landscape': dict(m=64, logo_top=64, top=180, foot=64, display=76, title=50, body=42, micro=28, source=38, number=160),   # 1600x900, seen ~360px wide on a phone
    'tall':      dict(m=72, logo_top=260, top=430, foot=350, display=104, title=62, body=46, micro=34, source=34, number=210),  # 1080x1920: top 250 / bottom 340 kept clear
}

def family(W, H):
    if W > H * 1.2:
        return 'landscape'
    if H / W > 1.6:
        return 'tall'
    return 'square' if abs(W - H) < 20 else 'portrait'

TYPE_KEYS = ('display', 'title', 'body', 'micro', 'source', 'number')

def scale_for(b, fam):
    """FMT for a canvas family with the brand's type.scale and type.sizes applied (wide fonts need smaller sizes)."""
    t = b.get('type', {})
    f = dict(FMT[fam])
    k = t.get('scale', 1)
    for key in TYPE_KEYS:
        f[key] = int(round(f[key] * k))
    f.update(t.get('sizes', {}).get(fam, {}))
    return f

def contact_html(b, dark=False):
    s = b.get('contact_line', '')
    link = b['tokens']['link_dark' if dark else 'link']
    keys = [k for k in ('email', 'phone', 'domain') if b.get(k) and b[k] in s]     # email first: it contains the domain
    for i, k in enumerate(keys):
        s = s.replace(b[k], f'\x00{i}\x00')
    for i, k in enumerate(keys):
        s = s.replace(f'\x00{i}\x00', ltr(b[k], link, True))
    return s

def _lum(hexc):
    h = str(hexc).lstrip('#')
    if len(h) != 6:
        return 1.0                                   # gradients/unknown: treat as light
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4 for v in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]

def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)

def _items(sl, f, b, keys=('display', 'title', 'body', 'list', 'source')):
    T, sz = b['tokens'], {**f, **sl.get('sizes', {})}
    out = []
    for k in keys:
        v = sl.get(k)
        if not v:
            continue
        if k == 'list':
            out += [{'cls': 'body', 'size': sz['body'], 'html': f'<span class="tk">{x}</span>'} for x in v]
        elif k == 'source':
            out.append({'cls': 'micro', 'size': sz['source'], 'html': v, 'color': T['sub_dark' if sl.get('dark') else 'sub'], 'mt': 12})
        elif k == 'number':
            out.append({'cls': 'display', 'size': sz['number'], 'html': v, 'color': T['accent']})
        else:
            out.append({'cls': k, 'size': sz[k], 'html': v, **({'color': T['ink_soft']} if k == 'title' and sl.get('display') and not sl.get('dark') else {})})
    return out

def make(sl, b, W, H, tag=None, counter=None, date=None):
    lay = sl.get('layout', 'typo')
    fam = family(W, H)
    f = scale_for(b, fam)
    fu = b['furniture']
    m, rtl = f['m'], b['dir'] == 'rtl'
    dark = sl.get('dark', False)
    spec = dict(w=W, h=H, margin=m, logo_top=f['logo_top'], foot_bottom=f['foot'], micro=f['micro'], tag=tag, counter=counter,
                example=sl.get('example', False), dark=dark, layout=lay, fam=fam)
    marks_on = fu.get('crop_marks', False)          # printer's crop marks are one brand's device (the tech brand), not a default
    for k in ('notes', 'circles', 'arrows', 'underlines', 'strikes', 'ticks', 'extra_html', 'under_html', 'css', 'crop', 'logo_h', 'decor'):
        if sl.get(k) is not None:
            spec[k] = sl[k]
    if dark:
        spec['bg'] = sl.get('bg', 'dark')
    bottom = H - f['foot'] - 70
    pos = f'50% {sl.get("pos_y", 50)}%'

    if lay == 'raw':
        spec.update(sl['spec'])
        return spec

    if lay in ('cover', 'typo', 'list'):
        spec.setdefault('bg', sl.get('bg', 'bg' if lay == 'cover' else 'alt'))
        anchor = sl.get('anchor', 'center' if fam == 'landscape' else 'top')
        spec['stacks'] = [{'y0': f['top'], 'y1': bottom, 'anchor': anchor, 'items': _items(sl, f, b)}]

    elif lay == 'number':
        spec.setdefault('bg', sl.get('bg', 'alt'))
        spec['stacks'] = [{'y0': f['top'], 'y1': bottom, 'anchor': sl.get('anchor', 'center'),
                           'items': _items(sl, f, b, ('number', 'title', 'body', 'source'))}]

    elif lay == 'plate_full':
        spec.setdefault('bg', 'plate_bg')
        spec['plate'] = {'src': sl['plate'], 'pos': pos}
        if marks_on:
            spec.setdefault('crop', True)
        spec['stacks'] = [{'y0': f['top'], 'y1': int(H * sl.get('text_band', .42)), 'anchor': 'top', 'items': _items(sl, f, b)}]

    elif lay == 'plate_top':
        spec['bg'] = sl.get('bg', 'dark' if dark else 'bg')      # a dark slide keeps a dark ground under its white type
        win = sl.get('window') or fu.get('plate_window', {}).get(fam)   # the brand's image window for this canvas family
        if fam == 'landscape':
            if win:
                px, py, pw, phh = win
            else:
                pw = int(W * .375)
                px, py, phh = (0 if rtl else W - pw), 0, H
            gap = 80
            left = px + pw / 2 < W / 2
            if left:                                  # image on the left: text column on its right, and vice versa
                tx, tw = px + pw + gap, W - (px + pw + gap) - m
            else:
                tx, tw = m, px - gap - m
            spec['plate'] = {'src': sl['plate'], 'x': px, 'y': py, 'w': pw, 'h': phh, 'pos': pos}
            if left == rtl:                           # the plate sits on the end side, where tag and footer live: move them
                off = px + pw + gap if rtl else W - px + gap
                spec.update(tag_x=off, foot_x=off)
            if marks_on:
                spec.setdefault('crop', [px, py, pw, phh] if win else [px + 40, 40, pw - 80, H - 80])
            spec['stacks'] = [{'x': tx, 'w': tw, 'y0': f['top'], 'y1': bottom, 'anchor': sl.get('anchor', 'center'), 'items': _items(sl, f, b)}]
        else:
            if win:
                px, py, pw, phh = win
            else:
                px, py, pw, phh = 0, 0, W, sl.get('plate_h', int(H * .62))
            spec['plate'] = {'src': sl['plate'], 'x': px, 'y': py, 'w': pw, 'h': phh, 'pos': pos}
            if marks_on:
                spec.setdefault('crop', [px, py, pw, phh] if win else [48, 48, W - 96, phh - 96])
            spec['stacks'] = [{'y0': py + phh + 44, 'y1': bottom, 'anchor': 'top', 'items': _items(sl, f, b)}]

    elif lay == 'news':
        # the fact on top (kicker · number · title · source), «what it means for you» in a panel below (beside it on
        # landscape, on the end side where the tag and footer already live). Facts stay exactly as the source has them.
        T = b['tokens']
        spec['bg'] = sl.get('bg', 'dark' if dark else 'bg')
        top_bg = T.get(spec['bg'], spec['bg'])
        pname = sl.get('panel', fu.get('news_panel', 'alt' if dark else 'dark'))
        pval = T.get(pname, pname)
        pfill = fu.get('bg_css', {}).get(pname, pval)
        pink = '#ffffff' if _lum(pval) < .4 else T['ink']
        ink = '#ffffff' if dark else T['ink']
        acc = T['accent']
        sz = {**f, **sl.get('sizes', {})}
        news = []
        if sl.get('kicker'):
            kc = acc if _ratio(acc, top_bg) >= 4.5 else T['sub_dark' if dark else 'sub']
            news.append({'cls': 'micro', 'size': sz['micro'], 'html': sl['kicker'], 'color': kc})
        if sl.get('number'):
            news.append({'cls': 'display', 'size': sz.get('news_number', int(sz['number'] * .78)), 'html': sl['number'],
                         'color': T.get(sl.get('number_color', ''), ink)})
        for k in ('title', 'body'):
            if sl.get(k):
                news.append({'cls': k, 'size': sz[k], 'html': sl[k], 'color': ink})
        if sl.get('source'):
            news.append({'cls': 'micro', 'size': sz['source'], 'html': sl['source'], 'color': T['sub_dark' if dark else 'sub'], 'mt': 8})
        label = sl.get('means_label', b.get('news', {}).get('question', 'ماذا يعني لك؟'))
        ml_ink = '#ffffff' if _lum(acc) < .45 else T['ink']
        means = [{'cls': 'micro', 'size': int(sz['micro'] * 1.1), 'color': ml_ink,
                  'html': f'<span class="ml" style="background:{acc};padding:.12em .7em .3em;display:inline-block">{label}</span>'}]
        if sl.get('means'):
            means.append({'cls': 'body', 'size': sz['body'], 'html': sl['means'], 'color': pink})
        if fam == 'landscape':
            pw = int(W * sl.get('panel_w', .4))
            px = 0 if rtl else W - pw
            box = (px, 0, pw, H)
            nx = pw + 80 if rtl else m
            spec['stacks'] = [{'x': nx, 'w': W - pw - 80 - m, 'y0': f['top'], 'y1': bottom, 'anchor': sl.get('anchor', 'center'), 'items': news},
                              {'x': px + m, 'w': pw - 2 * m, 'y0': f['top'], 'y1': H - f['foot'] - 120, 'anchor': 'center', 'items': means}]
            on_panel = '#foot'
        else:
            split = int(H * sl.get('split', {'portrait': .6, 'square': .6, 'tall': .58}[fam]))
            box = (0, split, W, H - split)
            spec['stacks'] = [{'y0': f['top'], 'y1': split - 48, 'anchor': sl.get('anchor', 'center'), 'items': news},
                              {'y0': split + 56, 'y1': H - f['foot'] - 100, 'anchor': sl.get('panel_anchor', 'top'), 'items': means}]
            on_panel = '#foot,#ex'
        x, y, w, h = box
        spec['under_html'] = (f'<div id="panel" class="panel" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
                              f'background:{pfill}"></div>' + sl.get('under_html', ''))
        # furniture that lands on the panel takes the panel's ink; :where() keeps specificity 0 so brand css still wins
        spec['css'] = f':where(.c.lay-news) :where({on_panel}){{color:{pink}!important}}' + sl.get('css', '')

    elif lay == 'cta':
        spec['bg'] = sl.get('bg', 'dark' if dark else 'surface')
        cf = fu.get('cta_footer', 'auto')
        ft = str(fu.get('footer', '')).lower().replace('www.', '').strip()
        if cf is False or (cf == 'auto' and ft and ft in b.get('contact_line', '').lower()):
            spec['footer'] = False           # the contact line already carries the footer's address: never print it twice
        big = {**f, 'display': int(f['display'] * 1.04), 'title': int(f['title'] * .85)}
        items = _items(sl, big, b, ('display', 'title'))
        contact = [{'cls': 'micro', 'size': max(int(f['micro'] * 1.27), f['source']), 'html': contact_html(b, dark)}] if b.get('contact_line') else []
        if fam == 'landscape':
            tw = int(W * .58)
            tx = W - m - tw if rtl else m
            spec['stacks'] = [{'x': tx, 'w': tw, 'y0': f['top'], 'y1': H - 230, 'anchor': 'top', 'items': items},
                              {'x': tx, 'w': tw, 'y0': H - 230, 'y1': H - f['foot'] - 50, 'anchor': 'bottom', 'items': contact}]
            sx = W * .2 if rtl else W * .8
            spec['stamp'] = {'x': sx, 'y': H * .5, 'rot': sl.get('rot', -6), 'scale': 1.2, 'date': date}
        else:
            spec['stacks'] = [{'y0': f['top'] + 70, 'y1': int(H * .55), 'anchor': 'top', 'items': items},
                              {'y0': int(H * .8), 'y1': H - f['foot'] - 50, 'anchor': 'bottom', 'items': contact}]
            spec['stamp'] = {'x': W * (.31 if rtl else .69), 'y': H * .68, 'rot': sl.get('rot', -6), 'scale': 1.35, 'date': date}
        if not fu.get('stamp_lines'):
            spec.pop('stamp')
    else:
        raise SystemExit(f'unknown layout «{lay}»')
    return spec
