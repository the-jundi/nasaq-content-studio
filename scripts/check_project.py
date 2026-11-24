#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check a brand project before rendering and before a content style is adopted.
It reads brand.json and says what is missing or inconsistent: official files that brand.json points to but that are not
on disk, colours still at the template defaults, posts that name an undefined style, an image-generation permission
that is incomplete. Read-only. Standard library only.

  python check_project.py [<project folder or brand.json>] [--for render|adopt]

Exit code 1 when something BLOCKS the stage asked for (--for), 0 otherwise. Guide: references/03-design-identity.md §0"""
import argparse
import json
import re
import sys
from pathlib import Path


def placeholder(v):
    return isinstance(v, str) and bool(re.search(r'<[^<>]+>', v))


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project', nargs='?', default='.')
    ap.add_argument('--for', dest='stage', choices=['render', 'adopt'], default='render')
    a = ap.parse_args()
    p = Path(a.project)
    bfile = p if p.is_file() else p / 'brand.json'
    if not bfile.exists():
        raise SystemExit(f'no brand.json at {bfile} (run the first interview, then init_project.py)')
    root = bfile.parent
    b = json.loads(bfile.read_text(encoding='utf-8'))
    block, warn, ok = [], [], []

    def exists(rel):
        q = Path(str(rel))
        try:
            return (q if q.is_absolute() else root / q).exists()
        except OSError:
            return False

    # ---- official identity: the fixed part every style sits on
    logo = b.get('logo') or {}
    if not logo.get('color') or placeholder(logo.get('color')) or not exists(logo['color']):
        block.append(f"الشعار الرسمي غير موجود على القرص: {logo.get('color') or '(لم يُحدَّد)'}. لا يُرسم شعار؛ اطلب ملفه من صاحب العلامة.")
    else:
        ok.append('الشعار الملون موجود')
    if logo.get('white') and not placeholder(logo['white']) and not exists(logo['white']):
        warn.append(f"الشعار الأبيض المشار إليه غير موجود: {logo['white']} (يلزم للشرائح الداكنة)")
    tok = b.get('tokens') or {}
    if str(tok.get('_status', '')).upper().startswith('TEMPLATE'):
        block.append('الألوان ما زالت ألوان القالب: خذها من ملف الشعار الرسمي (find_brand_identity.py)، ثم احذف tokens._status أو اكتب مصدرها.')
    else:
        ok.append('الألوان محددة (تحقق أن مصدرها ملف الشعار)')
    fonts = (b.get('font') or {}).get('files') or {}
    missing = [w for w, f in fonts.items() if placeholder(f) or not exists(f)]
    if not fonts or len(missing) == len(fonts):
        warn.append('لا ملف خط موجود: الرندر سيستعمل خط النظام. حدّد خط العلامة، أو خطًّا واحدًا للأساليب كلها.')
    elif missing:
        warn.append(f"أوزان خط مفقودة: {', '.join(missing)}")
    if not b.get('contact_line') or placeholder(b.get('contact_line')):
        warn.append('سطر التواصل غير مكتمل: لا تُنتَج شرائح الدعوة النهائية قبل اكتماله.')

    # ---- content styles
    style = b.get('style') or {}
    styles = {k: v for k, v in (b.get('styles') or {}).items() if not k.startswith('_')}
    phase = style.get('phase') or 'explore'
    if phase == 'explore':
        if len(styles) < 2:
            (block if a.stage == 'render' else warn).append(
                f'مرحلة الاستكشاف تحتاج أسلوبين على الأقل في brand.json ← styles (الموجود: {len(styles)}). المرجع 03 §0 ب.')
        else:
            ok.append(f"أساليب هذا التشغيل: {'، '.join(styles)}")
    else:
        ad = style.get('adopted')
        if not ad:
            block.append('style.phase = adopted لكن style.adopted فارغ.')
        if not (root / 'design-system.md').exists():
            block.append('الأسلوب مثبّت لكن design-system.md غير موجود: اكتبه من assets/design-system.template.md بدليل الأرقام.')
        else:
            ok.append(f'الأسلوب المثبّت: {ad}، ونظامه مكتوب')
    posts_file = root / 'posts.json'
    if posts_file.exists():
        try:
            posts = json.loads(posts_file.read_text(encoding='utf-8')).get('posts', [])
        except ValueError:
            posts = []
            warn.append('posts.json لا يُقرأ (JSON غير صحيح).')
        undefined = sorted({str(x['style']) for x in posts if x.get('style') and x['style'] not in styles})
        if undefined:
            block.append(f"منشورات تسمّي أسلوبًا غير معرّف في brand.json ← styles: {'، '.join(undefined)}")
        unstyled = [x['id'] for x in posts if not x.get('style')]
        if unstyled and phase == 'explore' and posts:
            warn.append(f"{len(unstyled)} منشور بلا أسلوب في مرحلة الاستكشاف (لن يدخل حكم الأساليب): {'، '.join(unstyled[:6])}")
        counts = {}
        for x in posts:
            if x.get('style'):
                counts[x['style']] = counts.get(x['style'], 0) + 1
        thin = [k for k, n in counts.items() if n < 2]
        if thin and phase == 'explore':
            warn.append(f"أسلوب في منشور واحد فقط هذا التشغيل: {'، '.join(thin)} (يلزم منشوران ليُقارَن)")

    # ---- image generation permission
    ig = b.get('image_generation') or {}
    if ig.get('allowed'):
        if not ig.get('tool'):
            block.append('image_generation.allowed = true بلا اسم أداة محدد: الإذن لأداة بعينها (المرجع 15).')
        if not ig.get('cap_week_usd'):
            warn.append('الإذن بتوليد الصور بلا سقف أسبوعي: اسأل صاحب العلامة عن السقف.')
        if not ig.get('approved_by') or not ig.get('approved_on'):
            warn.append('الإذن بتوليد الصور بلا اسم من أذن أو تاريخه.')
    else:
        ok.append('توليد الصور غير مأذون: تصميم بالكود وبصور العلامة الحقيقية')

    if a.stage == 'adopt' and not (root / 'ledger.json').exists():
        block.append('لا ledger.json: لا تثبيت بلا أرقام (ledger.py styles).')

    print(f"فحص المشروع · {b.get('name') or ''} · للمرحلة: {'الرندر' if a.stage == 'render' else 'تثبيت الأسلوب'}")
    for title, items in (('يمنع المتابعة', block), ('يحتاج انتباهًا', warn), ('سليم', ok)):
        if items:
            print(f'\n{title}:')
            for x in items:
                print('  -', x)
    if not block:
        print('\nلا شيء يمنع المتابعة.')
    sys.exit(1 if block else 0)


if __name__ == '__main__':
    main()
