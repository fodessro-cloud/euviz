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


show("AT Sonderauswertung", lambda: ods("https://www.statistik.at/fileadmin/pages/222/SonderauswertungImmobilienDurchschnittspreise.ods", 80))
show("AT Wohnungspreise2025 headers", lambda: ods_text("https://www.statistik.at/fileadmin/pages/222/Wohnungspreise2025.ods"))
for n in ("224078", "224079", "224081", "202358", "178009"):
    show(f"DE AKOGA {n}", lambda n=n: sniff(f"https://redaktion-akoga.niedersachsen.de/download/{n}"))
show("DK boligmarkedsstatistik", lambda: grep("https://finansdanmark.dk/tal-og-data/boligstatistik/boligmarkedsstatistikken/", r'href="([^"]*(?:xls|csv|media|download)[^"]*)"'))
show("HR new dwellings any file", lambda: grep("https://podaci.dzs.hr/en/statistics/construction/prices-of-sold-new-dwellings/", r"[^\"'\s<>]+\.(?:xlsx?|csv|px|pdf)"))
show("HU KSH lak0025 neighbours", lambda: [print(t, fetch(f"https://www.ksh.hu/stadat_files/lak/en/{t}.csv")[:600].decode("utf-8-sig", "replace")) for t in ("lak0024", "lak0026", "lak0027", "lak0028")])
