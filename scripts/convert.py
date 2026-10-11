#!/usr/bin/env python3
"""Convert cached Riksdagen SFS documents (see fetch.py) to LawCodex Markdown.

Usage:
  convert.py [--raw DIR] [--out DIR] [--retrieved YYYY-MM-DD]

Reads <raw>/list/*.json (listing) and <raw>/docs/<dok_id>.json (documents) and writes:
  grundlagar/   the four fundamental laws + riksdagsordningen
  balkar/       the codes ("balkar")
  lagar/<year>/       acts (title "Lag ..." or "...lag")
  forordningar/<year>/ ordinances (title "Förordning ..." or "...förordning")
  ovriga/<year>/      other SFS instruments still in force (kungörelser,
                      tillkännagivanden, myndighetsföreskrifter, older forms...)
Documents flagged as repealed ("Författningen är upphävd") or whose whole-text
expiry date ("/Upphör att gälla U:YYYY-MM-DD/") has passed are skipped.
"""
import argparse
import datetime as dt
import glob
import html
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RAW = os.path.normpath(os.path.join(HERE, "..", "..", "_raw", "se"))
DEFAULT_OUT = os.path.normpath(os.path.join(HERE, ".."))

GRUNDLAGAR = {
    "1974:152": "regeringsformen",
    "1810:0926": "successionsordningen",
    "1949:105": "tryckfrihetsforordningen",
    "1991:1469": "yttrandefrihetsgrundlagen",
    "2014:801": "riksdagsordningen",
}


# ---------------------------------------------------------------- helpers

def clean_title(t):
    t = re.sub(r"^\s*/r\d+/\s*", "", t or "")
    t = re.sub(r"\s+", " ", t).strip()
    t = t.rstrip(";").strip()
    return t


def slugify(s, maxlen=80):
    s = s.lower()
    s = s.replace("å", "a").replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("é", "e")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s


def bet_slug(bet):
    return slugify(bet.replace(":", "-").replace(" ", "-"), 40)


def name_part(title):
    """Title without the '(YYYY:NNN)' designation, e.g. 'Lag om avtal' / 'Brottsbalk'."""
    return re.sub(r"\s*\(\d{4}:[^)]*\)\s*", " ", title).strip()


def classify(title, bet):
    if bet in GRUNDLAGAR:
        return "grundlagar", "constitution" if bet != "2014:801" else "act"
    head = title.split("(")[0].strip().lower()
    head = re.sub(r"^kungl\.? maj:ts\s+", "", head)
    words = head.split()
    first = words[0] if words else ""
    if re.fullmatch(r"\w*balk", first) or re.fullmatch(r"\w*balk", head):
        return "balkar", "code"
    if first.endswith("förordning") or head.endswith("förordning"):
        return "forordningar", "regulation"
    if first == "lag" or first.endswith("lag") or head.endswith("lag"):
        return "lagar", "act"
    if first.startswith("kungörelse") or head.endswith("kungörelse"):
        return "ovriga", "regulation"
    if first.startswith("tillkännagivande"):
        return "ovriga", "notice"
    if first.startswith("instruktion") or first.startswith("reglemente"):
        return "ovriga", "regulation"
    return "ovriga", "other"


def md_escape_line(s):
    if re.match(r"^(#|>|\+ |=+$|-+$|\|)", s):
        s = "\\" + s
    s = re.sub(r"<(?=[A-Za-z/!])", "&lt;", s)
    return s


def norm_ws(s):
    return re.sub(r"[ \t\r\n ]+", " ", s).strip()


TAG = re.compile(r"<[^>]+>")


def strip_tags(s):
    return TAG.sub("", s)


# ------------------------------------------------------------- converter

def table_to_md(tbl):
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.S | re.I)
    grid = []
    for r in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S | re.I)
        grid.append([norm_ws(html.unescape(strip_tags(re.sub(r"<br\s*/?>", " ", c)))).replace("|", "\\|")
                     for c in cells])
    if not grid or re.search(r"(rowspan|colspan)", tbl, re.I):
        return None
    n = max(len(r) for r in grid)
    if n == 0:
        return None
    grid = [r + [""] * (n - len(r)) for r in grid]
    out = ["| " + " | ".join(grid[0]) + " |", "|" + " --- |" * n]
    out += ["| " + " | ".join(r) + " |" for r in grid[1:]]
    return "\n".join(out)


def convert_body(h):
    """Return (markdown_body, head_text) from the Riksdagen SFS HTML."""
    # drop metadata header (before first <hr />), style and table of contents
    m = re.search(r"<hr\s*/?>", h)
    if m:
        h = h[m.end():]
    h = re.sub(r"<style.*?</style>", "", h, flags=re.S | re.I)
    h = re.sub(r'<div class="sfstoc">.*?</div>', "", h, flags=re.S | re.I)

    blocks = {}

    def stash(md):
        k = f"\x05{len(blocks)}\x05"
        blocks[k] = md
        return f"\n\n{k}\n\n"

    def tbl(m):
        md = table_to_md(m.group(0))
        if md is None:
            t = re.sub(r"\s+(class|style|width|border|cellpadding|cellspacing|valign|align)=\"[^\"]*\"",
                       "", m.group(0), flags=re.I)
            t = re.sub(r"<a name=\"[^\"]*\">\s*</a>", "", t)
            md = t.strip()
        return stash(md)

    h = re.sub(r"<table.*?</table>", tbl, h, flags=re.S | re.I)

    def pre(m):
        txt = html.unescape(strip_tags(re.sub(r"<br\s*/?>", "\n", m.group(1))))
        txt = txt.replace("\r", "").strip("\n")
        if not txt.strip():
            return "\n\n"
        return stash("```\n" + txt.replace("```", "``​`") + "\n```")

    h = re.sub(r"<pre[^>]*>(.*?)</pre>", pre, h, flags=re.S | re.I)

    def heading(level):
        def f(m):
            t = norm_ws(html.unescape(strip_tags(m.group(1))))
            return f"\n\n\x01H{level}\x02{t}\x03\n\n" if t else "\n\n"
        return f

    for lv in (1, 2, 3, 4, 5, 6):
        h = re.sub(rf"<h{lv}[^>]*>(.*?)</h{lv}>", heading(lv), h, flags=re.S | re.I)

    def para(m):
        t = norm_ws(html.unescape(strip_tags(m.group(1))))
        return f"\n\n\x01P\x02{t}\x03\n\n"

    h = re.sub(r'<a class="paragraf"[^>]*>(.*?)</a>', para, h, flags=re.S | re.I)
    h = re.sub(r"<p>\s*<a name=\"[^\"]*\">\s*</a>\s*</p>", "\n\n", h, flags=re.I)
    h = re.sub(r"</?p[^>]*>|</?div[^>]*>", "\n\n", h, flags=re.I)
    h = re.sub(r"<br\s*/?>", "\x04", h, flags=re.I)

    def emph(mark):
        def f(m):
            inner = m.group(1)
            if not strip_tags(inner).strip():
                return inner
            lead = re.match(r"\s*", inner).group(0)
            trail = re.search(r"\s*$", inner).group(0)
            return f"{lead}{mark}{inner.strip()}{mark}{trail}"
        return f

    h = re.sub(r"<i>(.*?)</i>", emph("*"), h, flags=re.S | re.I)
    h = re.sub(r"<b>(.*?)</b>", emph("**"), h, flags=re.S | re.I)
    h = re.sub(r"<su[pb]>(.*?)</su[pb]>", r"\1", h, flags=re.S | re.I)
    h = strip_tags(h)
    h = html.unescape(h)

    items = []  # (kind, value)
    for chunk in re.split(r"\n\s*\n", h):
        if "\x01" in chunk:
            # may carry heading marker plus trailing text
            parts = re.split(r"(\x01\w+\x02.*?\x03)", chunk, flags=re.S)
        else:
            parts = [chunk]
        for p in parts:
            mm = re.fullmatch(r"\x01(\w+)\x02(.*?)\x03", p, flags=re.S)
            if mm:
                items.append((mm.group(1), mm.group(2)))
                continue
            lines = [norm_ws(x) for x in p.split("\x04")]
            lines = [x for x in lines if x]
            if lines:
                items.append(("T", lines))

    # heading levels
    present = sorted({k for k, _ in items if k.startswith("H")})
    lvl = {k: min(2 + i, 6) for i, k in enumerate(present)}
    plevel = min(2 + len(present), 6)

    out = []
    in_overgang = False
    for kind, val in items:
        if kind.startswith("H"):
            in_overgang = val.lower().startswith("övergångsbestämmelser")
            out.append("#" * lvl[kind] + " " + val)
        elif kind == "P":
            out.append("#" * plevel + " " + val if plevel <= 6 else f"**{val}**")
        else:
            for line in val:
                if line in blocks:
                    out.append(blocks[line])
                    continue
                if in_overgang and re.fullmatch(r"\d{4}:\d+(\s\S+)?", line):
                    out.append(f"**{line}**")
                    continue
                out.append(md_escape_line(line))
    body = "\n\n".join(out)
    # restore any stashed block that ended up inline
    for k, v in blocks.items():
        body = body.replace(k, "\n\n" + v + "\n\n")
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    return body


def yaml_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def uppgift(ds):
    res = {}
    for key in ("dokuppgift", "dokumentuppgift"):
        u = (ds.get(key) or {}).get("uppgift") or []
        if isinstance(u, dict):
            u = [u]
        for x in u:
            res.setdefault(x.get("kod"), x.get("text"))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=DEFAULT_RAW)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--retrieved", default=dt.date.today().isoformat())
    a = ap.parse_args()
    today = a.retrieved

    listing = {}
    for p in sorted(glob.glob(os.path.join(a.raw, "list", "*.json"))):
        for d in json.load(open(p)):
            listing[d["dok_id"]] = d

    for sub in ("grundlagar", "balkar", "lagar", "forordningar", "ovriga"):
        d = os.path.join(a.out, sub)
        if os.path.isdir(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith(".md"):
                        os.remove(os.path.join(root, f))

    stats = {"written": 0, "repealed": 0, "expired": 0, "not_sfst": 0, "missing": 0, "empty": 0}
    cats = {}
    index = []
    used = set()
    for dok_id, meta in sorted(listing.items()):
        if meta.get("subtyp") != "sfst":
            stats["not_sfst"] += 1
            continue
        if "upphävd" in ((meta.get("sokdata") or {}).get("statusrad") or ""):
            stats["repealed"] += 1
            continue
        path = os.path.join(a.raw, "docs", dok_id + ".json")
        if not os.path.exists(path):
            stats["missing"] += 1
            print(f"missing {dok_id}", file=sys.stderr)
            continue
        ds = json.load(open(path))["dokumentstatus"]
        doc = ds["dokument"]
        up = uppgift(ds)
        bet = (doc.get("beteckning") or meta.get("beteckning") or "").strip()
        title = clean_title(doc.get("titel") or meta.get("titel"))
        raw_html = doc.get("html") or ""
        text = doc.get("text") or ""
        head = norm_ws(text[:300])
        expires = None
        m = re.match(r"/Upphör att gälla U:(\d{4}-\d{2}-\d{2})/", head)
        if m:
            expires = m.group(1)
            if expires <= today:
                stats["expired"] += 1
                continue
        starts = None
        m = re.match(r"/Träder i kraft I:(\d{4}-\d{2}-\d{2})/", head)
        if m:
            starts = m.group(1)

        body = convert_body(raw_html) if raw_html.strip() else ""
        if not body.strip() and text.strip():
            body = "\n\n".join(md_escape_line(norm_ws(p)) for p in re.split(r"\r?\n\s*\r?\n", text)
                               if p.strip()) + "\n"
        if not body.strip():
            stats["empty"] += 1
            body = "*(Ingen författningstext tillgänglig i källan.)*\n"

        cat, typ = classify(title, bet)
        year = bet[:4] if re.match(r"\d{4}", bet) else (doc.get("rm") or "0000")[:4]
        if cat == "grundlagar":
            rel = f"grundlagar/{bet_slug(bet)}-{GRUNDLAGAR[bet]}.md"
        elif cat == "balkar":
            rel = f"balkar/{bet_slug(bet)}-{slugify(name_part(title), 60)}.md"
        else:
            rel = f"{cat}/{year}/{bet_slug(bet)}-{slugify(name_part(title), 70)}.md"
        rel = rel.replace("-.md", ".md")
        if rel in used:
            rel = rel[:-3] + "-" + slugify(dok_id) + ".md"
        used.add(rel)

        utf = (up.get("utfardad") or (doc.get("datum") or "")[:10] or "").strip()
        tom = (up.get("andrattillochmed") or doc.get("subtitel") or "").strip()
        fm = ["---",
              f"title: {yaml_str(title)}",
              f"identifier: {yaml_str('SFS ' + bet)}",
              f"type: {typ}",
              "jurisdiction: se",
              "language: sv"]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", utf):
            fm.append(f"date: {utf}")
        if tom:
            fm.append(f"amended_through: {yaml_str(re.sub(r'^t\.o\.m\.\s*', '', tom))}")
        if up.get("omtryck"):
            fm.append(f"reprinted: {yaml_str(norm_ws(up['omtryck']))}")
        if doc.get("organ"):
            fm.append(f"department: {yaml_str(norm_ws(doc['organ']))}")
        if starts:
            fm.append(f"entry_into_force: {starts}")
        if expires:
            fm.append(f"expires: {expires}")
        fm += ["status: in_force",
               f"source: {yaml_str('https://data.riksdagen.se/dokument/' + dok_id.replace(' ', '%20') + '.html')}",
               f"consolidated_text: {yaml_str('https://rkrattsbaser.gov.se/sfst?bet=' + bet.replace(' ', '%20'))}",
               f"retrieved: {today}",
               "---", ""]
        note = norm_ws(up.get("text2") or "")
        intro = f"# {title}\n\n"
        if note:
            intro += f"> {note}\n\n"
        out_path = os.path.join(a.out, rel)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(fm) + intro + body)
        stats["written"] += 1
        cats[cat] = cats.get(cat, 0) + 1
        index.append((cat, bet, title, rel))

    print(json.dumps(stats, ensure_ascii=False))
    print(json.dumps(cats, ensure_ascii=False))
    with open(os.path.join(a.raw, "index.json"), "w") as f:
        json.dump({"stats": stats, "cats": cats, "index": index}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
