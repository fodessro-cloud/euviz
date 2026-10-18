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


def ee_list(path):
    for t in json.loads(fetch("https://andmed.stat.ee/api/v1/en/stat/" + path)):
        print("  ", t["id"], t.get("type"), t.get("text"))


show("EE prices", lambda: ee_list("majandus/hinnad"))
show("EE construction", lambda: ee_list("majandus/ehitus"))
show("CZ Tab1", lambda: sniff("https://csu.gov.cz/docs/107823/0dc51dfa-22cd-d7b7-1dbb-29198fc9cf6a/Tab1_ceny_nemovitosti_kraje_okresy_2023_2025.xlsx?version=1.0"))
show("DK rkr", lambda: print(fetch("https://api.statbank.dk/v1/tableinfo/BM010?lang=en&format=JSON")[:1500].decode()))
