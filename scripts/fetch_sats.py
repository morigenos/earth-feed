"""Fetch orbital element sets from CelesTrak in the modern OMM JSON format and
write them for the page to propagate. CelesTrak asks that the same data is not
requested more often than every few hours, so this script refuses to run again
inside REFRESH_HOURS."""
import json, pathlib, datetime, requests
from feed_health import publish, record, run

OUT = pathlib.Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
TARGET = OUT / "sats.json"
REFRESH_HOURS = 6
GROUPS = ["stations", "weather", "gps-ops", "resource", "science", "starlink"]
STARLINK_CAP = 300
UA = {"User-Agent": "earth-observatory-feed (personal, non-commercial)"}

def fresh_enough():
    if not TARGET.exists():
        return False
    try:
        got = datetime.datetime.fromisoformat(json.loads(TARGET.read_text())["fetched"])
    except Exception:
        return False
    return (datetime.datetime.now(datetime.UTC) - got).total_seconds() < REFRESH_HOURS * 3600

def main():
    if fresh_enough():
        record("sats", "ok", "Cached orbital elements are within the 6-hour refresh interval"); return
    items = []
    failed_groups = []
    for g in GROUPS:
        try:
            r = requests.get(f"https://celestrak.org/NORAD/elements/gp.php?GROUP={g}&FORMAT=JSON",
                             headers=UA, timeout=90)
            r.raise_for_status()
            objs = r.json()
            if g == "starlink":
                objs = objs[:STARLINK_CAP]
            for o in objs:
                o["__g"] = g
            items += objs
            print(g, len(objs))
        except Exception as e:
            failed_groups.append(g)
    if not items:
        raise ValueError("No orbital elements fetched")
    publish('sats', {'items':items}, 'CelesTrak GP OMM orbital elements', 'calculated',
            'Element sets propagated with SGP4; accuracy falls as elements age.')
    if failed_groups:
        record('sats','partial','Some orbital groups failed: '+', '.join(failed_groups))
    print("wrote sats.json with", len(items), "objects")

if __name__ == "__main__":
    run("sats", main)
