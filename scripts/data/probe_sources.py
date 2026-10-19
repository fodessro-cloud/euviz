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


def pt_regions():
    d = json.loads(fetch("https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0012248&lang=EN"))[0]
    rows = d["Dados"][d["UltimoPref"]]
    print(d["UltimoPref"], len(rows), "keys", list(rows[0]))
    seen = set()
    for r in rows:
        if r.get("dim_3_t", "").lower() == "flats" and len(r.get("geocod", "")) <= 3 and r["geocod"] not in seen:
            seen.add(r["geocod"])
            print(r.get("geocod"), r.get("geodsg"), r.get("valor"))


def sk_exports():
    for name in ("real-estate-price-by-region", "real-estate-price-by-type", "real-estate-price"):
        try:
            t = fetch(f"https://nbs.sk/export/sk/{name}/csv").decode("utf-8", "replace")
            print(name, len(t)); print(t[:900])
        except Exception as e:  # noqa: BLE001
            print(name, "FAIL", e)


def es_notaries():
    base = "https://www.penotariado.com"
    page = fetch(base + "/inmobiliario/buscador-precio-vivienda").decode("utf-8", "replace")
    scripts = re.findall(r'src="([^"]+\.js[^"]*)"', page)
    print("scripts", scripts[:20])
    for sc in scripts[:12]:
        try:
            js = fetch(sc if sc.startswith("http") else base + sc).decode("utf-8", "replace")
            hits = sorted(set(re.findall(r'["\'`](/?(?:api|inmobiliario/api|ws|rest)[^"\'`\s]{2,120})["\'`]', js)))
            hits += sorted(set(re.findall(r'https?://[a-z0-9.-]*(?:notari|penotari)[a-z0-9./_-]*', js)))
            print(sc, len(js), hits[:40])
        except Exception as e:  # noqa: BLE001
            print(sc, "FAIL", e)


def bond_yields():
    ecb = "https://data-api.ecb.europa.eu/service/"
    for key in ("YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y+SR_5Y+SR_10Y", "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y+SR_5Y+SR_10Y"):
        try:
            t = fetch(f"{ecb}data/{key}?format=csvdata&lastNObservations=2").decode()
            print(key, "OK"); print("\n".join(l[:200] for l in t.splitlines()[:5]))
        except Exception as e:  # noqa: BLE001
            print(key, "FAIL", e)
    x = fetch(ecb + "dataflow/ECB").decode("utf-8", "replace")
    for fid, name in re.findall(r'<str:Dataflow[^>]*id="([^"]+)".*?<com:Name[^>]*>([^<]+)</com:Name>', x, re.S):
        if re.search(r"bond|yield|debt|securit|corporate|spread|cost of", name, re.I):
            print("FLOW", fid, name)
    for sid in ("BAMLHE00EHYIEY", "BAMLHE00EHYIOAS"):
        try:
            t = fetch(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}").decode()
            print("FRED", sid, t.splitlines()[:2], t.splitlines()[-2:])
        except Exception as e:  # noqa: BLE001
            print("FRED", sid, "FAIL", e)


def bundesbank_corporate():
    base = "https://api.statistiken.bundesbank.de/rest/data/BBSIS/"
    for key in ("M.I.UMR.RD.EUR..B...R.A._Z._Z.A", "D.I.UMR.RD.EUR..B...R.A._Z._Z.A", "M.I.UMR..EUR....."):
        try:
            t = fetch(f"{base}{key}?format=csv&lang=en&lastNObservations=1").decode("utf-8", "replace")
            lines = t.splitlines()
            print(key, "OK", len(lines), "lines"); print(lines[0][:300])
            for l in lines[1:80]:
                print("  ", l[:260])
        except Exception as e:  # noqa: BLE001
            print(key, "FAIL", e)


show("Bundesbank corporate bond yields", bundesbank_corporate)
