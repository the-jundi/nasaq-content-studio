#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Content ledger: one file (ledger.json) that holds where every post stands and what numbers it got.
It records; it never publishes anything. Standard library only. Guide: references/13-measure-and-improve.md

  python ledger.py init --goal leads [--brand "<name>"] [--collection manual]
  python ledger.py sync posts.json                       add the plan's posts (never overwrites tags or numbers)
  python ledger.py add post31 --title "..." --planned "2026-11-20 20:30" --tag hook=سؤال --tag format=carousel
  python ledger.py set post07 --status approved
  python ledger.py set post07 --platform ig --url https://... --at "2026-11-18 20:30" [--paid]
  python ledger.py set post07 --tag hook=رقم --test "هوك المرجعيات:hook:رقم" --hypothesis "..."
  python ledger.py snap post07 --platform ig --reach 1240 --likes 41 --saves 22 --shares 9 --dms 2 --followers 436
  python ledger.py unsnap post07 --platform ig             remove the last reading (entered by mistake)
  python ledger.py import export.csv --platform x [--map "Post Link=url"] [--add-unmatched]
  python ledger.py account --platform ig --followers 436
  python ledger.py due                                   which published posts need a reading now (24h/72h/7d/28d)
  python ledger.py board                                 status of every post and what waits on whom
  python ledger.py report [--since 2026-11-01] [--out performance/report-2026-11-24.md]
                                                         without --out it only prints; with --out it also saves the baseline in the ledger
  python ledger.py check performance/report-2026-11-24.md   fails while the analyst's placeholders are still in the report
  python ledger.py styles [--json performance/styles.json]  which content style is winning, and is it ready to be adopted

Every command takes --ledger <path> (default ./ledger.json)."""
import argparse
import csv
import datetime as dt
import json
import statistics
import sys
from pathlib import Path

STATUSES = ['idea', 'planned', 'designed', 'approved', 'scheduled', 'published', 'archived']
STATUS_AR = {'idea': 'فكرة', 'planned': 'في الخطة', 'designed': 'مصمَّم ينتظر الاعتماد', 'approved': 'معتمد ينتظر النشر',
             'scheduled': 'مجدول', 'published': 'منشور', 'archived': 'مؤرشف'}
METRICS = ['reach', 'impressions', 'views', 'likes', 'comments', 'saves', 'shares', 'profile_visits', 'follows',
           'link_clicks', 'dms', 'orders', 'avg_watch_s', 'full_watch_pct', 'followers']
# goal -> (how the governing number is built, the metrics it is built from, Arabic label)
GOALS = {
    'awareness': ('first', ['reach', 'impressions', 'views'], 'الوصول'),
    'trust': ('sum', ['saves', 'shares'], 'الحفظ + المشاركة'),
    'leads': ('sum', ['dms', 'link_clicks'], 'الرسائل + نقرات الرابط'),
    'sales': ('first', ['orders', 'link_clicks', 'dms'], 'الطلبات'),
    'hiring': ('sum', ['dms', 'link_clicks'], 'الرسائل + نقرات الرابط'),
}
CHECKPOINTS_H = [24, 72, 168, 672]
CP_AR = {24: '24 ساعة', 72: '72 ساعة', 168: '7 أيام', 672: '28 يومًا'}
MATURE_H = 120            # a reading at 5 days or later is judged as the 7-day reading
WIN, WEAK, OUTLIER = 1.5, 0.6, 5.0
PATTERN_HI, PATTERN_LO = 1.3, 0.7
# header aliases for platform exports (lower-case, spaces and underscores removed)
ALIASES = {
    'url': ['permalink', 'postlink', 'posturl', 'link', 'url', 'tweetpermalink', 'الرابط'],
    'reach': ['reach', 'accountsreached', 'الوصول'],
    'impressions': ['impressions', 'مراتالظهور'],
    'views': ['views', 'videoviews', 'plays', 'mediaviews', 'المشاهدات'],
    'likes': ['likes', 'reactions', 'الإعجابات'],
    'comments': ['comments', 'replies', 'التعليقات'],
    'saves': ['saves', 'saved', 'bookmarks', 'الحفظ'],
    'shares': ['shares', 'reposts', 'retweets', 'المشاركات'],
    'profile_visits': ['profilevisits', 'userprofileclicks', 'profileclicks', 'زياراتالملف'],
    'follows': ['follows', 'newfollowers', 'المتابعات'],
    'link_clicks': ['linkclicks', 'urlclicks', 'clicks', 'websiteclicks', 'نقراتالرابط'],
}


def now(args=None):
    v = getattr(args, 'now', None)
    return parse_time(v) if v else dt.datetime.now().replace(microsecond=0)


def parse_time(s):
    s = str(s).strip().replace('T', ' ')
    for f in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%d.%m.%Y %H:%M', '%d.%m.%Y', '%d/%m/%Y %H:%M', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(s[:19] if f.startswith('%Y') else s, f)
        except ValueError:
            continue
    raise SystemExit(f'time not understood: {s!r} (use "YYYY-MM-DD HH:MM")')


def fmt_time(t):
    return t.strftime('%Y-%m-%d %H:%M')


def load(path):
    p = Path(path)
    if not p.exists():
        raise SystemExit(f'no ledger at {p} (run: ledger.py init --goal <awareness|trust|leads|sales|hiring>)')
    return json.loads(p.read_text(encoding='utf-8'))


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def find(data, pid):
    for p in data['posts']:
        if p['id'] == pid:
            return p
    raise SystemExit(f'no post with id {pid!r} in the ledger (see: ledger.py board)')


def kv(items):
    out = {}
    for it in items or []:
        if '=' not in it:
            raise SystemExit(f'expected key=value, got {it!r}')
        k, v = it.split('=', 1)
        out[k.strip()] = v.strip()
    return out


def num(v):
    if v is None:
        return None
    s = str(v).strip().replace(',', '').replace('٬', '').replace('%', '')
    if s in ('', '-', '—', 'n/a', 'N/A'):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f == int(f) else f


# ---------------------------------------------------------------- commands that write

def cmd_init(a):
    p = Path(a.ledger)
    if p.exists() and not a.force:
        raise SystemExit(f'{p} already exists (use --force to replace it)')
    if a.goal not in GOALS:
        raise SystemExit('goal must be one of: ' + ', '.join(GOALS))
    save(p, {'brand': a.brand or '', 'goal': a.goal, 'collection': a.collection, 'baseline_window': 20,
             'checkpoints_h': CHECKPOINTS_H, 'account': [], 'posts': []})
    print(f'ledger created: {p} · goal: {a.goal} ({GOALS[a.goal][2]})')


def cmd_sync(a):
    data = load(a.ledger)
    src = json.loads(Path(a.posts).read_text(encoding='utf-8'))
    have = {p['id'] for p in data['posts']}
    added = 0
    for post in src.get('posts', []):
        if post['id'] in have:
            continue
        title = post.get('title') or ''
        if not title and post.get('slides'):
            d = post['slides'][0].get('display') or post['slides'][0].get('title') or ''
            title = d.get('*') or next(iter(d.values())) if isinstance(d, dict) else d
        slot = post.get('slot') or {}
        planned = ''
        if post.get('date'):
            try:
                planned = fmt_time(parse_time(f"{post['date']} {slot.get('time', '')}".strip()))
            except SystemExit:
                planned = str(post['date'])
        tags = dict(post.get('tags') or {})
        for k in ('series', 'type', 'hook', 'style', 'run'):      # style = the content style this post explores
            if post.get(k) and k not in tags:
                tags[k] = post[k]
        if src.get('run') and 'run' not in tags:                  # one plan = one run
            tags['run'] = src['run']
        data['posts'].append({'id': post['id'], 'title': title, 'planned': planned, 'status': a.status, 'tags': tags,
                              'platforms': {}})
        added += 1
    save(a.ledger, data)
    print(f'{added} post(s) added from {a.posts}; {len(have)} already in the ledger')


def cmd_add(a):
    data = load(a.ledger)
    if any(p['id'] == a.id for p in data['posts']):
        raise SystemExit(f'{a.id} is already in the ledger')
    data['posts'].append({'id': a.id, 'title': a.title or '', 'planned': fmt_time(parse_time(a.planned)) if a.planned else '',
                          'status': a.status, 'tags': kv(a.tag), 'platforms': {}})
    save(a.ledger, data)
    print('added', a.id)


def cmd_set(a):
    data = load(a.ledger)
    p = find(data, a.id)
    if a.status:
        if a.status not in STATUSES:
            raise SystemExit('status must be one of: ' + ', '.join(STATUSES))
        p['status'] = a.status
        p['status_at'] = fmt_time(now(a))
    if a.title:
        p['title'] = a.title
    p.setdefault('tags', {}).update(kv(a.tag))
    if a.test:
        parts = a.test.split(':')
        if len(parts) != 3:
            raise SystemExit('--test takes "name:variable:variant"')
        p['test'] = {'name': parts[0], 'variable': parts[1], 'variant': parts[2], 'hypothesis': a.hypothesis or ''}
    if a.platform:
        e = p.setdefault('platforms', {}).setdefault(a.platform, {'snapshots': []})
        if a.url:
            e['url'] = a.url
        if a.at:
            e['published_at'] = fmt_time(parse_time(a.at))
        if a.paid:
            e['paid'] = True
        if a.organic:
            e['paid'] = False
        if a.note:
            e['note'] = a.note
        if (a.url or a.at) and STATUSES.index(p['status']) < STATUSES.index('published'):
            p['status'] = 'published'
            p['status_at'] = fmt_time(now(a))
        if e.get('url') and not e.get('published_at'):
            print('note: no publish time yet for this platform; add --at "YYYY-MM-DD HH:MM" so readings can be timed')
    elif a.url or a.at or a.paid or a.note:
        raise SystemExit('--url / --at / --paid / --note need --platform')
    save(a.ledger, data)
    print('updated', a.id, '·', STATUS_AR.get(p['status'], p['status']))


def add_snapshot(post, platform, values, at, source):
    e = post.setdefault('platforms', {}).setdefault(platform, {'snapshots': []})
    snap = {'at': fmt_time(at), 'source': source}
    snap.update({k: v for k, v in values.items() if v is not None})
    e.setdefault('snapshots', []).append(snap)
    return snap


def cmd_snap(a):
    data = load(a.ledger)
    p = find(data, a.id)
    values = {m: getattr(a, m) for m in METRICS}
    if all(v is None for v in values.values()):
        raise SystemExit('give at least one number, e.g. --reach 1200 --saves 14')
    e = p.get('platforms', {}).get(a.platform, {})
    if not e.get('published_at'):
        print('note: this post has no publish time on this platform; set it with: ledger.py set', a.id, '--platform', a.platform,
              '--at "YYYY-MM-DD HH:MM"')
    s = add_snapshot(p, a.platform, values, parse_time(a.at) if a.at else now(a), a.source)
    save(a.ledger, data)
    print('reading saved for', a.id, a.platform, '·', ', '.join(f'{k}={v}' for k, v in s.items() if k in METRICS))


def norm_url(u):
    u = str(u or '').strip().lower().split('?')[0].split('#')[0].rstrip('/')
    for pre in ('https://', 'http://', 'www.', 'mobile.'):
        if u.startswith(pre):
            u = u[len(pre):]
    return u.replace('twitter.com', 'x.com')


def cmd_import(a):
    data = load(a.ledger)
    custom = {k.strip().lower().replace(' ', '').replace('_', ''): v.strip() for k, v in kv(a.map).items()}
    with open(a.csv, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit('the CSV has no rows')
    col = {}
    for h in rows[0].keys():
        key = (h or '').strip().lower().replace(' ', '').replace('_', '')
        if key in custom:
            col[h] = custom[key]
            continue
        for metric, names in ALIASES.items():
            if key in names:
                col[h] = metric
                break
    if 'url' not in col.values():
        raise SystemExit('no link column recognised. Columns: ' + ', '.join(rows[0].keys()) + '\nPass --map "<column>=url"')
    by_url = {}
    for p in data['posts']:
        e = p.get('platforms', {}).get(a.platform, {})
        if e.get('url'):
            by_url[norm_url(e['url'])] = p
    at = parse_time(a.at) if a.at else now(a)
    matched, unmatched = 0, []
    for r in rows:
        vals = {}
        for h, metric in col.items():
            vals[metric] = r[h] if metric == 'url' else num(r[h])
        url = norm_url(vals.pop('url', ''))
        post = by_url.get(url)
        if not post:
            unmatched.append(url)
            if not (a.add_unmatched and url):
                continue
            post = {'id': f'imp-{len(data["posts"]) + 1:03d}', 'title': '', 'planned': '', 'status': 'published',
                    'tags': {'planned': 'no'}, 'platforms': {a.platform: {'url': url, 'snapshots': []}}}
            data['posts'].append(post)
            by_url[url] = post
        add_snapshot(post, a.platform, vals, at, 'export')
        matched += 1
    save(a.ledger, data)
    print(f'{matched} reading(s) saved from {a.csv}; recognised columns: ' + ', '.join(sorted(set(col.values()))))
    if unmatched:
        print(f'{len(unmatched)} row(s) did not match a ledger link' + (' (added as unplanned)' if a.add_unmatched else
              ' (record the link with "ledger.py set <id> --platform ... --url ...", or pass --add-unmatched)') + ':')
        for u in unmatched[:15]:
            print('  ', u or '(empty link)')


def cmd_unsnap(a):
    data = load(a.ledger)
    p = find(data, a.id)
    snaps = (p.get('platforms') or {}).get(a.platform, {}).get('snapshots') or []
    if not snaps:
        raise SystemExit(f'{a.id} has no reading on {a.platform}')
    gone = snaps.pop()
    save(a.ledger, data)
    print('removed the last reading of', a.id, a.platform, '·', gone)


def cmd_account(a):
    data = load(a.ledger)
    data.setdefault('account', []).append({'at': fmt_time(parse_time(a.at) if a.at else now(a)), 'platform': a.platform,
                                           'followers': a.followers})
    save(a.ledger, data)
    print('account reading saved:', a.platform, a.followers)


# ---------------------------------------------------------------- commands that read

def entries(data):
    """one row per published post per platform"""
    for p in data['posts']:
        for plat, e in (p.get('platforms') or {}).items():
            yield p, plat, e


def age_h(e, t):
    return (t - parse_time(e['published_at'])).total_seconds() / 3600 if e.get('published_at') else None


def cmd_due(a):
    data = load(a.ledger)
    t = now(a)
    cps = data.get('checkpoints_h') or CHECKPOINTS_H
    out = []
    for p, plat, e in entries(data):
        age = age_h(e, t)
        if age is None or p.get('status') == 'archived':
            continue
        reached = [c for c in cps if age >= c]
        if not reached:
            continue
        cp = reached[-1]
        pub = parse_time(e['published_at'])
        # any reading taken at or after this checkpoint covers it (a late reading is better than none)
        covered = any((parse_time(s['at']) - pub).total_seconds() / 3600 >= cp * 0.75 for s in e.get('snapshots', []))
        if not covered:
            out.append((p['id'], plat, cp, age, e.get('url', ''), p.get('title', '')))
    if not out:
        print('لا قراءة مستحقة الآن.')
        return
    print(f'قراءات مستحقة الآن ({len(out)}):')
    for pid, plat, cp, age, url, title in sorted(out, key=lambda x: -x[3]):
        print(f'  {pid} · {plat} · قراءة {CP_AR.get(cp, str(cp) + "h")} (عمره {age / 24:.1f} يوم) · {title[:40]} · {url}')


def cmd_board(a):
    data = load(a.ledger)
    t = now(a)
    by = {s: [] for s in STATUSES}
    for p in data['posts']:
        by.setdefault(p.get('status', 'planned'), []).append(p)
    print(f"سجل المحتوى · {data.get('brand') or ''} · الهدف: {data.get('goal')} ({GOALS.get(data.get('goal'), ('', [], '?'))[2]})")
    print(' · '.join(f'{STATUS_AR[s]}: {len(by[s])}' for s in STATUSES if by.get(s)))
    notes = []
    for p in data['posts']:
        st = p.get('status')
        planned = None
        if p.get('planned'):
            try:
                planned = parse_time(p['planned'])
            except SystemExit:
                planned = None
        if st == 'designed' and p.get('status_at') and (t - parse_time(p['status_at'])).days >= 2:
            notes.append(f"  ينتظر الاعتماد منذ {(t - parse_time(p['status_at'])).days} يوم: {p['id']} · {p.get('title', '')[:40]}")
        if st in ('approved', 'scheduled') and planned and planned < t:
            notes.append(f"  معتمد وفات موعده ({p['planned']}) ولم يُسجَّل نشره: {p['id']} · {p.get('title', '')[:40]}")
        if st in ('idea', 'planned', 'designed') and planned and planned < t:
            notes.append(f"  فات موعده ({p['planned']}) وحالته «{STATUS_AR[st]}»: {p['id']}")
        if st == 'published':
            for plat, e in (p.get('platforms') or {}).items():
                if not e.get('url'):
                    notes.append(f"  منشور بلا رابط في {plat}: {p['id']}")
                if not e.get('published_at'):
                    notes.append(f"  منشور بلا وقت نشر في {plat}: {p['id']}")
            if not p.get('platforms'):
                notes.append(f"  حالته «منشور» ولا منصة مسجلة: {p['id']}")
        if st != 'idea' and not p.get('tags'):
            notes.append(f"  بلا وسوم (لن يدخل في الإسناد): {p['id']}")
    if notes:
        print('يحتاج انتباهًا:')
        print('\n'.join(notes))
    else:
        print('لا شيء معلّق.')


def judging_snapshot(e):
    """the reading we judge by: the one closest to 7 days among mature readings, else the latest one (young)"""
    snaps = e.get('snapshots') or []
    if not snaps or not e.get('published_at'):
        return None, None, True
    pub = parse_time(e['published_at'])
    aged = sorted(((parse_time(s['at']) - pub).total_seconds() / 3600, s) for s in snaps)
    mature = [x for x in aged if x[0] >= MATURE_H]
    if mature:
        h, s = min(mature, key=lambda x: abs(x[0] - 168))
        return s, h, False
    return aged[-1][1], aged[-1][0], True


def primary(goal, s):
    mode, keys, _ = GOALS[goal]
    vals = [s.get(k) for k in keys]
    if mode == 'first':
        for v in vals:
            if v is not None:
                return v
        return None
    present = [v for v in vals if v is not None]
    return sum(present) if present else None


def rate(n, s):
    base = s.get('reach') or s.get('impressions') or s.get('views') or s.get('followers')
    return n / base if base and n is not None else None


def median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def pct(x):
    return '—' if x is None else f'{x * 100:.1f}%'


def n2(x):
    if x is None:
        return '—'
    return str(int(x)) if float(x) == int(x) else f'{x:.2f}'


PLACE = '[يُكتب]'
# a content style is adopted by the numbers when all of these hold (references/03-design-identity.md §0)
ADOPT_MIN_POSTS, ADOPT_MIN_RUNS, ADOPT_REL, ADOPT_LEAD = 4, 2, 1.3, 1.2
TOTAL_MIN_POSTS, TOTAL_MIN_RUNS = 12, 3
FATIGUE_REL, FATIGUE_RUNS = 0.8, 3


def analyse(data, since=None):
    """every measured post-on-a-platform with its governing number, the account baseline and its rel"""
    goal = data.get('goal')
    if goal not in GOALS:
        raise SystemExit('the ledger has no valid goal; set "goal" to one of: ' + ', '.join(GOALS))
    rows, unmeasured = [], []
    for p, plat, e in entries(data):
        if not e.get('published_at'):
            if p.get('status') == 'published':
                unmeasured.append(f"{p['id']} · {plat}: بلا وقت نشر")
            continue
        pub = parse_time(e['published_at'])
        if since and pub < since:
            continue
        s, h, young = judging_snapshot(e)
        if s is None:
            unmeasured.append(f"{p['id']} · {plat}: منشور بلا أي قراءة")
            continue
        eng_parts = [s.get(k) for k in ('likes', 'comments', 'saves', 'shares') if s.get(k) is not None]
        rows.append({'p': p, 'plat': plat, 'e': e, 's': s, 'h': h, 'young': young, 'pub': pub, 'paid': bool(e.get('paid')),
                     'primary': primary(goal, s), 'eng': sum(eng_parts) if eng_parts else None})
    if not rows:
        raise SystemExit('no published post has a reading yet. Start with: ledger.py due')
    early = sum(1 for r in rows if not r['young']) < 5
    used = rows if early else [r for r in rows if not r['young']]
    window = data.get('baseline_window', 20)
    base = {}
    for plat in sorted({r['plat'] for r in used}):
        org = sorted((r for r in used if r['plat'] == plat and not r['paid']), key=lambda r: r['pub'])[-window:]
        base[plat] = {'n': len(org), 'rows': org, 'primary': median([r['primary'] for r in org]),
                      'er': median([rate(r['eng'], r['s']) for r in org]),
                      'save': median([rate(r['s'].get('saves'), r['s']) for r in org])}
    for r in used:
        b = base[r['plat']]
        others = [x['primary'] for x in b['rows'] if x is not r and x['primary'] is not None]
        r['rel'] = None
        if r['primary'] is not None and len(others) >= 4:
            m = statistics.median(others) or (sum(others) / len(others))
            r['rel'] = r['primary'] / m if m else None
        rel = r['rel']
        r['cls'] = ('—' if rel is None else 'شاذ' if rel >= OUTLIER else 'فائز' if rel >= WIN else 'ضعيف' if rel <= WEAK else 'عادي')
    ranked = sorted((r for r in used if r['rel'] is not None), key=lambda r: -r['rel'])
    return {'goal': goal, 'label': GOALS[goal][2], 'rows': rows, 'used': used, 'ranked': ranked, 'base': base, 'early': early,
            'unmeasured': unmeasured}


def run_of(r):
    """the batch a post belongs to: its `run` tag (one plan = one run), else its ISO week"""
    tag = (r['p'].get('tags') or {}).get('run')
    return str(tag) if tag else '%d-W%02d' % r['pub'].isocalendar()[:2]


def tag_stats(ranked):
    dims = {}
    for r in ranked:
        if r['paid']:
            continue
        for k, v in (r['p'].get('tags') or {}).items():
            if k != 'run':
                dims.setdefault((k, str(v)), []).append(r)
    stats = {}
    for key, rs in dims.items():
        med = statistics.median([r['rel'] for r in rs])
        weeks = len({r['pub'].isocalendar()[:2] for r in rs})
        strong = med >= PATTERN_HI or med <= PATTERN_LO
        stats[key] = {'med': med, 'weeks': weeks, 'n': len(rs), 'ids': {(r['p']['id'], r['plat']) for r in rs},
                      'verdict': '—' if not strong else ('نمط' if len(rs) >= 3 and weeks >= 2 else 'إشارة')}
    return stats


def overlaps(key, st, stats, only_strong=True):
    """tag values whose posts are mostly the same posts: one piece of evidence, not two"""
    out = []
    for (k2, v2), s2 in stats.items():
        if k2 == key[0] or (only_strong and s2['verdict'] == '—') or st['n'] < 2 or s2['n'] < 2:
            continue
        if len(st['ids'] & s2['ids']) / min(len(st['ids']), len(s2['ids'])) >= 0.75:
            out.append(f'{k2}={v2}')
    return out


def cmd_report(a):
    data = load(a.ledger)
    since = parse_time(a.since) if a.since else None
    t = now(a)
    an = analyse(data, since)
    goal, label, rows, used, ranked, base, early, unmeasured = (an[k] for k in ('goal', 'label', 'rows', 'used', 'ranked', 'base', 'early', 'unmeasured'))
    today = fmt_time(t)[:10]
    prev = {}
    for bl in data.get('baselines') or []:
        if bl['at'][:10] < today:
            prev[bl['platform']] = bl
    L = [f"# تقرير أداء المحتوى · {data.get('brand') or ''} · {today}", '',
         f"**الهدف:** {goal} · **المقياس الحاكم:** {label} · **المنشورات المحكوم عليها:** من {min(r['pub'] for r in used):%Y-%m-%d} إلى "
         f"{max(r['pub'] for r in used):%Y-%m-%d} · **طريقة قراءة الأرقام:** {data.get('collection') or '—'}", '',
         f'> الجداول من `ledger.py report`. كل موضع فيه {PLACE} يملؤه المحلّل في مكانه (أو يحذف صفه)، ثم يتحقق: `ledger.py check <هذا الملف>`.', '']
    if early:
        L += ['> **قراءة مبكرة:** أقل من 5 منشورات بلغت 5 أيام. الأرقام هنا من آخر قراءة لكل منشور، والحكم مؤقت.', '']
    L += ['## 1) الخلاصة', '', f'- **ما تحرك:** {PLACE}', f'- **لماذا نظن ذلك:** {PLACE}', f'- **القرار المقترح:** {PLACE}', '',
          '## 2) خط الأساس', '',
          f'| المنصة | منشورات عضوية مقيسة | وسيط {label} | وسيط معدل التفاعل | وسيط معدل الحفظ | التغيّر عن التقرير السابق |', '|---|---|---|---|---|---|']
    for plat, b in base.items():
        p0 = prev.get(plat)
        if p0 and p0.get('primary') and b['primary'] is not None:
            ch = f"{(b['primary'] / p0['primary'] - 1) * 100:+.0f}% عن {p0['at'][:10]}"
        else:
            ch = '—' if p0 else 'أول تقرير'
        L.append(f"| {plat} | {b['n']}{' (أقل من 5: لا خط أساس بعد)' if b['n'] < 5 else ''} | {n2(b['primary'])} | {pct(b['er'])} | {pct(b['save'])} | {ch} |")
    acc = {}
    for x in data.get('account') or []:
        acc.setdefault(x['platform'], []).append(x)
    for r in rows:
        if r['s'].get('followers') is not None:
            acc.setdefault(r['plat'], []).append({'at': r['s']['at'], 'followers': r['s']['followers']})
    if acc:
        L += ['', '**المتابعون:** ' + ' · '.join(
            f"{plat}: {v[0]['followers']} ← {v[-1]['followers']} ({v[0]['at'][:10]} إلى {v[-1]['at'][:10]})"
            for plat, v in ((k, sorted(vs, key=lambda x: x['at'])) for k, vs in sorted(acc.items())))]

    def line(r):
        tg = ' · '.join(f'{k}: {v}' for k, v in (r['p'].get('tags') or {}).items()) or 'بلا وسوم'
        return (f"| {r['p']['id']}{' (مروَّج)' if r['paid'] else ''} | {r['plat']} | {(r['p'].get('title') or '')[:38]} | {n2(r['primary'])} | "
                f"{n2(r['rel'])} | {pct(rate(r['eng'], r['s']))} | {pct(rate(r['s'].get('saves'), r['s']))} | {r['h'] / 24:.0f}ي | {tg} | {PLACE} |")

    head = [f'| المنشور | المنصة | العنوان | {label} | rel | معدل التفاعل | معدل الحفظ | عمر القراءة | الوسوم | التشخيص بالمسار |',
            '|---|---|---|---|---|---|---|---|---|---|']
    L += ['', '## 3) الفائزون والضعفاء', '']
    for title, sel in (('الفائزون (rel ≥ 1.5)', [r for r in ranked if r['cls'] in ('فائز', 'شاذ')]),
                       ('الضعفاء (rel ≤ 0.6)', [r for r in ranked if r['cls'] == 'ضعيف'])):
        L += [f'**{title}**', '']
        L += (head + [line(r) for r in sel]) if sel else ['لا يوجد.']
        L += ['']
    if any(r['cls'] == 'شاذ' for r in ranked):
        L += ['> منشور شاذ (rel ≥ 5): لا تُبنى عليه قاعدة؛ افهم سببه ثم اختبره.', '']
    L += ['التشخيص جملة واحدة فيها الدليل: هل الخلل في التوزيع، أم القيمة، أم أول ثانيتين، أم الدعوة؟ (المرجع 13 §10)', '',
          '## 4) الأنماط والإشارات حسب الوسم', '',
          '| الوسم | القيمة | المنشورات | الأسابيع | وسيط rel | الحكم | يتقاطع مع |', '|---|---|---|---|---|---|---|']
    stats = tag_stats(ranked)
    found = []
    for (k, v), st in sorted(stats.items()):
        over = overlaps((k, v), st, stats) if st['verdict'] != '—' else []
        if st['verdict'] != '—':
            found.append((st['verdict'], k, v, st['n'], st['weeks'], st['med'], over))
        L.append(f"| {k} | {v} | {st['n']} | {st['weeks']} | {st['med']:.2f} | {st['verdict']} | {'، '.join(over) or '—'} |")
    if not stats:
        L.append('| — | لا وسوم أو لا خط أساس بعد | | | | | |')
    L += ['', '«نمط» = 3 منشورات أو أكثر في أسبوعين مختلفين وفارق واضح. «إشارة» = فارق واضح بعينة أصغر؛ تدخل قائمة التجارب.',
          'وسمان يتقاطعان في المنشورات نفسها **دليل واحد لا دليلان**: لا يُعرف أيهما السبب إلا بتجربة تفصل بينهما.']
    if any(k == 'style' for k, _ in stats):
        L += ['أسلوب المحتوى (الوسم `style`) له حكمه الخاص: `ledger.py styles` (المرجع 03 §0).']
    L += ['', f'**ما قاله الجمهور:** {PLACE} (أسئلة واعتراضات تكررت؛ أو: لم تُقرأ التعليقات)', '', '## 5) التجارب', '']
    tests = {}
    for r in used:
        tt = r['p'].get('test')
        if tt:
            tests.setdefault(tt['name'], {'hyp': tt.get('hypothesis', ''), 'v': {}})['v'].setdefault(tt['variant'], []).append(r)
    if tests:
        L += [f'| التجربة | الفرضية | الخيار | المنشورات وأرقامها ({label}) | الوسيط | قراءة أولية | الحكم |', '|---|---|---|---|---|---|---|']
        for name, tv in tests.items():
            variants = tv['v']
            meds = {v: median([r['primary'] for r in rs]) for v, rs in variants.items()}
            enough = len(variants) >= 2 and all(len(rs) >= 2 for rs in variants.values())
            vals = [m for m in meds.values() if m is not None]
            if not enough:
                read = 'يحتاج منشورات أكثر (منشوران لكل خيار على الأقل)'
            elif len(vals) >= 2 and min(vals) > 0 and max(vals) / min(vals) >= PATTERN_HI:
                read = f"فرق ظاهر لصالح «{max(meds, key=lambda v: meds[v] or 0)}» ({max(vals) / min(vals):.1f}×)"
            elif len(vals) >= 2 and min(vals) == 0 and max(vals) > 0:
                read = 'فرق ظاهر لصالح «' + max(meds, key=lambda v: meds[v] or 0) + '» (الخيار الآخر صفر)'
            else:
                read = 'غير حاسم'
            for i, (v, rs) in enumerate(variants.items()):
                posts = '، '.join(f"{r['p']['id']}: {n2(r['primary'])}" for r in sorted(rs, key=lambda r: r['pub']))
                # one verdict per experiment: it is written on the first row only
                L.append(f"| {name} | {tv['hyp'] or '—'} | {v} | {posts} | {n2(meds[v])} | {read} | {PLACE if i == 0 else '↑'} |")
        L += ['', 'الحكم: ثبتت · لم تثبت · غير حاسمة (شروطه في المرجع 13 §9).']
    else:
        L.append('لا تجارب مسجلة. تسجيل تجربة عند التخطيط: `ledger.py set <id> --test "الاسم:المتغير:الخيار" --hypothesis "…"`.')
    L += ['', '## 6) ما نقترحه للأسبوع القادم (ثلاثة قرارات على الأكثر)', '',
          '| # | القرار (كرّر / عدّل / أوقف / اختبر) | الدليل بالأرقام | المتوقع | كيف نعرف بعد أسبوع أنه نفع |', '|---|---|---|---|---|']
    L += [f'| {i} | {PLACE} | {PLACE} | {PLACE} | {PLACE} |' for i in (1, 2, 3)]
    L += ['', '**مرشحات من الجداول** (مادة للاختيار، لا قرارات):', '']
    if found:
        ordered = sorted(found, key=lambda x: (x[0] != 'نمط', -abs(x[5] - 1)))
        shown = [x for x in ordered if x[0] == 'نمط'] + [x for x in ordered if x[0] != 'نمط'][:4]
        for verdict, k, v, n, weeks, med, over in shown:
            act = ('كرّر' if med >= PATTERN_HI else 'عدّل أو أوقف') if verdict == 'نمط' else 'اختبر'
            L.append(f'- **{act}:** {k} = «{v}» ({verdict} · وسيط rel {med:.2f} · المنشورات {n} · الأسابيع {weeks})'
                     + (f' · يتقاطع مع {"، ".join(over)}' if over else ''))
        if len(ordered) > len(shown):
            L.append(f'- وإشارات أضعف عددها {len(ordered) - len(shown)} في جدول القسم 4.')
    else:
        L.append('- لا نمط ولا إشارة بعد. استمر في القراءة، ونوّع وسمًا واحدًا عن قصد في الأسبوع القادم.')
    L += ['', '## 7) ما لم نستطع قياسه', '']
    L += [f'- {x}' for x in unmeasured]
    for r in (r for r in rows if r['young'] and not early):
        due7 = fmt_time(r['pub'] + dt.timedelta(days=7))
        L.append(f"- {r['p']['id']} · {r['plat']}: قراءة مبكرة عمرها {r['h'] / 24:.1f} يوم ({label}: {n2(r['primary'])}، الوصول: "
                 f"{n2(r['s'].get('reach') or r['s'].get('impressions'))}). لا تُقارَن بقراءات 7 أيام ولم تدخل الحكم؛ قراءة الحكم بعد {due7}")
    miss = sorted({f"{r['plat']}: {k}" for r in used for k in GOALS[goal][1] if r['s'].get(k) is None})
    L += [f'- أرقام المقياس الحاكم غير متاحة في بعض القراءات ({"، ".join(miss)})'] if miss else []
    paid = [r for r in used if r['paid']]
    L += [f"- {len(paid)} منشور مروَّج خارج خط الأساس: " + '، '.join(r['p']['id'] for r in paid)] if paid else []
    if L[-1] == '':
        L.append('- لا شيء.')
    L += ['', '## 8) يحتاج قرارك', '', 'كل بند سؤال جوابه نعم أو لا.', '', f'1. {PLACE}', '']
    text = '\n'.join(L)
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding='utf-8')
        hist = [bl for bl in data.get('baselines') or [] if bl['at'][:10] != today]
        hist += [{'at': fmt_time(t), 'platform': plat, 'n': b['n'], 'primary': b['primary'], 'er': b['er'], 'save': b['save']}
                 for plat, b in base.items()]
        data['baselines'] = hist
        save(a.ledger, data)
        print('report written:', out, '· baseline saved in the ledger')
    else:
        print(text)
    wins = sum(1 for r in ranked if r['cls'] in ('فائز', 'شاذ'))
    weak = sum(1 for r in ranked if r['cls'] == 'ضعيف')
    print(f'measured: {len(used)} · winners: {wins} · weak: {weak} · patterns/signals: {len(found)} · unmeasured: {len(unmeasured)}'
          + (' · EARLY READ' if early else ''), file=sys.stderr)


def cmd_styles(a):
    """which content style is winning, and whether the numbers are enough to adopt it (references/03 §0)"""
    data = load(a.ledger)
    an = analyse(data, parse_time(a.since) if a.since else None)
    label = an['label']
    org = [r for r in an['ranked'] if not r['paid']]
    styled = [r for r in org if (r['p'].get('tags') or {}).get('style')]
    brand_file = Path(a.ledger).resolve().parent / 'brand.json'
    phase, adopted = 'explore', None
    if brand_file.exists():
        try:
            st = json.loads(brand_file.read_text(encoding='utf-8')).get('style') or {}
            phase, adopted = st.get('phase') or 'explore', st.get('adopted')
        except (ValueError, OSError):
            pass
    groups = {}
    for r in styled:
        groups.setdefault(str(r['p']['tags']['style']), []).append(r)
    stats = tag_stats(an['ranked'])
    out = {'phase': phase, 'adopted': adopted, 'measured_with_style': len(styled), 'runs': len({run_of(r) for r in styled}), 'styles': [],
           'decision': '', 'candidate': None}
    for name, rs in groups.items():
        runs = sorted({run_of(r) for r in rs})
        key = ('style', name)
        over = overlaps(key, stats[key], stats, only_strong=False) if key in stats else []
        last = {}
        for r in rs:
            last.setdefault(run_of(r), []).append(r['rel'])
        out['styles'].append({'style': name, 'n': len(rs), 'runs': len(runs), 'median_rel': statistics.median([r['rel'] for r in rs]),
                              'median_primary': median([r['primary'] for r in rs]),
                              'by_run': {k: round(statistics.median(v), 2) for k, v in sorted(last.items())}, 'overlaps': over})
    out['styles'].sort(key=lambda s: -s['median_rel'])
    print(f"أساليب المحتوى · {data.get('brand') or ''} · المرحلة: {'مثبّت «' + str(adopted) + '»' if phase == 'adopted' else 'استكشاف'}")
    if not styled:
        waiting = [r for r in an['used'] if (r['p'].get('tags') or {}).get('style')]
        out['decision'] = (f'{len(waiting)} منشور بوسم style مقيس، لكن لا خط أساس بعد (يلزم 5 منشورات مقيسة). واصل القراءة.' if waiting else
                           'لا منشور مقيس يحمل وسم style بعد. اكتب أسلوب كل منشور في الخطة (posts.json ← "style")، ثم ledger.py sync.')
        print(out['decision'])
    else:
        print(f'\n| الأسلوب | المنشورات المقيسة | التشغيلات | وسيط rel | وسيط {label} | rel في كل تشغيل | يتقاطع مع |')
        print('|---|---|---|---|---|---|---|')
        for s in out['styles']:
            print(f"| {s['style']}{' (المثبّت)' if s['style'] == adopted else ''} | {s['n']} | {s['runs']} | {s['median_rel']:.2f} | {n2(s['median_primary'])} | "
                  f"{' · '.join(f'{k}: {v}' for k, v in s['by_run'].items())} | {'، '.join(s['overlaps']) or '—'} |")
        best = out['styles'][0]
        second = out['styles'][1]['median_rel'] if len(out['styles']) > 1 else None
        need = []
        if out['measured_with_style'] < TOTAL_MIN_POSTS:
            need.append(f"{TOTAL_MIN_POSTS - out['measured_with_style']} منشورًا مقيسًا آخر (المطلوب {TOTAL_MIN_POSTS})")
        if out['runs'] < TOTAL_MIN_RUNS:
            need.append(f"{TOTAL_MIN_RUNS - out['runs']} تشغيلًا آخر (المطلوب {TOTAL_MIN_RUNS})")
        if best['n'] < ADOPT_MIN_POSTS:
            need.append(f"«{best['style']}» في {ADOPT_MIN_POSTS - best['n']} منشورًا آخر (المطلوب {ADOPT_MIN_POSTS})")
        if best['runs'] < ADOPT_MIN_RUNS:
            need.append(f"«{best['style']}» في تشغيل ثانٍ")
        if best['median_rel'] < ADOPT_REL:
            need.append(f'أسلوب يبلغ وسيط rel {ADOPT_REL} (الأعلى الآن {best["median_rel"]:.2f})')
        if second is not None and second > 0 and best['median_rel'] / second < ADOPT_LEAD:
            need.append(f'فارق {ADOPT_LEAD}× عن الأسلوب التالي (الآن {best["median_rel"] / second:.2f}×)')
        if best['overlaps']:
            need.append(f"فصل «{best['style']}» عن {'، '.join(best['overlaps'])}: وزّع الأساليب على الأنواع والصيغ بالتساوي")
        if phase == 'adopted' and adopted:
            champ = next((s for s in out['styles'] if s['style'] == adopted), None)
            tail = list(champ['by_run'].values())[-FATIGUE_RUNS:] if champ else []
            if champ and len(tail) == FATIGUE_RUNS and all(v < FATIGUE_REL for v in tail):
                out['decision'] = (f'تعب الأسلوب: «{adopted}» تحت {FATIGUE_REL} في آخر {FATIGUE_RUNS} تشغيلات ({" · ".join(map(str, tail))}). '
                                   'أعد فتح الاستكشاف: نصف المنشورات لأساليب جديدة من إلهام هذا التشغيل.')
            elif best['style'] != adopted and not need:
                out['candidate'] = best['style']
                out['decision'] = (f'«{best["style"]}» تقدّم على المثبّت «{adopted}» بالشروط كلها: مرشح لنسخة جديدة من نظام التصميم (v+1).')
            else:
                out['decision'] = f'«{adopted}» باقٍ. واصل: نحو 80% به، ونحو 20% لأسلوب منافس من إلهام كل تشغيل.'
        elif not need:
            out['candidate'] = best['style']
            out['decision'] = (f'«{best["style"]}» مرشح للتثبيت هوية للمحتوى: {best["n"]} منشورات في {best["runs"]} تشغيلات، ووسيط rel {best["median_rel"]:.2f}. '
                               'اكتب design-system.md v1 منه، وغيّر style.phase إلى adopted، وأخبر صاحب العلامة بالدليل (المرجع 03 §0).')
        else:
            out['decision'] = 'واصل الاستكشاف. ينقص: ' + '؛ '.join(need) + '.'
        plats = sorted({r['plat'] for r in styled})
        if len(plats) == 1:
            out['decision'] += f' (الحكم من منصة واحدة: {plats[0]}؛ لا يُعمَّم على منصة لم تُقَس.)'
        print('\n' + out['decision'])
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print('saved:', a.json)


def cmd_check(a):
    lines = Path(a.report).read_text(encoding='utf-8').splitlines()
    left = [(i, l.strip()[:90]) for i, l in enumerate(lines, 1) if PLACE in l and not l.lstrip().startswith('>')]
    if left:
        print(f'{len(left)} line(s) still hold {PLACE} (fill them in, or delete the row):')
        for i, l in left:
            print(f'  {i}: {l}')
        raise SystemExit(1)
    print('report complete: no placeholder left.')


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--ledger', default='ledger.json')
    common.add_argument('--now', help='treat this as the current time, "YYYY-MM-DD HH:MM" (back-filling, tests)')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('init', parents=[common]); s.add_argument('--goal', required=True); s.add_argument('--brand')
    s.add_argument('--collection', default='manual', choices=['browser', 'export', 'manual', 'public']); s.add_argument('--force', action='store_true')
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser('sync', parents=[common]); s.add_argument('posts'); s.add_argument('--status', default='planned', choices=STATUSES)
    s.set_defaults(fn=cmd_sync)
    s = sub.add_parser('add', parents=[common]); s.add_argument('id'); s.add_argument('--title'); s.add_argument('--planned')
    s.add_argument('--status', default='planned', choices=STATUSES); s.add_argument('--tag', action='append'); s.set_defaults(fn=cmd_add)
    s = sub.add_parser('set', parents=[common]); s.add_argument('id'); s.add_argument('--status'); s.add_argument('--title')
    s.add_argument('--platform'); s.add_argument('--url'); s.add_argument('--at'); s.add_argument('--paid', action='store_true')
    s.add_argument('--organic', action='store_true'); s.add_argument('--note', help='free note on this platform entry, e.g. the boost budget')
    s.add_argument('--tag', action='append'); s.add_argument('--test')
    s.add_argument('--hypothesis'); s.set_defaults(fn=cmd_set)
    s = sub.add_parser('snap', parents=[common]); s.add_argument('id'); s.add_argument('--platform', required=True)
    s.add_argument('--at', help='when the numbers were read (default: now)')
    s.add_argument('--source', default='manual', choices=['insights', 'export', 'manual', 'public'])
    for m in METRICS:
        s.add_argument('--' + m, type=float)
    s.set_defaults(fn=cmd_snap)
    s = sub.add_parser('import', parents=[common]); s.add_argument('csv'); s.add_argument('--platform', required=True); s.add_argument('--at')
    s.add_argument('--map', action='append'); s.add_argument('--add-unmatched', action='store_true'); s.set_defaults(fn=cmd_import)
    s = sub.add_parser('unsnap', parents=[common]); s.add_argument('id'); s.add_argument('--platform', required=True); s.set_defaults(fn=cmd_unsnap)
    s = sub.add_parser('account', parents=[common]); s.add_argument('--platform', required=True); s.add_argument('--followers', type=int, required=True)
    s.add_argument('--at'); s.set_defaults(fn=cmd_account)
    s = sub.add_parser('due', parents=[common]); s.set_defaults(fn=cmd_due)
    s = sub.add_parser('board', parents=[common]); s.set_defaults(fn=cmd_board)
    s = sub.add_parser('report', parents=[common]); s.add_argument('--since'); s.add_argument('--out'); s.set_defaults(fn=cmd_report)
    s = sub.add_parser('check', parents=[common]); s.add_argument('report'); s.set_defaults(fn=cmd_check)
    s = sub.add_parser('styles', parents=[common]); s.add_argument('--since'); s.add_argument('--json'); s.set_defaults(fn=cmd_styles)
    a = ap.parse_args()
    if a.cmd == 'snap':
        for m in METRICS:
            v = getattr(a, m)
            if v is not None and v == int(v):
                setattr(a, m, int(v))
    a.fn(a)


if __name__ == '__main__':
    main()
