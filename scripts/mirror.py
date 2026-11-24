"""Keep a delivery folder identical on Google Drive (or any synced folder): copies new or changed files (size or mtime
differs), removes what was deleted locally (Drive's desktop.ini aside), then optionally byte-checks everything
(nasaq-content-studio skill). Run it after EVERY change to a content file, not only at first delivery.

  python mirror.py "<local folder>" "<Drive folder>"            sync
  python mirror.py "<local folder>" "<Drive folder>" --verify   sync, then compare every file byte by byte
  python mirror.py "<local folder>" "<Drive folder>" --dry      list what would change
Import: from mirror import mirror"""
import filecmp
import shutil
import sys
from pathlib import Path

KEEP = {'desktop.ini', '.DS_Store'}

def mirror(src, dst, dry=False):
    src, dst = Path(src), Path(dst)
    copied, removed = [], []
    for a in [src] + sorted(p for p in src.rglob('*') if p.is_dir()):
        b = dst / a.relative_to(src)
        if not dry:
            b.mkdir(parents=True, exist_ok=True)
        names = {p.name for p in a.iterdir()}
        if b.exists():
            for p in b.iterdir():
                if p.name not in names and p.name not in KEEP:
                    removed.append(p)
                    if not dry:
                        shutil.rmtree(p) if p.is_dir() else p.unlink()
        for f in a.iterdir():
            if f.is_file() and f.name not in KEEP:
                g, s = b / f.name, f.stat()
                if not g.exists() or g.stat().st_size != s.st_size or int(g.stat().st_mtime) != int(s.st_mtime):
                    copied.append(g)
                    if not dry:
                        shutil.copy2(f, g)
    return copied, removed

def verify(src, dst):
    bad = []
    for f in Path(src).rglob('*'):
        if f.is_file() and f.name not in KEEP:
            g = Path(dst) / f.relative_to(src)
            if not g.exists() or not filecmp.cmp(f, g, shallow=False):
                bad.append(str(g))
    return bad

if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    s, d = Path(sys.argv[1]), Path(sys.argv[2])
    if not d.parent.exists():
        sys.exit(f'Drive folder not reachable: {d.parent} (is Google Drive for desktop running?)')
    c, r = mirror(s, d, dry='--dry' in sys.argv)
    print(f'{"would copy" if "--dry" in sys.argv else "copied"} {len(c)}, {"would remove" if "--dry" in sys.argv else "removed"} {len(r)}')
    for p in (c + r)[:40]:
        print('  ', p)
    if '--verify' in sys.argv:
        bad = verify(s, d)
        print('verify: identical' if not bad else f'verify: {len(bad)} differ'); [print('  !', b) for b in bad[:40]]
        sys.exit(1 if bad else 0)
