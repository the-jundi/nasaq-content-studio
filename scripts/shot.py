"""Render HTML designs to PNG at exact sizes with headless Chromium: 2x device scale for crisp Arabic, then a LANCZOS
downscale to the target size (nasaq-content-studio skill).

  python shot.py page.html out.png 1080 1350
  python shot.py --batch list.json          list.json = [["page.html", "out.png", 1080, 1350], ...]
Set CHROME_PATH to reuse a Chromium already on the machine (e.g. on a VPS); otherwise Playwright's own browser is used
(pip install playwright pillow && python -m playwright install chromium).
Import: from shot import render_all"""
import json
import os
import sys
from pathlib import Path

def render_all(items, scale=2, settle_ms=500):
    from PIL import Image
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get('CHROME_PATH') or None)
        for html, out, w, h in items:
            pg = b.new_page(viewport={'width': int(w), 'height': int(h)}, device_scale_factor=scale)
            pg.goto(Path(html).resolve().as_uri())
            pg.evaluate('document.fonts.ready')          # Arabic webfonts must be in before the shot
            pg.wait_for_timeout(settle_ms)
            tmp = str(out) + '.2x.png'
            pg.screenshot(path=tmp)
            pg.close()
            Image.open(tmp).convert('RGB').resize((int(w), int(h)), Image.LANCZOS).save(out)
            Path(tmp).unlink()
            print('ok', out)
        b.close()

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--batch':
        render_all(json.loads(Path(sys.argv[2]).read_text(encoding='utf-8')))
    elif len(sys.argv) == 5:
        render_all([(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))])
    else:
        print(__doc__)
