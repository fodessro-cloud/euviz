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


HREF = r'(?:href|src|data-[a-z-]+)="([^"]+)"'
show("SK NBS export strings", lambda: grep("https://nbs.sk/statisticke-udaje/vybrane-makroekonomicke-ukazovatele/ceny-nehnutelnosti-na-byvanie/", r"(?:export/[^\"'\s<]+|[^\"'\s<]+\.(?:csv|xlsx?))"))
for kind in ("real-estate-price-by-type", "real-estate-price-by-flat-type", "real-estate-price-flats", "real-estate-price"):
    show(f"SK NBS {kind}", lambda k=kind: print(fetch(f"https://nbs.sk/export/sk/{k}/csv")[:1500].decode("utf-8-sig", "replace")))
show("HU KSH lak strings", lambda: grep("https://www.ksh.hu/stadat_eng?lang=en&theme=lak", r"[^\"'\s<>]*lak0\d+[^\"'\s<>]*"))
show("NO SSB 06035 query", lambda: print(fetch("https://data.ssb.no/api/v0/en/table/06035", data=json.dumps({"query": [
    {"code": "Region", "selection": {"filter": "item", "values": ["0", "0301", "4601", "5001", "1103"]}},
    {"code": "Boligtype", "selection": {"filter": "item", "values": ["03"]}},
    {"code": "ContentsCode", "selection": {"filter": "item", "values": ["KvPris"]}},
    {"code": "Tid", "selection": {"filter": "top", "values": ["2"]}}], "response": {"format": "csv"}}).encode())[:1500].decode("utf-8", "replace")))
show("AT Wohnungspreise2025", lambda: ods("https://www.statistik.at/fileadmin/pages/222/Wohnungspreise2025.ods", 60))
show("SI 0419030S", lambda: px_meta("https://pxweb.stat.si/SiStatData/api/v1/en/Data/0419030S.px"))
show("HR new dwellings page", lambda: grep("https://podaci.dzs.hr/en/statistics/construction/prices-of-sold-new-dwellings/", r'href="([^"]+\.(?:xlsx?|csv|pdf|px)[^"]*)"'))
show("HR house price page", lambda: grep("https://podaci.dzs.hr/en/statistics/prices/house-price-indices/", r'href="([^"]+\.(?:xlsx?|csv|pdf|px)[^"]*)"'))
show("DE AKOGA data", lambda: grep("https://redaktion-akoga.niedersachsen.de/startseite/download/daten_der_immobilienmarktberichte/download-daten-des-immobilienmarktberichtes-201850.html", r'href="([^"]+)"'))
show("CZ CZSO search", lambda: grep("https://csu.gov.cz/vyhledavani?q=ceny%20byt%C5%AF", r'href="([^"]*(?:cen|byt)[^"]*)"'))
show("CZ CZSO EN", lambda: grep("https://csu.gov.cz/prices-of-dwellings", r'href="([^"]+)"', 40))
show("EE Maa-amet", lambda: grep("https://www.maaamet.ee/kinnisvara/htraru/FilterUI.aspx", r'(?:href|value)="([^"]+)"', 40))
show("ES notaries", lambda: grep("https://www.notariado.org/portal/estad%C3%ADsticas", r'href="([^"]*(?:estad|precio|vivienda|xls|csv)[^"]*)"', 40))
show("DK Finans Danmark", lambda: grep("https://finansdanmark.dk/tal-og-data/boligstatistik/", r'href="([^"]*(?:xls|csv|bolig|statistik)[^"]*)"', 40))
show("BG infostat", lambda: grep("https://infostat.nsi.bg/infostat/pages/module.jsf?x_2=223", r'(?:href|title)="([^"]*(?:price|dwell|цени|жилищ)[^"]*)"', 40))
