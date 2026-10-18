"""Actual home prices (price per m², or per dwelling where that is all a country publishes),
from national statistics offices, central banks and land registries.

Step 1 (this version): probe each source and log what it returns, so the parsers can be written
against real responses. The container that writes this code cannot reach these hosts.
"""
import json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UA = {"User-Agent": "Mozilla/5.0 (compatible; FINILA data refresh; +https://www.finila.com)"}

PROBES = {
    "SK NBS": "https://nbs.sk/export/sk/real-estate-price-by-region/csv",
    "FR DVF stats (resource)": "https://www.data.gouv.fr/api/1/datasets/r/851d342f-9c96-41c1-924a-11a7a7aae8a6",
    "FR DVF dataset": "https://www.data.gouv.fr/api/1/datasets/statistiques-dvf/",
    "UK HPI average 2026-08": "https://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/Average-prices-2026-08.csv",
    "UK HPI average 2026-07": "https://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/Average-prices-2026-07.csv",
    "NL CBS 83625ENG": "https://opendata.cbs.nl/ODataApi/odata/83625ENG/TypedDataSet?$top=5",
    "NL CBS 83625ENG regions": "https://opendata.cbs.nl/ODataApi/odata/83625ENG/RegionS?$top=20",
    "FI ashi tables": "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/ashi/",
    "FI 13mu meta": "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/ashi/statfin_ashi_pxt_13mu.px",
    "PT INE 0012248": "https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0012248&lang=EN",
    "PT INE 0009490": "https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0009490&lang=EN",
    "LU dataset": "https://data.public.lu/api/1/datasets/57f26768cc765e23279433b0/",
    "ES datos.gob.es": "https://datos.gob.es/apidata/catalog/dataset/e05233601-valor-tasado-de-la-vivienda.json",
    "IE CSO catalogue HPM": "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadCollection",
    "PL GUS BDL search": "https://bdl.stat.gov.pl/api/v1/variables/search?name=mieszka%C5%84%20za%201%20m2&format=json&page-size=50",
    "HU KSH lak0025": "https://www.ksh.hu/stadat_files/lak/en/lak0025.csv",
    "HU KSH stadat list": "https://www.ksh.hu/stadat_eng?lang=en&theme=lak",
    "SE SCB BO0501": "https://api.scb.se/OV0104/v1/doris/en/ssd/BO/BO0501/",
    "HR DZS": "https://podaci.dzs.hr/en/statistics/prices/",
    "BG NSI": "https://www.nsi.bg/en/content/2903/average-market-prices-dwellings",
    "DK EJEN77": "https://api.statbank.dk/v1/tableinfo/EJEN77?format=JSON",
    "AT OGD": "https://data.statistik.gv.at/web/catalog.jsp",
    "CZ CSU": "https://csu.gov.cz/ceny-sledovanych-druhu-nemovitosti",
    "BE Statbel": "https://statbel.fgov.be/en/open-data?category=All&search=real%20estate",
}


def probe(name, url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read(400_000)
            ctype = r.headers.get("Content-Type", "")
        try:
            text = body.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = body.decode("cp1250", "replace")
        print(f"\n===== {name} OK {ctype} {len(body)} bytes\n{text[:2500]}")
    except Exception as e:  # noqa: BLE001
        print(f"\n===== {name} FAIL {e}")


if __name__ == "__main__":
    only = sys.argv[1:]
    for n, u in PROBES.items():
        if not only or any(o in n for o in only):
            probe(n, u)
