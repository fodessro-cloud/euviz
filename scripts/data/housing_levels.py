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
    "FI ashi tables": "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/ashi/",
    "FI 13mt meta": "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/ashi/statfin_ashi_pxt_13mt.px",
    "LU dataset": "https://data.public.lu/api/1/datasets/57f26768cc765e23279433b0/",
    "FR DVF dataset": "https://www.data.gouv.fr/api/1/datasets/statistiques-dvf/",
    "DK EJEN77": "https://api.statbank.dk/v1/tableinfo/EJEN77?format=JSON",
    "ES MIVAU VDP006_01": "https://cdn.mivau.gob.es/portal-web-mivau/Datos_MIVAU/CSV/VDP006_01.csv",
    "SE SCB BO0501C": "https://api.scb.se/OV0104/v1/doris/en/ssd/BO/BO0501/BO0501C/",
    "SE SCB BO0501B": "https://api.scb.se/OV0104/v1/doris/en/ssd/BO/BO0501/BO0501B/",
    "PL GUS BDL search m2": "https://bdl.stat.gov.pl/api/v1/variables/search?name=1%20m2&format=json&page-size=100&lang=en",
    "PL GUS BDL subjects": "https://bdl.stat.gov.pl/api/v1/subjects/search?name=price&format=json&lang=en",
    "IE CSO catalogue HPM": "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadCollection",
    "CZ CSU": "https://csu.gov.cz/ceny-sledovanych-druhu-nemovitosti",
    "ECB HUF": "https://data-api.ecb.europa.eu/service/data/EXR/Q.HUF+PLN+SEK+DKK+CZK+GBP+CHF+NOK+RON+ISK.EUR.SP00.A?format=csvdata&startPeriod=2024-Q1",
}


def summary(name, text):
    """What the parser needs to know about each response, short enough to read."""
    try:
        if name.startswith("FI") and "tables" in name:
            return "\n".join(f"{x['id']} {x['text']}" for x in json.loads(text))
        if name.startswith(("FI", "DK", "SE")):
            d = json.loads(text)
            if isinstance(d, list):
                return "\n".join(f"{x.get('id')} {x.get('text')}" for x in d)
            return json.dumps({k: d[k] for k in d if k != "variables"})[:600] + "\n" + "\n".join(
                f"{v.get('code') or v.get('id')} {v.get('text')}: {[str(x)[:60] for x in (v.get('valueTexts') or [y.get('text') for y in v.get('values', [])])][:25]} ({len(v.get('valueTexts') or v.get('values', []))})"
                for v in d.get("variables", []))
        if name.startswith(("LU", "FR")):
            d = json.loads(text)
            return f"{d.get('title')} | license {d.get('license')}\n" + "\n".join(
                f"{r.get('title')} | {r.get('format')} | {r.get('filesize')} | {r.get('url')}" for r in d.get("resources", []))
        if name.startswith("IE"):
            d = json.loads(text)
            out = []
            for item in (d.get("link", {}).get("item", []) if isinstance(d, dict) else d):
                lab = item.get("label", "")
                if any(w in lab.lower() for w in ("price", "house", "dwelling", "property")):
                    out.append(f"{item.get('extension', {}).get('matrix')} {lab}")
            return "\n".join(out[:80])
        if name.startswith("PL"):
            d = json.loads(text)
            return "\n".join(json.dumps(r, ensure_ascii=False)[:300] for r in d.get("results", [])[:60])
    except Exception as e:  # noqa: BLE001
        return f"(summary failed: {e})\n{text[:2500]}"
    return text[:4000]


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
        print(f"\n===== {name} OK {ctype} {len(body)} bytes\n{summary(name, text)}")
    except Exception as e:  # noqa: BLE001
        print(f"\n===== {name} FAIL {e}")


if __name__ == "__main__":
    only = sys.argv[1:]
    for n, u in PROBES.items():
        if not only or any(o in n for o in only):
            probe(n, u)
