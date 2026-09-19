"""Fetch public feeds a browser cannot reach (CORS or key needed) and write small
JSON files into data/. Each file records its source, fetch time and data class."""
import json, os, pathlib, datetime, requests

OUT = pathlib.Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
NOW = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
UA = {"User-Agent": "earth-observatory-feed (personal, non-commercial)"}

def write(name, payload, source, kind, note=""):
    payload = dict(payload, fetched=NOW, source=source, **{"class": kind}, note=note)
    (OUT / name).write_text(json.dumps(payload, separators=(",", ":")))
    print("wrote", name)

def get(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    return r

def quakes():
    g = get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson").json()
    items = [[round(f["geometry"]["coordinates"][0], 3), round(f["geometry"]["coordinates"][1], 3),
              round(f["geometry"]["coordinates"][2], 1), f["properties"]["mag"],
              f["properties"].get("place", ""), int(f["properties"]["time"] / 1000)]
             for f in g["features"] if f["properties"].get("mag") is not None]
    write("quakes.json", {"items": items}, "USGS M4.5+ past 7 days", "observed")

def storms():
    j = get("https://www.nhc.noaa.gov/CurrentStorms.json").json()
    items = [{"n": f'{s.get("classification","")} {s.get("name","")}'.strip(),
              "basin": s.get("basin", "NHC area"), "lat": float(s["latitudeNumeric"]),
              "lon": float(s["longitudeNumeric"]), "windKt": float(s.get("intensity") or 0),
              "pres": float(s.get("pressure") or 0), "status": "active",
              "d": f'Moving {s.get("movementDir","?")} degrees at {s.get("movementSpeed","?")} kt.'}
             for s in j.get("activeStorms", [])]
    write("storms.json", {"items": items}, "NOAA National Hurricane Center CurrentStorms", "observed",
          "Atlantic, eastern and central Pacific only; other basins need JTWC.")

def alerts():
    g = get("https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP?eventtypes=FL,DR,WF,TC,VO,EQ").json()
    m = {"FL": "flood", "DR": "drought", "WF": "heat", "TC": "storm", "VO": "ash", "EQ": "quake"}
    items = []
    for f in g.get("features", [])[:120]:
        p, c = f["properties"], f["geometry"]["coordinates"]
        items.append({"t": m.get(p.get("eventtype"), "flood"),
                      "n": p.get("name") or p.get("eventname") or p.get("eventtype"),
                      "lat": c[1], "lon": c[0],
                      "d": f'{p.get("alertlevel","")} alert'
                           f'{", " + p["country"] if p.get("country") else ""}'
                           f'{", from " + str(p.get("fromdate"))[:10] if p.get("fromdate") else ""}.'})
    write("alerts.json", {"items": items}, "GDACS event list", "reported")

def space():
    kp = get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json").json()[-1]
    ov = get("https://services.swpc.noaa.gov/json/ovation_aurora_latest.json").json()
    write("space.json", {"kp": float(kp[1]), "kpTime": kp[0],
                         "aurora": ov.get("coordinates", []), "auroraTime": ov.get("Forecast Time")},
          "NOAA SWPC planetary K index and OVATION aurora model", "modelled")

def fires():
    key = os.environ.get("FIRMS_KEY", "").strip()
    if not key:
        print("no FIRMS_KEY secret, skipping fires"); return
    rows = [r.split(",") for r in get(
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_NOAA20_NRT/world/1").text.strip().splitlines()]
    head = [h.strip().lower() for h in rows[0]]
    la, lo = head.index("latitude"), head.index("longitude")
    fp = head.index("frp") if "frp" in head else None
    items = [[round(float(r[la]), 3), round(float(r[lo]), 3), round(float(r[fp]), 1) if fp else 5]
             for r in rows[1:] if len(r) > max(la, lo)]
    write("fires.json", {"items": items}, "NASA FIRMS VIIRS NOAA-20, past 24 hours", "observed",
          "Satellite thermal anomalies, not confirmed fires on the ground.")

def manifest():
    files = sorted(p.name for p in OUT.glob("*.json") if p.name != "index.json")
    write("index.json", {"files": files}, "feed manifest", "reference")

if __name__ == "__main__":
    for fn in (quakes, storms, alerts, space, fires):
        try:
            fn()
        except Exception as e:
            print(f"{fn.__name__} failed: {e}")
    manifest()
