"""Find national home-price-per-m² tables (run in GitHub Actions: the editor can't reach these hosts)."""
import json, re, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from housing_levels import fetch


def show(title, fn):
    print(f"\n===== {title}")
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {type(e).__name__}: {e}")


def links(url, pat):
    t = fetch(url).decode("utf-8", "replace")
    found = sorted(set(m for m in re.findall(r'href="([^"#]+)"', t) if re.search(pat, m, re.I)))
    print(f"{url}: {len(t)} bytes, {len(found)} links")
    for m in found[:80]:
        print("  ", m)


def ssb():
    d = json.loads(fetch("https://data.ssb.no/api/v0/en/table/06035"))
    for v in d["variables"]:
        print(v["code"], v["text"], list(zip(v["values"], v["valueTexts"]))[:12], len(v["values"]))


def dk():
    d = json.loads(fetch("https://api.statbank.dk/v1/tables?lang=en&format=JSON"))
    for t in d:
        if re.search(r"square|sqm|per m2|price.*(dwelling|flat|house|property|real)|(flat|dwelling|property).*price", t["text"], re.I):
            print(t["id"], t["text"], t["unit"], t["latestPeriod"], t["variables"])


def pxsearch(base, q):
    d = json.loads(fetch(f"{base}?query={q}"))
    for t in d[:40]:
        print(t.get("id"), t.get("path"), t.get("title"), t.get("published"))


def pxtree(base, depth=0, path=""):
    d = json.loads(fetch(base + path))
    for t in d:
        txt = t.get("text", "")
        if t.get("type") == "l" and depth < 2 and re.search(r"price|dwell|real|hous|construct|stanovanj|kinnis|cen|nekust", txt + t["id"], re.I):
            print("  " * depth + f"[{t['id']}] {txt}")
            pxtree(base, depth + 1, f"{path}/{t['id']}")
        elif t.get("type") == "t" and re.search(r"m2|m²|square|price per|per sq", txt, re.I):
            print("  " * depth + f"TABLE {path}/{t['id']} {txt}")


show("SK NBS export links", lambda: links("https://nbs.sk/statisticke-udaje/vybrane-makroekonomicke-ukazovatele/ceny-nehnutelnosti-na-byvanie/", r"export|\.csv|\.xls"))
show("HU KSH lak tables", lambda: links("https://www.ksh.hu/stadat_eng?lang=en&theme=lak", r"lak0"))
show("NO SSB 06035", ssb)
show("DK statbank price tables", dk)
show("SI SiStat search", lambda: pxsearch("https://pxweb.stat.si/SiStatData/api/v1/en/Data", "flats"))
show("SI SiStat tree", lambda: pxtree("https://pxweb.stat.si/SiStatData/api/v1/en/Data"))
show("EE stat tree", lambda: pxtree("https://andmed.stat.ee/api/v1/en/stat"))
show("LV stat tree", lambda: pxtree("https://data.stat.gov.lv/api/v1/en/OSP_PUB"))
show("LT", lambda: links("https://osp.stat.gov.lt/statistiniu-rodikliu-analize?hash=", r"kain|price|bust"))
show("BG NSI", lambda: links("https://www.nsi.bg/en/content/2924/average-market-prices-dwellings", r"xls|csv|file|download|dwell|price"))
show("BG NSI 2", lambda: links("https://www.nsi.bg/en/statistical-data/245", r"xls|csv|file|download|dwell|price"))
show("HR DZS", lambda: links("https://podaci.dzs.hr/en/statistics/construction/", r"xls|csv|stan|dwell|price|cijen"))
show("HR DZS prices", lambda: links("https://podaci.dzs.hr/en/statistics/prices/", r"xls|csv|stan|dwell|price|cijen"))
show("CZ CZSO", lambda: links("https://csu.gov.cz/ceny-bytu-a-nemovitosti", r"xls|csv|byt|cen"))
show("CZ CZSO 2", lambda: links("https://csu.gov.cz/residential-property-prices", r"xls|csv|byt|cen|price"))
show("AT Statistik", lambda: links("https://www.statistik.at/statistiken/volkswirtschaft-und-oeffentliche-finanzen/preise-und-preisindizes/immobilien-durchschnittspreise", r"xls|csv|ods|ogd|download"))
show("AT data.gv.at", lambda: print(fetch("https://www.data.gv.at/api/3/action/package_search?q=Immobilien%20Durchschnittspreise")[:3000].decode("utf-8","replace")))
show("BE Statbel", lambda: links("https://statbel.fgov.be/en/themes/housing/real-estate-prices", r"xls|csv|zip|download|open"))
show("IE CSO RPPI", lambda: print(fetch("https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadMetadata/HPM04/JSON-stat/2.0/en")[:2000].decode("utf-8","replace")))
show("NL CBS", lambda: print(fetch("https://opendata.cbs.nl/ODataApi/odata/83625NED/DataProperties")[:3000].decode("utf-8","replace")))
show("SE SCB", lambda: pxtree("https://api.scb.se/OV0104/v1/doris/en/ssd/BO"))
show("DE AK OGA", lambda: links("https://www.immobilienmarktbericht-deutschland.info/", r"pdf|xls|download"))
show("IT OMI", lambda: links("https://www.agenziaentrate.gov.it/portale/web/guest/schede/fabbricatiterreni/omi/banche-dati/quotazioni-immobiliari", r"xls|csv|zip|download|statist"))
show("GR BoG", lambda: links("https://www.bankofgreece.gr/en/statistics/real-estate-market", r"xls|csv|download"))
show("RO INS", lambda: links("https://insse.ro/cms/en/tags/house-price-index", r"xls|csv|pdf"))
