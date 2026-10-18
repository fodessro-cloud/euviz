"""Actual home prices in euros: price per m² by country and by region or city, from national
statistics offices, central banks and land registries (all free to reuse with attribution).

Only official figures. Countries publish sale prices, bank appraisals or (Slovakia) asking prices
in listings; the page says which. Writes js/housing-levels.json:
{updated, failed, countries: {code: {name, eur, unit, basis, period, source, url, regions: [...]}}}
"""
import csv, io, json, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "js" / "housing-levels.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FINILA data refresh; +https://www.finila.com)"}


def fetch(url, data=None, limit=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **({"Content-Type": "application/json"} if data else {})})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read(limit) if limit else r.read()


def text(url, data=None, enc="utf-8-sig"):
    return fetch(url, data).decode(enc)


def num(s):
    """'3 041,4123' / '1 194' / '2.736' -> float, or None."""
    s = str(s or "").replace("\xa0", "").replace(" ", "").strip()
    if not s or not re.search(r"\d", s):
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


RATES = {}


def eur_rate(cur, year):
    """Units of `cur` per euro, ECB reference rate averaged over `year` (or the latest year)."""
    if cur == "EUR":
        return 1.0
    if cur not in RATES:
        rows = csv.DictReader(io.StringIO(text(
            f"https://data-api.ecb.europa.eu/service/data/EXR/A.{cur}.EUR.SP00.A?format=csvdata&startPeriod=2015")))
        RATES[cur] = {r["TIME_PERIOD"]: float(r["OBS_VALUE"]) for r in rows if r.get("OBS_VALUE")}
    r = RATES[cur]
    return r.get(str(year)) or r[max(r)]


def region(name, value, note=None):
    return {"name": name, "eur": round(value), **({"note": note} if note else {})}


# ── Countries ─────────────────────────────────────────────

def slovakia():
    rows = list(csv.reader(io.StringIO(text("https://nbs.sk/export/sk/real-estate-price-by-region/csv")), delimiter=";"))
    head = next(r for r in rows if r and r[0].startswith("Rok"))
    latest = next(r for r in rows if r and re.match(r"\dQ \d{4}", r[0]))
    names = {"SR spolu": None, "BA": "Bratislava region", "TT": "Trnava region", "NR": "Nitra region",
             "TN": "Trenčín region", "ZA": "Žilina region", "BB": "Banská Bystrica region",
             "KE": "Košice region", "PO": "Prešov region"}
    vals = dict(zip(head, latest))
    q, y = latest[0].split()
    # NBS builds these from listings on property portals: asking prices, above what buyers finally pay.
    return {"eur": round(num(vals["SR spolu"])), "unit": "m2", "basis": "asking", "period": f"{y}-Q{q[0]}",
            "type": "mixed", "what": "flats and houses, asking prices in listings",
            "source": "Národná banka Slovenska", "url": "https://nbs.sk/statisticke-udaje/vybrane-makroekonomicke-ukazovatele/ceny-nehnutelnosti-na-byvanie/",
            "regions": sorted([region(names[k], num(vals[k])) for k in head[2:] if k in names], key=lambda r: -r["eur"])}


def france():
    # Whole DVF period (last five years of notarised sales): median €/m², flats and houses together.
    url = "https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/stats_whole_period.csv"
    rows = csv.DictReader(io.StringIO(text(url)))
    nation, deps, cities = None, [], []
    levels = {}
    for r in rows:
        lvl = r.get("echelle_geo")
        levels[lvl] = levels.get(lvl, 0) + 1
        v = num(r.get("med_prix_m2_whole_appartement"))
        n = num(r.get("nb_ventes_whole_appartement")) or 0
        if not v:
            continue
        if lvl == "nation":
            nation = v
        elif lvl == "departement":
            deps.append((r["libelle_geo"], v, n))
        elif lvl == "commune":
            # Paris, Marseille and Lyon come as arrondissements: fold them into the city.
            name = re.sub(r" \d+(er|e) Arrondissement$", "", r["libelle_geo"])
            cities.append((name, v, n))
    print(f"  FR levels: {levels}")
    if not nation:  # no national row: sales-weighted median of departments is close enough
        tot = sum(n for *_, n in deps)
        nation = sum(v * n for _, v, n in deps) / tot
    by_city = {}
    for name, v, n in cities:
        by_city.setdefault(name, []).append((v, n))
    cities = []
    for name, parts in by_city.items():
        n = sum(x for _, x in parts)
        if n >= 3000:  # sales-weighted across arrondissements
            cities.append((name, sum(v * x for v, x in parts) / n, n))
    cities.sort(key=lambda c: -c[2])
    return {"eur": round(nation), "unit": "m2", "basis": "sale", "period": "last 5 years",
            "type": "flats", "what": "flats, median sale price",
            "source": "DVF, Etalab (Licence Ouverte)", "url": "https://www.data.gouv.fr/datasets/statistiques-dvf/",
            "regions": sorted([region(n, v) for n, v, _ in cities[:20]], key=lambda r: -r["eur"])}


def pxweb(base, table, query):
    d = json.loads(text(f"{base}{table}", data=json.dumps({"query": query, "response": {"format": "json-stat2"}}).encode()))
    dims = d["id"]
    cats = {k: list(d["dimension"][k]["category"]["index"]) for k in dims}
    labels = {k: d["dimension"][k]["category"].get("label", {}) for k in dims}
    out, sizes = [], d["size"]
    for i, v in enumerate(d["value"]):
        idx, rem = {}, i
        for k, n in zip(reversed(dims), reversed(sizes)):
            idx[k] = cats[k][rem % n]
            rem //= n
        out.append(({k: labels[k].get(c, c) for k, c in idx.items()}, {k: c for k, c in idx.items()}, v))
    return out


def finland():
    base = "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/ashi/"
    meta = json.loads(text(f"{base}13mx.px"))
    print("  FI 13mx variables: " + "; ".join(f"{v['code']} {v['text']} {v['valueTexts'][:6]} ({len(v['values'])})" for v in meta["variables"]))
    var = {v["code"]: v for v in meta["variables"]}
    year = next(v for v in meta["variables"] if v.get("time") or "time" in v["code"].lower() or v["text"] == "Year")
    price = next(v for v in meta["variables"] if v["code"].lower() in ("tiedot", "information", "contentscode"))
    area_var = next(v for v in meta["variables"] if v["code"].lower().startswith(("kunta", "alue")))
    print(f"  FI areas start: {area_var['valueTexts'][:3]}, has whole country: {any('whole country' in t.lower() for t in area_var['valueTexts'])}")
    pcode = next(c for c, t in zip(price["values"], price["valueTexts"]) if "per square" in t.lower() or "€/m" in t)
    q = [{"code": year["code"], "selection": {"filter": "item", "values": [year["values"][-1]]}},
         {"code": price["code"], "selection": {"filter": "item", "values": [pcode]}}]
    for code, v in var.items():  # every other dimension: its total ("all", "total")
        if code in (year["code"], price["code"], area_var["code"]):
            continue
        tot = next((c for c, t in zip(v["values"], v["valueTexts"]) if re.search(r"blocks of flats", t, re.I)), None) \
            or next((c for c, t in zip(v["values"], v["valueTexts"]) if re.search(r"total|all|yhteensä", t, re.I)), v["values"][0])
        q.append({"code": code, "selection": {"filter": "item", "values": [tot]}})
    rows = [(lab, val) for lab, _, val in pxweb(base, "13mx.px", q) if val]
    area = area_var["code"]
    # The municipality table has no national row: take it from the quarterly whole-country table.
    nmeta = json.loads(text(f"{base}13mv.px"))
    print("  FI 13mv variables: " + "; ".join(f"{v['code']} {v['valueTexts'][:4]} ({len(v['values'])})" for v in nmeta["variables"]))
    nq = []
    for v in nmeta["variables"]:
        if v.get("time") or "time" in v["code"].lower():
            nq.append({"code": v["code"], "selection": {"filter": "item", "values": [v["values"][-1]]}})
            quarter = v["valueTexts"][-1]
        elif v["code"].lower() == "contentscode":
            nq.append({"code": v["code"], "selection": {"filter": "item", "values": [next(c for c, t in zip(v["values"], v["valueTexts"]) if "square" in t.lower())]}})
        else:
            pick = next((c for c, t in zip(v["values"], v["valueTexts"]) if re.search(r"whole country|blocks of flats", t, re.I)), None) \
                or next((c for c, t in zip(v["values"], v["valueTexts"]) if re.search(r"total", t, re.I)), v["values"][0])
            nq.append({"code": v["code"], "selection": {"filter": "item", "values": [pick]}})
    whole = next(val for *_, val in pxweb(base, "13mv.px", nq) if val)
    big = ["Helsinki", "Espoo", "Tampere", "Vantaa", "Oulu", "Turku", "Jyväskylä", "Kuopio", "Lahti", "Pori"]
    regions = [region(lab[area], v) for lab, v in rows if lab[area] in big]
    return {"eur": round(whole), "unit": "m2", "basis": "sale", "period": quarter.rstrip("*").replace("Q", "-Q"),
            "type": "flats", "what": "flats in blocks, resale prices (cities: last full year)",
            "source": "Statistics Finland (CC BY 4.0)", "url": "https://stat.fi/en/statistics/ashi",
            "regions": sorted(regions, key=lambda r: -r["eur"])}


def portugal():
    d = json.loads(text("https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0012248&lang=EN"))[0]
    period = d["UltimoPref"]
    rows = d["Dados"][period]
    flats = [r for r in rows if r.get("dim_3_t", "").lower() == "flats"]
    print(f"  PT types: {sorted({r.get('dim_3_t') for r in rows})}, flats rows: {len(flats)}")
    rows = flats or rows
    nat = next((num(r.get("valor")) for r in rows if r.get("geodsg") == "Portugal"), None)
    big = ["Lisboa", "Porto", "Sintra", "Vila Nova de Gaia", "Cascais", "Loures", "Braga", "Almada", "Matosinhos",
           "Amadora", "Oeiras", "Seixal", "Gondomar", "Odivelas", "Coimbra", "Funchal", "Faro", "Loulé", "Setúbal", "Aveiro"]
    regions = [region(r["geodsg"], num(r["valor"])) for r in rows if r.get("geodsg") in big and num(r.get("valor"))]
    m = datetime.strptime(period, "%B %Y")
    return {"eur": round(nat), "unit": "m2", "basis": "appraisal", "period": m.strftime("%Y-%m"),
            "type": "flats", "what": "flats, median bank appraisal",
            "source": "Statistics Portugal, INE (CC BY 4.0)", "url": "https://www.ine.pt/xportal/xmain?xpid=INE&xpgid=ine_indicadores&indOcorrCod=0012248",
            "regions": sorted({r["name"]: r for r in regions}.values(), key=lambda r: -r["eur"])}


def spain():
    raw = fetch("https://cdn.mivau.gob.es/portal-web-mivau/Datos_MIVAU/CSV/VDP006_01.csv")
    try:
        body = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        body = raw.decode("latin-1")
    rows = list(csv.DictReader(io.StringIO(body), delimiter=";"))
    cols = list(rows[0])
    print(f"  ES columns: {cols}")
    year_col, reg_col = cols[0], cols[3]
    rows = [r for r in rows if (r.get(reg_col) or "").startswith("Libre")]
    key = lambda r: (int(r[year_col]), int(r["Trimestre"]))
    rows = [r for r in rows if num(r["Valor"])]
    last = max(key(r) for r in rows)
    now = [r for r in rows if key(r) == last]
    prov = [r for r in now if r.get("CPRO") not in (None, "", "null")]
    other = [r for r in now if r.get("CPRO") in (None, "", "null")]
    print(f"  ES {last}: {len(now)} rows, {len(prov)} provinces, others: {[(r.get('Provincia'), r.get('Comunidad_Autónoma'), r['Valor']) for r in other]}")
    nat = [r for r in other if re.search(r"nacional|españa|total nacional", r.get("Provincia", "") + " " + r.get("Comunidad_Autónoma", ""), re.I)]
    big = ["Madrid", "Barcelona", "Valencia/València", "Valencia", "Sevilla", "Málaga", "Alicante/Alacant", "Balears (Illes)",
           "Illes Balears", "Bizkaia", "Las Palmas", "Murcia", "Zaragoza", "Gipuzkoa", "Girona", "Santa Cruz de Tenerife"]
    regions = [region(r["Provincia"], num(r["Valor"])) for r in prov if r["Provincia"] in big]
    # Single-province regions appear only as regional totals.
    for r in other:
        name = {"Madrid, Comunidad de": "Madrid", "Balears, Illes": "Balearic Islands"}.get(r.get("Comunidad_Autónoma"))
        if r.get("Provincia") == "Total CCAA" and name and num(r["Valor"]) and name not in [x["name"] for x in regions]:
            regions.append(region(name, num(r["Valor"])))
    nat_v = num(nat[0]["Valor"]) if nat else None
    return {"eur": round(nat_v) if nat_v else None, "unit": "m2", "basis": "appraisal", "period": f"{last[0]}-Q{last[1]}",
            "type": "mixed", "what": "flats and houses, average bank appraisal",
            "source": "Ministry of Housing (MIVAU)", "url": "https://datos.gob.es/catalogo/e05233601-valor-tasado-de-la-vivienda",
            "regions": sorted(regions, key=lambda r: -r["eur"])}


def hungary():
    raw = fetch("https://www.ksh.hu/stadat_files/lak/en/lak0025.csv")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace")), delimiter=";"))
    head = next(r for r in rows if r and r[0] == "Region")
    year = head[-1] if head[-1] else head[-2]
    col = head.index(year)
    rate = eur_rate("HUF", year)
    second = []
    for r in rows[rows.index(head) + 1:]:
        if r and r[0] and not r[1] and second:
            break  # next block (new dwellings) starts
        if len(r) > col and num(r[col]):
            second.append((r[0], r[1], num(r[col]) * 1000 / rate))
    nat = next((v for a, b, v in second if a == "Country" and b == "total"), None)
    regions = [region("Budapest" if a == "Budapest" else f"{a}, county seats", v) for a, b, v in second
               if a == "Budapest" or (b == "county seats" and a != "Country")]
    return {"eur": round(nat) if nat else None, "unit": "m2", "basis": "sale", "period": year,
            "type": "mixed", "what": "flats and houses, resale prices", "currency": "HUF", "rate": round(rate, 2),
            "source": "Hungarian Central Statistical Office (KSH)", "url": "https://www.ksh.hu/stadat_files/lak/en/lak0025.html",
            "regions": sorted(regions, key=lambda r: -r["eur"])}


COUNTRIES = {"SK": ("Slovakia", slovakia), "FR": ("France", france), "FI": ("Finland", finland),
             "PT": ("Portugal", portugal), "ES": ("Spain", spain), "HU": ("Hungary", hungary)}


def main():
    try:
        old = json.loads(OUT.read_text())["countries"] if OUT.exists() else {}
    except Exception:  # noqa: BLE001
        old = {}
    countries, failed = {}, []
    for code, (name, job) in COUNTRIES.items():
        try:
            c = job()
            if not c.get("eur"):
                raise RuntimeError("no national figure")
            countries[code] = {"name": name, **c}
            print(f"ok    {code} {c['eur']} €/{c['unit']} {c['period']} ({len(c['regions'])} regions: "
                  + ", ".join(f"{r['name']} {r['eur']}" for r in c["regions"][:6]) + ")")
        except Exception as e:  # noqa: BLE001 - each country fails on its own
            failed.append(code)
            print(f"FAIL  {code}: {type(e).__name__}: {e}", file=sys.stderr)
            if code in old:
                countries[code] = old[code]
    if not countries:
        sys.exit(1)
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                               "failed": failed, "countries": countries}, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(countries)} countries, failed: {failed or 'none'}")


def sheets(body):
    """{sheet name: rows} from an .xlsx or .xls file."""
    if body[:2] == b"PK":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
        return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}
    import xlrd
    wb = xlrd.open_workbook(file_contents=body)
    return {sh.name: [sh.row_values(i) for i in range(sh.nrows)] for sh in wb.sheets()}


def probe(urls):
    """Log the start of each response, to write parsers for new sources (hosts are unreachable from the editor)."""
    for url in urls:
        try:
            body = fetch(url, limit=None if url.endswith((".xls", ".xlsx")) else 300_000)
            if body[:2] == b"PK" or body[:4] == b"\xd0\xcf\x11\xe0":
                print(f"\n===== {url} OK spreadsheet {len(body)} bytes")
                for name, rows in sheets(body).items():
                    print(f"--- sheet {name}: {len(rows)} rows")
                    for r in rows[:45]:
                        print(" | ".join(str(c)[:22] for c in r if c not in (None, "")))
                continue
            try:
                t = body.decode("utf-8-sig")
            except UnicodeDecodeError:
                t = body.decode("cp1250", "replace")
            links = sorted(set(re.findall(r'href="([^"]+\.(?:xlsx?|csv|json|px)[^"]*)"', t)))[:60]
            print(f"\n===== {url} OK {len(body)} bytes\n{t[:3000]}\n--- data links: {links}")
        except Exception as e:  # noqa: BLE001
            print(f"\n===== {url} FAIL {e}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--probe"]:
        probe(sys.argv[2:])
    else:
        main()
