"""Read public posts without logging in, for the research corpus (nasaq-content-studio; the methods that worked in the
the real-estate brand test, 2026-11-03). Read-only: nothing is liked, followed, accepted or posted; a sign-up modal is closed with its
X only. Polite: 2 s between calls, stop at the first 429 or authwall.

  python public_capture.py x  out.json shots/ <tweet id or URL> ...     X: syndication JSON + embed screenshot
  python public_capture.py ig out.json shots/ <post or reel URL> ...    Instagram: og:description + screenshot
  python public_capture.py page out.json shots/ <URL> ...               any public page (LinkedIn post, TikTok, a site)

What each gives (and what it cannot):
  x     text, created_at, favorite_count, conversation_count, media types, quoted tweet id. Followers, reposts and
        views are NOT exposed, and long posts come truncated (text_truncated). X profiles and search need login
        (HTTP 403), and the profile timeline endpoint rate-limits at once, so tweet IDs come from web search
        snippets or from quoted_tweet inside other tweets' JSON.
  ig    likes, comments, account, date and caption from og:description (often rounded: "13.7K"), plus the carousel
        slide count. Plain curl gets an app shell with no data; only a real browser exposes og: tags.
  page  og:title, og:description and a screenshot; LinkedIn guest pages show reaction counters until an authwall
        appears (about 20 requests), then stop.
Results merge into out.json (keyed by id), so a run can resume. Record how/where each item came from in
research/search-log.md (the owner's rule for research briefs)."""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'

def _meta(pg, prop):
    el = pg.query_selector(f"meta[property='{prop}']") or pg.query_selector(f"meta[name='{prop}']")
    return el.get_attribute('content') if el else None

def _close_modal(pg):
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(500)
    el = pg.query_selector("div[role='dialog'] svg[aria-label='Close']") or pg.query_selector("svg[aria-label='Close']")
    if el:
        try:
            el.click(timeout=2000)
        except Exception:  # noqa: BLE001
            pass
    pg.wait_for_timeout(500)

def capture(kind, out_json, shots, items):
    data = json.loads(Path(out_json).read_text(encoding='utf-8')) if Path(out_json).exists() else {}
    os.makedirs(shots, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get('CHROME_PATH') or None)
        pg = b.new_context(viewport={'width': 1080, 'height': 1100}, locale='en-US', user_agent=UA).new_page()
        for it in items:
            if kind == 'x':
                key = re.search(r'(\d{8,})', it).group(1)
            elif kind == 'ig':
                key = re.search(r'/(?:p|reel)/([A-Za-z0-9_-]+)', it).group(1)
            else:
                key = re.sub(r'\W+', '_', it.split('//', 1)[-1])[:80]
            if data.get(key, {}).get('ok'):
                continue
            rec = {'id': key, 'source': it, 'captured': time.strftime('%Y-%m-%d')}
            try:
                if kind == 'x':
                    url = f'https://cdn.syndication.twimg.com/tweet-result?id={key}&token=a&lang=ar'
                    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=30) as r:
                        body = r.read().decode('utf-8')
                    j = json.loads(body) if body.strip() else {}
                    if not j:
                        raise ValueError('empty body: deleted or protected')
                    u = j.get('user') or {}
                    rec.update(method=url, text=j.get('text'), created_at=j.get('created_at'), likes=j.get('favorite_count'),
                               replies=j.get('conversation_count'), account=u.get('screen_name'),
                               media=[m.get('type') for m in j.get('mediaDetails') or []],
                               quoted=(j.get('quoted_tweet') or {}).get('id_str'), text_truncated=bool(j.get('note_tweet')))
                    pg.goto(f'https://platform.twitter.com/embed/Tweet.html?id={key}&lang=ar', wait_until='networkidle', timeout=45000)
                else:
                    r = pg.goto(it, wait_until='domcontentloaded', timeout=45000)
                    pg.wait_for_timeout(4000)
                    if r and r.status in (403, 429) or 'authwall' in pg.url or '/login' in pg.url:
                        rec['stopped'] = f'HTTP {r.status if r else "?"} / {pg.url}'
                        data[key] = rec
                        print('STOP', key, rec['stopped']); break
                    rec.update(method=f'Playwright, no login: {it} -> og: meta', og_title=_meta(pg, 'og:title'),
                               og_description=_meta(pg, 'og:description'))
                    _close_modal(pg)
                    if kind == 'ig':
                        t = pg.query_selector('main time[datetime], article time[datetime]')
                        rec['datetime'] = t.get_attribute('datetime') if t else None
                        m = re.match(r'([\d.,KkMm]+) likes?, ([\d.,KkMm]+) comments?', rec['og_description'] or '')
                        rec['likes'], rec['replies'] = (m.group(1), m.group(2)) if m else (None, None)
                        n = 1
                        while n < 20 and (nx := pg.query_selector("main button[aria-label='Next']")):
                            nx.click(timeout=2000); pg.wait_for_timeout(400); n += 1
                        rec['slides'] = n
                shot = str(Path(shots) / f'{kind}-{key}.png')
                pg.screenshot(path=shot)
                rec.update(shot=shot, ok=True)
            except urllib.error.HTTPError as e:
                rec['error'] = f'HTTP {e.code}'
                if e.code == 429:
                    data[key] = rec; print('STOP rate limit'); break
            except Exception as e:  # noqa: BLE001
                rec['error'] = str(e)[:200]
            data[key] = rec
            print(key, 'ok' if rec.get('ok') else rec.get('error'), (rec.get('text') or rec.get('og_description') or '')[:80].replace('\n', ' '))
            Path(out_json).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
            time.sleep(2)
        b.close()
    Path(out_json).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    return data

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    a = sys.argv[1:]
    if len(a) < 4 or a[0] not in ('x', 'ig', 'page'):
        print(__doc__); sys.exit(2)
    capture(a[0], a[1], a[2], a[3:])
