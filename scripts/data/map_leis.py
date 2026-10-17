"""Match each stock in js/data.js to its filer on filings.xbrl.org.

Downloads the full entity list (name + LEI), matches on normalised names
(with an alias table for names that differ from the legal name) and writes
data/leis.json ({ticker: {lei, legal_name, ...} | null}) plus a review report.
"""
import difflib, json, re, sys, time, unicodedata, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://filings.xbrl.org"
UA = {"User-Agent": "FINILA data refresh (finila.com)"}

# Legal names on the filings, where they differ from the screener name.
ALIASES = {
    "BBVA": "BANCO BILBAO VIZCAYA ARGENTARIA", "PHIA": "KONINKLIJKE PHILIPS",
    "VOLV": "VOLVO", "MAERSK": "A P MOLLER MAERSK", "ERICB": "TELEFONAKTIEBOLAGET LM ERICSSON", "PKN": "ORLEN",
    "DG": "VINCI", "CS": "AXA", "MC": "LVMH MOET HENNESSY LOUIS VUITTON",
    "EDP": "EDP ENERGIAS DE PORTUGAL", "MUV2": "MUENCHENER RUECKVERSICHERUNGS",
    "UCB": "UCB", "BP": "BP", "ORA": "ORANGE", "ENI": "ENI", "OMV": "OMV",
}
LEGAL = r"\b(SE|AG|SA|S A|NV|N V|PLC|P L C|AB|PUBL|ASA|A S|AS|SPA|S P A|OYJ|LTD|LIMITED|HOLDINGS?|GROUP|GROEP|INTERNATIONAL|AKTIENGESELLSCHAFT|AKTIEBOLAG(ET)?|SOCIETE ANONYME|SPOLKA AKCYJNA|SPOKA AKCYJNA|SOCIETA PER AZIONI|INC|CORPORATION|THE)\b"


def norm(s):
    s = s.translate(str.maketrans({"Ø": "O", "ø": "o", "Æ": "AE", "æ": "ae", "Ł": "L", "ł": "l", "ß": "SS"}))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(LEGAL, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.load(r)
        except Exception as e:
            err = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{url}: {err}")


def all_entities():
    out, url = [], f"{BASE}/api/entities?page[size]=500"
    while url:
        page = get(url)
        out += [(e["attributes"]["identifier"], e["attributes"]["name"]) for e in page["data"]]
        nxt = page.get("links", {}).get("next")
        url = (nxt if nxt.startswith("http") else BASE + nxt) if nxt else None
    return out


def stocks():
    src = (ROOT / "js/data.js").read_text()
    return re.findall(r"ticker:'([^']+)',\s*name:(?:'([^']*)'|\"([^\"]*)\"),\s*country:'([^']+)'", src)


def main():
    ents = all_entities()
    print(f"{len(ents)} entities on filings.xbrl.org")
    by_norm = {}
    for lei, name in ents:
        by_norm.setdefault(norm(name), []).append((lei, name))
    keys = list(by_norm)
    result, report = {}, []
    for ticker, n1, n2, country in stocks():
        name = n1 or n2
        want = norm(ALIASES.get(ticker, name))
        hit, how = None, ""
        if want in by_norm:
            hit, how = by_norm[want][0], "exact"
        else:
            close = difflib.get_close_matches(want, keys, n=1, cutoff=0.93)
            if close:
                hit, how = by_norm[close[0]][0], f"fuzzy~{close[0]}"
        result[ticker] = {"lei": hit[0], "legal_name": hit[1], "match": how} if hit else None
        report.append(f"{ticker:7} {country:12} {name[:32]:32} [{want}] -> " +
                      (f"{hit[0]} {hit[1]} ({how})" if hit else "none"))
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data/leis.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    (ROOT / "data/leis-report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    print(f"\nmatched {sum(1 for v in result.values() if v)} / {len(result)}")


if __name__ == "__main__":
    sys.exit(main())
