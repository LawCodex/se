#!/usr/bin/env python3
"""Fetch Swedish consolidated statutes (SFS) from Riksdagen open data into a raw cache.

Phase 1 ("list"): page through https://data.riksdagen.se/dokumentlista/?doktyp=sfs
(max 200 hits per page) and store every result page as JSON.
Phase 2 ("docs"): download https://data.riksdagen.se/dokument/<dok_id>.json for every
listed document (metadata + consolidated HTML/text).

Usage:
  fetch.py list [--raw DIR]
  fetch.py docs [--raw DIR] [--refresh] [--all]

Documents flagged "Författningen är upphävd" (repealed) are skipped unless --all.

Everything is cached under --raw (default ../../_raw/se); re-runs skip what exists
(use --refresh to re-download documents whose "systemdatum" in the listing is newer).
Be polite: <= 4 concurrent connections, retries with exponential backoff.
"""
import argparse
import concurrent.futures as cf
import glob
import json
import os
import sys
import threading
import time

import requests

LIST = "https://data.riksdagen.se/dokumentlista/"
DOC = "https://data.riksdagen.se/dokument/{id}.json"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
WORKERS = 4
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RAW = os.path.normpath(os.path.join(HERE, "..", "..", "_raw", "se"))

_local = threading.local()


def session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = UA
        _local.s = s
    return s


def get(url, params=None, tries=10):
    delay = 2
    for i in range(tries):
        try:
            r = session().get(url, params=params, timeout=180)
            if r.status_code == 200 and r.content.strip():
                return r
            if r.status_code == 404:
                return None
            err = f"HTTP {r.status_code} ({len(r.content)} bytes)"
        except requests.RequestException as e:
            err = str(e)[:200]
        print(f"  retry {i+1} {url} {params or ''}: {err}", file=sys.stderr)
        time.sleep(delay)
        delay = min(delay * 2, 120)
    raise RuntimeError(f"giving up on {url} {params}")


# Riksdagen's list API refuses to page beyond 10,000 hits, so the corpus is
# listed in date ranges that each stay well below that cap.
RANGES = [("", "1969-12-31"), ("1970-01-01", "1989-12-31"), ("1990-01-01", "2004-12-31"),
          ("2005-01-01", "2014-12-31"), ("2015-01-01", "")]


def cmd_list(raw):
    out = os.path.join(raw, "list")
    os.makedirs(out, exist_ok=True)
    total = 0
    for frm, tom in RANGES:
        tag = f"{frm or 'start'}_{tom or 'end'}"
        page, pages = 1, None
        while pages is None or page <= pages:
            fn = os.path.join(out, f"{tag}-p{page:04d}.json")
            params = {"doktyp": "sfs", "utformat": "json", "sz": 200, "sort": "datum",
                      "sortorder": "asc", "p": page}
            if frm:
                params["from"] = frm
            if tom:
                params["tom"] = tom
            d = get(LIST, params).json()["dokumentlista"]
            hits = int(d["@traffar"])
            if hits > 10000:
                sys.exit(f"range {tag} has {hits} hits (>10000): split RANGES")
            pages = int(d["@sidor"])
            docs = d.get("dokument") or []
            with open(fn, "w") as f:
                json.dump(docs, f, ensure_ascii=False)
            print(f"{tag} page {page}/{pages}: {len(docs)} (range total {hits})")
            page += 1
            time.sleep(0.3)
        total += hits
    print(f"listed {total} documents")


def is_repealed(meta):
    return "upphävd" in ((meta.get("sokdata") or {}).get("statusrad") or "")


def listed(raw):
    seen = {}
    for p in sorted(glob.glob(os.path.join(raw, "list", "*.json"))):
        for d in json.load(open(p)):
            seen[d["dok_id"]] = d
    return seen


def cmd_docs(raw, refresh=False, all_docs=False):
    out = os.path.join(raw, "docs")
    os.makedirs(out, exist_ok=True)
    items = listed(raw)
    todo = []
    for dok_id, meta in items.items():
        if is_repealed(meta) and not all_docs:
            continue
        path = os.path.join(out, dok_id + ".json")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            if not refresh:
                continue
            try:
                old = json.load(open(path))["dokumentstatus"]["dokument"].get("systemdatum", "")
            except Exception:
                old = ""
            if old >= meta.get("systemdatum", ""):
                continue
        todo.append((dok_id, path))
    print(f"{len(items)} listed, {len(todo)} to download")
    done = [0]
    lock = threading.Lock()

    def work(t):
        dok_id, path = t
        r = get(DOC.format(id=dok_id))
        if r is None:
            print(f"  404 {dok_id}", file=sys.stderr)
            return
        json.loads(r.content)  # validate
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(r.content)
        os.replace(tmp, path)
        with lock:
            done[0] += 1
            if done[0] % 250 == 0:
                print(f"  {done[0]}/{len(todo)}")

    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for _ in ex.map(work, todo):
            pass
    print("done")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "docs"])
    ap.add_argument("--raw", default=DEFAULT_RAW)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="also download documents listed as repealed (upphävd)")
    a = ap.parse_args()
    if a.cmd == "list":
        cmd_list(a.raw)
    else:
        cmd_docs(a.raw, a.refresh, a.all)


if __name__ == "__main__":
    main()
