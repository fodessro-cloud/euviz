"""House prices across Europe, by country: how fast prices rose (before and after inflation)
and whether homes look expensive against incomes and rents.

Sources, both free to reuse with attribution:
- Eurostat house price index (prc_hpi_q): every EU country plus Norway, Iceland, Switzerland.
- OECD analytical house price indicators: real house prices, price-to-income and price-to-rent
  ratios for its European members (not Bulgaria, Croatia, Cyprus, Malta, Romania).

Writes js/housing.json: {updated, sources, countries: {code: {...}}}.
"""
import csv, io, json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "js" / "housing.json"
RAW = ROOT / "data" / "housing-raw.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FINILA data refresh; +https://www.finila.com)"}
START = "2000"

COUNTRIES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia", "CY": "Cyprus", "CZ": "Czechia",
    "DK": "Denmark", "EE": "Estonia", "FI": "Finland", "FR": "France", "DE": "Germany", "GR": "Greece",
    "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LV": "Latvia", "LT": "Lithuania", "LU": "Luxembourg",
    "MT": "Malta", "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SK": "Slovakia",
    "SI": "Slovenia", "ES": "Spain", "SE": "Sweden", "NO": "Norway", "IS": "Iceland", "CH": "Switzerland",
    "GB": "United Kingdom",
}
ESTAT_GEO = {"GR": "EL", "GB": "UK"}
ISO3 = {"AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY", "CZE": "CZ", "DNK": "DK", "EST": "EE",
        "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "GR", "HUN": "HU", "IRL": "IE", "ITA": "IT", "LVA": "LV",
        "LTU": "LT", "LUX": "LU", "MLT": "MT", "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK",
        "SVN": "SI", "ESP": "ES", "SWE": "SE", "NOR": "NO", "ISL": "IS", "CHE": "CH", "GBR": "GB"}

ESTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
OECD = ("https://sdmx.oecd.org/public/rest/data/OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,1.0/all"
        f"?startPeriod={START}-Q1&dimensionAtObservation=AllDimensions&format=csvfilewithlabels")
SOURCES = [
    ["Eurostat house price index", "https://ec.europa.eu/eurostat/databrowser/view/prc_hpi_q/default/table"],
    ["OECD analytical house price indicators", "https://data-explorer.oecd.org/"],
]
# OECD measure labels -> our keys (matched on lower-case words, so small label changes still match)
OECD_MEASURES = {
    "real": ["real house price"],
    "nominal_oecd": ["nominal house price"],
    "income": ["price to income", "price-to-income"],
    "rent": ["price to rent", "price-to-rent"],
    "rents": ["rent price"],
}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read().decode("utf-8-sig")


def eurostat():
    """{country: {"2024-Q1": index (2015 = 100)}} nominal house prices, all dwellings."""
    geos = "&".join(f"geo={ESTAT_GEO.get(c, c)}" for c in COUNTRIES)
    d = json.loads(fetch(f"{ESTAT}prc_hpi_q?{geos}&purchase=TOTAL&unit=I15_Q&sinceTimePeriod={START}-Q1"))
    back = {ESTAT_GEO.get(c, c): c for c in COUNTRIES}
    ids, sizes = d["id"], d["size"]
    cat = {k: d["dimension"][k]["category"]["index"] for k in ids}
    strides, s = {}, 1
    for k, n in zip(reversed(ids), reversed(sizes)):
        strides[k] = s
        s *= n
    out = {}
    for g, gi in cat["geo"].items():
        pts = {t: float(d["value"][str(gi * strides["geo"] + ti * strides["time"])])
               for t, ti in cat["time"].items() if str(gi * strides["geo"] + ti * strides["time"]) in d["value"]}
        if pts and g in back:
            out[back[g]] = dict(sorted(pts.items()))
    return out


def oecd():
    """{key: {country: {"2024-Q1": value}}} for the measures in OECD_MEASURES, quarterly only."""
    rows = list(csv.DictReader(io.StringIO(fetch(OECD))))
    if not rows:
        raise RuntimeError("OECD returned no rows")
    labels = {}
    out = {}
    for r in rows:
        if r.get("FREQ") not in (None, "Q"):
            continue
        code = ISO3.get(r.get("REF_AREA", ""))
        label = (r.get("Measure") or r.get("MEASURE") or "").lower()
        labels[label] = labels.get(label, 0) + 1
        key = next((k for k, words in OECD_MEASURES.items() if any(w in label for w in words)), None)
        if not code or not key or not r.get("OBS_VALUE"):
            continue
        out.setdefault(key, {}).setdefault(code, {})[r["TIME_PERIOD"]] = float(r["OBS_VALUE"])
    print("OECD measures: " + "; ".join(f"{k} ({v})" for k, v in sorted(labels.items())))
    return {k: {c: dict(sorted(v.items())) for c, v in by.items()} for k, by in out.items()}


def change(s, quarters):
    """Percentage change over the last `quarters` quarters, or None."""
    keys = sorted(s)
    if len(keys) <= quarters:
        return None
    a, b = s[keys[-1 - quarters]], s[keys[-1]]
    return round((b / a - 1) * 100, 1) if a else None


def vs_average(s):
    """How far the latest value is above (+) or below (-) its average since 2000, in percent."""
    if len(s) < 40:
        return None
    avg = sum(s.values()) / len(s)
    return round((s[max(s)] / avg - 1) * 100, 1)


def main():
    try:
        old = json.loads(RAW.read_text()) if RAW.exists() else {}
    except Exception:  # noqa: BLE001
        old = {}
    raw, failed = {}, []
    for name, job in (("eurostat", eurostat), ("oecd", oecd)):
        try:
            raw[name] = job()
            print(f"ok    {name}: {len(raw[name])} series")
        except Exception as e:  # noqa: BLE001 - each source fails on its own
            failed.append(name)
            print(f"FAIL  {name}: {e}", file=sys.stderr)
            if name in old:
                raw[name] = old[name]
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(raw, separators=(",", ":")))

    es, oe = raw.get("eurostat", {}), raw.get("oecd", {})
    countries = {}
    for code, name in COUNTRIES.items():
        nominal = es.get(code) or oe.get("nominal_oecd", {}).get(code) or {}
        real = oe.get("real", {}).get(code) or {}
        income = oe.get("income", {}).get(code) or {}
        rent = oe.get("rent", {}).get(code) or {}
        if not nominal:
            continue
        countries[code] = {
            "name": name,
            "latest": max(nominal),
            "nominal": {"1y": change(nominal, 4), "5y": change(nominal, 20), "10y": change(nominal, 40)},
            "real": {"1y": change(real, 4), "5y": change(real, 20), "10y": change(real, 40)} if real else None,
            "realLatest": max(real) if real else None,
            # Above 0: homes cost more against incomes (or rents) than on average since 2000.
            "vsIncome": vs_average(income) if income else None,
            "vsRent": vs_average(rent) if rent else None,
            "valuationLatest": max(income) if income else None,
            "series": {
                "nominal": {k: round(v, 2) for k, v in nominal.items()},
                **({"real": {k: round(v, 2) for k, v in real.items()}} if real else {}),
                **({"income": {k: round(v, 2) for k, v in income.items()}} if income else {}),
                **({"rent": {k: round(v, 2) for k, v in rent.items()}} if rent else {}),
            },
        }
    if not countries:
        print("no country data, keeping the previous file", file=sys.stderr)
        sys.exit(1)
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                               "sources": SOURCES, "failed": failed, "countries": countries},
                              ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB), {len(countries)} countries, failed: {failed or 'none'}")
    for code, c in countries.items():
        print(f"  {code} {c['latest']} nominal {c['nominal']} real {c['real']} vsIncome {c['vsIncome']} vsRent {c['vsRent']}")


if __name__ == "__main__":
    main()
