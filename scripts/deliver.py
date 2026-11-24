"""Per-platform delivery tree from a built batch (nasaq-content-studio; generalised from the tech-brand and real-estate-brand runs).
Nothing is published: it only copies files and writes caption files for a human to upload.

  python deliver.py posts.json [--captions captions.json] [--brand brand.json] [--dry <dir>]

Reads posts.json (the same file build.py used) plus, per post, these optional keys:
  "title": "عنوان المنشور"                       post folder name and LinkedIn document title (default: the id)
  "slot": {"day": "اليوم 1 - الأحد 8 نوفمبر", "time": "8.30ص"}     day folder + time prefix (default: «بلا موعد»);
                                                 post folders are numbered by their order within the day
  "platforms": ["ig", "x", "li"]                 where the post goes (default all three)
  "ig_format": "ig", "x_format": "ig", "li_format": "w"           which built format feeds each platform
  "video": "out/post04/reel.mp4", "cover": "out/post04/cover.png"  a reel instead of slides (IG/X), cover kept as غلاف
  "video_w": "out/post04/wide.mp4", "cover_w": "out/post04/wide-cover.png"  optional 16:9 cut: X and LinkedIn get it
                                                 («فيديو أفقي 16x9.mp4» + «غلاف الفيديو.png») instead of the reel/slides
brand.json → delivery: local_root (the tree), platform_folders {ig, x, li}, caption_file, sheet_names {fmt: name}, note (line under the review file title), readme (a file copied as
«00 - اقرأني أولًا.md»), production_files [paths copied to «10 - ملفات الإنتاج»]. captions.json is lint_captions.py's
format (ig, x [..], x_media [[..]], li, alt {"1": "..."}).
X: 4 media at most, all on tweet 1. A longer carousel needs out/<id>/x4/x-1..4.png from subset_carousel.py first;
without it the post stops with an error instead of shipping a 5-image tweet. LinkedIn: a landscape carousel goes as
the PDF build.py --pdf made, a single landscape slide as its PNG.
An existing tree is renamed to «… - أرشيف <time>», never deleted. Afterwards run check_delivery.py, then mirror.py."""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PF_DEFAULT = {'ig': '01 - إنستقرام Instagram (عمودي)', 'x': '02 - إكس X', 'li': '03 - لينكدإن LinkedIn (أفقي)'}
SHEETS = {'ig': 'إنستقرام وكاروسيل إكس', 'w': 'لينكدإن والأفقي', 'st': 'الستوري', 'sq': 'المربع'}

def slides(out, pid, fmt):
    d = out / pid / fmt
    return sorted(d.glob(f'{pid}-{fmt}-*.png'), key=lambda p: int(p.stem.rsplit('-', 1)[1])) if d.exists() else []

def deliver(posts_path, caps_path=None, brand_path=None, dry=None):
    pp = Path(posts_path).resolve()
    base = pp.parent
    doc = json.loads(pp.read_text(encoding='utf-8'))
    brand = json.loads(Path(brand_path or base / doc['brand']).read_text(encoding='utf-8'))
    caps = json.loads(Path(caps_path or base / 'captions.json').read_text(encoding='utf-8'))
    dl = brand.get('delivery', {})
    root = Path(dry or dl['local_root'])
    pf = {**PF_DEFAULT, **dl.get('platform_folders', {})}
    capf = dl.get('caption_file', 'النص (كابشن).txt')
    out = (base / doc.get('out', 'out')).resolve()
    if root.exists():                                        # never delete a delivery: archive it
        root.rename(root.with_name(root.name + ' - أرشيف ' + time.strftime('%Y%m%d-%H%M%S')))
    root.mkdir(parents=True)
    problems = []
    review = [f'# {brand.get("name", "")}: كل النصوص في ملف واحد (للمراجعة)\n\n> {dl.get("note", "لم يُنشر شيء ولم يُجدوَل.")}\n']

    per_day = {}
    for post in doc['posts']:
        pid = post['id']
        c = caps.get(pid)
        if not c:
            problems.append(f'{pid}: no captions'); continue
        title = post.get('title', pid)
        slot = post.get('slot', {})
        day, tm = slot.get('day', 'بلا موعد'), slot.get('time', '')
        per_day[day] = k = per_day.get(day, 0) + 1

        def pdir(plat):
            d = root / pf[plat] / day / (f'{k} - {tm} - {title}' if tm else f'{k} - {title}')
            d.mkdir(parents=True, exist_ok=True)
            return d

        def wide_copy(post, d):
            """the 16:9 cut (X and LinkedIn), when the post has one; True if copied"""
            if not post.get('video_w'):
                return False
            vw = base / post['video_w']
            shutil.copy2(vw, d / ('فيديو أفقي 16x9' + vw.suffix))
            if post.get('cover_w'):
                shutil.copy2(base / post['cover_w'], d / 'غلاف الفيديو.png')
            return True
        plats = post.get('platforms', ['ig', 'x', 'li'])
        video = post.get('video') and (base / post['video'])
        if 'ig' in plats and c.get('ig'):
            d = pdir('ig')
            if video:
                shutil.copy2(video, d / ('ريل' + video.suffix))
                if post.get('cover'):
                    shutil.copy2(base / post['cover'], d / 'غلاف الريل.png')
            else:
                src = slides(out, pid, post.get('ig_format', 'ig'))
                if not src:
                    problems.append(f'{pid} ig: no slides in {out / pid}')
                for i, s in enumerate(src, 1):
                    shutil.copy2(s, d / f'{i:02d}.png')
            alt = c.get('alt') or {}
            alt_txt = ('\n\n━━━ النص البديل (اختياري، لكل صورة) ━━━\n' + '\n'.join(f'{int(n):02d}.png: {v}' for n, v in alt.items())) if alt else ''
            (d / capf).write_text(c['ig'] + alt_txt + '\n', encoding='utf-8')
        if 'x' in plats and c.get('x'):
            d = pdir('x')
            if video:
                wide_copy(post, d) or shutil.copy2(video, d / ('ريل' + video.suffix))
            else:
                x4 = sorted((out / pid / 'x4').glob('x-*.png'))
                src = x4 or slides(out, pid, post.get('x_format', 'ig'))
                if len(src) > 4:
                    problems.append(f'{pid} x: {len(src)} slides; run subset_carousel.py to make out/{pid}/x4 (4 media max)')
                    src = []
                for i, s in enumerate(src, 1):
                    shutil.copy2(s, d / f'{i:02d}.png')
            blocks = []
            xm = c.get('x_media') or [[]]
            for i, t in enumerate(c['x'], 1):
                m = xm[i - 1] if i - 1 < len(xm) else []
                head = f'التغريدة {i} · أرفق: ' + '، '.join(f'{n:02d}.png' for n in m) if m else (
                    f'التغريدة {i}' if i == 1 else f'التغريدة {i} (ردّ على التغريدة {i - 1})')
                blocks.append(f'━━━ {head} ━━━\n{t}')
            (d / capf).write_text('\n\n'.join(blocks) + '\n', encoding='utf-8')
        if 'li' in plats and c.get('li'):
            d = pdir('li')
            fmt = post.get('li_format', 'w')
            pdf = out / pid / f'{pid}-{fmt}.pdf'
            src = [] if wide_copy(post, d) else slides(out, pid, fmt)
            if post.get('video_w'):
                pass
            elif len(src) > 1:
                if pdf.exists():
                    shutil.copy2(pdf, d / f'ارفعه كمستند PDF - {title}.pdf')
                else:
                    problems.append(f'{pid} li: {len(src)} landscape slides but no {pdf.name} (build.py --pdf)')
            elif src:
                shutil.copy2(src[0], d / '01.png')
            else:
                problems.append(f'{pid} li: no {fmt} slides')
            (d / capf).write_text(c['li'] + (f'\n\nعنوان المستند عند الرفع: {title}' if len(src) > 1 else '') + '\n', encoding='utf-8')
        review.append(f'## {title} ({pid})\n\n### إنستقرام\n\n{c.get("ig", "—")}\n\n### إكس\n\n' +
                      '\n\n'.join(f'**التغريدة {i}:**\n{t}' for i, t in enumerate(c.get('x', []), 1)) +
                      f'\n\n### لينكدإن\n\n{c.get("li", "—")}\n')

    (root / '04 - كل النصوص في ملف واحد (للمراجعة).md').write_text('\n'.join(review), encoding='utf-8')
    for sh in sorted(out.glob('sheet-*.jpg')):
        fmt = sh.stem.split('-', 1)[1]
        shutil.copy2(sh, root / f'00 - نظرة سريعة - {dl.get("sheet_names", SHEETS).get(fmt, fmt)}.jpg')
    if dl.get('readme'):
        shutil.copy2(base / dl['readme'], root / '00 - اقرأني أولًا.md')
    else:
        problems.append('no delivery.readme: write it from assets/delivery-README.template.md')
    if dl.get('production_files'):
        prod = root / '10 - ملفات الإنتاج (الخطة، والدراسة، والهوية)'
        prod.mkdir()
        for f in dl['production_files']:
            if (base / f).exists():
                shutil.copy2(base / f, prod / Path(f).name)
            else:
                problems.append(f'production file missing: {f}')
    print('delivered to', root)
    for p in problems:
        print('PROBLEM', p)
    r = subprocess.run([sys.executable, str(HERE / 'check_delivery.py'), str(root), '--brand',
                        str(Path(brand_path or base / doc['brand']).resolve())])
    return 1 if problems or r.returncode else 0

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    a = sys.argv[1:]
    if not a or a[0].startswith('--'):
        print(__doc__); sys.exit(2)
    opt = lambda k: a[a.index(k) + 1] if k in a else None  # noqa: E731
    sys.exit(deliver(a[0], opt('--captions'), opt('--brand'), opt('--dry')))
