"""X (Twitter) weighted length + on-image dialect check, brand-neutral (nasaq-content-studio skill).

  python xlen.py "tweet text"                     weighted length (twitter-text v3: URL 23, emoji 2, Arabic/Latin 1, CJK 2)
  python xlen.py --cta "brand contact line" "tweet text"   also says whether the contact line is in it and what it costs
  python xlen.py --image "on-image text"          flags explicit Gulf/white-dialect words (keep them off shared landscape images)
Import: from xlen import x_weighted_len, dialect_words"""
import re
import sys

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿‼⁉〰〽㊗㊙]"
    "[️‍\U0001F3FB-\U0001F3FF\U0001F000-\U0001FAFF☀-➿]*")
URL_RE = re.compile(r"(https?://\S+|(?<![@\w.])[a-z0-9-]+\.(?:com|sa|ai|co|in|io|net|org|store|app)(?:/\S*)?)", re.I)
DIALECT = {"وش", "مو", "الحين", "اللي", "بس", "ودك", "ودّك", "عشان", "هذي", "كذا", "ليش", "وين", "تبي",
           "يبي", "شوف", "خل", "خلّ", "خلها", "خلّها", "عطنا", "ترى", "طيب", "للحين", "مب", "ماهو", "مافيه"}

def x_weighted_len(text):
    """twitter-text v3 weighting: U+0000-U+10FF (Latin AND Arabic) weigh 1, a few punctuation ranges 1, the rest 2;
    every URL counts 23, every emoji sequence 2."""
    t = URL_RE.sub("\x00", text)
    n = t.count("\x00") * 23
    t = EMOJI_RE.sub("\x01", t.replace("\x00", ""))
    n += t.count("\x01") * 2
    for ch in t.replace("\x01", ""):
        o = ord(ch)
        n += 1 if (o <= 4351 or 8192 <= o <= 8205 or 8208 <= o <= 8223 or 8242 <= o <= 8247) else 2
    return n

def dialect_words(text):
    return sorted({w for w in re.findall(r"[؀-ۿ]+", text) if w in DIALECT or (w.startswith("و") and w[1:] in DIALECT)})

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    if a[0] == "--image":
        hits = dialect_words(" ".join(a[1:]))
        print("OK: neutral" if not hits else "DIALECT on image: " + "، ".join(hits)); return
    cta = None
    if a[0] == "--cta":
        cta, a = a[1], a[2:]
    text = " ".join(a).replace("\\n", "\n")
    n = x_weighted_len(text)
    note = ""
    if cta and cta not in text:
        note = f" (contact line not included; adding it costs {x_weighted_len(cta) + 1})"
    print(f"{n}/280 {'OK' if n <= 280 else 'OVER by ' + str(n - 280)}{note}")

if __name__ == "__main__":
    main()
