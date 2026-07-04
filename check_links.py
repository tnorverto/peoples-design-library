"""Check every link in the built site and write dead-links-report.md.

Report-only by design: link checkers get fooled (bot-blocking, outages,
rate limits), so nothing is deleted automatically — the report tells you
what to look at in the spreadsheet.

Usage: python check_links.py   (expects index.html next to it; build first)
"""
import json, re, sys, time
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WORKERS = 32
TIMEOUT = 15
UA = {"User-Agent": "Mozilla/5.0 (compatible; PDL-LinkCheck/1.0; library maintenance)"}

# status codes that usually mean "blocked the robot", not "dead"
UNVERIFIABLE = {401, 403, 405, 406, 429, 999}


def check(url):
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers=UA, method=method)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if method == "GET" or e.code not in (403, 405, 406):
                return e.code
        except Exception:
            if method == "GET":
                return 0          # network-level failure (DNS, refused, timeout)
    return 0


def main():
    html = Path("index.html").read_text(encoding="utf-8")
    lib = json.loads(re.search(r"window\.LIB=(\{.*?\});", html, re.S).group(1))
    cols, secs, items = lib["collections"], lib["sections"], lib["items"]

    seen, targets = set(), []
    for it in items:
        if it[4] and it[4] not in seen:
            seen.add(it[4])
            targets.append(it)
    print(f"Checking {len(targets)} unique links with {WORKERS} workers…")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        statuses = list(ex.map(lambda it: check(it[4]), targets))
    print(f"Done in {int(time.time()-t0)}s")

    dead, blocked = [], 0
    for it, st in zip(targets, statuses):
        if st == 0 or st in (404, 410) or 500 <= st < 600:
            dead.append((it, st))
        elif st in UNVERIFIABLE:
            blocked += 1

    dead.sort(key=lambda x: (x[0][0], x[0][1]))
    lines = [
        "# Dead links report",
        "",
        f"Generated {time.strftime('%Y-%m-%d')} · {len(targets)} links checked · "
        f"**{len(dead)} look dead** · {blocked} unverifiable (bot-blocked — probably fine)",
        "",
        "Codes: `0` network failure/timeout · `404/410` gone · `5xx` server error.",
        "Check a few by hand before removing them from the spreadsheet — some sites only fail for robots.",
        "",
    ]
    last = None
    for it, st in dead:
        key = (it[0], it[1])
        if key != last:
            lines.append(f"\n## {cols[it[0]]['name']} → {secs[it[1]]['n']}")
            last = key
        sub = f" ({it[2]})" if it[2] else ""
        lines.append(f"- `{st}` **{it[3]}**{sub} — {it[4]}")

    Path("dead-links-report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote dead-links-report.md — {len(dead)} suspected dead links")


if __name__ == "__main__":
    sys.exit(main())
