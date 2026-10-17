"""Temporary: lists which source series have the newest data (run in Actions, the container cannot reach the APIs)."""
import csv, io, json, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (compatible; FINILA data refresh)"}
def get(url, accept=None):
    h = dict(UA)
    if accept: h["Accept"] = accept
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=90) as r:
            return r.read().decode("utf-8-sig")
    except Exception as e:
        return f"ERROR {e}"
def keys(url, accept=None):
    t = get(url, accept)
    print("==", url)
    if t.startswith("ERROR"): print(t); return
    rows = list(csv.DictReader(io.StringIO(t)))
    if not rows: print(t[:500]); return
    for r in rows[:60]:
        print("  ", r.get("KEY") or {k: v for k, v in r.items() if k not in ("OBS_VALUE",)} , r.get("TIME_PERIOD"), r.get("OBS_VALUE"), (r.get("TITLE") or "")[:80])
E = "https://data-api.ecb.europa.eu/service/data/"
keys(E + "ICP/M.U2.N..4.ANR?lastNObservations=1&format=csvdata")
keys(E + "ICP/M.U2...4.ANR?lastNObservations=1&format=csvdata&startPeriod=2026-01")
keys(E + "MIR/M.PL.B.L22.F.R.A.2250..N?lastNObservations=1&format=csvdata")
keys(E + "IRS/M..L.L40.CI.0000..N.Z?lastNObservations=1&format=csvdata")
B = "https://api.statistiken.bundesbank.de/rest/data/BBEX3/"
keys(B + "D.XAU..EA.AC.?lastNObservations=1", "application/vnd.sdmx.data+csv;version=1.0.0")
keys(B + "M.XAU..EA.AC.?lastNObservations=1", "application/vnd.sdmx.data+csv;version=1.0.0")
S = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
for ds in ["prc_hicp_manr?geo=EA20&coicop=CP00&lastTimePeriod=2", "prc_hicp_manr?geo=EA20&lastTimePeriod=1",
           "prc_hicp_minr?geo=EA20&lastTimePeriod=1", "prc_hicp_mv12r?geo=EA20&lastTimePeriod=1",
           "prc_hpi_q?geo=PL&purchase=TOTAL&unit=I15_Q&lastTimePeriod=1", "prc_hpi_q?geo=CH&purchase=TOTAL&unit=I15_Q&lastTimePeriod=1",
           "prc_hicp_manr?geo=CH&lastTimePeriod=1", "prc_hicp_manr?geo=UK&lastTimePeriod=1"]:
    t = get(S + ds)
    print("==", ds)
    if t.startswith("ERROR"): print(t); continue
    d = json.loads(t)
    print("   dims", {k: list(v["category"]["index"])[:12] for k, v in d["dimension"].items()}, "values", list(d["value"].items())[:6])
