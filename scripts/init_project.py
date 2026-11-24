#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a brand content project from the first-interview answers (references/00-onboarding-interview.md).

  python init_project.py intake.json [--dir <parent folder>] [--name <folder name>] [--force]

Writes <parent>/<name>/ with brand.json (filled from the answers, the rest left as <...> placeholders), brand-notes.md,
feedback-log.md, playbook.md, ledger.json (goal + how numbers are collected), performance/experiments.md and the working
folders. Then prints the fields that are still empty. It never invents an answer: what was not given stays a placeholder.
Standard library only. Example answers: assets/intake.example.json"""
import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / 'assets'
GOALS = ('awareness', 'trust', 'leads', 'sales', 'hiring')
PLATFORM_KEYS = {'instagram': 'instagram', 'ig': 'instagram', 'x': 'x', 'twitter': 'x', 'linkedin': 'linkedin', 'li': 'linkedin',
                 'tiktok': 'tiktok', 'snapchat': 'snapchat', 'youtube': 'youtube_shorts', 'youtube_shorts': 'youtube_shorts',
                 'whatsapp': 'whatsapp_channel', 'whatsapp_channel': 'whatsapp_channel'}
SHORT = {'instagram': 'ig', 'x': 'x', 'linkedin': 'li', 'tiktok': 'tt', 'snapchat': 'sc', 'youtube_shorts': 'yt'}
DIRS = ['research/posts', 'research/moodboard/refs', 'plan', 'assets/fonts', 'assets/logo', 'plates', 'masks', 'performance',
        'profile-kit']


def slug(name):
    return re.sub(r'[^A-Za-z0-9]+', '-', str(name or '')).strip('-').lower()


def folder_name(it, links):
    """Latin slug from name_latin or the site; an Arabic-only brand keeps its own name, so two brands never collide"""
    s = slug(it.get('name_latin')) or slug(domain_of(links.get('site')).split('.')[0])
    return f'{s}-content' if s else re.sub(r'[\\/:*?"<>|\s]+', '-', it['name']).strip('-') + '-content'


def domain_of(url):
    m = re.match(r'^(?:https?://)?(?:www\.)?([^/\s]+)', str(url or '').strip())
    return m.group(1) if m else ''


def gaps(node, path=''):
    """every value still holding a <...> placeholder, as a dotted path"""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if not k.startswith('_'):
                out += gaps(v, f'{path}.{k}' if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += gaps(v, f'{path}[{i}]')
    elif isinstance(node, str) and re.search(r'<[^<>]+>', node):
        out.append(path)
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('intake')
    ap.add_argument('--dir', default='.')
    ap.add_argument('--name')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()

    it = json.loads(Path(a.intake).read_text(encoding='utf-8'))
    if not it.get('name'):
        raise SystemExit('intake.json needs "name" (question 1 of the interview)')
    goal = it.get('goal') or 'leads'
    if goal not in GOALS:
        raise SystemExit('"goal" must be one of: ' + ', '.join(GOALS))
    links = it.get('links') or {}
    root = Path(a.dir) / (a.name or folder_name(it, links))
    if root.exists() and any(root.iterdir()) and not a.force:
        raise SystemExit(f'{root} already exists and is not empty (use --force, or --name for another folder)')
    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)

    b = json.loads((ASSETS / 'brand.template.json').read_text(encoding='utf-8'))
    b['name'] = it['name']
    b['name_in_text'] = it.get('name_in_text') or it['name']
    b['hashtag'] = it.get('hashtag') or '#' + re.sub(r'\s+', '_', b['name_in_text'])
    if it.get('name_latin'):
        b['name_latin'] = it['name_latin']
    # no site: nothing to print in the footer yet; never leave a live-looking example domain behind
    b['domain'] = domain_of(links.get('site'))
    b['furniture']['footer'] = it.get('footer') or b['domain']
    b['email'] = it.get('email') or ''
    for k in ('phone', 'contact_line', 'positioning'):
        if it.get(k):
            b[k] = it[k]
    if it.get('sector') or it.get('sells'):
        b['sector'] = ' · '.join(x for x in (it.get('sector'), it.get('sells')) if x)
    if it.get('difference'):
        b['promise'] = it['difference']
    b['goal'] = goal
    if it.get('customer'):
        b['audience'] = [{'name': 'العميل الذي وصفه صاحب العلامة', 'description': it['customer'],
                          '_note': 'تُستكمل ثلاث شخصيات بالأدلة بعد القراءة الذاتية (references/01-brand-intake.md §4)'}]
    if it.get('proof'):
        b['proof_pool'] = list(it['proof'])
    if it.get('cta'):
        b['offer']['cta_formula'] = it['cta']
    if it.get('prices'):
        b['offer']['price_status'] = it['prices']
    active = {PLATFORM_KEYS[p.lower()] for p in it.get('platforms') or [] if p.lower() in PLATFORM_KEYS}
    if active:
        b['platforms'] = {k: (k in active) for k in b['platforms']}
    cad = {'_times': b['cadence']['_times'], '_density': b['cadence'].get('_density', '')}
    if it.get('per_week'):
        cad['ideas_per_week'] = it['per_week']     # ideas the owner can review; each idea gets a version per platform
    for k in ('start', 'horizon', 'season'):
        if it.get(k):
            cad[k] = it[k]
    b['cadence'] = cad
    # voice: one entry per ACTIVE platform; the template's entries for switched-off platforms are dropped
    on = [SHORT[k] for k in ('instagram', 'x', 'linkedin', 'tiktok', 'snapchat', 'youtube_shorts')
          if b['platforms'].get(k)] if active else ['ig', 'x', 'li']
    reg = it.get('register')
    if isinstance(reg, dict):
        reg = {SHORT.get(PLATFORM_KEYS.get(k.lower(), k), k): v for k, v in reg.items()}
    else:
        reg = {k: reg for k in on} if reg else {}
    voice = {}
    for k in on:
        voice[k] = reg.get(k) or (b['voice'][k] if k in ('ig', 'x', 'li') else reg.get('ig') or b['voice']['ig'])
    if 'x' in on or 'li' in on:
        voice['image_landscape'] = b['voice']['image_landscape']
    for k in ('image_portrait', 'emoji', 'glossary'):
        voice[k] = b['voice'][k]
    b['voice'] = voice
    b['captions']['register'] = {k: b['captions']['register'].get(k, 'mixed') for k in on}
    if it.get('banned_words'):
        b['captions']['banned_words'] = sorted(set(b['captions']['banned_words']) | set(it['banned_words']))
    if it.get('never_mention'):
        b['rules']['excluded_projects'] = list(it['never_mention'])
    if it.get('limits'):
        b['rules']['limits'] = list(it['limits'])
    if it.get('proof_rules'):
        b['rules']['proof_redaction'] = list(it['proof_rules'])
    b['series'] = []                       # designed at the plan stage (references/04 §5)
    b['demo_brands'] = []                  # only for brands with no real work to show yet
    ident = it.get('identity') or {}
    if ident.get('logo_color'):
        b['logo']['color'] = ident['logo_color']
    if ident.get('logo_white'):
        b['logo']['white'] = ident['logo_white']
    if ident.get('font_name'):
        b['font']['name'] = ident['font_name']
    if ident.get('font_files'):
        b['font']['files'] = ident['font_files']
    if ident.get('colors'):
        b['tokens']['_brand_colors_from_owner'] = ident['colors']
    b['tokens']['_status'] = 'TEMPLATE DEFAULTS: derive every colour from the official logo file before any render (references/03-design-identity.md §4)'
    if it.get('approver'):
        b['approvals']['approver'] = it['approver']
    if it.get('channel'):
        b['approvals']['channel'] = it['channel']
    b['approvals']['publisher'] = it.get('publisher') or 'manual, by the brand owner'
    b['approvals']['pending_decisions'] = list(it.get('assumptions') or [])
    b['budget']['per_week_usd'] = it.get('budget_week_usd', 0) if it.get('paid_generation') else 0
    if not it.get('paid_generation'):
        b['budget']['per_clip_usd'] = 0
        b['budget']['_note'] = 'بلا توليد مدفوع: تصميم بالكود وصور حقيقية. أي توليد مدفوع يحتاج قرارًا وسقفًا'
    b['delivery']['local_root'] = it.get('delivery_root') or str((root / 'delivery').resolve()).replace('\\', '/')
    b['delivery']['drive_root'] = it.get('drive_root') or ''
    b['delivery']['platform_folders'] = {SHORT[k]: v for k, v in (
        ('instagram', '01 - إنستقرام Instagram'), ('x', '02 - إكس X'), ('linkedin', '03 - لينكدإن LinkedIn'),
        ('tiktok', '04 - تيك توك TikTok'), ('snapchat', '05 - سناب Snapchat'), ('youtube_shorts', '06 - يوتيوب شورتس'))
        if not active or k in active}
    (root / 'brand.json').write_text(json.dumps(b, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (root / 'intake.json').write_text(json.dumps(it, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    today = dt.date.today().isoformat()
    notes = [f"# ملاحظات «{it['name']}»", '', 'الأحدث أولًا، وكل سطر مؤرخ. هنا ما لا يدخل في `brand.json`: القصة، والقرارات، وما رُفض ولماذا، وقائمة «لا تذكر».', '',
             f'## {today} · المقابلة الأولى', '']
    for label, key in (('ماذا تبيع ولمن', 'sells'), ('العميل كما وصفه صاحب العلامة', 'customer'), ('الفرق عن غيرها', 'difference'),
                       ('الهدف الأساسي', 'goal'), ('من ينشر', 'publisher'), ('طريقة قراءة الأرقام', 'metrics_method'), ('المراجعة', 'review')):
        if it.get(key):
            notes.append(f'- **{label}:** {it[key]}')
    if links:
        notes += ['', '**الروابط:**'] + [f'- {k}: {v}' for k, v in links.items() if v]
    for label, key in (('حسابات يعجبه أسلوبها (بذور البحث)', 'likes'), ('حسابات لا يريد أن يشبهها', 'dislikes'),
                       ('لا يُذكر', 'never_mention'), ('قيود', 'limits')):
        if it.get(key):
            notes += ['', f'**{label}:**'] + [f'- {x}' for x in it[key]]
    notes += ['', '**افتراضات تحتاج تأكيدًا** (كل ما لم يُجب عنه صاحب العلامة):']
    notes += [f'- {x}' for x in it.get('assumptions') or []] or ['- لا شيء.']
    (root / 'brand-notes.md').write_text('\n'.join(notes) + '\n', encoding='utf-8')

    for src, dst in (('feedback-log.template.md', 'feedback-log.md'), ('playbook.template.md', 'playbook.md'),
                     ('experiments.template.md', 'performance/experiments.md')):
        if (ASSETS / src).exists():
            (root / dst).write_text((ASSETS / src).read_text(encoding='utf-8').replace('<العلامة>', it['name']), encoding='utf-8')
    shutil.copy2(ASSETS / 'design-system.template.md', root / 'design-system.TEMPLATE.md')

    account = [{'at': today + ' 00:00', 'platform': SHORT.get(PLATFORM_KEYS.get(k.lower(), k), k), 'followers': v}
               for k, v in (it.get('followers') or {}).items() if isinstance(v, int)]
    ledger = {'brand': it['name'], 'goal': goal, 'collection': it.get('metrics_method') or 'manual', 'review': it.get('review') or 'weekly',
              'baseline_window': 20, 'checkpoints_h': [24, 72, 168, 672], 'account': account, 'posts': []}
    (root / 'ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

    print(f'project created: {root.resolve()}')
    print(f'  goal: {goal} · platforms: {", ".join(sorted(active)) or "(not set)"} · numbers: {ledger["collection"]}')
    print('  colours: still the template defaults; take them from the official logo file in the design stage, before any render')
    g = gaps(b)
    if g:
        print(f'  still empty in brand.json ({len(g)}), fill them from the site, the logo file and the design stage:')
        for x in g:
            print('    -', x)
    print('next: build the design system (design-system.TEMPLATE.md -> design-system.md), get 3 sample slides approved, then plan two days.')


if __name__ == '__main__':
    main()
