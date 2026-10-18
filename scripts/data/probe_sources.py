"""Find national home-price-per-m² tables (run in GitHub Actions: the editor can't reach these hosts)."""
import io, json, re, sys, zipfile
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from housing_levels import fetch


def show(title, fn):
    print(f"\n===== {title}")
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {type(e).__name__}: {e}")


def grep(url, pat, n=60):
    t = fetch(url).decode("utf-8", "replace")
    found = sorted(set(re.findall(pat, t, re.I)))
    print(f"{url}: {len(t)} bytes, {len(found)} matches")
    for m in found[:n]:
        print("  ", m[:300] if isinstance(m, str) else m)


def ods(url, rows=40):
    z = zipfile.ZipFile(io.BytesIO(fetch(url)))
    x = z.read("content.xml").decode("utf-8")
    for tab in re.findall(r'<table:table [^>]*table:name="([^"]+)"', x):
        print("sheet", tab)
    out = []
    for row in re.findall(r"<table:table-row[^>]*>(.*?)</table:table-row>", x, re.S)[:rows]:
        cells = [re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<table:table-cell[^>]*>(.*?)</table:table-cell>", row, re.S)]
        cells = [c for c in cells if c.strip()]
        if cells:
            out.append(" | ".join(c[:25] for c in cells))
    print("\n".join(out))


def px_meta(url):
    d = json.loads(fetch(url))
    print(d.get("title"))
    for v in d["variables"]:
        print(" ", v["code"], v["text"], list(zip(v["values"], v["valueTexts"]))[:15], len(v["values"]))




def sniff(url):
    b = fetch(url)
    kind = "xlsx/zip" if b[:2] == b"PK" else "xls" if b[:4] == b"\xd0\xcf\x11\xe0" else "pdf" if b[:4] == b"%PDF" else "other"
    print(url, kind, len(b))
    if kind == "xlsx/zip":
        z = zipfile.ZipFile(io.BytesIO(b))
        names = z.namelist()
        if "content.xml" in names:
            return ods(url, 30)
        from housing_levels import sheets
        for name, rows in sheets(b).items():
            print("--- sheet", name, len(rows))
            for r in rows[:25]:
                print(" | ".join(str(c)[:22] for c in r if c not in (None, "")))
    elif kind == "other":
        print(b[:400])


def ods_text(url, n=12):
    """First header lines of each sheet, untruncated."""
    z = zipfile.ZipFile(io.BytesIO(fetch(url)))
    x = z.read("content.xml").decode("utf-8")
    for tab in re.findall(r'<table:table [^>]*table:name="([^"]+)".*?</table:table>', x, re.S)[:2]:
        print("sheet", tab)
    for row in re.findall(r"<table:table-row[^>]*>(.*?)</table:table-row>", x, re.S)[:n]:
        print("  ", " | ".join(t for t in (re.sub(r"<[^>]+>", " ", c).strip() for c in re.findall(r"<table:table-cell[^>]*>(.*?)</table:table-cell>", row, re.S)) if t))


def ods_sheet(url, name, n=60):
    z = zipfile.ZipFile(io.BytesIO(fetch(url)))
    x = z.read("content.xml").decode("utf-8")
    m = re.search(r'<table:table [^>]*table:name="%s".*?</table:table>' % re.escape(name), x, re.S)
    for row in re.findall(r"<table:table-row[^>]*>(.*?)</table:table-row>", m.group(0), re.S)[:n]:
        cells = [re.sub(r"<[^>]+>", " ", c).strip() for c in re.findall(r"<table:table-cell[^>]*>(.*?)</table:table-cell>", row, re.S)]
        if any(cells):
            print("  ", " | ".join(cells))


def zlist(url):
    z = zipfile.ZipFile(io.BytesIO(fetch(url)))
    for i in z.infolist()[:80]:
        print("  ", i.filename, i.file_size)


def ksh(t, pat):
    raw = fetch(f"https://www.ksh.hu/stadat_files/lak/en/{t}.csv").decode("utf-8-sig", "replace")
    lines = raw.splitlines()
    print(lines[0]); print(lines[1])
    for l in lines[2:]:
        if re.search(pat, l):
            print("  ", l)


def xlsx_sheet(url, names, n=45):
    from housing_levels import sheets
    for name, rows in sheets(fetch(url)).items():
        if name in names:
            print("--- sheet", name)
            for r in rows[:n]:
                print(" | ".join(str(c)[:30] for c in r if c not in (None, "")))


def ecb_resr():
    """ECB residential property statistics: list every series whose unit is a price level (EUR per m2), not an index."""
    import csv as _csv
    t = fetch("https://data-api.ecb.europa.eu/service/data/RESR?lastNObservations=1&format=csvdata&detail=dataonly").decode("utf-8", "replace")
    rows = list(_csv.DictReader(io.StringIO(t)))
    print(len(rows), "series; columns:", list(rows[0].keys()) if rows else None)
    keys = sorted({r["KEY"] for r in rows})
    for k in keys[:400]:
        r = next(x for x in rows if x["KEY"] == k)
        print(k, r.get("TIME_PERIOD"), r.get("OBS_VALUE"))


def ecb_titles():
    t = fetch("https://data-api.ecb.europa.eu/service/data/RESR?lastNObservations=1&format=csvdata").decode("utf-8", "replace")
    import csv as _csv
    for r in _csv.DictReader(io.StringIO(t)):
        title = r.get("TITLE") or r.get("TITLE_COMPL") or ""
        if re.search(r"m2|square|sq\.? ?m|per m|EUR", title + r.get("UNIT", "") + r.get("UNIT_MEASURE", ""), re.I) and not re.search(r"index", title, re.I):
            print(r["KEY"], r.get("TIME_PERIOD"), r.get("OBS_VALUE"), "|", title[:160], "|", r.get("UNIT", ""), r.get("UNIT_MEASURE", ""))


def ecb_units():
    import csv as _csv, collections
    t = fetch("https://data-api.ecb.europa.eu/service/data/RESR?lastNObservations=1&format=csvdata&detail=dataonly").decode("utf-8", "replace")
    rows = list(_csv.DictReader(io.StringIO(t)))
    print(collections.Counter(r["UNIT_MEASURE"] for r in rows))
    print(collections.Counter(r["INDICATOR"] for r in rows))
    for r in rows:
        if r["UNIT_MEASURE"] not in ("IX",) and r["KEY"].split(".")[-1] != "IX":
            print(r["KEY"], r["TIME_PERIOD"], r["OBS_VALUE"])


def ssb_regions():
    for t in ("06035",):
        d = json.loads(fetch(f"https://data.ssb.no/api/v0/no/table/{t}"))
        print(t, d.get("title"))
        for v in d["variables"]:
            print(" ", v["code"], v["text"], len(v["values"]))
            if v["code"] in ("Region", "Boligtype"):
                print("   ", list(zip(v["values"], v["valueTexts"])))
    hits = json.loads(fetch("https://data.ssb.no/api/v0/no/table/?query=kvadratmeterpris&filter=*"))
    for h in hits[:40]:
        print(h.get("id"), h.get("title"))


def fi_tables():
    base = "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/ashi/"
    for t in json.loads(fetch(base)):
        print(t.get("id"), "|", t.get("text"))
        if not t.get("id", "").endswith(".px"):
            continue
        try:
            m = json.loads(fetch(base + t["id"]))
            for v in m["variables"]:
                print("    ", v["code"], v["text"], len(v["values"]), v["valueTexts"][:25])
        except Exception as e:  # noqa: BLE001
            print("    FAIL", e)


show("Statistics Finland flat price tables by region", fi_tables)
