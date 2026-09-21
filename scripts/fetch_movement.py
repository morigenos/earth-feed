"""Movement feeds: aircraft, vessels, fishing effort and internet disruption.
Each one is optional and needs its own credentials, so the script skips what it
cannot reach instead of writing empty files over good ones."""
import json, os, pathlib, datetime, requests
from feed_health import publish, run, NotConfigured

OUT = pathlib.Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
NOW = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
UA = {"User-Agent": "earth-observatory-feed (personal, non-commercial)"}

def write(name, items, source, kind, note=""):
    publish(name.removesuffix('.json'), {'items':items}, source, kind, note)


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
        payload = r.json()
        if not isinstance(payload, dict) or "states" not in payload:
            raise ValueError("Invalid aircraft collection")
        states = payload["states"] or []
        if not isinstance(states, list):
            raise ValueError("Invalid aircraft states")
        rows = [s for s in states if s[5] is not None and s[6] is not None]
        rows.sort(key=lambda s: 1 if s[8] else 0)          # airborne aircraft before grounded ones
        items = [[round(s[5], 2), round(s[6], 2), int(s[7] or s[13] or 0), 1 if s[8] else 0, (s[1] or "").strip()]
                 for s in rows[:3000]]
        write("flights.json", items, "OpenSky Network state vectors", "observed",
              "Coverage follows volunteer receivers: oceans and remote regions are sparse.")
    except Exception as e:
        raise

def fishing():
    tok = os.environ.get("GFW_TOKEN")
    if not tok:
        raise NotConfigured()
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
        if not isinstance(rows, dict) or not isinstance(rows.get("entries"), list):
            raise ValueError("Invalid fishing collection")
        cells = []
        for entry in (rows.get("entries") or []):
            for rec in (entry.get("public-global-fishing-effort:latest") or []):
                if rec.get("lat") is not None:
                    cells.append([round(rec["lon"], 2), round(rec["lat"], 2), round(rec.get("hours", 0), 1)])
        write("fishing.json", cells[:20000], "Global Fishing Watch apparent fishing effort", "calculated",
                  "Apparent effort inferred from AIS, several days behind, and vessels without AIS are invisible.")
    except Exception as e:
        raise

def outages():
    try:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        r = requests.get("https://api.ioda.inetintel.cc.gatech.edu/v2/outages/alerts"
                         f"?from={now-86400}&until={now}&limit=200", headers=UA, timeout=60)
        r.raise_for_status()
        payload = r.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("Invalid outage collection")
        items = []
        for a in payload["data"]:
            at = (a.get("entity") or {}).get("attrs") or {}
            if at.get("latitude") is not None and at.get("longitude") is not None:
                items.append({"n": a["entity"].get("name", "unknown"), "lat": float(at["latitude"]),
                              "lon": float(at["longitude"]),
                              "d": f'{a.get("datasource","signal")} dropped {a.get("level","")} at '
                                   f'{datetime.datetime.fromtimestamp(a["time"], datetime.UTC):%Y-%m-%d %H:%M} UTC.'})
        write("outages.json", items, "IODA (Georgia Tech) outage alerts", "reported",
                  "A drop in connectivity signals. The cause is not part of the data.")
    except Exception as e:
        raise

if __name__ == "__main__":
    for fn in (flights, fishing, outages):
        run(fn.__name__, fn)
