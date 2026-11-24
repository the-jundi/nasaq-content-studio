"""Caption lint for a batch, before anything is written into delivery folders (nasaq-content-studio).

  python lint_captions.py captions.json --brand brand.json

captions.json: {"post01": {"ig": "...", "x": ["tweet 1", "reply", ...], "x_media": [[1, 2, 3, 4], []],
                           "x_poll": ["..."], "li": "...", "li_poll": ["..."], "news": false}, ...}
Errors: a tweet over 280 weighted characters (twitter-text v3: Arabic 1, URL 23, emoji 2); media on a reply or more than
4 media on X; contact line missing (last tweet, or first reply when "news": true; IG; LinkedIn); brand hashtag missing on
IG/LinkedIn; a banned word; a misspelt brand name; IG caption over 2,200 or LinkedIn over 3,000; poll options over
4 or over 25 (X) / 30 (LinkedIn) characters; dialect words on any platform whose register is "formal".
Warnings: first line over 10 words, a Latin first word, hashtags on X, more hashtags than the brand allows, Latin «AI»
inside Arabic. brand.json keys: contact_line, hashtag, captions{banned_words, spelling{wrong: right}, max_hashtags,
register {"ig": "dialect|mixed|formal", "x": ..., "li": ...} (default: LinkedIn formal, the rest mixed; the older
li_formal: false still turns LinkedIn to mixed), ai_latin_ok (default false)}. A formal-register brand (a government
body, a law firm, a real-estate developer) sets every platform to "formal"."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xlen import x_weighted_len, dialect_words  # noqa: E402

AR = '؀-ۿ'

def first_line(t):
    return next((ln for ln in t.strip().splitlines() if ln.strip()), '')

def lint(caps, brand):
    c = brand.get('captions', {})
    contact, tag = brand.get('contact_line'), brand.get('hashtag')
    banned, spelling = c.get('banned_words', []), c.get('spelling', {})
    max_tags = c.get('max_hashtags', 3)
    reg = {'ig': 'mixed', 'x': 'mixed', 'li': 'formal' if c.get('li_formal', True) else 'mixed', **c.get('register', {})}
    errs, warns, tweets = [], [], []

    def common(where, text):
        for w in banned:
            if w in text:
                errs.append(f'{where}: banned word «{w}»')
        for wrong, right in spelling.items():
            if re.search(rf'(?<![{AR}]){re.escape(wrong)}(?![{AR}])', text):
                errs.append(f'{where}: «{wrong}» should be «{right}»')
        if not c.get('ai_latin_ok') and re.search(rf'[{AR}]\s+AI\s+[{AR}]', text):
            warns.append(f'{where}: Latin «AI» inside an Arabic sentence (write الذكاء الاصطناعي)')
        fl = first_line(text)
        if len(fl.split()) > 10:
            warns.append(f'{where}: first line has {len(fl.split())} words (aim for ≤ 10)')
        if re.match(r'\s*[A-Za-z]', fl):
            warns.append(f'{where}: first line starts with a Latin word')

    for pid, p in caps.items():
        for k in ('ig', 'li'):
            t = p.get(k)
            if t is None:
                continue
            common(f'{pid} {k}', t)
            lim = 2200 if k == 'ig' else 3000
            if len(t) > lim:
                errs.append(f'{pid} {k}: {len(t)} characters (max {lim})')
            if contact and contact not in t:
                errs.append(f'{pid} {k}: contact line missing')
            if tag and tag not in t and not p.get(f'{k}_poll'):
                errs.append(f'{pid} {k}: brand hashtag {tag} missing')
            n = len(re.findall(r'#\S+', t))
            if n > max_tags:
                warns.append(f'{pid} {k}: {n} hashtags (brand limit {max_tags})')
            if reg.get(k) == 'formal' and dialect_words(t):
                errs.append(f'{pid} {k}: dialect words in a formal-register caption: {", ".join(sorted(set(dialect_words(t))))}')
        xs = p.get('x') or []
        for i, t in enumerate(xs):
            n = x_weighted_len(t)
            tweets.append((n, f'{pid} tweet {i + 1}'))
            if n > 280:
                errs.append(f'{pid} tweet {i + 1}: {n}/280 weighted')
            if reg.get('x') == 'formal' and dialect_words(t):
                errs.append(f'{pid} tweet {i + 1}: dialect words in a formal-register tweet: {", ".join(sorted(set(dialect_words(t))))}')
            if re.search(r'#\S+', t) and not (tag and re.findall(r'#\S+', t) == [tag]):
                warns.append(f'{pid} tweet {i + 1}: hashtags on X (keep none, or the brand tag only)')
        if xs:
            common(f'{pid} x', xs[0])
            for t in xs[1:]:
                for w in banned:
                    if w in t:
                        errs.append(f'{pid} x reply: banned word «{w}»')
            where_contact = xs[1] if p.get('news') and len(xs) > 1 else xs[-1]
            if contact and contact not in where_contact:
                errs.append(f'{pid} x: contact line must be in the {"first reply" if p.get("news") else "last tweet"}')
        for i, m in enumerate(p.get('x_media') or []):
            if len(m) > 4:
                errs.append(f'{pid} x: tweet {i + 1} attaches {len(m)} media (max 4)')
            if i > 0 and m:
                errs.append(f'{pid} x: media on reply {i + 1}; all media go on tweet 1, replies are text only')
        for k, lim in (('x_poll', 25), ('li_poll', 30)):
            opts = p.get(k) or []
            if len(opts) > 4:
                errs.append(f'{pid} {k}: {len(opts)} options (max 4)')
            for o in opts:
                if len(o) > lim:
                    errs.append(f'{pid} {k}: option «{o}» is {len(o)} characters (max {lim})')
    return errs, warns, sorted(tweets, reverse=True)[:5]

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    a = sys.argv[1:]
    if not a or '--brand' not in a:
        print(__doc__); sys.exit(2)
    caps = json.loads(Path(a[0]).read_text(encoding='utf-8'))
    brand = json.loads(Path(a[a.index('--brand') + 1]).read_text(encoding='utf-8'))
    e, w, longest = lint(caps, brand)
    print(f'{len(caps)} posts, {sum(len(p.get("x") or []) for p in caps.values())} tweets')
    for x in e:
        print('ERROR  ', x)
    for x in w:
        print('warning', x)
    print('longest tweets:', '; '.join(f'{n} {k}' for n, k in longest))
    print(f'{len(e)} error(s), {len(w)} warning(s)' if e or w else 'no problems')
    sys.exit(1 if e else 0)
