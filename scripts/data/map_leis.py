"""Find the LEI and the filings.xbrl.org entity for each stock in js/data.js.

Writes data/leis.json ({ticker: {lei, xbrl_name, filings}}) and prints a
review report. Run occasionally; the nightly refresh only reads leis.json.
"""
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UA = {"User-Agent": "FINILA data refresh (finila.com)", "Accept": "application/vnd.api+json"}


def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def stocks():
    src = (ROOT / "js/data.js").read_text()
    return re.findall(r"ticker:'([^']+)',\s*name:(?:'([^']*)'|\"([^\"]*)\"),\s*country:'([^']+)'", src)


def candidates(name):
    q = re.sub(r"\b(SE|AG|SA|S\.A\.|NV|N\.V\.|PLC|plc|AB|ASA|A/S|SpA|S\.p\.A\.|Ltd|Group|Holding|Holdings|Inc)\b\.?", "", name).strip(" ,.-")
    url = "https://api.gleif.org/api/v1/fuzzycompletions?field=entity.legalName&q=" + urllib.parse.quote(q)
    data = get(url) or {}
    out = []
    for d in data.get("data", [])[:8]:
        lei = (d.get("relationships", {}).get("lei-records", {}).get("data") or {}).get("id")
        if lei:
            out.append((lei, d["attributes"]["value"]))
    return q, out


def main():
    result, report = {}, []
    for ticker, n1, n2, country in stocks():
        name = n1 or n2
        q, cands = candidates(name)
        hit = None
        for lei, legal in cands:
            ent = get(f"https://filings.xbrl.org/api/entities/{lei}/filings?page[size]=50")
            if ent and ent.get("data"):
                hit = {"lei": lei, "legal_name": legal, "filings": len(ent["data"]),
                       "periods": sorted({f["attributes"]["period_end"] for f in ent["data"]})[-3:]}
                break
        result[ticker] = hit
        report.append(f"{ticker:7} {country:12} {name[:32]:32} -> " +
                      (f"{hit['lei']} {hit['legal_name'][:40]} ({hit['filings']} filings, {hit['periods']})" if hit
                       else "NO XBRL MATCH; candidates: " + "; ".join(f"{l} {n[:30]}" for l, n in cands[:3])))
        time.sleep(0.3)
    out = ROOT / "data/leis.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    (ROOT / "data/leis-report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    print(f"\nmatched {sum(1 for v in result.values() if v)} / {len(result)}")


if __name__ == "__main__":
    sys.exit(main())
