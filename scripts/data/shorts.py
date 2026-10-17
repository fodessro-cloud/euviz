"""Net short positions of funds in European shares, from the official regulator registers.

Under the EU Short Selling Regulation (and the UK rules) a fund must publish every net short
position of 0.5 % of a company's shares or more. Each regulator keeps a public register:
  NL  AFM                 CSV export (current positions)
  IT  Consob              XLSX (current + historic)
  SE  Finansinspektionen  ODS (current + historic)
  NO  Finanstilsynet      JSON API (events per share)
  UK  FCA                 XLSX (one aggregated position per company, no fund names)
Writes js/shorts.json for the site. Every country is fetched on its own; a failing register
keeps its rows from the previous run so the page never loses a whole country.
"""
import csv, io, json, re, sys, urllib.request, zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "js" / "shorts.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FINILA data refresh; +https://www.finila.com)"}
THRESHOLD = 0.5      # positions below this are not public
TREND_DAYS = 30

SOURCES = {
    "NL": ("AFM (Netherlands)", "https://www.afm.nl/en/sector/registers/meldingenregisters/netto-shortposities-actueel"),
    "IT": ("Consob (Italy)", "https://www.consob.it/web/area-pubblica/pnc"),
    "SE": ("Finansinspektionen (Sweden)", "https://www.fi.se/en/our-registers/net-short-positions/"),
    "NO": ("Finanstilsynet (Norway)", "https://ssr.finanstilsynet.no/"),
    "UK": ("FCA (United Kingdom)", "https://www.fca.org.uk/markets/short-selling"),   # aggregated per company
}


def fetch(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def to_date(v):
    if isinstance(v, (int, float)):            # Excel serial day
        return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()
    s = str(v or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def to_pct(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip().replace("%", "").replace("\xa0", "").replace(" ", "")
    if s.startswith("<"):
        return 0.0                              # "<0.5" = position closed below the threshold
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


# ── spreadsheet readers (standard library only) ──────────────────────────────
X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def xlsx_sheets(raw):
    """{sheet name: [rows]} with plain values; numbers as float, text as str."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(X + "si"):
            shared.append("".join(t.text or "" for t in si.iter(X + "t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels}
    out = {}
    for s in wb.iter(X + "sheet"):
        rid = s.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        path = target[rid].lstrip("/")
        path = path if path.startswith("xl/") else "xl/" + path
        rows = []
        for r in ET.fromstring(z.read(path)).iter(X + "row"):
            row = {}
            for c in r.iter(X + "c"):
                col = 0
                for ch in re.match(r"[A-Z]+", c.get("r")).group():
                    col = col * 26 + ord(ch) - 64
                t, v = c.get("t"), c.find(X + "v")
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(X + "t"))
                elif v is not None:
                    try:
                        val = float(v.text)
                    except ValueError:
                        val = v.text
                else:
                    val = None
                row[col - 1] = val
            rows.append([row.get(i) for i in range(max(row) + 1)] if row else [])
        out[s.get("name")] = rows
    return out


T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
TX = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


def ods_rows(raw):
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(raw)).read("content.xml"))
    rows = []
    for r in root.iter(T + "table-row"):
        cells = []
        for c in r:
            if c.tag not in (T + "table-cell", T + "covered-table-cell"):
                continue
            rep = min(int(c.get(T + "number-columns-repeated", "1")), 20)
            val = " ".join("".join(p.itertext()) for p in c.iter(TX + "p"))
            cells += [val] * rep
        rows.append(cells)
    return rows


def table(rows, first_header_cell):
    """Rows after the header row whose first cell starts with first_header_cell."""
    for i, r in enumerate(rows):
        if r and isinstance(r[0], str) and r[0].strip().lower().startswith(first_header_cell):
            return rows[i + 1:]
    raise ValueError(f"header '{first_header_cell}' not found")


def event(holder, issuer, isin, pct, day):
    pct, day = to_pct(pct), to_date(day)
    if not holder or not isin or pct is None or not day:
        return None
    return {"holder": " ".join(str(holder).split()), "issuer": " ".join(str(issuer or "").split()),
            "isin": str(isin).strip().upper(), "pct": round(pct, 2), "date": day}


def norm(holder):
    """Same fund spelled differently across files: 'D. E. Shaw & Co., L.P.' == 'D E Shaw Co LP'."""
    return re.sub(r"[^a-z0-9]", "", holder.lower())


# ── one function per register; each returns (current positions or None, all events with history or None) ──
def nl():
    raw = fetch("https://www.afm.nl/export.aspx?type=8a46a4ef-f196-4467-a7ab-1ae1cb58f0e7&format=csv")
    text = raw.decode("utf-8-sig") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("cp1252")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    evs = [event(*r[:5]) for r in rows[1:] if len(r) >= 5]
    # the "current" register still lists each earlier update of a position: keep the latest per fund
    return positions_at([e for e in evs if e], date.today().isoformat()), None


def it():
    url = "https://www.consob.it/documents/11973/395154/PncPubbl.xlsx/fbefe0a2-795b-bad3-9369-beccbeb14f27"
    current, events = [], []
    for name, rows in xlsx_sheets(fetch(url)).items():
        try:
            body = table(rows, "position holder")
        except ValueError:
            continue
        evs = [event(r[0], r[2], r[4], r[5], r[6]) for r in body if len(r) >= 7]
        (current if "current" in name.lower() else events).extend(evs)
    return current, events + current


def se():
    files = []
    for f in ("GetAktuellFile", "GetHistFile"):
        rows = ods_rows(fetch(f"https://www.fi.se/en/our-registers/net-short-positions/{f}/"))
        files.append([event(*r[:5]) for r in table(rows, "innehavare") if len(r) >= 5])
    return files[0], files[0] + files[1]


def no():
    events = []
    for share in json.loads(fetch("https://ssr.finanstilsynet.no/api/v2/instruments")):
        name, isin, held = share.get("issuerName"), share.get("isin"), set()
        for ev in sorted(share.get("events", []), key=lambda e: e.get("date") or ""):
            now = {p.get("positionHolder"): p for p in ev.get("activePositions", [])}
            for h in held - set(now):           # holder dropped out = went below 0.5 %
                events.append(event(h, name, isin, 0, ev.get("date")))
            for h, p in now.items():
                events.append(event(h, name, isin, p.get("shortPercent"), p.get("date")))
            held = set(now)
    return None, events


AGGREGATE = "All funds together (UK publishes no names)"


def uk():
    """Since the Short Selling Regulations 2025 the FCA publishes one aggregated net short
    position per company instead of each fund's position."""
    sheets = xlsx_sheets(fetch("https://www.fca.org.uk/publication/documents/aggregated-net-short-positions.xlsx"))
    current, events = [], []
    for name, rows in sheets.items():
        try:
            body = table(rows, "name of company")
        except ValueError:
            continue
        if name.lower().startswith("current"):
            current += [event(AGGREGATE, r[0], r[1], r[2], r[3]) for r in body if len(r) >= 4]
        else:   # historical: the value held from its position date until the date it became historical
            events += [event(AGGREGATE, r[0], r[1], 0, r[4]) for r in body if len(r) >= 5]
            events += [event(AGGREGATE, r[0], r[1], r[2], r[3]) for r in body if len(r) >= 4]
    events = [e for e in events if e]
    return current, events + current


def positions_at(events, day):
    """Latest position of each (holder, isin) on or before day, kept when >= THRESHOLD."""
    latest = {}
    for e in events:
        if e["date"] <= day:
            k = (norm(e["holder"]), e["isin"])
            if k not in latest or e["date"] >= latest[k]["date"]:
                latest[k] = e
    return [e for e in latest.values() if e["pct"] >= THRESHOLD]


def main():
    old = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text())
            for c in prev.get("countries", {}):
                old[c] = ([p for p in prev["positions"] if p["c"] == c], prev["countries"][c])
        except Exception as e:  # noqa: BLE001
            print("previous file unreadable:", e)
    today = date.today().isoformat()
    ago = (date.today() - timedelta(days=TREND_DAYS)).isoformat()
    positions, countries, failed = [], {}, []
    for c, fn in (("NL", nl), ("IT", it), ("SE", se), ("NO", no), ("UK", uk)):
        try:
            current, events = fn()
            events = [e for e in events or [] if e]
            now = [e for e in current if e and e["pct"] >= THRESHOLD] if current is not None else positions_at(events, today)
            hist = bool(events) and min(e["date"] for e in events) <= ago
            before = {(norm(e["holder"]), e["isin"]): e["pct"] for e in positions_at(events, ago)} if hist else {}
            for e in now:
                e["c"] = c
                e["prev"] = before.get((norm(e["holder"]), e["isin"]), 0.0) if hist else None
            if not now:
                raise ValueError("no current positions found")
            positions += now
            countries[c] = {"name": SOURCES[c][0], "url": SOURCES[c][1], "positions": len(now),
                            "latest": max(e["date"] for e in now), "trend": hist}
            print(f"{c}: {len(events)} events, {len(now)} current positions, latest {countries[c]['latest']}")
        except Exception as e:  # noqa: BLE001
            failed.append(c)
            print(f"::warning::shorts {c}: {e}")
            if c in old:
                positions += old[c][0]
                countries[c] = old[c][1]
    if not positions:
        sys.exit("no short positions from any register")
    # a share listed in two countries (e.g. Stellantis in Milan and Amsterdam) is reported to both: keep the newest
    best = {}
    for p in positions:
        k = (norm(p["holder"]), p["isin"])
        if k not in best or p["date"] > best[k]["date"]:
            best[k] = p
    positions = list(best.values())
    positions.sort(key=lambda p: (-p["pct"], p["issuer"]))
    OUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "threshold": THRESHOLD, "trendDays": TREND_DAYS, "countries": countries,
        "positions": positions,
    }, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {OUT.name}: {len(positions)} positions, failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
