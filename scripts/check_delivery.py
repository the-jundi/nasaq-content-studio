"""Pre-flight check of a per-platform delivery folder before anything is uploaded (nasaq-content-studio skill).
Layout it expects (see references/10-delivery-drive-approvals.md):
  <root>/<platform folder>/<day folder>/<post folder>/{01.png, 02.png ... | reel.mp4 + cover.png | doc.pdf, <caption file>}

  python check_delivery.py "<root>" [--brand brand.json]
Errors (exit 1): an X post with more than 4 media or a tweet over 280 weighted characters; an Instagram carousel over
20 items; a post folder without a caption file or with an empty one; a banned word; the brand's contact line missing.
Warnings: image ratios a platform will crop, hashtags over the brand's limit, captions over platform limits.
brand.json keys used (all optional): contact_line, banned_words, max_hashtags, caption_file, platform_folders
({"ig": "...", "x": "...", "li": "..."} substrings of the platform folder names)."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xlen import x_weighted_len  # noqa: E402

MEDIA = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.mov', '.pdf'}
IMG = {'.png', '.jpg', '.jpeg', '.webp'}
COVER = re.compile(r'غلاف|cover|thumbnail', re.I)        # reference thumbnails, not uploaded as media
DEFAULT_PF = {'ig': ['Instagram', 'إنستقرام', 'انستقرام'], 'x': [' X', 'إكس', 'Twitter'], 'li': ['LinkedIn', 'لينكدإن']}
BLOCK = re.compile(r'━━━ (.+?) ━━━\n(.*?)(?=\n━━━ |\Z)', re.S)

def platform_of(name, pf):
    for k, keys in pf.items():
        if any(s in name for s in ([keys] if isinstance(keys, str) else keys)):
            return k
    return None

def tweets(text):
    """caption file blocks «━━━ التغريدة N · أرفق: 01.png، 02.png ━━━» -> [(label, body, [attachments])]; no blocks = one tweet"""
    out = []
    for lab, body in BLOCK.findall(text):
        if 'التصويت' in lab or 'poll' in lab.lower():
            continue
        att = re.split(r'[،,]\s*', lab.split('أرفق:', 1)[1].strip()) if 'أرفق:' in lab else []
        out.append((lab, body.strip(), [a for a in att if a]))
    return out or [('tweet', text.strip(), [])]

def check(root, brand):
    from PIL import Image
    errs, warns, scanned = [], [], {}
    dl, cp = brand.get('delivery', {}), brand.get('captions', {})      # brand.json nests these; flat keys also work
    pf = brand.get('platform_folders') or dl.get('platform_folders') or DEFAULT_PF
    cap_name = brand.get('caption_file') or dl.get('caption_file') or 'النص (كابشن).txt'
    contact, banned = brand.get('contact_line'), brand.get('banned_words') or cp.get('banned_words', [])
    max_tags = brand.get('max_hashtags') or cp.get('max_hashtags', 3)
    for plat_dir in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        plat = platform_of(' ' + plat_dir.name, pf)
        if not plat:
            continue
        posts = sorted({c.parent for c in plat_dir.rglob(cap_name)} | {d for d in plat_dir.rglob('*') if d.is_dir()
                        and any(f.suffix.lower() in MEDIA for f in d.iterdir()) and d.parent != plat_dir})
        scanned[plat] = scanned.get(plat, 0) + len(posts)
        for post in posts:
            where = f'{plat}: {post.relative_to(root)}'
            media = [f for f in sorted(post.iterdir()) if f.suffix.lower() in MEDIA]
            upload = [f for f in media if not COVER.search(f.stem)]
            cap = post / cap_name
            text = cap.read_text(encoding='utf-8') if cap.exists() else ''
            if not text.strip():
                errs.append(f'{where}: no caption file or it is empty ({cap_name})')
            for w in banned:
                if w in text:
                    errs.append(f'{where}: banned word «{w}»')
            tags = re.findall(r'#\S+', text)
            if len(tags) > max_tags * (len(tweets(text)) if plat == 'x' else 1):
                warns.append(f'{where}: {len(tags)} hashtags (brand limit {max_tags})')
            if contact and text.strip() and contact not in text:
                errs.append(f'{where}: the contact line is missing')
            if plat == 'x':
                if len(upload) > 4:
                    errs.append(f'{where}: {len(upload)} media — X allows at most 4 in one post; make an X-only set of 4')
                for lab, body, att in tweets(text):
                    n = x_weighted_len(body)
                    if n > 280:
                        errs.append(f'{where}: «{lab}» is {n}/280 weighted characters')
                    if len(att) > 4:
                        errs.append(f'{where}: «{lab}» attaches {len(att)} media (max 4)')
                    for a in att:
                        if not (post / a).exists():
                            errs.append(f'{where}: «{lab}» attaches {a}, which is not in the folder')
            if plat == 'ig' and len(upload) > 20:
                errs.append(f'{where}: {len(upload)} items — Instagram carousels hold at most 20')
            if plat == 'ig' and len(text) > 2200:
                errs.append(f'{where}: caption {len(text)} characters (Instagram max 2,200)')
            if plat == 'li' and len(text) > 3000:
                errs.append(f'{where}: caption {len(text)} characters (LinkedIn max 3,000)')
            imgs = [f for f in upload if f.suffix.lower() in IMG]
            for f in imgs:
                w, h = Image.open(f).size
                r = w / h
                if plat == 'ig' and not (0.75 <= r <= 1.91) and not (abs(r - 9 / 16) < .01):
                    warns.append(f'{where}/{f.name}: ratio {w}x{h} will be cropped on Instagram (feed accepts 3:4 to 1.91:1)')
                if plat == 'x' and len(imgs) > 1 and not (0.75 <= r <= 1.18):
                    warns.append(f'{where}/{f.name}: {w}x{h} in an X multi-image post gets cropped (keep 3:4 .. ~20:17; 4:5 is safe)')
    return errs, warns, scanned

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    b = {}
    if '--brand' in sys.argv:
        b = json.loads(Path(sys.argv[sys.argv.index('--brand') + 1]).read_text(encoding='utf-8'))
    e, w, n = check(sys.argv[1], b)
    print('scanned posts:', ', '.join(f'{k} {v}' for k, v in n.items()) or 'none (check the platform folder names)')
    for x in e:
        print('ERROR  ', x)
    for x in w:
        print('warning', x)
    print(f'{len(e)} error(s), {len(w)} warning(s)' if e or w else 'no problems')
    sys.exit(1 if e else 0)
