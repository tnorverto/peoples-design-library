"""Build The People's Design Library website from the Google Sheet.

Downloads the spreadsheet as a zipped web page (the only export that keeps
EVERY hyperlink, including several per cell), parses each sheet's HTML,
detects section headers by their background colour, captures the
Tips & Tricks sidebars, and injects everything into shell.html
to produce index.html.

Usage:  python build.py             (downloads from SHEET_ID)
        python build.py export.zip  (uses a local zip instead)
        python build.py folder/     (uses an already-unzipped folder)
"""
import io, json, re, sys, zipfile, urllib.request
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup

SHEET_ID = "13GStMRQfbn5glWVkUPqFtW1oovyKhMDdRKD3m5cstBg"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=zip"

# (html file name, display name, call-number code, spine color)
COLLECTIONS = [
    ("GRAPHIC   GENERAL DESIGN", "Graphic & General Design", "GD", "#2E6E7E"),
    ("VIDEO   ANIMATION   SOUND", "Video, Animation & Sound", "VA", "#7A4E8C"),
    ("ARCHITECTURE   3D", "Architecture & 3D", "AR", "#B07A2A"),
    ("AI   SOFTWARE   PLUGINS", "AI, Software & Plugins", "AI", "#3D6B35"),
    ("TUTORIALS", "Tutorials", "TU", "#34518F"),
    ("EXTRAS", "Extras", "EX", "#A8502F"),
]

SECTION_RENAME = {
    "SOUND DESIGN / ENGEENEERING": "SOUND DESIGN / ENGINEERING",
    "PERSONAL RECCOMENDATIONS ⬇️⬇️⬇️": "PERSONAL RECOMMENDATIONS",
}

FIRE = re.compile("\U0001F525+")
PIRATE = re.compile("\U0001F3F4\u200d\u2620\ufe0f|\u200d")
WS = re.compile(r"\s+")
TIPS_RE = re.compile(r"^Tips\s*&\s*tricks!?\s*[-–—:]?\s*", re.I)
KW_RE = re.compile(r"keyword|jargon|grammar", re.I)
PAT_RE = re.compile(r"^(Types of .+ Patterns|Historic Wallpapers)\s*:?\s*$", re.I)
COUNTRY_FLAGS = [
    (r"Italy|Italian", "🇮🇹"), (r"Spain|Spanish", "🇪🇸"), (r"France|French", "🇫🇷"),
    (r"Germany|German\b", "🇩🇪"), (r"Netherlands|Holland|Dutch", "🇳🇱"),
    (r"Denmark|Danish", "🇩🇰"), (r"Sweden|Swedish|Sweeden", "🇸🇪"), (r"Norway|Norwegian", "🇳🇴"),
    (r"Finland|Finnish", "🇫🇮"), (r"Iceland", "🇮🇸"),
    (r"\bUK\b|England|Britain|United Kingdom|Scotland", "🇬🇧"),
    (r"\bUSA\b|\bUS\b|United States", "🇺🇸"),
    (r"Portugal|Portuguese", "🇵🇹"), (r"Poland|Polish", "🇵🇱"), (r"Switzerland|Swiss", "🇨🇭"),
    (r"Austria(?!lia)", "🇦🇹"), (r"Belgium|Belgian", "🇧🇪"), (r"Ireland|Irish", "🇮🇪"),
    (r"Greece", "🇬🇷"), (r"Japan\b|Japanese", "🇯🇵"), (r"China\b|Chinese", "🇨🇳"),
    (r"India\b|Indian", "🇮🇳"), (r"Turkey|Turkish", "🇹🇷"), (r"Iran\b|Persia\b|Persian", "🇮🇷"),
    (r"Moro?cc?o|Moroccan|Morroco", "🇲🇦"), (r"Egypt", "🇪🇬"), (r"Mexico|Mexican", "🇲🇽"),
    (r"Brazil", "🇧🇷"), (r"Peru\b|Peruvian", "🇵🇪"), (r"Bolivia", "🇧🇴"), (r"Chile\b", "🇨🇱"),
    (r"Argentina", "🇦🇷"), (r"Canada|Canadian", "🇨🇦"), (r"Australia\b", "🇦🇺"),
    (r"Russia\b", "🇷🇺"), (r"Ukraine", "🇺🇦"), (r"Georgia\b", "🇬🇪"), (r"Armenia", "🇦🇲"),
    (r"Azerbaijan|\bAzer\b", "🇦🇿"), (r"Kazakh?stan|Kazajstan", "🇰🇿"),
    (r"Uzbekistan|\bUzbe\b", "🇺🇿"), (r"Tajikistan|\bTajiki\b", "🇹🇯"),
    (r"Nepal", "🇳🇵"), (r"Pakistan", "🇵🇰"), (r"Myanmar|\bMyanm\b", "🇲🇲"),
    (r"Thailand|Thai\b", "🇹🇭"), (r"Vietnam|\btnam\b", "🇻🇳"), (r"Korea\b|Korean", "🇰🇷"),
    (r"Cc?zech", "🇨🇿"), (r"Hungary", "🇭🇺"), (r"Romania", "🇷🇴"), (r"Croatia", "🇭🇷"),
    (r"Israel", "🇮🇱"), (r"Nigeria", "🇳🇬"), (r"Indonesia", "🇮🇩"), (r"Singapore", "🇸🇬"),
    (r"Taiwan", "🇹🇼"), (r"Slovenia", "🇸🇮"), (r"Estonia", "🇪🇪"),
]
COUNTRY_FLAGS = [(re.compile(p, re.I), f) for p, f in COUNTRY_FLAGS]

def flags_for(*texts):
    out = []
    for t in texts:
        if not t:
            continue
        for rx, f in COUNTRY_FLAGS:
            if f not in out and rx.search(t):
                out.append(f)
    return "".join(out[:4])


# ---------------------------------------------------------------- download
def download(path="sheet_export.zip"):
    print("Downloading sheet (web page export)…")
    req = urllib.request.Request(EXPORT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


def load_htmls(src):
    """Return {basename: html_text} from a zip file or folder."""
    out = {}
    p = Path(src)
    if p.is_dir():
        for f in p.glob("*.html"):
            out[f.stem] = f.read_text(encoding="utf-8", errors="replace")
    else:
        with zipfile.ZipFile(src) as z:
            for name in z.namelist():
                if name.lower().endswith(".html"):
                    out[Path(name).stem] = z.read(name).decode("utf-8", errors="replace")
    return out


# ---------------------------------------------------------------- helpers
def css_classes(html):
    return {m.group(1): m.group(2) for m in re.finditer(r"\.(s\d+)\{([^}]+)\}", html)}


def expand_grid(table):
    """Yield (row_index, col_index, td) with rowspan/colspan resolved."""
    occupied = {}  # (r, c) -> True for cells shadowed by spans
    for ri, tr in enumerate(table.find_all("tr")):
        ci = 0
        for td in tr.find_all(["td", "th"]):
            while occupied.pop((ri, ci), None):
                ci += 1
            rs = int(td.get("rowspan", 1) or 1)
            cs = int(td.get("colspan", 1) or 1)
            yield ri, ci, cs, td
            for dr in range(rs):
                for dc in range(cs):
                    if dr or dc:
                        occupied[(ri + dr, ci + dc)] = True
            ci += cs


def clean_text(t):
    return WS.sub(" ", PIRATE.sub("", t)).strip()


def clean_section(s):
    s = SECTION_RENAME.get(s, s)
    s = WS.sub(" ", FIRE.sub("", s)).strip().rstrip(":").strip()   # keep the pirate flag visible
    return s or "General"


def clean_name(n):
    pick = bool(FIRE.search(n))
    n = clean_text(FIRE.sub("", n)).strip(" -–—:").strip()
    if len(n) > 110:
        n = n[:110].rsplit(" ", 1)[0] + "…"
    return n, pick


def domain(u):
    try:
        d = urlparse(u).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""


def good_href(h):
    return isinstance(h, str) and h.startswith(("http://", "https://"))


def cell_prefix(td):
    """Text appearing before the first <a> in the cell."""
    first = td.find("a")
    if first is None:
        return ""
    parts = []
    for el in td.descendants:
        if el is first:
            break
        if isinstance(el, str):
            parts.append(el)
    return clean_text("".join(parts))


# ---------------------------------------------------------------- parsing
def parse_sheet(col_i, html):
    """Return (entries, tips). entries: (section, subheader, name, url, note)."""
    css = css_classes(html)

    def bg(td):
        cls = (td.get("class") or [None])[0]
        m = re.search(r"background-color:(#\w+)", css.get(cls or "", ""))
        c = m.group(1).lower() if m else None
        return None if c in (None, "#ffffff", "#fff") else c

    def is_bold(td):
        cls = (td.get("class") or [None])[0]
        return "font-weight:bold" in css.get(cls or "", "")

    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table") or soup

    cells = list(expand_grid(table))
    plain = {}                # (row, col) -> text of non-link, non-colored cells
    for ri, ci, span, td in cells:
        t = clean_text(td.get_text(" ", strip=True))
        if t and not td.find("a") and not bg(td):
            plain[(ri, ci)] = t

    entries, tips = [], []
    col_section = {}          # col -> section name
    col_sub = {}              # col -> subheader
    tip_state = {}            # col -> {"title","body","links","last"}
    kw = None                 # active keyword-library zone
    bz = None                 # active furnishing-brands zone
    pz = None                 # active patterns/archives zone
    title_seen = False

    def close_tip(c):
        st = tip_state.pop(c, None)
        if st and (st["body"] or st["links"]):
            tips.append(st)

    for ri, ci, span, td in cells:
        text = clean_text(td.get_text(" ", strip=True))
        if not text:
            continue
        cols = range(ci, ci + span)

        if kw and ri - kw["last"] > 8:
            kw = None
        if bz and ri - bz["last"] > 10:
            bz = None
        if pz and ri - pz["last"] > 6:
            pz = None

        # ---- colored cell → sheet title (first) or section header
        if bg(td):
            if kw and (ci + span - 1) >= kw["col"]:
                kw = None
            if bz and (ci + span - 1) >= bz["col"]:
                bz = None
            if pz and (ci + span - 1) >= pz["col"]:
                pz = None
            if not title_seen:
                title_seen = True
                continue
            section = clean_section(WS.sub(" ", td.get_text(" ", strip=True)).strip())
            for c in list(tip_state):
                if c in cols or (span >= 3 and ci <= 3):
                    close_tip(c)
            if span >= 3 and ci <= 3:          # full-width: applies everywhere
                col_section = {c: section for c in set(list(col_section) + list(cols))}
                col_section["_global"] = section
                col_sub = {}
            else:                               # column-scoped header
                for c in cols:
                    col_section[c] = section
                    col_sub.pop(c, None)
            continue

        # ---- tips capture (keyword libraries get their own zone instead)
        if TIPS_RE.match(text):
            close_tip(ci)
            kw = None
            if bz and ci >= bz["col"]:
                bz = None
            rest = clean_text(TIPS_RE.sub("", text)).rstrip(":").strip()
            if KW_RE.search(rest):
                kw = {"title": rest.title() if rest.isupper() else rest,
                      "col": ci, "sub": None, "last": ri}
            else:
                tip_state[ci] = {"c": col_i, "t": rest or "Tip",
                                 "body": [], "links": [], "last": ri}
            continue

        # ---- patterns & archives zone (Historic Wallpapers, Types of X Patterns)
        if is_bold(td) and not bg(td) and PAT_RE.match(text):
            block = re.sub(r"^Types of\s+", "", text).rstrip(":").strip()
            pz = {"col": ci, "block": block, "colhead": {}, "last": ri}
            continue
        if pz and ci >= pz["col"]:
            pz["last"] = ri
            anchors = [a for a in td.find_all("a") if good_href(a.get("href"))]
            if anchors:
                sub = pz["block"]
                ch = pz["colhead"].get(ci)
                if ch:
                    sub = f"{sub} · {ch}"
                raw = td.get_text(" ", strip=True)
                cellfire = " 🔥" if FIRE.search(raw) else ""
                cellpir = 1 if "\U0001F3F4" in raw else 0
                if len(anchors) == 1:
                    a = anchors[0]
                    atext = clean_text(a.get_text(" ", strip=True))
                    note = ""
                    nm = atext or text
                    if atext and len(text) > len(atext):
                        note = clean_text(text.replace(atext, "", 1)).strip(" -–—:/").strip()
                    entries.append(("📜 Patterns & Archives", sub, nm + cellfire, a["href"].strip(), note, cellpir))
                else:
                    prefix = cell_prefix(td)
                    for a in anchors:
                        atext = clean_text(a.get_text(" ", strip=True))
                        if re.match(r"https?://", atext):
                            atext = domain(a["href"]) or atext
                        nm = f"{prefix} {atext}".strip() if prefix else (atext or domain(a["href"]))
                        entries.append(("📜 Patterns & Archives", sub, nm + cellfire, a["href"].strip(), "", cellpir))
            elif is_bold(td):
                pz["colhead"][ci] = clean_text(text).rstrip(":").strip()
            continue

        # ---- furnishing-brands zone (parallel sidebar of brand blocks)
        if is_bold(td) and not bg(td) and text.upper().startswith("FURNISHING BRANDS"):
            bz = {"col": ci, "block": None, "minor": None, "colhead": {}, "last": ri}
            kw = None
            continue
        if bz and ci >= bz["col"]:
            bz["last"] = ri
            anchors = [a for a in td.find_all("a") if good_href(a.get("href"))]
            if anchors:
                grp = bz["colhead"].get(ci) or bz["minor"]
                sub = bz["block"] or grp or "Brands"
                if bz["block"] and grp:
                    sub = f'{bz["block"]} · {grp}'
                raw = td.get_text(" ", strip=True)
                cellfire = " 🔥" if FIRE.search(raw) else ""
                cellpir = 1 if "\U0001F3F4" in raw else 0
                if len(anchors) == 1:
                    a = anchors[0]
                    atext = clean_text(a.get_text(" ", strip=True))
                    note = ""
                    nm = atext or text
                    if atext and len(text) > len(atext):
                        note = clean_text(text.replace(atext, "", 1)).strip(" -–—:/").strip()
                    entries.append(("🛋️ Furnishing Brands", sub, nm + cellfire, a["href"].strip(), note, cellpir))
                else:
                    prefix = cell_prefix(td)
                    for a in anchors:
                        atext = clean_text(a.get_text(" ", strip=True))
                        if re.match(r"https?://", atext):
                            atext = domain(a["href"]) or atext
                        nm = f"{prefix} {atext}".strip() if prefix else (atext or domain(a["href"]))
                        entries.append(("🛋️ Furnishing Brands", sub, nm + cellfire, a["href"].strip(), "", cellpir))
            elif is_bold(td):
                head = clean_text(text.split("(")[0]).strip()
                if head and head == head.upper() and len(head) >= 4 and ":" not in head:
                    bz["block"] = head.title()  # major block: FURNITURE, LIGHT, ACOUSTIC… (legend may share the cell)
                    bz["minor"] = None
                    bz["colhead"] = {}
                elif text.startswith("(") or ": Has " in text or text.startswith("🏛") or not head:
                    pass                       # legend cells
                elif text.rstrip().endswith(":"):
                    bz["colhead"][ci] = clean_text(text).rstrip(":").strip()
                else:
                    bz["minor"] = clean_text(text)  # mixed-case group inside a block
            else:
                # non-bold ALL-CAPS titles (some block headers are styled with borders, not bold)
                head = clean_text(text.split("(")[0]).strip()
                if head and head == head.upper() and len(head) >= 6 and ":" not in head and not head.startswith("("):
                    bz["block"] = head.title()
                    bz["minor"] = None
                    bz["colhead"] = {}
            continue

        # ---- keyword-library zone: everything in its columns becomes a Keywords entry
        if kw and ci >= kw["col"]:
            kw["last"] = ri
            anchors = [a for a in td.find_all("a") if good_href(a.get("href"))]
            if anchors:
                sub = kw["sub"] or kw["title"]
                raw = td.get_text(" ", strip=True)
                cellfire = " 🔥" if FIRE.search(raw) else ""
                cellpir = 1 if "\U0001F3F4" in raw else 0
                if len(anchors) == 1:
                    entries.append(("🔤 Keywords", sub, text + cellfire, anchors[0]["href"].strip(), "", cellpir))
                else:
                    prefix = cell_prefix(td)
                    for a in anchors:
                        atext = clean_text(a.get_text(" ", strip=True))
                        if re.match(r"https?://", atext):
                            atext = domain(a["href"]) or atext
                        nm = f"{prefix} {atext}".strip() if prefix else (atext or domain(a["href"]))
                        entries.append(("🔤 Keywords", sub, nm + cellfire, a["href"].strip(), "", cellpir))
            elif is_bold(td):
                kw["sub"] = clean_text(text).rstrip(":").strip() or None
            continue
        if ci in tip_state:
            st = tip_state[ci]
            if ri - st["last"] > 6 or is_bold(td):
                close_tip(ci)
            else:
                st["last"] = ri
                links = [a for a in td.find_all("a") if good_href(a.get("href"))]
                if links:
                    for a in links:
                        st["links"].append([clean_text(a.get_text(" ", strip=True)) or domain(a["href"]), a["href"].strip()])
                else:
                    st["body"].append(text)
                continue

        # ---- link cells → entries
        anchors = [a for a in td.find_all("a") if good_href(a.get("href"))]
        if anchors:
            sec = col_section.get(ci) or col_section.get("_global") or "General"
            sub = col_sub.get(ci)
            raw = td.get_text(" ", strip=True)
            cellfire = " 🔥" if FIRE.search(raw) else ""
            cellpir = 1 if "🏴" in raw else 0
            if len(anchors) == 1:
                a = anchors[0]
                atext = clean_text(a.get_text(" ", strip=True))
                note = ""
                if re.match(r"https?://", text):   # raw-URL cell: title sits to the left
                    left = plain.get((ri, ci - 1))
                    left2 = plain.get((ri, ci - 2))
                    if left:
                        name = left
                        if left2:
                            sub = left2
                    else:
                        name = domain(a["href"]) or text
                else:
                    name = atext or text
                    if atext and len(text) > len(atext):
                        note = clean_text(text.replace(atext, "", 1)).strip(" -–—:/()").strip()
                        if note.lower() == name.lower():
                            note = ""
                        elif len(name) <= 3 and len(note) > 3:   # anchor was just "1" etc.
                            name, note = f"{note} {name}", ""
                entries.append((sec, sub, name + cellfire, a["href"].strip(), note, cellpir))
            else:
                prefix = cell_prefix(td)
                for a in anchors:
                    atext = clean_text(a.get_text(" ", strip=True))
                    if re.match(r"https?://", atext):
                        atext = domain(a["href"]) or atext
                    name = f"{prefix} {atext}".strip() if prefix else (atext or domain(a["href"]))
                    entries.append((sec, sub, name + cellfire, a["href"].strip(), "", cellpir))
        elif is_bold(td):
            for c in cols:
                col_sub[c] = clean_text(text).rstrip(":").strip()

    for c in list(tip_state):
        close_tip(c)
    return entries, tips


def parse_support(html):
    soup = BeautifulSoup(html, "lxml")
    url = None
    for a in soup.find_all("a", href=True):
        if "buymeacoffee" in a["href"]:
            url = a["href"]
            break
    m = re.search(r"Coffee counter:?\s*([0-9]+)", soup.get_text(" ", strip=True))
    return {"url": url or "https://buymeacoffee.com/freedesigntools",
            "count": int(m.group(1)) if m else None}


# ---------------------------------------------------------------- build
def previous_urls():
    """URLs from the previous build: local index.html, or the live site (PREV_URL env)."""
    import os
    html = None
    try:
        html = Path("index.html").read_text(encoding="utf-8")
    except Exception:
        pass
    if html is None and os.environ.get("PREV_URL"):
        try:
            req = urllib.request.Request(os.environ["PREV_URL"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                html = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  (no previous build reachable: {e})")
    if not html:
        return None
    m = re.search(r"window\.LIB=(\{.*?\});", html, re.S)
    if not m:
        return None
    try:
        prev = json.loads(m.group(1))
        return {it[4] for it in prev.get("items", []) if len(it) > 4 and it[4]}
    except Exception:
        return None


def build(src):
    prev = previous_urls()
    htmls = load_htmls(src)
    sections, sec_lookup, items, all_tips, seen = [], {}, [], [], set()

    for col_i, (fname, disp, code, color) in enumerate(COLLECTIONS):
        if fname not in htmls:
            print(f"  ! Tab not found in export: {fname!r} — skipped")
            continue
        entries, tips = parse_sheet(col_i, htmls[fname])
        all_tips.extend(tips)
        n0 = len(items)
        for sec, sub, name, url, note, pir in entries:
            key = (col_i, sec)
            if key not in sec_lookup:
                sec_lookup[key] = len(sections)
                sections.append({"c": col_i, "n": sec})
            name, pick = clean_name(name)
            if not name:
                continue
            if sub:
                sub = clean_text(FIRE.sub("", sub)).rstrip(":").strip()
                if len(sub) > 60 and "(" in sub:
                    sub = sub.split("(")[0].strip()
                if len(sub) > 60:
                    sub = sub[:60].rsplit(" ", 1)[0] + "…"
            dedupe = (col_i, name.lower(), url)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            note = clean_text(FIRE.sub("", note or ""))
            if len(note) > 140:
                note = note[:140].rsplit(" ", 1)[0] + "…"
            fl = flags_for(name, note)
            if fl:
                note = (fl + " " + note).strip()
            flags = (1 if pick else 0) | (2 if pir else 0)
            if prev is not None and url not in prev:
                flags |= 4                     # new since the previous build
            items.append([col_i, sec_lookup[key], sub or "", name, url, domain(url), flags, note])
        print(f"  {disp}: {len(items)-n0} links, {len(tips)} tips, "
              f"{sum(1 for s in sections if s['c']==col_i)} sections")

    # tidy URL-named leftovers: drop if the same link already has a proper name, else use its domain
    named = {(i[0], i[4]) for i in items if not re.match(r"https?://", i[3])}
    tidied = []
    for i in items:
        if re.match(r"https?://", i[3]):
            if (i[0], i[4]) in named:
                continue
            i[3] = i[5] or i[3]
        tidied.append(i)
    items = tidied

    # drop sections that ended up empty and remap indices
    used = {i[1] for i in items}
    remap, kept = {}, []
    for si, s in enumerate(sections):
        if si in used:
            remap[si] = len(kept)
            kept.append(s)
    sections = kept
    for i in items:
        i[1] = remap[i[1]]

    support = parse_support(htmls["MENU"]) if "MENU" in htmls else {"url": "https://buymeacoffee.com/freedesigntools", "count": None}

    out = {
        "collections": [{"name": n, "code": c, "color": col} for _, n, c, col in COLLECTIONS],
        "sections": sections,
        "items": items,
        "tips": [{"c": t["c"], "t": t["t"], "b": t["body"], "l": t["links"]} for t in all_tips],
        "support": support,
    }
    data_js = "window.LIB=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    data_js = re.sub(r"</(script)", r"<\\/\1", data_js, flags=re.I)

    shell = Path("shell.html").read_text(encoding="utf-8")
    Path("index.html").write_text(shell.replace("__DATA__", data_js), encoding="utf-8")
    print(f"Built index.html — {len(items)} resources, {len(sections)} sections, "
          f"{sum(i[6] & 1 for i in items)} staff picks, {sum(1 for i in items if i[6] & 2)} pirate-flagged, "
          f"{sum(1 for i in items if i[6] & 4)} new since last build, {len(all_tips)} tips")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else download()
    build(src)
