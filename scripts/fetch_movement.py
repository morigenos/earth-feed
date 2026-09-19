"""Movement feeds: aircraft, vessels, fishing effort and internet disruption.
Each one is optional and needs its own credentials, so the script skips what it
cannot reach instead of writing empty files over good ones."""
import json, os, pathlib, datetime, requests

OUT = pathlib.Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
NOW = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
UA = {"User-Agent": "earth-observatory-feed (personal, non-commercial)"}

def write(name, items, source, kind, note=""):
    (OUT / name).write_text(json.dumps({"items": items, "fetched": NOW, "source": source,
                                        "class": kind, "note": note}, separators=(",", ":")))
    print("wrote", name, len(items), "items")

def flights():
    cid, secret = os.environ.get("OPENSKY_ID"), os.environ.get("OPENSKY_SECRET")
    try:
        if cid and secret:
            tok = requests.post(
                "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token",
                data={"grant_type": "client_credentials", "client_id": cid, "client_secret": secret},
                timeout=60).json()["access_token"]
            r = requests.get("https://opensky-network.org/api/states/all",
                             headers={**UA, "Authorization": f"Bearer {tok}"}, timeout=90)
        else:
            r = requests.get("https://opensky-network.org/api/states/all", headers=UA, timeout=90)
        r.raise_for_status()
        states = r.json().get("states") or []
        items = [[round(s[5], 3), round(s[6], 3), int(s[7] or s[13] or 0), 1 if s[8] else 0, (s[1] or "").strip()]
                 for s in states if s[5] is not None and s[6] is not None][:5000]
        write("flights.json", items, "OpenSky Network state vectors", "observed",
              "Coverage follows volunteer receivers: oceans and remote regions are sparse.")
    except Exception as e:
        print("flights skipped:", e)

def fishing():
    tok = os.environ.get("GFW_TOKEN")
    if not tok:
        print("no GFW_TOKEN, skipping fishing"); return
    end = datetime.date.today() - datetime.timedelta(days=3)
    start = end - datetime.timedelta(days=1)
    url = ("https://gateway.api.globalfishingwatch.org/v3/4wings/report"
           "?spatial-resolution=LOW&temporal-resolution=DAILY&group-by=GEARTYPE&format=JSON"
           "&datasets[0]=public-global-fishing-effort:latest"
           f"&date-range={start}%2C{end}")
    try:
        r = requests.post(url, headers={**UA, "Authorization": f"Bearer {tok}"},
                          json={"geojson": {"type": "Polygon", "coordinates":
                                [[[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]]]}}, timeout=120)
        r.raise_for_status()
        rows = r.json()
        cells = []
        for entry in (rows.get("entries") or []):
            for rec in (entry.get("public-global-fishing-effort:latest") or []):
                if rec.get("lat") is not None:
                    cells.append([round(rec["lon"], 2), round(rec["lat"], 2), round(rec.get("hours", 0), 1)])
        if cells:
            write("fishing.json", cells[:20000], "Global Fishing Watch apparent fishing effort", "calculated",
                  "Apparent effort inferred from AIS, several days behind, and vessels without AIS are invisible.")
    except Exception as e:
        print("fishing skipped:", e)

def outages():
    try:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        r = requests.get("https://api.ioda.inetintel.cc.gatech.edu/v2/outages/alerts"
                         f"?from={now-86400}&until={now}&limit=200", headers=UA, timeout=60)
        r.raise_for_status()
        items = []
        for a in r.json().get("data", []):
            at = (a.get("entity") or {}).get("attrs") or {}
            if at.get("latitude"):
                items.append({"n": a["entity"].get("name", "unknown"), "lat": float(at["latitude"]),
                              "lon": float(at["longitude"]),
                              "d": f'{a.get("datasource","signal")} dropped {a.get("level","")} at '
                                   f'{datetime.datetime.fromtimestamp(a["time"], datetime.UTC):%Y-%m-%d %H:%M} UTC.'})
        if items:
            write("outages.json", items, "IODA (Georgia Tech) outage alerts", "reported",
                  "A drop in connectivity signals. The cause is not part of the data.")
    except Exception as e:
        print("outages skipped:", e)

if __name__ == "__main__":
    for fn in (flights, fishing, outages):
        fn()
